# S03 T01 Spike：KPL c1/c2 假定 + 7 处参数差异机械目录

> 本文档是 S03 起始的 spike-as-task 输出，作为 T02 KPL connector 重构的 ground truth 输入。
> T02 的任何参数偏离 daban_pc 实测可由 reviewer 通过 `grep` 比对本文表格与新 client 代码定位。

## Spike 元信息

| 字段 | 值 |
|---|---|
| Spike date | 2026-04-30 |
| 模式 | autonomous-mode（无业主真实 Cookie 实证） |
| Spike 类型 | 文档 spike（不打 API、不读 DB、不跑容器） |
| 证据来源 | `docs/gsd-input/raw/PySise6Code/daban_pc/models/kpl/kpl_server.py`（1135 行）+ `docs/gsd-input/raw/PySise6Code/daban_fastapi/app/api/v1/kpl/kpl_router.py`（1267 行） |
| 输出契约 | `prototype/docs/S03-T01-SPIKE.md`（本文件） |
| 决策 | 采用 c1（共享 Cookie）假定落地，c2（独立 Cookie）升级路径预留 |
| 业主真实 Cookie 验证 | 推迟到 S08 收口；本 spike 不打真实 KPL HTTP，避免占用业主额度 |

### autonomous-mode 限制说明

S03 必须 proof-first，但 autonomous-mode 下没有业主真实 Cookie 可跑实证。本 spike 改用「**daban_pc 客户端用同一份 device_id 同时打 apphwhq + apphis + applhb 三个 host**」这条强证据落地 c1 假定，把 7 处参数差异从 daban_pc 抓包代码机械化提取到一份可比对的 markdown table。S08 业主上 staging 时再用真实 cookie 验证 c1，若 apphis 401 → 触发 c2 升级 PR。

### 版本号修齐策略

prototype `KplClient.__init__` 行 107 默认值 `version: str = "10.1.1"`，与 daban_pc 抓包正式版本 `5.17.0.0` 不一致。**T02 必须把默认值改为 `"5.17.0.0"`**；保留构造参数允许业主在 admin UI 改写（万一未来 KPL 升版本号校验）。endpoints.py 行 4 `KPL_ARTICLE_HOST` 已硬编码 `VerSion=5.17.0.0`，本身没问题，但 client.py 的 `_base_params` 用 `self.version` → 本任 task 后必须保证 prototype 全栈仅一个版本号事实。

## 7 处差异完整目录

每条差异均给出：接口语义 / prototype 当前参数 / daban_pc 实测参数（具体字段值）/ 影响 prototype 哪个路由 / 预期上游响应 shape。所有 daban_pc 实测参数已逐字段逐字符从 `kpl_server.py` 1135 行机械提取，未做任何抽象或省略。

