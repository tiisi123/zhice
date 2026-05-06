---
title: zhiceV1 数据源统一与自动化提升 PRD
owner: data-platform
last_updated: 2026-05-06
status: draft
---

## 1. 背景与目标
- zhiceV1 多板块数据源存在模拟/静态样例，真实行情缺位，影响策略可信度。
- TuShare/DFCF 等第三方源已经在部分模块接入，但缺乏统一配置、缓存及兜底策略。
- 需要配合 GSD plan → slice → task 流程，为后续自动化实施提供明确需求蓝图。

**核心目标**
1. 统一关键板块（ETF 轮动、宏观、行业景气、成长/估值、另类数据）数据源，确保 `data_mode=live` 为默认形态。
2. 参照 zer0share 实现的离线同步模式，引入 TuShare 批量抓取 + 本地缓存/数据库，降低实时调用失败率。
3. 清除前端/后端残留的样例数据，所有输出都需标注真实来源与时间戳，并提供异常兜底文案。
4. 建立数据校验与监控机制，发现涨跌幅穿透、数据缺失等逻辑异常。
5. 打通 gsd auto 模式所需的文档、脚本、测试支撑，确保后续任务自动化执行。

## 2. 范围
| 模块 | 当前问题 | 目标状态 |
| --- | --- | --- |
| ETF 轮动 + 回测 | `sample_engine` 为常态，缺少持久缓存 | TuShare 批量缓存 + 热数据落盘，命中率 > 90% |
| 宏观 & 行业景气 | 静态样例数据，偶尔 fallback | TuShare/DFCF 主源，静态数据仅作应急 |
| 估值/成长面板 | TuShare/DFCF 交叉使用，缺少统一校验 | 财务口径统一、涨幅计算准确、字段完备 |
| 另类数据 & 轮动推演 | 样例脚本/随机数据 | 接入真实指标或下线功能 |
| 自动化 & 测试 | 无 `.gsd` 目录，测试覆盖低 | 初始化 gsd assets + 集成测试/契约测试框架 |

**不在范围**
- 新增业务策略功能。
- 前端大规模重构。
- 生产级监控告警系统（仅列出需求与 Todo）。

## 3. 角色与利益相关者
- **产品负责人**：确认业务优先级与验收标准。
- **数据平台**：实现数据源接入、缓存和验证。
- **后端**：路由改造、标注 data_source/data_mode。
- **测试工程师**：制定校验用例、自动化脚本。
- **运维/自动化**：保障 gsd auto 工作流、环境变量配置。

## 4. 功能需求详情
### 4.1 数据源统一
1. **TuShare 批量同步任务**
   - 定时器或 CLI：`python -m packages.jobs.tushare_sync --table fund_daily --days 90 --output data/cache/etf_fund_daily.parquet`。
   - 支持增量刷新与失败告警，写入 SQLite/Parquet。
   - 缓存命中率监控（新字段 `cache_hit_rate`）。
2. **ETF 轮动**
   - 后端优先读取本地缓存；缓存缺失时再实时拉取并刷新。
   - 元信息需透出 `data_mode`、`data_source`、`as_of`、`cache_stale`。
3. **宏观 & 行业景气**
   - 用 TuShare `cn_pmi/cn_cpi/cn_ppi/sf_month/index_classify/sw_daily` 等接口替换静态数组。
   - 添加 `fetched_at`, `data_source` 字段，LPR/汇率保留静态但明确标注 `static`。
4. **估值/成长**
   - DFCF 作为主源，TuShare 备用；当任何关键字段缺失时标记 `status="fallback"` 并提示原因。
   - 复核涨跌幅计算逻辑，新增单元测试覆盖 `pre_close=0` 情形。
5. **另类数据 & Meso 指标**
   - 若无法接通真实源，需明确功能范围及下线计划；可先放入 roadmap。

### 4.2 业务逻辑校验
- 统一 `%` 单位与数值范围（涨跌幅 ∈ [-30, 30]，资金流 ∈ [-200, 200] 等）。
- 增加断言：若外部接口字段缺失，写入 `status="unavailable"`，并触发日志/告警。
- 建立数据完整性测试：
  - ETF：覆盖率 >= 80%，缺失时记录 `tushare_missing_codes`。
  - 宏观：所有指标近两期数据必须存在。
  - 估值：PE/PB/ROE 等非空验证。

### 4.3 自动化与 gsd auto 支撑
1. **仓库结构**
   - 初始化 `.gsd/`、模板 `M001-PLAN.md` 等必备文件。
   - 提供 `scripts/gsd-bootstrap.ps1/.sh` 自动创建目录。
2. **CI 与脚本**
   - 在 `Makefile` 添加 `make gsd-preflight`（运行 doctor、recover）。
   - 集成测试命令：`pytest tests/integration/test_data_sources.py`。
3. **自动化测试覆盖**
   - ETF 轮动：mock TuShare 响应 + 缓存命中测试。
   - 宏观/行业：验证真实数据字段 + fallback 分支。
   - 估值面板：涨跌幅计算、异常输入断言。

## 5. 技术实现与拆分建议
| Slice | 工作内容 | 输出物 |
| --- | --- | --- |
| S1 - TuShare 缓存 | 实现批量同步 CLI、缓存读写、元信息标注 | CLI、缓存模块、单测 |
| S2 - 宏观/行业真实化 | 接入真实接口 + 校验、兜底提示 | `macro/data.py` 改造、合同测试 |
| S3 - 估值 & 逻辑校验 | 优化涨跌幅、领域断言、数据完整性测试 | 单元/集成测试、API 更新 |
| S4 - 自动化基础 | `.gsd` 初始化、CI 命令、gsd auto 文档 | 脚本、doc、CI 配置 |
| S5 - 验收与监控 | 数据监控说明、运营手册 | README/Playbook |

## 6. 里程碑
1. **M1（T+2 周）**：ETF 轮动 live 模式可达 90% 覆盖，缓存生效。
2. **M2（T+4 周）**：宏观/行业全部使用真实数据，前端无 `mock` 标记。
3. **M3（T+5 周）**：估值板块校验上线；关键接口契约测试通过。
4. **M4（T+6 周）**：gsd auto 流程可执行；CI 集成 `gsd doctor` 与核心集成测试。

## 7. 验收标准
- 所有 API 响应包含 `data_source`、`data_mode`、`as_of` 字段。
- `mock` 或 `sample` 标记只在真实源失效时出现，且带有明确提示。
- 自动化测试新增 ≥ 10 个用例，覆盖率提升 ≥ 15%。
- gsd auto 模式可在开发环境跑通 plan → slice → task。

## 8. 风险与缓解
| 风险 | 等级 | 缓解措施 |
| --- | --- | --- |
| TuShare 速率限制导致同步失败 | 高 | 批量任务加入退避 + 排程，缓存兜底 |
| 数据字段变动 | 中 | 封装域转换层，增加 schema 校验 |
| 缺失真实数据源 | 中 | 与产品确认最小可用集，提供兜底文案或临时隐藏 |
| gsd auto 依赖缺失 | 中 | 新增 bootstrap 脚本，CI 阻断缺资源情况 |

## 9. 后续迭代建议
- 引入 Redis/SQLite 统一缓存服务。
- 接入监控与报警（Grafana + Prometheus 或第三方）。
- 支持多源权重融合（TuShare + DFCF + Wind）。
- 设计前端数据状态透出（tooltip 显示更新时间、命中缓存等）。
