import { useEffect, useState } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import { Card, Col, Row, Tabs, Tag, Spin, Empty } from 'antd'
import {
  AppstoreOutlined, EyeOutlined, ExperimentOutlined, StockOutlined,
  FileTextOutlined, RobotOutlined, BellOutlined, ThunderboltOutlined,
} from '@ant-design/icons'
import { fetchApi } from '../api/client'
import { AskAIChip } from '../components/smart'

export default function ToolsHomePage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const tab = searchParams.get('tab') || 'todo'
  const [alerts, setAlerts] = useState<any[]>([])
  const [reports, setReports] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      fetchApi<{ alerts: any[] }>('/watchlist/check-alerts').catch(() => ({ alerts: [] })),
      fetchApi<{ items: any[] }>('/analysis/report-archive?limit=5').catch(() => ({ items: [] })),
    ]).then(([a, r]) => {
      setAlerts(a.alerts || [])
      setReports(r.items || [])
    }).finally(() => setLoading(false))
  }, [])

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '120px auto' }} />

  return (
    <div>
      <h2 style={{ margin: '0 0 12px', display: 'flex', alignItems: 'center', gap: 8 }}>
        <AppstoreOutlined style={{ color: '#722ed1' }} /> 投研工具台
        <span style={{ fontSize: 13, color: '#999', fontWeight: 400 }}>· 今日待办与常用入口</span>
      </h2>

      {/* 今日摘要 */}
      <Card size="small" style={{ marginBottom: 16, borderLeft: '4px solid #722ed1' }} bodyStyle={{ padding: '12px 16px' }}>
        <Row gutter={16}>
          <Col xs={12} md={6}>
            <div style={{ fontSize: 12, color: '#999' }}>研究池异动</div>
            <div style={{ fontSize: 16, fontWeight: 700, color: alerts.length > 0 ? '#f5222d' : '#999' }}>
              {alerts.length} 条
            </div>
          </Col>
          <Col xs={12} md={6}>
            <div style={{ fontSize: 12, color: '#999' }}>最近报告</div>
            <div style={{ fontSize: 16, fontWeight: 700 }}>{reports.length} 篇</div>
          </Col>
          <Col xs={24} md={12}>
            <AskAIChip prompt="总结我今天应该关注的投研任务：研究池有哪些标的触发异动，是否需要调整观察状态。" label="AI 今日建议" />
          </Col>
        </Row>
      </Card>

      <Tabs
        activeKey={tab}
        onChange={(k) => setSearchParams({ tab: k }, { replace: true })}
        type="card" size="small"
        items={[
          {
            key: 'todo',
            label: <span><ThunderboltOutlined /> 今日待办</span>,
            children: (
              <Row gutter={16}>
                <Col xs={24} lg={12}>
                  <Card size="small" title={<span><BellOutlined /> 研究池异动</span>}>
                    {alerts.length === 0 ? <Empty description="暂无异动" image={Empty.PRESENTED_IMAGE_SIMPLE} /> :
                      alerts.slice(0, 8).map((a: any, i: number) => (
                        <div key={i} style={{ padding: '6px 0', borderBottom: '1px solid #f5f5f5', fontSize: 13 }}>
                          <Link to={`/stock/${a.code}`} style={{ fontWeight: 600 }}>{a.name || a.code}</Link>
                          <Tag color="orange" style={{ marginLeft: 8 }}>{a.kind}</Tag>
                          <span style={{ color: '#666', marginLeft: 4 }}>{a.message}</span>
                        </div>
                      ))
                    }
                  </Card>
                </Col>
                <Col xs={24} lg={12}>
                  <Card size="small" title={<span><FileTextOutlined /> 最近报告</span>}>
                    {reports.length === 0 ? <Empty description="暂无报告" image={Empty.PRESENTED_IMAGE_SIMPLE} /> :
                      reports.map((r: any) => (
                        <div key={r.id} style={{ padding: '6px 0', borderBottom: '1px solid #f5f5f5', fontSize: 13 }}>
                          <span style={{ color: '#999', marginRight: 8 }}>{r.trade_date}</span>
                          <span style={{ fontWeight: 500 }}>{r.title}</span>
                        </div>
                      ))
                    }
                  </Card>
                </Col>
              </Row>
            ),
          },
          {
            key: 'alerts',
            label: <span><BellOutlined /> 研究池异动</span>,
            children: <Card size="small"><div style={{ color: '#666' }}>研究池异动历史（完整列表见<Link to="/research-pool?tab=alerts">研究池</Link>）</div></Card>,
          },
          {
            key: 'strategy',
            label: <span><ExperimentOutlined /> 策略待验证</span>,
            children: <Card size="small"><div style={{ color: '#666' }}>策略回测待查看（详见<Link to="/strategy-workshop">策略工坊</Link>）</div></Card>,
          },
          {
            key: 'reports',
            label: <span><FileTextOutlined /> 最近报告</span>,
            children: <Card size="small"><div style={{ color: '#666' }}>研究报告归档（详见<Link to="/my-workspace?tab=archive">研究档案</Link>）</div></Card>,
          },
          {
            key: 'shortcuts',
            label: <span><AppstoreOutlined /> 常用工具</span>,
            children: (
              <Row gutter={[12, 12]}>
                {[
                  { label: '标的研究', link: '/stock-research', icon: <StockOutlined />, color: '#1677ff' },
                  { label: '研究池', link: '/research-pool', icon: <EyeOutlined />, color: '#22c55e' },
                  { label: '策略工坊', link: '/strategy-workshop', icon: <ExperimentOutlined />, color: '#722ed1' },
                  { label: '我的工作台', link: '/my-workspace', icon: <AppstoreOutlined />, color: '#f97316' },
                  { label: '会员', link: '/membership', icon: <RobotOutlined />, color: '#faad14' },
                ].map(item => (
                  <Col xs={12} md={4} key={item.label}>
                    <Link to={item.link}>
                      <Card size="small" hoverable bodyStyle={{ padding: 16, textAlign: 'center' }}
                        style={{ borderTop: `3px solid ${item.color}` }}>
                        <div style={{ fontSize: 24, color: item.color, marginBottom: 4 }}>{item.icon}</div>
                        <div style={{ fontWeight: 600 }}>{item.label}</div>
                      </Card>
                    </Link>
                  </Col>
                ))}
              </Row>
            ),
          },
        ]}
      />
    </div>
  )
}