| # | 接口语义 | prototype 当前 | daban_pc 实测（关键字段值） | 预期上游响应 shape | 影响的 prototype 路由 | 出处 |
|---|---|---|---|---|---|---|
| 1 | **板块强度（实时 + 历史）** | `a=ConceptSelected, c=HomeDingPan/HisHomeDingPan, Order, st=20, Index=str, Date(可选)` | `a=RealRankingInfo, c=ZhiShuRanking, Order=1, st=30, RStart=0925, REnd=<recent_5min>, Type=1, ZSType=7, Index=str, Date(可选)` | `{list: [{plate_id, plate_name, change, ...}]}` | `routes/replay.py /sectors`, `routes/intraday.py cycle-batch`, `routes/theme.py` | `kpl_server.py:151-187` |
| 2 | **板块详情个股** | `a=ConceptDetail, c=HomeDingPan/HisHomeDingPan, PlateID, Order=0, st=60, Index=str, Date(可选)` | `a=ZhiShuStockList_W8, c=ZhiShuRanking, Order=1, TSZB=0, st=30, old=1, IsZZ=0, Token="0", UserID="0", Type=-4, IsKZZType=0, TSZB_Type=0, filterType=0, PlateID, Index=str, RStart=0925, REnd=<recent_5min> 或 Date(历史)` | `{list: [{stock_code, stock_name, change, ...}]}` | `routes/replay.py sector_detail`, `routes/intraday.py sector_detail` | `kpl_server.py:240-323` |
| 3 | **子板块** | `a=ConceptSubsection, c=HomeDingPan/HisHomeDingPan, PlateID, IsShow=1, Date(可选)` | `a=SonPlate_Info, c=ZhiShuRanking, PlateID, IsShow=1（仅历史）, DEnd=<recent_5min>（仅实时）, Date(可选)` | `{list: [{son_plate_id, son_plate_name, ...}]}` | `routes/replay.py sector_detail (sub-list)` | `kpl_server.py:198-237` |
| 4 | **市场异动** | `a=MarketAnomaly, c=HomeDingPan/HisHomeDingPan, Index=0, st=100, Date(可选)` | `a=Radar, c=HomeDingPan, st=30, Index=0, Date=data_desc`（**a 字段名都不一样，prototype 用了错的方法名**） | `{list: [{stock_code, anomaly_type, time, ...}]}` | `routes/intraday.py anomaly`, `routes/sentiment.py` | `kpl_server.py:692-713` |
| 5 | **市场情绪/市值** | `a=MarketStatistics, c=HisHomeDingPan, Day` + 二次 `a=DiskReview` | `a=HisZhangFuDetail, c=HisHomeDingPan, Day=data_desc`（**单接口聚合，daban_pc 不需要二次 DiskReview 拼**） | `{info: {market_count, strong, weak, ...}}` | `routes/replay.py summary`, `routes/sentiment.py` | `kpl_server.py:121-141` |
| 6 | **实时窗口（午休处理）** | 缺 `RStart=0925` + `REnd=<recent_5min>`；client.py 未实现 `_recent_5min()` | 必带 `RStart=0925` + `REnd=<recent_5min>`；午休 11:30-13:00 强制 `recent_time=1130`；最大不超过 1500 | 实时端点缺这两参数会被 KPL 服务端按"全天"返回，可能 OOM 或 truncate | sectors / sector_detail / anomaly / 涨停板等所有实时路径 | `kpl_server.py:29-48`（`get_recent_5_minutes`） |
| 7 | **历史详情扩展参数** | 缺 `Token="0"` / `UserID="0"` / `IsZZ` / `TSZB` / `IsKZZType` / `TSZB_Type` / `filterType` / `Order` / `Type=-4` / `old=1` / `ZSType=7`（板块强度） / `Index` 字串化 | 全带（值见 # 1、# 2 行）；`Token`/`UserID` 即使匿名也填字符串 `"0"` 而非空串；`Index` 必须 `str(int)` | 缺这些字段大概率被服务端按"参数缺失"返回 422/empty | `concept_detail` / `concept_selected` 历史路径 | `kpl_server.py:154-187`（板块强度） + `261-313`（详情） |

### 配套差异（同一证据链，T02 必须落地但不进 7 处主表）

| 项 | prototype 当前 | daban_pc 实测 | 备注 |
|---|---|---|---|
| `_DEFAULT_HEADERS` 缺 `Cookie` | client.py:19-24 没有 cookie 字段 | daban_pc client 通过 `requests.post(... headers=...)` 自带 cookie jar；KPL 服务端无 cookie 大概率 200 + empty list 或 401 | T02 必须加 `cookie_provider` + `_headers()` 注入 |
| `version` | client.py:107 默认 `"10.1.1"` | `5.17.0.0` | T02 默认值改 `5.17.0.0` |
| 凭证缺失 silent return | client.py:121-123 返回 `{}` | daban_pc 不做凭证缺失短路（依赖运行时 cookie 有效） | T02 改成 sentinel 路径 + `cookie_missing` last_error，不计入 consecutive failure |
| 涨停表现 `DailyLimitPerformance` | 当前 `PidType` 缺、`Type` 缺、`st=20` | `PidType=3`（实时连板）/ `4`（历史）, `Type=4`（实时）/ `5`（历史）, `st=2000`, `Order=0`/`1` | `kpl_server.py:367-405`，影响 `routes/replay.py /ladder` |
| 龙虎榜 `GetStockList,c=LongHuBang` | 已带 `Token=self.token, UserID=self.user_id, st=str(size), Type=2`，方向正确 | daban_pc 同样结构，`DeviceID` 用 `971c5207-ee29-3aa3-9377-a7ed59e8d322`（与主 device_id 不同） | `kpl_server.py:421-436`；T02 保留主 device_id 即可，分歧不影响 c1 假定 |

