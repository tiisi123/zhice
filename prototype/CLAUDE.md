# 智策 — AI投研与策略中枢

## 项目概况
A股 AI 投研平台，FastAPI 后端 + React 前端 + AI Agent 层。

## 技术栈
- 后端: Python 3.11+, FastAPI, Pydantic 2, APScheduler
- 前端: React 19, TypeScript 6, Vite 8, Ant Design 6, ECharts 6
- AI: OpenAI GPT-4o / Anthropic Claude, 多 Agent 架构
- 数据源: KPL(开盘啦，短线主源), TuShare, Eastmoney, ETF connector

## 目录结构
- packages/normalizers/ — 数据标准化（枚举、股票代码、日期、字段转换）
- packages/shared/types.py — Pydantic 公共模型
- packages/connectors/ — 数据源连接器（KPL/TuShare/Eastmoney/ETF）
- packages/connectors/registry.py — 连接器单例注册
- packages/features/ — 特征工程（行情/主题/分析/估值/产业链/ETF/宏观）
- packages/backtest/ — 策略 DSL + 回测引擎 + 参数优化
- apps/api/ — FastAPI 应用（14 个路由模块）
- apps/ai/ — AI Agent（5 个 Agent + LLM 客户端 + 上下文构建 + 提示词模板）
- apps/web/ — React 前端（14 个页面）

## 开发规范
- 启动后端: cd zhice && python -m uvicorn apps.api.main:app --reload
- 启动前端: cd zhice/apps/web && npm run dev
- 连接器使用: 短线默认使用 KPL；不要把 XGT 重新作为短线默认源
- 添加新路由: 在 apps/api/routes/ 新建文件，在 main.py 注册
- 公共类型: 后端加到 packages/shared/types.py，前端同步更新 apps/web/src/api/types.ts

## 业务模块地图（按侧边栏对应）

每个模块可由一个独立窗口开发，包含完整的前端+后端+数据垂直切片。

### 短线/热点
| 模块 | 后端路由 | 前端页面 | 特征/数据 |
|------|---------|---------|----------|
| 收盘复盘 | routes/replay.py | pages/ReplayPage.tsx | features/market.py, features/theme.py |
| 盘中盯盘 | routes/intraday.py, routes/ws.py | pages/IntradayPage.tsx, api/useMarketWS.ts | ws_hub.py |
| 情绪周期 | routes/sentiment.py | pages/SentimentPage.tsx | features/market.py |
| 题材板块 | routes/theme.py | pages/ThemePage.tsx | — |
| 炸板案例库 | routes/analysis.py | pages/BrokenCasesPage.tsx | features/analysis.py |

### 成长/价值
| 模块 | 后端路由 | 前端页面 | 特征/数据 |
|------|---------|---------|----------|
| 景气度分析 | routes/growth.py | pages/GrowthPage.tsx | features/macro/ |
| ETF轮动 | routes/etf.py | pages/EtfRotationPage.tsx | features/etf/ |
| 价值/持仓 | (用 /growth/portfolio) | pages/ValuePage.tsx | — |
| 估值分析 | routes/value.py | pages/ValuationPage.tsx | features/valuation.py |

### 工具
| 模块 | 后端路由 | 前端页面 | 特征/数据 |
|------|---------|---------|----------|
| 个股分析 | routes/stock.py | pages/StockPage.tsx | — |
| 产业链图谱 | routes/chain.py | pages/ChainPage.tsx | features/chain/ |
| 策略回测 | routes/strategy.py | pages/StrategyPage.tsx | packages/backtest/ |
| 高级策略 | routes/advanced_strategy.py | pages/AdvancedStrategyPage.tsx | packages/backtest/ |
| 报告存档 | routes/analysis.py | pages/ReportArchivePage.tsx | — |

### 横切模块
| 模块 | 后端路由 | 前端组件 | 数据 |
|------|---------|---------|------|
| AI Copilot | routes/ai.py | components/AICopilot.tsx | apps/ai/ 全部 |

## 并行开发约定（3 窗口按模块）
- 每个窗口开发一个业务模块，按上表找到该模块的全部文件
- 不同窗口不要修改同一个文件
- 公共基础设施（packages/shared/types.py、packages/connectors/registry.py）如需修改，先沟通

## 分支规范
- main: 稳定分支
- feat/模块名: 如 feat/sentiment、feat/growth、feat/stock
- fix/xxx: 修复分支
