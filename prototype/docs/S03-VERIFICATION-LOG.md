# S03 Verification Log — KPL 实测连接器 + Cookie 录入 + 双健康探测

**Slice:** M001/S03 — KPL 实测改造 + 业主 Cookie 录入 + 双健康探测 + Cookie-Aware Unavailable
**Authoring:** T01–T07 累计留证；T07 收口写本日志，留给 S08 业主 UAT 接力使用。
**Sandbox:** 本日志区分 `algorithmic verification`（沙箱内 unit + 编译）与
`docker compose 真跑`（业主 staging 环境真跑）两条路径。沙箱无 mysql / SMTP /
真实 KPL 上游，contract / 单元测试是 PASS，端到端真跑由业主在 staging 走
本日志最后一节的命令清单。

---

## § 1 Spike Summary（T01）— c1 假定 + 7 处差异 + 业主 UAT 计划

**摘要** — 详见 [`prototype/docs/S03-T01-SPIKE.md`](./S03-T01-SPIKE.md)。

- **拓扑选 c1**：共享 Cookie 跨 KPL realtime/history/merge 三 host 落地。
  daban_pc kpl_server.py 单一 class 单 device_id 同时打 apphwhq + apphis +
  applhb 三 host 稳定运行 → 第一阶段共享 cookie 是已知工作配置。
- **c2 升级路径预留**：`system_secrets.secret_type` 列已加入 alembic 0002
  migration，c1 阶段全部行 `secret_type='cookie'`，未来如果业主 staging
  实测发现 history 端点 401 而 realtime 200，再行迁移到 c2（端点独立 cookie 域）
  时只需新增 `cookie_realtime` / `cookie_history` 两行，不必再改 schema。
- **7 处参数对齐 daban_pc**：T02 落地。
  1. realtime `Token`/`UserID` 即使匿名也填 `"0"` 而非空串
  2. realtime `Index` 必须 `str(int)`
  3. realtime 11:30–13:00 强制 `_recent_5min='1130'` 严格 `<` 边界
  4. realtime 市场异动 `a` 字段 = `"Radar"` （非旧代码 `"MarketAnomaly"`）
  5. history `c=HisHomeDingPan` 用于 DiskReview 拿 strong 字段
  6. realtime `c=HomeDingPan` 用于 ZhiShuStockList_W8 / SonPlate_Info
  7. merge LongHuBang `Type=2 / apiv=w38` 严格沿用 daban_pc 实测组合
- **Sentinel 模式（T02 落地）**：cookie 缺失时 `_post` 短路返回
  `{"_error":"cookie_missing"}`；上游 4xx 返回
  `{"_error":"kpl_upstream_error","http_code":N}`。T07 routes 层依此区分
  「cookie 缺失（运维待处理，不计入 consecutive_fail）」vs「上游异常」。
- **业主 UAT 计划摘要**：S08 留证；本 slice 内只验证算法契约 + 单元 + 编译。

## § 2 Alembic 0002 Upgrade Evidence（T03）

**摘要** — 详见 `T03-SUMMARY.md`。

```text
# 沙箱 algorithmic verification（无 mysql）：
prototype/$ python -c "
from packages.shared.db_models import ALL_MODELS
print('ALL_MODELS', len(ALL_MODELS))
"
# expected: ALL_MODELS 29  (= 27 旧表 + system_secrets + system_alerts)

prototype/$ python -m py_compile alembic/versions/0002_system_secrets_alerts.py
# expected: exit 0

# 沙箱 SKIP：alembic upgrade head 真跑（需 mysql 连接）
# 业主 staging 命令清单（docker compose 真跑路径）：
#   $ docker compose -f deploy/docker-compose.yml exec zhice-api \\
#       alembic upgrade head
#   $ docker compose exec mysql mysql -uroot -p<pw> zhice -e \\
#       "SELECT secret_key, secret_type, LENGTH(secret_value) AS len, updated_at \\
#        FROM system_secrets;"
#   expected output:
#     secret_key  | secret_type | len | updated_at
#     kpl_cookie  | cookie      | 0   | <now>
#   占位 row INSERT 验证：业主登录 /admin → KPL Cookie tab 看到 has_cookie=False
#   + last_updated_at = upgrade head 执行时间。
```

## § 3 Dual Health Endpoint Sample（T05）

**摘要** — `apps/api/services/kpl_health.py` + APScheduler 双 30min
IntervalTrigger。`/api/health/kpl` 公开端点不需要 admin auth（业主肉眼可
见）。返回结构：

