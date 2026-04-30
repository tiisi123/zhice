# 多 Agent 任务拆分与启动清单

## 启动原则

- 一次先并行 3 个 Agent，稳定后扩到 5 个。
- 一个 Agent 只处理一个 Issue。
- 每个 Issue 必须写清允许修改文件和禁止修改文件。
- Issue 必须说明角色、目标、验收标准、服务依赖检查和回滚方式。
- `apps/api/main.py`、`apps/web/src/App.tsx`、`apps/api/db.py` 等共享文件只允许架构整合角色修改。
- 每个 Agent 完成后必须跑 `python scripts/check_before_pr.py`，并汇报改动文件和风险。

## 给 Codex Agent 派 Issue

优先使用 `.github/ISSUE_TEMPLATE/agent_task.yml`。每张 Issue 只派给一个角色，标题建议使用：

```text
[Agent] <role>: <short goal>
```

Issue 必须包含：

- 任务目标：可验收、可回滚，不写开放式探索。
- 允许修改：列出精确文件或目录 glob，例如 `scripts/**`。
- 禁止修改：列出 `data/**`、`.env`、其他 Agent 所属路径和共享文件。
- 必读文档：至少包含 `AGENTS.md`、协作规范、评审清单；涉及接口或数据源时补充对应规范。
- 验收标准：列出必须运行的命令和人工验收点。
- 服务依赖：标明是否需要本地 API/Web 服务，是否可能触达实时行情源。

Agent 启动后先读 Issue 和必读文档，再确认当前 git 状态。发现禁止范围已有改动时，不要回滚，最终汇报中说明即可。

## 允许/禁止文件写法

允许修改建议尽量窄：

```text
.github/workflows/**
.github/ISSUE_TEMPLATE/**
docs/process/**
scripts/**
```

禁止修改必须覆盖高风险和其他 Agent 范围：

```text
apps/**
packages/**
data/**
.env
*.log
pyproject.toml
apps/web/package.json
apps/web/package-lock.json
```

如果任务必须修改共享文件，Issue 中要点名文件、说明原因，并指定 Architecture Integrator review。

可以用默认 PR 检查入口检查当前工作区是否越界：

```powershell
python scripts/check_before_pr.py `
  --allow ".github/**" `
  --allow "docs/process/**" `
  --allow "scripts/**" `
  --deny "apps/**" `
  --deny "packages/**" `
  --deny "data/**" `
  --deny ".env"
