import { lazy, Suspense } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Tabs, Spin } from 'antd'
import { AppstoreOutlined, FileTextOutlined, RobotOutlined, BarChartOutlined, SettingOutlined } from '@ant-design/icons'

const DashboardPage = lazy(() => import('./DashboardPage'))
const ReportArchivePage = lazy(() => import('./ReportArchivePage'))
const SettingsPage = lazy(() => import('./SettingsPage'))
const fallback = <div style={{ padding: 48, textAlign: 'center' }}><Spin size="large" /></div>

export default function MyWorkspacePage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const tab = searchParams.get('tab') || 'dashboard'

  return (
    <div>
      <h2 style={{ margin: '0 0 12px', display: 'flex', alignItems: 'center', gap: 8 }}>
        <AppstoreOutlined style={{ color: '#f97316' }} /> 我的工作台
        <span style={{ fontSize: 13, color: '#999', fontWeight: 400 }}>· 沉淀个人投研体系</span>
      </h2>
      <Tabs
        activeKey={tab}
        onChange={(k) => setSearchParams({ tab: k }, { replace: true })}
        type="card" size="small"
        items={[
          { key: 'dashboard', label: <span><AppstoreOutlined /> 模板看板</span>, children: <Suspense fallback={fallback}><DashboardPage /></Suspense> },
          { key: 'archive', label: <span><FileTextOutlined /> 研究档案</span>, children: <Suspense fallback={fallback}><ReportArchivePage /></Suspense> },
          { key: 'memo', label: <span><RobotOutlined /> 投委会备忘录</span>, children: <Suspense fallback={fallback}><ReportArchivePage /></Suspense> },
          { key: 'weekly', label: <span><BarChartOutlined /> 周总结</span>, children: <Suspense fallback={fallback}><ReportArchivePage /></Suspense> },
          { key: 'settings', label: <span><SettingOutlined /> 设置</span>, children: <Suspense fallback={fallback}><SettingsPage /></Suspense> },
        ]}
      />
    </div>
  )
}