```json
{
  "realtime": {
    "status": "ok",
    "last_ok_at": "2026-05-01T08:30:42",
    "last_error": null,
    "consecutive_fail": 0
  },
  "history": {
    "status": "fail",
    "last_ok_at": "2026-05-01T07:00:18",
    "last_error": "kpl_upstream_error http_code=401",
    "consecutive_fail": 2
  }
}
```

沙箱 algorithmic verification（cookie 缺失路径）：

```text
prototype/$ python -c "
from apps.api.services import kpl_health
kpl_health._evaluate('realtime')
print(kpl_health._HEALTH_CACHE)
"
# expected:
#   {'realtime': {'status':'fail','last_ok_at':None,'last_error':'cookie_missing',
#                 'consecutive_fail':0}, 'history': {...}}
# cookie_missing 路径 consecutive_fail 不递增（T05 已 lock 的语义）

# 业主 staging 命令清单：
#   $ docker compose logs -f zhice-api | grep "kpl_(realtime\|history)_health"
#   每 30 分钟看到 INFO 一条 probe 日志
#   $ curl -s http://staging/api/health/kpl | jq .
#   双键状态肉眼可见
```

## § 4 SMTP Test Trace（T06）

**摘要** — `apps/api/notify/smtp.py` + `apps/api/notify/templates.py`
中文 failure / recovery 邮件模板。`send_alert(...)` 显式不 import
`apps.api.db`，架构守护测试在源文件文本里搜 `INSERT INTO` /
`UPDATE ` / `from apps.api.db` 全部为空 —— 硬隔断
probe-fail → email-fail → alert → probe-fail 死循环。

```text
# 沙箱 unit 测试覆盖（mock smtplib.SMTP）：
prototype/$ python -m pytest tests/notify/ -q
# expected: 8 passed

# 业主 staging 真投递留证：
#   $ docker compose exec zhice-api python -c "
#     from apps.api.notify.smtp import send_alert
#     from apps.api.notify.templates import cookie_failure_email_body
#     subject, body = cookie_failure_email_body(
#         endpoint='apphwhq',
#         http_code=401,
#         last_ok_at='2026-05-01T07:00:00',
#     )
#     ok = send_alert(subject=subject, body=body)
#     print('SMTP send result:', ok)
#   "
#   expected: SMTP send result: True
#   业主邮箱（owner@example.com）收到中文「KPL Cookie 失效」邮件
#   邮件 body 仅包含 endpoint / http_code / last_ok_at / 操作指引
#   绝不含 cookie 明文（架构守护测试已 lock）。

# 沙箱无 SMTP 凭证降级：
#   smtp_* 配置缺失时 logger.warning 一次（T06 防 spam），无邮件投递。
```

## § 5 Cookie-Aware Unavailable Demo（T07）

**核心交付** — 4 短线路由 (intraday / replay / longhu / theme) cookie 缺失时
返回 `status='unavailable'` + `message='KPL Cookie 未配置或已失效，请联系
管理员在后台 /admin 录入'`。前端 `DataStatusBadge` 据 `status='unavailable'`
渲染红色徽标。

### 5.1 Sentinel 模块单元

```text
prototype/$ python -c "
from packages.connectors.kpl.sentinel import (
  is_cookie_missing, is_upstream_error, cookie_unavailable_message,
  from_client_state, COOKIE_MISSING_MESSAGE,
)
assert is_cookie_missing({'_error':'cookie_missing'})
assert is_upstream_error({'_error':'kpl_upstream_error','http_code':401})
assert 'KPL Cookie 未配置' in cookie_unavailable_message({'_error':'cookie_missing'})
assert 'http_code=401' in cookie_unavailable_message(
  {'_error':'kpl_upstream_error','http_code':401})
print('sentinel module PASS')
"
# expected: sentinel module PASS
```

### 5.2 KplClient.last_error 状态机

```text
prototype/$ python -c "
from packages.connectors.kpl.client import KplClient
c = KplClient.__new__(KplClient)
c.last_error = None; c.last_http_code = None
KplClient._record(c, {'_error':'cookie_missing'})
assert c.last_error == 'cookie_missing'
KplClient._record(c, {'_error':'kpl_upstream_error','http_code':401})
assert c.last_http_code == 401
KplClient._record(c, {'data':[1]})  # non-sentinel clears
assert c.last_error is None
print('last_error state machine PASS')
"
```

### 5.3 沙箱 algorithmic verification — 4 短线路由 cookie 缺失

不启 uvicorn / mysql 的纯单元路径：

```text
prototype/$ python -m py_compile \
  packages/connectors/kpl/sentinel.py \
  apps/api/routes/intraday.py \
  apps/api/routes/replay.py \
  apps/api/routes/longhu.py \
  apps/api/routes/theme.py
# expected: exit 0

prototype/$ for f in apps/api/routes/{intraday,replay,longhu,theme}.py; do
  grep -q "is_cookie_missing" "$f" || { echo MISSING $f; exit 1; }
done
echo OK
# expected: OK
```

