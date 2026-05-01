import { lazy, Suspense } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { Card, Tabs, Spin, Row, Col, Button } from 'antd'
import { CrownOutlined, CheckOutlined, RocketOutlined, StarOutlined, UnorderedListOutlined } from '@ant-design/icons'

const VipPage = lazy(() => import('./VipPage'))
const fallback = <div style={{ padding: 48, textAlign: 'center' }}><Spin size="large" /></div>

const TASK_VALUES = [
  { level: '基础版', color: '#999', plan: '', desc: '我能快速看懂一个标的', tasks: ['个股 AI 结论', '风险提示', '基础研究池', '限次 AI 对话'] },
  { level: '标准版', color: '#1677ff', plan: 'standard_month', desc: '我能完成一次完整投研', tasks: ['标的研究 + 产业链', '研究池异动提醒', 'AI 研究摘要', '报告归档', '短线/成长/价值工作台'] },
  { level: '专业版', color: '#faad14', plan: 'pro_month', desc: '我能验证策略并沉淀投研体系', tasks: ['策略工坊全功能', '参数优化', '专业模板看板', '投委会 AI 备忘录', '深度报告库', '盘中实时推送'] },
]

export default function MembershipPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const tab = searchParams.get('tab') || 'value'

  return (
    <div>
      <h2 style={{ margin: '0 0 12px', display: 'flex', alignItems: 'center', gap: 8 }}>
        <CrownOutlined style={{ color: '#faad14' }} /> 会员
        <span style={{ fontSize: 13, color: '#999', fontWeight: 400 }}>· 按任务价值解锁投研能力</span>
      </h2>
      <Tabs
        activeKey={tab}
        onChange={(k) => setSearchParams({ tab: k }, { replace: true })}
        type="card" size="small"
        items={[
          {
            key: 'value',
            label: <span><RocketOutlined /> 任务价值</span>,
            children: (
              <Row gutter={16}>
                {TASK_VALUES.map(tv => (
                  <Col xs={24} md={8} key={tv.level}>
                    <Card size="small" title={<span style={{ color: tv.color, fontWeight: 700 }}>{tv.level}</span>}
                      style={{ height: '100%', borderTop: `3px solid ${tv.color}` }}>
                      <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>{tv.desc}</div>
                      {tv.tasks.map(t => (
                        <div key={t} style={{ margin: '6px 0' }}>
                          <CheckOutlined style={{ color: '#52c41a', marginRight: 8 }} />{t}
                        </div>
                      ))}
                      {tv.plan && (
                        <Button type="primary" block style={{ marginTop: 16 }}
                          onClick={() => navigate(`/account/checkout?plan=${tv.plan}`)}>
                          升级套餐
                        </Button>
                      )}
                    </Card>
                  </Col>
                ))}
              </Row>
            ),
          },
          { key: 'basic', label: <span><StarOutlined /> 基础版</span>, children: <Suspense fallback={fallback}><VipPage /></Suspense> },
          { key: 'standard', label: <span><StarOutlined /> 标准版</span>, children: <Suspense fallback={fallback}><VipPage /></Suspense> },
          { key: 'pro', label: <span><StarOutlined /> 专业版</span>, children: <Suspense fallback={fallback}><VipPage /></Suspense> },
          { key: 'compare', label: <span><UnorderedListOutlined /> 权益对比</span>, children: <Suspense fallback={fallback}><VipPage /></Suspense> },
        ]}
      />
    </div>
  )
}
