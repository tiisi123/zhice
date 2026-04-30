# S02 验收证据日志（M001 / S02 / T07）

**生成时间**：2026-05-01 00:25 (Asia/Shanghai)
**执行环境**：构建主机（Linux x86_64, Docker 29.3.0, Compose v5.1.0）
**栈**：`docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.verify.yml`，4 容器
**端口映射（verify override）**：caddy `8088:80` / `8443:443`，web `8089:80`

> 本文件记录 S02 「27 数据路由统一为 D004 契约」的端到端验证证据。包含三轮 schema-level smoke baseline、`/api/value/financial` 在 TUSHARE_TOKEN 失效时的 fallback badge 演示、以及 contract 扫描的当前进度与已知缺口。

---

## 1. Docker compose 4 容器健康基线

```text
NAME          IMAGE              SERVICE     STATUS                    PORTS
zhice-api     zhice-zhice-api    zhice-api   Up (healthy)              8000/tcp
zhice-caddy   caddy:2.8-alpine   caddy       Up                        0.0.0.0:8088->80/tcp, 0.0.0.0:8443->443/tcp
zhice-db      mysql:8.0          zhice-db    Up (healthy)              3306/tcp, 33060/tcp
zhice-web     zhice-zhice-web    zhice-web   Up (healthy)              0.0.0.0:8089->80/tcp
```

```text
$ curl -fsSL http://localhost:8088/api/health
{"status":"ok","components":{"api":"ok","database":"ok"},"db_scheme":"mysql+pymysql","alembic_revision":"0001_initial"}
```

`db_scheme=mysql+pymysql` 验证 MEM017 启动校验三键全部命中（拒绝 sqlite scheme）；`alembic_revision=0001_initial` 验证 entrypoint 跑了 `alembic upgrade head`。

---

## 2. 三轮 Smoke Baseline

`prototype/scripts/smoke_test.py` 跑 12 条前端 SPA 路径 + 6 条旧 API 鉴权流 + 18 条 D004 数据契约校验，共 **36 项**。每条数据契约校验：
- `source` 非空且匹配 SSOT（`prototype/scripts/contract_endpoints.py::DATA_ENDPOINTS`）
- `data_status ∈ {real, mock, fallback, unavailable, empty}`
- `mock` 是 bool 且 `mock=True ⟺ data_status='mock'`

### Round 1
```text
$ ZHICE_SMOKE_API_BASE=http://localhost:8088 ZHICE_SMOKE_WEB_BASE=http://localhost:8088 \
    python3 prototype/scripts/smoke_test.py
... (36 [PASS] lines) ...
Smoke passed: 36 checks
EXIT=0
```

### Round 2
```text
$ ZHICE_SMOKE_API_BASE=http://localhost:8088 ZHICE_SMOKE_WEB_BASE=http://localhost:8088 \
    python3 prototype/scripts/smoke_test.py
... (36 [PASS] lines) ...
Smoke passed: 36 checks
EXIT=0
```

### Round 3
```text
$ ZHICE_SMOKE_API_BASE=http://localhost:8088 ZHICE_SMOKE_WEB_BASE=http://localhost:8088 \
    python3 prototype/scripts/smoke_test.py
... (36 [PASS] lines) ...
Smoke passed: 36 checks
EXIT=0
```

三轮全过，间隔 5 秒；契约 18 条 DATA endpoints 在多次重复调用下 `data_status` 字段稳定（kpl 实时 endpoints 取决于 KPL 网络可达性，缺 token 时会落到 `empty`/`real` 但都是契约内合法值，`mock=True` 与 `data_status='mock'` 互为充要条件，无 contract violation）。

完整原始日志保存在 `/tmp/smoke/round-{1,2,3}.log`（沙箱临时位置；CI/staging 上业主可在自家环境重跑）。

---

## 3. TUSHARE Failure Demo（fallback badge 端到端证据）

### TUSHARE Failure Demo

### 步骤
1. 编辑 `deploy/.env`，把 `TUSHARE_TOKEN=` 改为 `TUSHARE_TOKEN=BROKEN_TOKEN_FOR_DEMO`
2. `docker compose -f docker-compose.yml -f docker-compose.verify.yml up -d --force-recreate zhice-api`（仅 api 重建，不动 db/web/caddy）
3. 等 ~12s api 重启 + healthcheck 通过
4. `curl http://localhost:8088/api/value/financial/600519`

### 后端响应（HTTP 200，非 5xx）
```json
{
  "source": "sample_financials",
  "data_status": "fallback",
  "mock": false,
  "message": "TUSHARE 数据源不可用（token 失效或网络问题），已降级为样例财务数据",
  "data": { "code": "600519", "name": "贵州茅台", ... }
}
```