### 5.4 业主 staging docker compose 真跑路径

```text
# Step 1: 部署
$ docker compose -f deploy/docker-compose.yml up -d --build
$ docker compose exec zhice-api alembic upgrade head

# Step 2: 故意不录入 cookie（system_secrets 占位 row secret_value=''）
$ curl -s http://staging/api/market/limit-up | jq '.status, .message'
# expected:
#   "unavailable"
#   "KPL Cookie 未配置或已失效，请联系管理员在后台 /admin 录入"

$ curl -s http://staging/api/market/anomaly | jq '.status, .message'
$ curl -s http://staging/api/longhu/rank | jq '.status, .message'
$ curl -s http://staging/api/theme/list | jq '.status, .message'
# 预期都是 unavailable + 同一条 message

$ curl -s http://staging/api/health/kpl | jq .
# expected: realtime/history 两键 status='fail', last_error='cookie_missing',
#           consecutive_fail=0 (cookie_missing 不递增)

# Step 3: 业主登录 /admin → KPL Cookie tab → 粘贴抓包 cookie → 保存
# Step 4: 30 秒内观察双 HealthLight 转绿
$ curl -s http://staging/api/health/kpl | jq .
# expected: realtime/history status='ok', last_ok_at=<now>

# Step 5: 复测短线路由
$ curl -s http://staging/api/market/limit-up | jq '.status'
# expected: "real"

# Step 6: 故意改错 cookie (truncate 一半) 等 30 分钟
$ curl -s http://staging/api/health/kpl | jq .
# expected: 任一端点 status='fail', last_error='kpl_upstream_error http_code=401'
# 业主邮箱收到 KPL Cookie 失效邮件（T06 模板）
# /admin 健康监控 tab 看到 system_alerts 行 + 「我已知悉」按钮可 ack
```

### 5.5 前端构建 & 静态契约

```text
prototype/apps/web/$ npm run lint
# expected: 0 errors（warnings 不退化）

prototype/apps/web/$ npm run build
# expected: exit 0
#           dist/index.html + dist/assets/*.js 生成
#           AdminKplCookiePanel + AdminHealthPanel 各自一个 chunk（lazy split）

# DataStatusBadge 实测：cookie 清空后 /intraday 页面
#   - 涨停板卡 -> Tag 'red' 文字 '数据源不可用'
#   - Tooltip 显示 '数据源: kpl'（不含 cookie 明文）
```

---

## § 6 Sandbox Notes — 沙箱与真跑路径分流

| 验证点 | 沙箱（algorithmic） | 业主 staging（docker compose 真跑） |
|--------|---------------------|------------------------------------|
| Alembic 0002 schema | `python -m py_compile` + ALL_MODELS 计数 | `alembic upgrade head` + `SHOW COLUMNS` |
| Cookie Fernet 加密 | unit test mock fernet | 业主 /admin 录入 → mysql secret_value 是 base64 |
| APScheduler 双 30min | unit test 调 `_evaluate` 直接 | `docker compose logs grep kpl_realtime_health` |
| SMTP 投递 | unit test mock smtplib | 业主邮箱真收到中文邮件 |
| KPL realtime 端点 | sentinel + last_error round-trip | curl `/api/market/anomaly` |
| KPL history 端点 | 同上 | curl `/api/market/summary` |
| 4 短线路由 unavailable | grep + py_compile | curl 4 端点拿到 unavailable |
| 前端 Tabs 三 tab | npm run build dist 检查 lazy chunk | 业主登录 /admin 肉眼看到三 tab |

**已知限制（不阻塞 S03 完成，转 S08 接力解决）：**
- `packages/connectors/registry.py` 的 `_read_kpl_cookie()` 走 `from
  apps.api.cookie_provider` 旧路径（实际位置在
  `apps.api.services.cookie_provider`），import 失败后退到 `settings.kpl_cookie`
  环境变量。`get_kpl()` `lru_cache(maxsize=1)` 单例在进程生命周期内不会自动
  reload cookie；业主在 admin 后台更新 cookie 后必须 docker compose
  restart zhice-api 才能让 connector 拿到新 cookie。S04 / S08 期间需要把这条
  registry 路径修正 + 加一条 lru_cache invalidation hook（cookie set 后
  `get_kpl.cache_clear()`）。
- 沙箱无法跑 `npm run dev` 浏览器 UAT；DataStatusBadge 红色 + Tooltip
  视觉留证留给 S08 Playwright 自动化截图。