```

如果要按分支对比而不是检查当前工作区，可加 `--base origin/develop`。底层脚本是 `scripts/check_changed_paths.py`，只读取 git 状态，不修改文件。

## PR 前检查分层

每个 Agent 默认运行：

```powershell
python scripts/check_before_pr.py
```

涉及前端时运行：

```powershell
python scripts/check_before_pr.py --web
```

本地 API 已启动且任务涉及接口契约或实时数据源时运行：

```powershell
python scripts/check_before_pr.py --api --api-base http://127.0.0.1:8000
```

完整本地验收需要 API/Web 服务：

```powershell
python scripts/check_before_pr.py --api --web --smoke
```

默认 CI 只运行不依赖服务和 secret 的检查：`check_python_syntax.py`、Python import、`check_no_mock.py`、默认 `check_before_pr.py`、前端 build。前端 lint 通过 `python scripts/check_before_pr.py --lint` 在本地检查，待存量 lint 问题清理后再升级为默认 CI。`check_api_contract.py`、`check_realtime_sources.py` 和 `smoke_test.py` 属于本地或手动检查，不作为默认 PR CI。

默认 `check_before_pr.py` 会阻断 `data/**`、`.env`、`*.log`。如果 `data/zhice.db` 已被本地服务改动，不要提交、删除或回滚，由架构整合者统一处理。

## 建议第一批并行任务

### Agent 1：短线后端契约补强

角色：Shortline Backend

目标：

- 给短线核心 API 统一补齐 `trade_date`、`updated_at`。
- 确认 `source/data_status/mock` 对所有短线核心接口一致。
- 扩展 `scripts/check_api_contract.py` 覆盖更多短线接口。

允许修改：

```text
apps/api/routes/intraday.py
apps/api/routes/replay.py
apps/api/routes/analysis.py
apps/api/routes/longhu.py
scripts/check_api_contract.py
docs/短线作战接口映射清单.md
```

禁止修改：

```text
apps/web/**
data/**
.env
apps/api/db.py
apps/api/main.py
```

验收：

```text
python scripts/check_before_pr.py
python scripts/check_api_contract.py
```

### Agent 2：短线前端状态验收

角色：Shortline Frontend

目标：

- 检查短线页面 loading、empty、error 状态。
- 去掉重复头部和多余说明。
- 表格字段不显示 `undefined/null/NaN`。
- 页面不直接适配外部源字段。

允许修改：

```text
apps/web/src/pages/IntradayPageV2.tsx
apps/web/src/pages/ReplayPageV2.tsx
apps/web/src/pages/ThemeWorkshopPage.tsx
apps/web/src/pages/VerificationPage.tsx
apps/web/src/pages/BrokenCasesPage.tsx
apps/web/src/pages/LonghuPage.tsx
apps/web/src/api/useMarketWS.ts
```

禁止修改：

```text
apps/api/**
packages/**
data/**
.env
apps/web/src/App.tsx
apps/web/src/layouts/AppLayout.tsx
```

验收：

```text
python scripts/check_before_pr.py
cd apps/web
npm run build
```

### Agent 3：工程质量与 CI 草案

角色：Engineering Quality

目标：

- 增加 GitHub Actions 草案，跑基础检查。
- 更新流程文档，说明 Codex Agent 的 Issue/PR 使用方式。
- 不接入任何 secret，不做部署。

允许修改：

```text
.github/workflows/**
.github/ISSUE_TEMPLATE/**
.github/pull_request_template.md
docs/process/**
scripts/**
```

禁止修改：

```text
apps/**
packages/**
data/**
.env
```

验收：

```text
python scripts/check_before_pr.py
```

### Agent 4：成长价值真实数据清单

角色：Growth Value

目标：

- 梳理成长价值页面当前真实数据、规则推演、mock/待接入状态。
- 建立成长价值接口映射清单。
- 不做大规模功能改造。

允许修改：

```text
docs/成长价值产品改造方案.md
docs/process/**
apps/api/routes/growth.py
apps/api/routes/value.py
apps/api/routes/finance.py
apps/api/routes/etf.py
apps/web/src/pages/GrowthValueOverviewPage.tsx
apps/web/src/pages/GrowthWorkshopPage.tsx
apps/web/src/pages/ValueWorkshopPage.tsx
apps/web/src/pages/FinanceReportPage.tsx
apps/web/src/pages/EtfRotationPage.tsx
```

禁止修改：

```text
apps/api/routes/intraday.py
apps/api/routes/replay.py
packages/connectors/kpl/**
data/**
.env
```

验收：

```text
python scripts/check_before_pr.py
```

### Agent 5：用户与商业化风险清单

角色：User Commerce

目标：

- 梳理登录、会员、支付、研究池、报告归档的上线风险。
- 标记 mock 支付和权限边界。
- 提出最小上线闭环，不改支付真实接入。

允许修改：

```text
docs/process/**
DEPLOY.md
apps/api/routes/auth.py
apps/api/routes/payment.py
apps/api/routes/watchlist.py
apps/web/src/pages/LoginPage.tsx
apps/web/src/pages/MembershipPage.tsx
apps/web/src/pages/WatchlistPage.tsx
```

禁止修改：

```text
packages/connectors/kpl/**
apps/api/db.py
data/**
.env
```

验收：

```text
python scripts/check_before_pr.py
```

## Codex 任务提示词模板

```text
你是本仓库的 Codex Agent，角色是【填角色】。

请先阅读：
- AGENTS.md
- docs/process/01-协作规范.md
- docs/process/03-接口开发规范.md
- docs/process/07-代码评审清单.md

任务目标：
【填目标】

允许修改：
【填文件列表】

禁止修改：
【填文件列表】

验收标准：
【填验收标准】

要求：
- 不要修改禁止范围。
- 不要引入 mock 数据。
- 不要改 data/*.db 或 .env。
- 不要做无关重构。
- 完成后汇报改动文件、检查命令、结果和风险。
```

## 架构整合检查

所有 Agent PR 合并前，由架构整合角色统一检查：

```powershell
python scripts/check_before_pr.py --web
python scripts/check_no_mock.py
```

如果本地 API 已重启：

```powershell
python scripts/check_before_pr.py --api --api-base http://127.0.0.1:8000
```