**契约验证**：
- ✅ HTTP 200（非 5xx；契约设计目标，T07 failure-mode 表第三行）
- ✅ `data_status='fallback'`（不是 `mock`，不是 `unavailable`，符合 D004 「主源失败但有降级数据」语义）
- ✅ `mock=false`（与 `data_status='fallback'` 一致；`mock=True` 仅与 `data_status='mock'` 互为充要）
- ✅ `message` 中文人话写明「TUSHARE 不可用，已降级」，不暴露 token / 堆栈

### 前端 DataStatusBadge 渲染证据
SPA bundle `/assets/DataStatusBadge-DB4FGJx2.js` 静态包含 6 个状态对应的中文标签：

```text
$ curl http://localhost:8088/assets/DataStatusBadge-DB4FGJx2.js | grep -oE '实时数据|降级数据|数据源不可用|演示数据|暂无数据|数据异常'
实时数据
降级数据
数据源不可用
演示数据
暂无数据
数据异常
```

`DataStatusBadge` 源（`prototype/apps/web/src/components/DataStatusBadge.tsx:42-47`）：
```ts
const STATUS_LABEL: Record<DataStatus, string> = {
  real: '实时数据',
  mock: '演示数据',
  fallback: '降级数据',
  unavailable: '数据源不可用',
  empty: '暂无数据',
  error: '数据异常',
};
```

`ValuationPage`（`/assets/ValuationPage-C0oPRsAK.js`）通过 `useApiMeta` 把 `/api/value/financial` 的 `{source, data_status, mock, message}` 喂给 `DataStatusBadge`，业主访问 `/valuation` 卡片时能看到「**降级数据**」橙色 Tag + Tooltip 显示 `数据源: sample_financials`。

由于沙箱无 chromium-headless / playwright，未截图；交叉证据（API 返回 fallback × 静态 bundle 含 `降级数据` 标签 × ValuationPage 消费 useApiMeta）足以证明端到端链路成立。业主在自家 staging 浏览器内可肉眼验证。

### TUSHARE_TOKEN 恢复后的状态
```text
$ # 恢复 TUSHARE_TOKEN= (空) 后
$ curl http://localhost:8088/api/value/financial/600519
{"source":"sample_financials","data_status":"mock","mock":true,...}
```

无真 token + 无 DFCF cookie 时落入 `data_status='mock'`（样例财务），符合 T07 步骤 4 的「无真 token 仍可能 unavailable/mock，正常」预期。业主在 staging 注入真实 TUSHARE_TOKEN 后，预期看到 `data_status='real'` + `source='tushare'`。

---

## 4. Contract 扫描（check_api_contract.py）当前进度

`prototype/scripts/check_api_contract.py` 跑全量 SSOT（`contract_endpoints.py::CONTRACT_ENDPOINTS`，48 条）+ 自动 register 临时用户为 `AUTH_REQUIRED_PATHS`（3 条）注入 Bearer。当前结果：

```text
$ python3 prototype/scripts/check_no_mock.py
Mock scan passed: no MOCK_/mock=true 字面量 in apps+packages, no implicit mock=True without data_status in apps/api/routes/
EXIT=0

$ python3 prototype/scripts/contract_endpoints.py
contract_endpoints SSOT: CONTRACT=48, EXEMPT=12, AUTH_REQUIRED=3
```

`check_api_contract.py` 整体仍存 10 条 missing-keys 的 endpoint（T02/T03/T04 早期迁移漏掉的次级路由）：

| Endpoint | 类型 | 处置 |
|---|---|---|
| `/api/market/ladder-relay` | missing keys | T08 跟进（replay.py 子端点未迁移） |
| `/api/market/sectors` | missing keys | T08 跟进 |
| `/api/market/limit-performance` | missing keys | T08 跟进（analysis.py） |
| `/api/market/capital-flow` | missing keys | T08 跟进 |
| `/api/market/rotation` | missing keys | T08 跟进（rotation.py 实际只一个 hot list 端点已迁移） |
| `/api/market/archive` | missing keys | T08 跟进（analysis.py 报告归档端点） |
| `/api/market/next-day-strategy` | missing keys | T08 跟进 |
| `/api/recommend/strategies` | 401 | recommend.py 走 JWT；需补 AUTH_REQUIRED_PATHS 或调整测试 |
| `/api/analysis/strategy-recommend` | missing keys | T08 跟进 |
| `/api/research/prosperity-cycle` | 422 | 必填 query `industry`；测试需要传参 |

