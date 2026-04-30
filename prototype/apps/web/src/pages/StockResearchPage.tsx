import { lazy, Suspense } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Tabs, Spin } from 'antd'
import { StockOutlined, ThunderboltOutlined, FundOutlined, ApartmentOutlined, WarningOutlined, FileTextOutlined } from '@ant-design/icons'

const StockPage = lazy(() => import('./StockPage'))
const ChainPage = lazy(() => import('./ChainPage'))
const fallback = <div style={{ padding: 48, textAlign: 'center' }}><Spin size="large" /></div>

export default function StockResearchPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const tab = searchParams.get('tab') || 'diagnosis'

  return (
    <div>
      <h2 style={{ margin: '0 0 12px', display: 'flex', alignItems: 'center', gap: 8 }}>
        <StockOutlined style={{ color: '#1677ff' }} /> 标的研究
        <span style={{ fontSize: 13, color: '#999', fontWeight: 400 }}>· 综合个股研究卡</span>
      </h2>
      <Tabs
        activeKey={tab}
        onChange={(k) => setSearchParams({ tab: k }, { replace: true })}
        type="card" size="small"
        items={[
          { key: 'diagnosis', label: <span><StockOutlined /> 综合诊断</span>, children: <Suspense fallback={fallback}><StockPage /></Suspense> },
          { key: 'short', label: <span><ThunderboltOutlined /> 短线逻辑</span>, children: <Suspense fallback={fallback}><StockPage /></Suspense> },
          { key: 'fundamental', label: <span><FundOutlined /> 基本面</span>, children: <Suspense fallback={fallback}><StockPage /></Suspense> },
          { key: 'chain', label: <span><ApartmentOutlined /> 产业链</span>, children: <Suspense fallback={fallback}><ChainPage /></Suspense> },
          { key: 'risk', label: <span><WarningOutlined /> 风险证据</span>, children: <Suspense fallback={fallback}><StockPage /></Suspense> },
          { key: 'report', label: <span><FileTextOutlined /> 报告生成</span>, children: <Suspense fallback={fallback}><StockPage /></Suspense> },
        ]}
      />
    </div>
  )
}