### 结构性证据：daban_pc 客户端类一份 device_id 打三 host

`docs/gsd-input/raw/PySise6Code/daban_pc/models/kpl/kpl_server.py` 全文 1135 行，是一个 **单 class** `kpl_server`，全部 KPL 方法绑在同一对象上。`docs/gsd-input/raw/PySise6Code/daban_fastapi/app/api/v1/kpl/kpl_router.py:34` 进一步证据：

```python
kpls = kpl_server()  # 模块级单例，所有 26 个 /api/v1/kpl_* 路由共用
```

这个单例同时调用 apphwhq（实时板块强度）、apphis（历史详情）、applhb（龙虎榜），三 host 都用同一份 device_id `a59f30e2-5978-3ab5-ac32-d6ae2cc89fd5`（除龙虎榜用次级 device_id）。如果 KPL 服务端按 host 隔离 cookie 域，这种共享 device_id 在 daban_pc 部署上不可能稳定运行 → daban_pc 既然能稳定运行，**c1（共享 Cookie 跨 host 有效）的命中概率显著高于 c2（端点独立 cookie 域）**。

## c1 vs c2 假定决策

### 决策

**S03 落 c1（业主单输入框 + 单 system_secrets row + 单 cookie 注入到所有 KPL host）**。c2 升级路径作为 schema 级预留，不展开实现，仅在以下条件触发：

1. S08 业主上 staging 跑 `GET /api/health/kpl` 时 history 端点（apphis）返回 401/403/cookie 失效，但 realtime 端点（apphwhq）同时仍返 200。
2. 或业主明确反馈"我有两份 cookie 想分别录入"。

### 决策证据（按强度递减）

| 强度 | 证据 | 来源 |
|---|---|---|
| 强 | daban_pc 单一 `kpl_server` 实例同 device_id `a59f30e2-5978-3ab5-ac32-d6ae2cc89fd5` 同时打 apphwhq + apphis + applhb 三 host，未拆 cookie jar | `kpl_server.py:127, 157, 177, 210, 224, 269, 299, 378, 398, 426, 458, 553, 624, 676, 701, 724, 753, 765`（device_id 出现 18 次以上，全是同一值） |
| 强 | daban_fastapi 单一 `kpls = kpl_server()` 模块级单例服务 26 个 /api/v1/kpl_* 路由 | `kpl_router.py:34` |
| 中 | 三 host 同公司同域名 `*.longhuvip.com`；KPL 移动 App 单登录态推送多端口 | endpoints.py + 业内常识 |
| 弱 | prototype `endpoints.py` 已通过 `Host` header 切 host，不切 client；本身就是 c1 友好结构 | `prototype/packages/connectors/kpl/endpoints.py` + `client.py:115-118` |

### c1 假定的具体落地形态（T02-T07）

| Slice 工件 | c1 形态 |
|---|---|
| `system_secrets` 行 | 一行 `secret_key='kpl_cookie', secret_type='cookie'` Fernet 密文 |
| `cookie_provider.get_kpl_cookie()` | 不带 `scope` 参数；返回单个 cookie 字符串；空字符串 → unavailable |
| `KplRealtimeClient` / `KplHistoryClient` | 共用同一个 cookie 来源；构造时各自 `httpx.Client(cookies={...})` |
| Admin UI | 单 TextArea「KPL 共享 Cookie」+ 单保存按钮 |
| `kpl_realtime_health` / `kpl_history_health` job | 各 30min 各自 probe；都用同一份 cookie；任一失败都写 `system_alerts.kind` |

### c2 假定下需要变更的工件清单（升级时一次性 PR）

见下文 `## c2 升级路径`。

## 午休时间窗策略

### 11:30 强制规则

`docs/gsd-input/raw/PySise6Code/daban_pc/models/kpl/kpl_server.py:29-48` 是 ground truth 实现。逻辑摘要：

```python
def get_recent_5_minutes(self):
    current_time = datetime.datetime.now()
    # 向下取整到最近 5 分钟
    recent_time = current_time - datetime.timedelta(minutes=current_time.minute % 5,
                                                    seconds=current_time.second,
                                                    microseconds=current_time.microsecond)
    # 上限 15:00
    max_time = recent_time.replace(hour=15, minute=0, second=0, microsecond=0)
    if recent_time > max_time:
        recent_time = max_time
    # 11:30 < t < 13:00 → 强制 11:30（休市段不查实时，沿用上午收盘快照）
    if datetime.time(11, 30) < recent_time.time() < datetime.time(13, 0):
        recent_time = recent_time.replace(hour=11, minute=30, second=0, microsecond=0)
    return recent_time.strftime("%H%M")  # → "1130"
```

