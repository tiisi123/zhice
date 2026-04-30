# 前端开发指南

## 技术栈
React 19 + TypeScript + Vite + Ant Design 6 + ECharts 6

## 关键约定
- API 调用: 使用 src/api/client.ts 的 fetchApi / postApi / deleteApi
- 类型定义: 集中在 src/api/types.ts，与后端 packages/shared/types.py 对应
- 新页面: 在 src/pages/ 创建，在 App.tsx 注册路由，在 AppLayout.tsx 加菜单项
- 状态管理: 纯 React hooks，不用全局状态库
- 图表: ECharts，遵循 chartRef + useEffect init/dispose 模式
- WebSocket: 仅 IntradayPage 使用 useMarketWS hook
- 颜色: 涨红 #f5222d，跌绿 #52c41a
- 错误提示: 使用 antd 的 message.error()

## 页面 → 后端路由对应（按模块开发时需同步修改）
- ReplayPage → /api/market/summary,ladder,sectors,capital-flow,rotation
- IntradayPage → /api/market/limit-up,broken,hot-stocks,anomaly + WebSocket
- SentimentPage → /api/market/sentiment-history
- ThemePage → /api/theme/*
- BrokenCasesPage → /api/analysis/broken-cases
- GrowthPage → /api/growth/*
- EtfRotationPage → /api/etf/rotation/dashboard
- ValuePage → /api/growth/portfolio
- ValuationPage → /api/value/financial,expectations,dcf,forecast,screen
- StockPage → /api/stock/{code} + /api/ai/stock-insight/{code}
- ChainPage → /api/chain/*
- StrategyPage → /api/strategy/*
- AdvancedStrategyPage → /api/advanced-strategy/*
- ReportArchivePage → /api/analysis/report-archive

## 公共文件（多模块共用，修改需谨慎）
- src/api/client.ts — HTTP 客户端
- src/api/types.ts — 共享 TypeScript 接口（新增类型加在末尾）
- src/App.tsx — 路由注册
- src/layouts/AppLayout.tsx — 侧边栏菜单
- src/components/AICopilot.tsx — AI 助手抽屉
