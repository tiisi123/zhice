import { lazy, Suspense } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Tabs, Spin, Alert } from 'antd'
import { ExperimentOutlined, BulbOutlined, BuildOutlined, ThunderboltOutlined, ControlOutlined, LineChartOutlined, FundOutlined } from '@ant-design/icons'
import AIBadge from '../components/AIBadge'

const RecommendPage = lazy(() => import('./RecommendPage'))
const StrategyBuilderPage = lazy(() => import('./StrategyBuilderPage'))
const StrategyPage = lazy(() => import('./StrategyPage'))
const AdvancedStrategyPage = lazy(() => import('./AdvancedStrategyPage'))
const LabPage = lazy(() => import('./LabPage'))
const BoardBacktestPanel = lazy(() => import('../components/BoardBacktestPanel'))
const fallback = <div style={{ padding: 48, textAlign: 'center' }}><Spin size="large" /></div>

export default function StrategyWorkshopPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const tab = searchParams.get('tab') || 'recommend'

  return (
    <div>
      <h2 style={{ margin: '0 0 12px', display: 'flex', alignItems: 'center', gap: 8 }}>
        <ExperimentOutlined style={{ color: '#722ed1' }} /> 策略工坊
        <span style={{ fontSize: 13, color: '#999', fontWeight: 400 }}>· 从想法到可验证策略</span>
      </h2>
      <AIBadge style={{ marginBottom: 8 }} />
      <Alert
        type="warning"
        showIcon
        style={{ marginBottom: 12 }}
        message="蒙特卡洛模拟提示"
        description="当前为蒙特卡洛模拟数据（非真实回测），结果仅供策略思路参考"
      />
      <Tabs
        activeKey={tab}
        onChange={(k) => setSearchParams({ tab: k }, { replace: true })}
        type="card" size="small"
        items={[
          { key: 'recommend', label: <span><BulbOutlined /> 推荐策略</span>, children: <Suspense fallback={fallback}><RecommendPage /></Suspense> },
          { key: 'builder', label: <span><BuildOutlined /> 策略搭建</span>, children: <Suspense fallback={fallback}><StrategyBuilderPage /></Suspense> },
          { key: 'backtest', label: <span><LineChartOutlined /> 回测体检</span>, children: <Suspense fallback={fallback}><StrategyPage /></Suspense> },
          { key: 'advanced', label: <span><ThunderboltOutlined /> 参数优化</span>, children: <Suspense fallback={fallback}><AdvancedStrategyPage /></Suspense> },
          { key: 'simulate', label: <span><LineChartOutlined /> 模拟组合</span>, children: <Suspense fallback={fallback}><AdvancedStrategyPage /></Suspense> },
          { key: 'board-backtest', label: <span><FundOutlined /> 打板回测</span>, children: <Suspense fallback={fallback}><BoardBacktestPanel /></Suspense> },
          { key: 'lab', label: <span><ControlOutlined /> 实验室</span>, children: <Suspense fallback={fallback}><LabPage /></Suspense> },
        ]}
      />
    </div>
  )
}
