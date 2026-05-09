# M009 KPL 题材工坊改造 PRD

## Project Description
将老 `daban_pc` 的 KPL 题材库能力接入 zhiceV1 题材工坊，使用户可以在产品内看到 KPL 题材库、题材列表、题材详情、题材成员和个股行情匹配状态。改造保持 KPL 作为题材与盘中短线数据第一来源；当 KPL 题材库接口不可用或返回空时，产品必须明确展示不可用或派生来源，不能静默展示 mock 或空壳结论。

## Why This Milestone
当前题材工坊主要依赖板块强度与涨停池派生题材，缺少老桌面端“题材库”的结构化信息：题材生成时间、题材热度、涨停数、细分题材、题材成员、BriefIntro、Introduction 和产业链层级。用户已多次反馈数据不一致、空数据误判和 AI 固定模式分析问题，本里程碑先把题材数据链路做成可审计、可降级、可展示的产品契约。

## User-Visible Outcome
用户进入题材工坊后，可以切到“题材库”页签，看到 KPL 题材库列表。点击任一题材后，右侧展示题材详情、生成时间、简介、题材成员、产业链层级和正文。如果 KPL 题材库详情暂不可用，页面会展示明确的 fallback 文案，并保留板块/涨停池派生的题材行，避免误以为“市场没有题材”。

## Completion Class
Integration。必须覆盖连接器契约、API 响应契约、前端展示契约和测试。真实 KPL 题材库接口是否返回内容受上游 Cookie/网关限制，完成标准不能要求伪造成功数据，但必须能证明不可用状态被正确显式化。

## Final Integrated Acceptance
- 访问题材工坊 `tab=library` 可以看到题材库页签，不影响已有板块强度、事件时间线、轮动推演和题材周期页签。
- `/api/theme/library` 优先返回 KPL 题材库列表；不可用或为空时返回 `data_status=fallback/unavailable` 和中文原因。
- `/api/theme/library/{theme_id}` 优先调用 KPL `InfoGet/Theme` 详情；不可用或为空时返回明确 fallback，不使用 mock。
- 老 KPL 详情块 `StockList/Table/BriefIntro/Introduction` 被规整为稳定字段，前端不依赖原始大小写。
- 题材库成员中的股票代码可以跳转到个股页，为后续实时行情 enrichment 留出字段。

## Architectural Decisions
### KPL 题材库与板块强度分层
题材库使用独立 `/theme/library*` API，不复用 `/theme/sectors` 的含义。原因是题材库来自 `HomeThemeList` 与 `InfoGet/Theme`，板块强度来自 `ConceptSelected/ZhiShuRanking`，两者口径不同。备选方案是把题材库混进 sectors，但会继续放大“涨停数量、主线题材不一致”的问题。

### 详情 HTML 先纯文本展示
`Introduction` 暂以纯文本展示。原因是 KPL 返回外部 HTML，直接渲染需要 sanitizer 与样式策略。备选方案是直接 `dangerouslySetInnerHTML`，风险过高。

### 不可用显式化优先于假空数据
当 KPL 详情空响应或上游 200 空 body 时，API 返回 `fallback/unavailable` 和 message。原因是用户明确要求不能把“没命中/没拿到”误报为“没有题材/没有短线事件”。

## Error Handling Strategy
KPL 连接器保留 sentinel：`cookie_missing`、`kpl_upstream_error`、`kpl_market_closed`。路由层将 sentinel 转为统一 contract：`data/source/data_status/mock/message/updated_at`。题材库列表可从板块强度和涨停池派生 fallback；详情只有列表信息可 fallback 时，不编造细分个股、简介或正文。

## Risks and Unknowns
- `HomeThemeList` 和 `InfoGet/Theme` 可能需要 KPL Cookie、旧服务 DB 或特殊网关；当前 token/user 直连可能返回空 body。
- `StockTable` 的层级形状可能因 KPL 版本变化而变化，前端第一版以 JSON/层级块展示，后续再做专门树形 UI。
- 题材名与板块名存在同名、包含、简称和概念扩展关系，需要后续单独做别名匹配与置信度。

## Existing Codebase / Prior Art
- 老 `daban_pc` 的 `kpl_controller.py` 注册“题材库”，对应 `HomeThemeDetailPage`。
- 老 `FieldMapping` 定义题材库列表与详情字段中文名。
- 老 `daban_fastapi` 的 KPL 路由用 `HomeThemeList` 和 `InfoGet/Theme` 作为题材库核心接口。
- 当前 zhiceV1 题材工坊已有 `/theme/sectors`、`/theme/cycle-batch` 和 React 页面。
- 当前 KPL facade 已支持板块强度、概念详情、涨停池和 5000+ 个股 ranking。

## Relevant Requirements
- M008 数据接入：继续执行无 mock、真实空状态可见、KPL 优先的约束。
- S07 收口：修复数据不一致后，新增题材库口径必须和板块强度分开标识来源。

## Scope
In Scope:
- KPL 题材库列表与详情连接器契约。
- `/theme/library` 与 `/theme/library/{theme_id}` API。
- 题材工坊“题材库”页签。
- 题材库 PRD、roadmap 和最小测试。

Out of Scope:
- 直接修改产品内 AI API 环境或 IDE AI API 环境。
- 将东财作为题材库第一来源。
- 对 KPL 外部 HTML 做富文本渲染。
- 完整题材别名知识库和机器学习匹配。

Non-Goals:
- 不用 mock 填充题材库。
- 不把 KPL 上游不可用解释为市场无题材。

## Technical Constraints
- 后端必须保持现有 D004 contract。
- KPL token/user/cookie 不应泄露到前端。
- 前端不能直接访问 KPL 外部接口。
- 改动应局限于题材工坊、KPL connector 和对应测试。

## Integration Points
- KPL realtime：`InfoGet / Theme / ID=<theme_id>`。
- KPL history：`HomeThemeList / HisHomeDingPan`。
- KPL concept：`ConceptSelected` 与 `ZhiShuStockList_W8` 作为 fallback/匹配来源。
- KPL stock ranking：后续用于给题材成员补实时涨幅、价格、成交额、热度。
- 题材工坊 React 页面：新增 library tab。

## Testing Requirements
- 单元测试锁定 `get_theme_info` 参数。
- 单元测试锁定 `normalize_theme_library_detail` 对老字段的规整。
- API 测试锁定 `/theme/library` 和 `/theme/library/{id}` 的 real/fallback contract。
- 前端至少通过 TypeScript 构建或测试命令验证新组件无类型错误。
- 如本地服务可用，手工探测 `/api/theme/library` 与页面 tab。

## Acceptance Criteria
- S01：连接器与 API 能稳定返回题材库列表/详情 contract，空数据和上游错误不会静默吞掉。
- S02：题材工坊展示题材库列表和详情，能区分 real/fallback/unavailable。
- S03：题材库成员与板块强度、涨停池、5000+ 个股 ranking 做匹配，输出匹配置信度和行情字段。
- S04：AI 分析题材时使用题材库、板块强度、题材成员、实时行情的证据包，而不是固定模板。
- S05：完成端到端 QA，列出仍无数据的接口和原因。

## Open Questions
- 生产环境是否能提供 KPL Cookie 或旧 `kpl_home_theme_mes` 数据表，以恢复完整 `HomeThemeList/InfoGet`。
- 题材工坊是否需要把 `Introduction` 渲染为富文本；若需要，应先引入 sanitizer。
- 题材名与板块名的别名规则由产品人工维护，还是从历史匹配自动沉淀。
