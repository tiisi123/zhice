# AI Agent & 数据层开发指南

## 职责范围
- apps/ai/ — Agent 类、LLM 客户端、上下文构建器、提示词模板
- packages/features/ — 特征工程函数（被各业务模块的路由调用）
- packages/connectors/ — 数据源连接器
- packages/backtest/ — 回测引擎

## 关键约定
- LLM 客户端: apps/ai/agents/llm_client.py，支持 OpenAI -> Anthropic -> mock 三级降级
- 新 Agent: 继承同目录模式，在 agents.py 中添加类
- 新连接器: 在 packages/connectors/ 下新建目录，注册到 registry.py
- 特征函数: 纯函数，输入 list[dict]，输出标准化结果
- 回测: StrategyDSL (Pydantic) -> BacktestEngine.run() -> BacktestResult

## 哪些业务模块依赖 AI/数据层
- 收盘复盘 → MarketReplayAgent + features/market.py + features/theme.py
- 盘中盯盘 → (直接用 connectors，不经过 features)
- 情绪周期 → features/market.py (calc_sentiment_level)
- 炸板案例库 → features/analysis.py
- 景气度分析 → features/macro/
- ETF轮动 → features/etf/rotation.py
- 估值分析 → features/valuation.py
- 产业链图谱 → features/chain/data.py
- 策略回测 → packages/backtest/
- 个股分析 → StockInsightAgent
- AI Copilot → 全部 Agent

## 目录结构
- agents/agents.py — 5 个 Agent 类
- agents/llm_client.py — LLMClient 单例
- context_builders/market_context.py — 上下文格式化函数
- prompts/templates.py — 5 个 prompt 模板