T02 在 `KplRealtimeClient` 内部新增 `_recent_5min()` 方法，必须 byte-for-byte 复刻这段逻辑（包括 `<` 而非 `<=` 边界）。

### 4 个 boundary（T02 单元测试覆盖）

| boundary | 当前时刻 | 期望 `_recent_5min()` 返回 | 解释 |
|---|---|---|---|
| 1 | 09:24（开盘前） | `0920` | 取 5 分钟下界，不强制 11:30 |
| 2 | 11:31（午休首分） | `1130` | 强制 11:30（11:30 < 11:31 < 13:00） |
| 3 | 12:55（午休末分） | `1130` | 强制 11:30（11:30 < 12:55 < 13:00） |
| 4 | 14:55（收盘前） | `1455` | 5 分钟下界，未触发 11:30 与 15:00 上限 |

> **边界陷阱**：daban_pc 用严格小于 `<`，意味着 `t == 11:30` 时 **不** 强制。`_recent_5min()` 在 11:30 整点本身就返回 `"1130"`（5 分钟下界），等价于强制态，所以这条 corner 不需要单独写测试。

### 实测参数中的 RStart / REnd / DEnd 影响范围

- `RStart=0925`（硬编码 9:25 开盘前 5 分钟）+ `REnd=_recent_5min()` 用于 **板块强度** 实时（# 1）和 **板块详情** 实时（# 2）。
- `DEnd=_recent_5min()` 用于 **子板块** 实时（# 3，daban_pc 用 DEnd 不用 REnd，参数名差异由 KPL 历史命名造成）。
- `MarketAnomaly` (# 4) 和 `MarketStatistics` (# 5) **不需要** RStart/REnd/DEnd（实时按 Date 即可）。

## c2 升级路径

c2 升级触发条件已在前文 § c1 vs c2 假定决策给出。一旦触发，按以下顺序在单一 PR 内一次性变更：

### (a) DB schema：`system_secrets` 加 `secret_type` 列（已在 0002 migration 预留）

`prototype/alembic/versions/0002_system_secrets_alerts.py`（T03 实现）必须 **现在就** 加 `secret_type VARCHAR(32) DEFAULT 'cookie'` 列。c1 阶段所有行都是 `secret_type='cookie'`。c2 升级时新增两行：

```sql
INSERT INTO system_secrets(secret_key, secret_type, secret_value)
  VALUES ('kpl_realtime_cookie', 'cookie_realtime', '<Fernet ciphertext>'),
         ('kpl_history_cookie',  'cookie_history',  '<Fernet ciphertext>');
-- 旧 'kpl_cookie' 行通过 secret_type='cookie' 留下不删，admin UI 只读，避免向后不兼容
```

### (b) `cookie_provider` 改造

```python
# c1 形态（T02 默认实现）
def get_kpl_cookie() -> str: ...

# c2 形态（升级 PR）
def get_kpl_cookie(scope: Literal["shared", "realtime", "history"] = "shared") -> str:
    if scope == "shared":
        return _read("kpl_cookie")
    return _read(f"kpl_{scope}_cookie") or _read("kpl_cookie")  # fallback
```

`KplRealtimeClient` / `KplHistoryClient` 各自调 `get_kpl_cookie('realtime')` / `get_kpl_cookie('history')`，自动 fallback 到共享 cookie。

### (c) Admin UI 拆两 TextArea

- 单 TextArea「KPL 共享 Cookie」 → 拆为「实时端点 Cookie (apphwhq)」+「历史端点 Cookie (apphis)」两个 TextArea + 一个「使用同一份 Cookie（c1 模式）」开关。
- `POST /api/admin/kpl-cookie` body 增 `type` 字段：`'shared' | 'realtime' | 'history'`。c1 时业主只用 `'shared'`，c2 时用后两者。
- 龙虎榜端点（applhb，merge）继续走 `'shared'` cookie，不拆三份（业主负担过大）。

### (d) 健康探针不变

`kpl_realtime_health` / `kpl_history_health` 各自 30min IntervalTrigger 已存在；c2 升级只是各自取的 cookie 不同，其它逻辑不变。

### 估时

c2 升级 PR 估时 **+0.5 day**（schema 列已预留 → 仅升级 cookie_provider + admin UI + 灌入两条新行）。当前 c1 落地估时不含此 0.5 day。

## 业主真实 Cookie UAT 计划

S03 不在 autonomous-mode 下打 KPL 真实 HTTP，**S08 收口阶段** 由业主登录 admin 后台粘贴真实 cookie 后跑联通验证。本节明确验收脚本与触发 c2 的判据。

### S08 业主操作脚本

1. 业主从手机抓包 / 浏览器 DevTools 拿到 KPL 实时端点 Cookie（同一份预期对历史端点也有效）。
2. 登录 staging admin 后台 `/admin` → KPL Cookie tab → 粘贴 cookie → 保存。
3. 30s 内观察后台 health 面板：
   - **期望**：`kpl_realtime_health` 转绿（http_code=200, list 非空）+ `kpl_history_health` 转绿。c1 假定通过。
   - **退路**：实时绿 + 历史红 → c1 假定不成立，触发 c2 升级 PR；本 spike 文档 append `## c2 Triggered` 章节记录时间、错误码、上游响应片段。
4. 故意改坏 cookie（删尾几位字符）→ 30 分钟内业主邮箱收到失效告警邮件 + 后台双健康灯转红 + 短线 4 路由 DataStatusBadge 转「数据源不可用」。
5. 恢复正确 cookie → 30 分钟内健康灯转绿 + `system_alerts.resolved_at` 更新 + 业主收恢复邮件。

### S08 验收 checklist（追加到 S08 UAT.md）

- [ ] `GET /api/health/kpl` 返 dual `{realtime, history}` 都为 `ok`
- [ ] `/intraday` 看到当日真实涨停板（DataStatusBadge=real）
- [ ] `/replay` 看到连板天梯 + 板块强度
- [ ] `/verification?tab=longhu` 看到龙虎榜
- [ ] `/admin` health 面板双绿
- [ ] 故意失效 cookie → 双红 + 邮件 + 短线页 unavailable
- [ ] 恢复 cookie → 双绿 + 恢复邮件 + 短线页 real

### c2 触发条件汇总

任意一项命中即触发 c2 升级 PR：

| 触发场景 | 观察信号 | 后续动作 |
|---|---|---|
| 历史端点 401/403 但实时端点 200 | `system_alerts.kind='kpl_history_health', meta.http_code in (401,403)`，同时 `kpl_realtime_health` 无 critical | 业主 ack alert → c2 PR |
| 业主明确两份 cookie | 业主邮件 / 后台反馈 | c2 PR |
| KPL 服务端在 S03→S08 期间改造 cookie 域 | 任意端点突发性 4xx，且业主拿到的新 cookie 不能跨端点 | 紧急 c2 PR |

### 不触发 c2 的情形（保留 c1）

- 双端点同时失败（=cookie 整体失效，不是 cookie 域问题）→ 业主重粘 cookie 即可，不动 schema。
- realtime 偶发 4xx 但 history 始终 200 → KPL 限流，不是 cookie 域问题；走 health job 重试 + alert 即可。
- SMTP 告警偶发漏发 → 与 cookie 域无关，独立排查。

---

## 校验

本 spike 不做实际 HTTP 验证，仅做以下静态校验（与本 task 验证命令对齐）：

- 文件存在：`prototype/docs/S03-T01-SPIKE.md`
- H2 章节数 ≥ 6（本文档当前 6 个：元信息 / 7 处差异 / c1 vs c2 / 午休 / c2 升级 / 业主 UAT）
- 无未填占位（grep 三连占位字符串应返回 0 行）
- 含 `c1` / `c2` / `11:30` / `RealRankingInfo` / `ZhiShuStockList_W8` / `HisZhangFuDetail` 关键词

T02 reviewer 须将本表 # 1-7 行作为 `KplRealtimeClient` / `KplHistoryClient` 参数 dict 的 ground truth；任何 prototype 实现与本表不一致都必须先修本表（含证据）再改代码。
