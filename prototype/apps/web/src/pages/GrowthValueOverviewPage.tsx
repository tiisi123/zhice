import { useEffect, useState } from 'react'
import { Alert, Card, Col, Row, Spin, Tag, Space, Button, Tabs } from 'antd'
import {
  DashboardOutlined, RiseOutlined, FundOutlined, RobotOutlined,
  ArrowUpOutlined, ArrowDownOutlined, MinusOutlined,
} from '@ant-design/icons'
import { Link } from 'react-router-dom'
import { fetchApi } from '../api/client'
import { askAI } from '../api/copilot'
import AIDisclaimer from '../components/AIDisclaimer'
import AIBadge from '../components/AIBadge'
import { AskAIChip } from '../components/smart'
import type { AnyData } from '../api/types'

const DIR_ICON: Record<string, React.ReactNode> = {
  up: <ArrowUpOutlined style={{ color: '#f5222d' }} />,
  down: <ArrowDownOutlined style={{ color: '#52c41a' }} />,
  flat: <MinusOutlined style={{ color: '#999' }} />,
}

const DEFAULT_VALUE_STOCKS = [
  { code: '600519', name: '贵州茅台', tag: '消费龙头' },
  { code: '601318', name: '中国平安', tag: '金融价值' },
  { code: '601088', name: '中国神华', tag: '红利资源' },
]
const DEFAULT_GROWTH_STOCKS = [
  { code: '300750', name: '宁德时代', tag: '新能源' },
  { code: '002371', name: '北方华创', tag: '半导体' },
  { code: '300308', name: '中际旭创', tag: 'AI算力' },
]

