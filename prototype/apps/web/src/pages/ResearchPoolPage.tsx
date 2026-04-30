import { lazy, Suspense } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Tabs, Spin } from 'antd'
import { EyeOutlined, BellOutlined, AppstoreOutlined, FileTextOutlined, UnorderedListOutlined } from '@ant-design/icons'

const WatchlistPage = lazy(() => import('./WatchlistPage'))
const fallback = <div style={{ padding: 48, textAlign: 'center' }}><Spin size="large" /></div>

export default function ResearchPoolPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const tab = searchParams.get('tab') || 'pipeline'

  return (
    <div>
      <h2 style={{ margin: '0 0 12px', display: 'flex', alignItems: 'center', gap: 8 }}>
        <EyeOutlined style={{ color: '#22c55e' }} /> 研究池
        <span style={{ fontSize: 13, color: '#999', fontWeight: 400 }}>· 研究管线与异动提醒</span>
      </h2>
      <Tabs
        activeKey={tab}
        onChange={(k) => setSearchParams({ tab: k }, { replace: true })}
        type="card" size="small"
        items={[
          { key: 'pipeline', label: <span><EyeOutlined /> 管线视图</span>, children: <Suspense fallback={fallback}><WatchlistPage /></Suspense> },
          { key: 'alerts', label: <span><BellOutlined /> 异动提醒</span>, children: <Suspense fallback={fallback}><WatchlistPage /></Suspense> },
          { key: 'groups', label: <span><AppstoreOutlined /> 分组模板</span>, children: <Suspense fallback={fallback}><WatchlistPage /></Suspense> },
          { key: 'notes', label: <span><FileTextOutlined /> 跟踪笔记</span>, children: <Suspense fallback={fallback}><WatchlistPage /></Suspense> },
          { key: 'list', label: <span><UnorderedListOutlined /> 明细列表</span>, children: <Suspense fallback={fallback}><WatchlistPage /></Suspense> },
        ]}
      />
    </div>
  )
}
