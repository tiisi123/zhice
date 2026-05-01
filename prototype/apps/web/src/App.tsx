import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import AppLayout from './layouts/AppLayout'
import AuthGuard from './components/AuthGuard'
import LoginPage from './pages/LoginPage'
import { Result, Button, Spin } from 'antd'

// 路由级代码分割：减小首屏 bundle
const IntradayPage = lazy(() => import('./pages/IntradayPageV2'))
const IntradayPageLegacy = lazy(() => import('./pages/IntradayPage'))
const ReplayPage = lazy(() => import('./pages/ReplayPageV2'))
const ReplayPageLegacy = lazy(() => import('./pages/ReplayPage'))
const StockPage = lazy(() => import('./pages/StockPage'))
const ThemePage = lazy(() => import('./pages/ThemePage'))
const SentimentPage = lazy(() => import('./pages/SentimentPageV2'))
const SentimentPageLegacy = lazy(() => import('./pages/SentimentPage'))
const StyleOnboardingPage = lazy(() => import('./pages/StyleOnboardingPage'))
const SettingsPage = lazy(() => import('./pages/SettingsPage'))
const FeatureMapPage = lazy(() => import('./pages/FeatureMapPage'))
const AdminPage = lazy(() => import('./pages/AdminPage'))
const ThemeWorkshopPage = lazy(() => import('./pages/ThemeWorkshopPage'))
const VerificationPage = lazy(() => import('./pages/VerificationPage'))
const GrowthValueOverviewPage = lazy(() => import('./pages/GrowthValueOverviewPage'))
const GrowthWorkshopPage = lazy(() => import('./pages/GrowthWorkshopPage'))
const ValueWorkshopPage = lazy(() => import('./pages/ValueWorkshopPage'))
const ToolsHomePage = lazy(() => import('./pages/ToolsHomePage'))
const StockResearchPage = lazy(() => import('./pages/StockResearchPage'))
const ResearchPoolPage = lazy(() => import('./pages/ResearchPoolPage'))
const StrategyWorkshopPage = lazy(() => import('./pages/StrategyWorkshopPage'))
const MyWorkspacePage = lazy(() => import('./pages/MyWorkspacePage'))
const MembershipPage = lazy(() => import('./pages/MembershipPage'))
const CheckoutPage = lazy(() => import('./pages/CheckoutPage'))
// M001/S01/T06: dev-only demo of DataStatusBadge; S02 will消费同一组件
const DemoBadgePage = lazy(() => import('./pages/DemoBadgePage'))

function NotFound() {
  return (
    <Result
      status="404"
      title="404"
      subTitle="页面不存在"
      extra={<Button type="primary" href="/">返回首页</Button>}
    />
  )
}

const PageFallback = (
  <div style={{ padding: 48, textAlign: 'center' }}>
    <Spin size="large" />
  </div>
)

function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={PageFallback}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        {/* M001/S01/T06: DataStatusBadge 4 态手测页（dev only，AuthGuard 之外）；
            S02 将由所有数据卡片统一消费 components/DataStatusBadge */}
        {import.meta.env.DEV && (
          <Route path="/dev/data-status-badge" element={<DemoBadgePage />} />
        )}
        <Route element={<AuthGuard><AppLayout /></AuthGuard>}>
          <Route path="/" element={<Navigate to="/replay" replace />} />
          <Route path="/intraday" element={<IntradayPage />} />
          <Route path="/intraday-legacy" element={<IntradayPageLegacy />} />
          <Route path="/replay" element={<ReplayPage />} />
          <Route path="/replay-legacy" element={<ReplayPageLegacy />} />
          <Route path="/sentiment" element={<Navigate to="/replay" replace />} />
          <Route path="/sentiment-legacy" element={<SentimentPageLegacy />} />
          <Route path="/sentiment-page" element={<SentimentPage />} />
          <Route path="/stock/:code" element={<StockPage />} />
          <Route path="/theme" element={<ThemePage />} />
          <Route path="/theme/:id" element={<ThemePage />} />
          {/* 新工具工作台 */}
          <Route path="/tools-home" element={<ToolsHomePage />} />
          <Route path="/stock-research" element={<StockResearchPage />} />
          <Route path="/research-pool" element={<ResearchPoolPage />} />
          <Route path="/strategy-workshop" element={<StrategyWorkshopPage />} />
          <Route path="/my-workspace" element={<MyWorkspacePage />} />
          <Route path="/membership" element={<Navigate to="/account/membership" replace />} />
          <Route path="/account/membership" element={<MembershipPage />} />
          <Route path="/account/checkout" element={<CheckoutPage />} />
          {/* 旧工具 URL 重定向 */}
          <Route path="/stock" element={<Navigate to="/stock-research?tab=diagnosis" replace />} />
          <Route path="/chain" element={<Navigate to="/stock-research?tab=chain" replace />} />
          <Route path="/strategy" element={<Navigate to="/strategy-workshop?tab=backtest" replace />} />
          <Route path="/strategy-builder" element={<Navigate to="/strategy-workshop?tab=builder" replace />} />
          <Route path="/advanced-strategy" element={<Navigate to="/strategy-workshop?tab=advanced" replace />} />
          <Route path="/recommend" element={<Navigate to="/strategy-workshop?tab=recommend" replace />} />
          <Route path="/lab" element={<Navigate to="/strategy-workshop?tab=lab" replace />} />
          <Route path="/dashboard" element={<Navigate to="/my-workspace?tab=dashboard" replace />} />
          <Route path="/report-archive" element={<Navigate to="/my-workspace?tab=archive" replace />} />
          <Route path="/vip" element={<Navigate to="/account/membership" replace />} />
          <Route path="/watchlist" element={<Navigate to="/research-pool" replace />} />
          <Route path="/broken-cases" element={<Navigate to="/verification?tab=broken" replace />} />
          <Route path="/gv-overview" element={<GrowthValueOverviewPage />} />
          <Route path="/growth-workshop" element={<GrowthWorkshopPage />} />
          <Route path="/value-workshop" element={<ValueWorkshopPage />} />
          <Route path="/growth" element={<Navigate to="/growth-workshop?tab=prosperity" replace />} />
          <Route path="/prosperity" element={<Navigate to="/growth-workshop?tab=prosperity" replace />} />
          <Route path="/etf-rotation" element={<Navigate to="/growth-workshop?tab=etf" replace />} />
          <Route path="/value" element={<Navigate to="/value-workshop?tab=portfolio" replace />} />
          <Route path="/valuation" element={<Navigate to="/value-workshop?tab=valuation" replace />} />
          <Route path="/finance-compare" element={<Navigate to="/value-workshop?tab=compare" replace />} />
          <Route path="/finance-report" element={<Navigate to="/value-workshop?tab=finance" replace />} />
          <Route path="/research" element={<Navigate to="/value-workshop?tab=research" replace />} />
          <Route path="/longhu" element={<Navigate to="/verification?tab=longhu" replace />} />
          <Route path="/rotation" element={<Navigate to="/theme-workshop?tab=rotation" replace />} />
          <Route path="/onboarding" element={<StyleOnboardingPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/admin" element={<AdminPage />} />
          <Route path="/feature-map" element={<FeatureMapPage />} />
          <Route path="/hot-events" element={<Navigate to="/theme-workshop?tab=events" replace />} />
          <Route path="/theme-workshop" element={<ThemeWorkshopPage />} />
          <Route path="/verification" element={<VerificationPage />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
      </Suspense>
    </BrowserRouter>
  )
}

export default App