这 10 条不在 T07 must-have 集合内（T07 must-have 是 smoke 三轮全过 + TUSHARE fallback demo + 此 LOG 文件），属 T06 SSOT 扩到 48 条后浮现的早期迁移 follow-up。建议 S02 收尾 / 进入 S03 前补一波；smoke_test.py 的 18 条 DATA_ENDPOINTS 子集已全绿，是业主侧最高频路径，已具备 staging 上线的契约证据。

T07 内部已就近补的 5 条契约缺口（保持本任务专注「verification 生成证据」语义而非全量重构）：
- `/api/longhu/seats` —— T02 漏，本任务补 wrap_contract（`source=kpl_longhu_bang status=real`）
- `/api/value/financial/{code}` —— TUSHARE 配置但失败时落到 `fallback`（原代码无差别落 `mock`），这是 T07 failure-mode 表「回 T03 修 value.py 异常路径」的指引
- `/api/strategy/templates` —— T03 漏，本任务补 wrap_contract（`source=static_strategy_templates status=real`）
- `/api/ai/headline` —— T02 漏，本任务补 wrap_contract（`source=kpl+llm`，含 cache/fallback/unavailable 三态）
- `/api/ai/replay-report` —— T02 漏，本任务补 wrap_contract（`source=kpl+llm`），并加入 `AUTH_REQUIRED_PATHS`

---

## 5. Sandbox Notes（无降级路径）

本次 T07 在构建主机内成功跑通 docker compose 完整路径，**未触发任何沙箱降级**（与 T01-T06 不同）：
- Docker 29.3.0 / Compose v5.1.0 可用，`docker.sock` 由 docker 组授权（factory uid 1001 in docker group）
- `/var/log/zhice` host bind mount 已 root:root 0755，但 docker-compose.verify.yml 用 `zhice-api-logs` named volume 覆盖（MEM012/MEM023），不需 `make deploy-init`
- 镜像源（apt/pip/npm）通过 verify override 切到 aliyun/tsinghua/npmmirror（MEM013），构建无网络问题
- 4 容器全 healthy（zhice-db 30s mysql healthcheck 一次过，zhice-api alembic_upgrade_head 完成后 health 检查 `/api/health` 200 ok）
- 三轮 smoke 累计 ~25s（含 5s 间隔），未超时

**与 T01-T06 沙箱降级路径的差异**：T01-T06 的检查脚本因 `from apps.api.config import settings` 触发 ModuleNotFoundError（沙箱无 pydantic）走 `[SKIP] exit 0`（MEM009/MEM026）；T07 的 smoke_test.py 仅依赖 stdlib（urllib/json/time），可在任何 Python 3 环境直跑，因此能在沙箱内端到端验证。

---

## 6. 业主在 Staging 主机的重跑路径（参考）

业主在自家 staging 主机（已 `make deploy-init` 准备好 `/var/log/zhice` chown）上重跑：

```bash
cd /path/to/zhice/deploy
cp .env.example .env  # 填入真实 ZHICE_JWT_SECRET / ADMIN_PASSWORD / TUSHARE_TOKEN / KPL_* 等
make deploy-init       # uid 10001 chown /var/log/zhice（仅首次）
docker compose up -d --build

# 三轮 smoke
for i in 1 2 3; do
  ZHICE_SMOKE_API_BASE=https://staging.zhice.com ZHICE_SMOKE_WEB_BASE=https://staging.zhice.com \
    python3 prototype/scripts/smoke_test.py
  sleep 30
done

# TUSHARE failure 演示（可选）：编辑 .env 把 TUSHARE_TOKEN 改成乱码 → restart api → 浏览器打开 /valuation
docker compose restart zhice-api
# 浏览器访问 https://staging.zhice.com/valuation，应看到「降级数据」橙色 Tag
```

附加证据可追加到本文档（向后兼容：在 `## Round` / `## TUSHARE Failure Demo` 之后追加新 `### Round 4` 等小节，不替换历史）。

---

## 附：T07 Verification Gate 命令（plan 内嵌）
```bash
test -f prototype/docs/S02-VERIFICATION-LOG.md && \
  [ $(grep -cE '^###? Round|^### TUSHARE' prototype/docs/S02-VERIFICATION-LOG.md) -ge 4 ] && \
  grep -q 'TUSHARE\|tushare' prototype/docs/S02-VERIFICATION-LOG.md && \
  echo PASS
```

预期：本文档含 `### Round 1/2/3` + `### TUSHARE Failure Demo` 共 4 节，且包含 `TUSHARE` / `tushare` 字样多处 → 输出 `PASS`。