export default function GrowthValueOverviewPage() {
  const [macro, setMacro] = useState<AnyData[]>([])
  const [industries, setIndustries] = useState<AnyData[]>([])
  const [dataStatus, setDataStatus] = useState<AnyData[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    void Promise.all([
      fetchApi<{ indicators: AnyData[] }>('/growth/macro').catch(() => ({ indicators: [] })),
      fetchApi<{ industries: AnyData[] }>('/growth/prosperity').catch(() => ({ industries: [] })),
    ]).then(([m, p]) => {
      setMacro(m.indicators || [])
      setIndustries(p.industries || [])
      setDataStatus([
        { label: '宏观', source: (m as AnyData).source, data_status: (m as AnyData).data_status, mock: (m as AnyData).mock, message: (m as AnyData).message },
        { label: '景气', source: (p as AnyData).source, data_status: (p as AnyData).data_status, mock: (p as AnyData).mock, message: (p as AnyData).message },
      ])
    }).finally(() => setLoading(false))
  }, [])

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '120px auto' }} />

  const topGrowth = industries.filter(i => i.trend === 'up').sort((a, b) => (b.q4 || 0) - (a.q4 || 0)).slice(0, 3)
  const topValue = industries.filter(i => i.trend === 'down' || i.trend === 'flat').sort((a, b) => (a.q4 || 0) - (b.q4 || 0)).slice(0, 3)
  const pmi = macro.find(m => m.name === 'PMI')
  const cpi = macro.find(m => m.name === 'CPI')

  const styleLabel = (pmi?.value || 0) > 50.5 ? '成长修复' : (pmi?.value || 0) < 49.5 ? '价值防御' : '均衡配置'
  const styleColor = styleLabel === '成长修复' ? '#f5222d' : styleLabel === '价值防御' ? '#1677ff' : '#666'

  return (
    <div>
      <h2 style={{ margin: '0 0 16px', display: 'flex', alignItems: 'center', gap: 8 }}>
        <DashboardOutlined style={{ color: '#722ed1' }} /> 成长/价值 · 投研总览
      </h2>

      {dataStatus.some(s => s.mock || s.data_status === 'stale') && (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 12 }}
          message="当前总览包含样例或规则推演数据"
          description={dataStatus.map(s => `${s.label}: ${s.source || 'unknown'} / ${s.data_status || 'unknown'}${s.message ? `（${s.message}）` : ''}`).join('；')}
        />
      )}

      {/* 顶部结论条 */}
      <Card size="small" style={{ marginBottom: 16, borderLeft: `4px solid ${styleColor}` }} bodyStyle={{ padding: '12px 16px' }}>
        <Row gutter={16}>
          <Col xs={24} md={5}>
            <div style={{ fontSize: 12, color: '#999' }}>当前风格</div>
            <div style={{ fontSize: 16, fontWeight: 700, color: styleColor }}>{styleLabel}</div>
          </Col>
          <Col xs={24} md={5}>
            <div style={{ fontSize: 12, color: '#999' }}>景气方向</div>
            <div style={{ fontSize: 14, fontWeight: 600 }}>{topGrowth.map(i => i.industry).join('、') || '—'}</div>
          </Col>
          <Col xs={24} md={5}>
            <div style={{ fontSize: 12, color: '#999' }}>价值方向</div>
            <div style={{ fontSize: 14, fontWeight: 600 }}>{topValue.map(i => i.industry).join('、') || '红利、银行'}</div>
          </Col>
          <Col xs={24} md={4}>
            <div style={{ fontSize: 12, color: '#999' }}>PMI</div>
            <div style={{ fontSize: 14, fontWeight: 600 }}>
              {pmi ? `${pmi.value}` : '—'} {pmi && DIR_ICON[pmi.direction]}
            </div>
          </Col>
          <Col xs={24} md={5}>
            <div style={{ fontSize: 12, color: '#999' }}>CPI</div>
            <div style={{ fontSize: 14, fontWeight: 600 }}>
              {cpi ? `${cpi.value}%` : '—'} {cpi && DIR_ICON[cpi.direction]}
            </div>
          </Col>
        </Row>
      </Card>

      <Tabs
        size="small"
        type="line"
        style={{ marginBottom: 16 }}
        items={[
          { key: 'conclusion', label: '配置结论' },
          { key: 'health', label: '持仓健康' },
          { key: 'opportunity', label: '机会地图' },
          { key: 'valuation', label: '估值分位' },
          { key: 'revision', label: '预期修正' },
          { key: 'etf', label: 'ETF确认' },
        ]}
      />

      <Row gutter={16}>
        {/* 左：宏观指标 */}
        <Col xs={24} lg={8}>
          <Card size="small" title={<span><RiseOutlined /> 宏观环境</span>} style={{ marginBottom: 16 }}>
            {macro.length === 0 ? <div style={{ color: '#999' }}>暂无数据</div> : (
              macro.map(m => (
                <div key={m.name} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid #f5f5f5' }}>
                  <span style={{ fontWeight: 500 }}>{m.name}</span>
                  <Space size={8}>
                    <span style={{ fontWeight: 600 }}>{m.value}{m.unit}</span>
                    {DIR_ICON[m.direction]}
                    <span style={{ fontSize: 11, color: '#999' }}>前值 {m.prev}</span>
                  </Space>
                </div>
              ))
            )}
            {macro.some(m => m.data_source === 'mock') && (
              <Tag color="orange" style={{ marginTop: 8, fontSize: 11 }}>示例数据</Tag>
            )}
          </Card>
        </Col>

        {/* 中：行业景气 Top */}
        <Col xs={24} lg={8}>
          <Card size="small" title={<span><RiseOutlined style={{ color: '#f5222d' }} /> 景气上行行业</span>}
            extra={<Link to="/growth-workshop" style={{ fontSize: 12 }}>查看全部 →</Link>}
            style={{ marginBottom: 16 }}
          >
            {topGrowth.length === 0 ? <div style={{ color: '#999' }}>暂无</div> : topGrowth.map(i => (
              <div key={i.industry} style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid #f5f5f5' }}>
                <span style={{ fontWeight: 600 }}>{i.industry}</span>
                <Space>
                  <Tag color={i.level === 'high' ? 'red' : i.level === 'medium' ? 'orange' : 'default'}>
                    Q4 景气 {i.q4}
                  </Tag>
                  <Tag color="green">{i.trend === 'up' ? '上行' : '—'}</Tag>
                </Space>
              </div>
            ))}
          </Card>

          <Card size="small" title="成长候选" style={{ marginBottom: 16 }}>
            {DEFAULT_GROWTH_STOCKS.map(s => (
              <div key={s.code} style={{ padding: '6px 0', borderBottom: '1px solid #f5f5f5' }}>
                <Link to={`/stock/${s.code}`} style={{ fontWeight: 600 }}>{s.name}</Link>
                <Tag style={{ marginLeft: 8 }}>{s.tag}</Tag>
              </div>
            ))}
            <Link to="/growth-workshop" style={{ fontSize: 12, marginTop: 8, display: 'block' }}>进入成长景气 →</Link>
          </Card>
        </Col>

        {/* 右：价值候选 */}
        <Col xs={24} lg={8}>
          <Card size="small" title={<span><FundOutlined style={{ color: '#1677ff' }} /> 价值候选</span>}
            extra={<Link to="/value-workshop" style={{ fontSize: 12 }}>查看全部 →</Link>}
            style={{ marginBottom: 16 }}
          >
            {DEFAULT_VALUE_STOCKS.map(s => (
              <div key={s.code} style={{ padding: '8px 0', borderBottom: '1px solid #f5f5f5' }}>
                <Link to={`/stock/${s.code}`} style={{ fontWeight: 600 }}>{s.name}</Link>
                <Tag color="blue" style={{ marginLeft: 8 }}>{s.tag}</Tag>
              </div>
            ))}
          </Card>

          <Card size="small" title={<span><RobotOutlined /> AI 投委会备忘录</span>}>
            <Button type="primary" block icon={<RobotOutlined />}
              onClick={() => askAI(`作为 A 股投委会投研顾问，生成今日投委会决策备忘录。格式要求：一、核心结论；二、配置逻辑（宏观→行业→公司→估值）；三、关键证据（3-5条）；四、反向风险；五、跟踪指标；六、AI参考建议（加仓/持有/减仓/剔除/观察）；七、触发与失效条件；八、免责声明。当前宏观：PMI ${pmi?.value || '—'}，CPI ${cpi?.value || '—'}。景气上行行业：${topGrowth.map(i => i.industry).join('、')}。`)}
            >
              生成投委会备忘录
            </Button>
            <AskAIChip
              prompt="当前 A 股中长线应该配成长还是价值？从宏观流动性、行业景气、估值分位三个维度分析。"
              label="AI 风格判断"
            />
          </Card>
        </Col>
      </Row>

      {/* 6 板块快速导航 */}
      <Card size="small" title="板块导航" style={{ marginTop: 16 }}>
        <Row gutter={[12, 12]}>
          {[
            { label: '宏观灯塔', desc: '流动性与风格判断', link: '/growth-workshop?tab=workshop', color: '#722ed1' },
            { label: '景气热力', desc: '行业景气度排行', link: '/growth-workshop?tab=heatmap', color: '#f5222d' },
            { label: '拐点预警', desc: '景气转好/转弱行业', link: '/growth-workshop?tab=turning', color: '#f97316' },
            { label: '估值分位', desc: '公司估值贵不贵', link: '/value-workshop?tab=valuation', color: '#1677ff' },
            { label: '预期差', desc: '卖方预期上修下修', link: '/value-workshop?tab=expectation', color: '#22c55e' },
            { label: 'ETF 确认', desc: '资金是否确认方向', link: '/growth-workshop?tab=etf', color: '#8b5cf6' },
          ].map(item => (
            <Col xs={12} md={4} key={item.label}>
              <Link to={item.link}>
                <Card size="small" hoverable bodyStyle={{ padding: 10, textAlign: 'center' }}
                  style={{ borderTop: `3px solid ${item.color}` }}>
                  <div style={{ fontWeight: 600, fontSize: 14 }}>{item.label}</div>
                  <div style={{ fontSize: 11, color: '#999', marginTop: 2 }}>{item.desc}</div>
                </Card>
              </Link>
            </Col>
          ))}
        </Row>
      </Card>

      <AIBadge style={{ marginBottom: 8 }} />
      <AIDisclaimer variant="inline" />
    </div>
  )
}
