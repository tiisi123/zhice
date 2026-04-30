# 后端 API 开发指南

## 架构
FastAPI 应用，14 个路由模块，通过 main.py include_router 注册。

## 关键约定
- 连接器: 短线默认使用 `get_kpl()`；不要把 XGT 重新作为短线默认源
- 配置: 所有环境变量通过 config.py 的 Settings 类读取，不直接读 os.environ
- 错误处理: 用 HTTPException，格式 "获取XXX失败: {detail}"
- 公共模型: packages/shared/types.py 定义 Pydantic 模型
- 新路由: 在 routes/ 新建文件，在 main.py 注册 router

## 路由文件 → 业务模块对应
- routes/replay.py → 收盘复盘 (prefix: /api/market)
- routes/intraday.py → 盘中盯盘 (prefix: /api/market)
- routes/sentiment.py → 情绪周期 (prefix: /api/market)
- routes/theme.py → 题材板块 (prefix: /api/theme)
- routes/analysis.py → 炸板案例库 + 报告存档 (prefix: /api/analysis)
- routes/growth.py → 景气度分析 + 价值/持仓 (prefix: /api/growth)
- routes/etf.py → ETF轮动 (prefix: /api/etf)
- routes/value.py → 估值分析 (prefix: /api/value)
- routes/stock.py → 个股分析 (prefix: /api/stock)
- routes/chain.py → 产业链图谱 (prefix: /api/chain)
- routes/strategy.py → 策略回测 (prefix: /api/strategy)
- routes/advanced_strategy.py → 高级策略 (prefix: /api/advanced-strategy)
- routes/ai.py → AI Copilot (prefix: /api/ai)
- routes/ws.py → WebSocket 推送 (prefix: /api)

## 公共基础设施（跨模块共用）
- config.py — Settings（读 .env）
- main.py — router 注册（新增模块时修改）
- scheduler.py — APScheduler 定时任务
- ws_hub.py — WebSocket 消息推送中心
