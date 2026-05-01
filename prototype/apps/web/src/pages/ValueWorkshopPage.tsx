import { lazy, Suspense, useEffect, useRef, useState } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import { Alert, Card, Col, Row, Tag, Spin, Tabs, Space, Button, Statistic, Input, message } from 'antd'
import {
  FundOutlined, DollarOutlined, FileTextOutlined, BarChartOutlined,
  ReadOutlined, RobotOutlined, SafetyOutlined, SearchOutlined,
} from '@ant-design/icons'
import * as echarts from 'echarts'
import { fetchApi } from '../api/client'
import { askAI } from '../api/copilot'
import { AskAIChip } from '../components/smart'
import AIDisclaimer from '../components/AIDisclaimer'
import AIBadge from '../components/AIBadge'
import type { AnyData } from '../api/types'

const ValuePage = lazy(() => import('./ValuePage'))
const ValuationPage = lazy(() => import('./ValuationPage'))
const FinanceReportPage = lazy(() => import('./FinanceReportPage'))
const FinanceComparePage = lazy(() => import('./FinanceComparePage'))
const ResearchPage = lazy(() => import('./ResearchPage'))
const fallback = <div style={{ padding: 48, textAlign: 'center' }}><Spin size="large" /></div>

const DEFAULT_VALUE_STOCKS = [
  { code: '600519', name: '贵州茅台', tag: '消费龙头', industry: '白酒' },
  { code: '000858', name: '五粮液', tag: '消费龙头', industry: '白酒' },
  { code: '601318', name: '中国平安', tag: '金融保险', industry: '保险' },
  { code: '600036', name: '招商银行', tag: '银行质量', industry: '银行' },
  { code: '601088', name: '中国神华', tag: '红利/资源', industry: '煤炭' },
]

// ========== 公司质量雷达图 ==========
function QualityRadar({ code }: { code: string }) {
  const ref = useRef<HTMLDivElement>(null)
  const [data, setData] = useState<AnyData>(null)
  const [status, setStatus] = useState<AnyData>(null)

  useEffect(() => {
    if (!code) return
    fetchApi<AnyData>(`/value/financial/${code}`)
      .then((r) => {
        setData(r.data || null)
        setStatus({ source: r.source, data_status: r.data_status, mock: r.mock, message: r.message })
      })
      .catch(() => { setData(null); setStatus(null) })
  }, [code])

  useEffect(() => {
    if (!ref.current || !data) return
    const chart = echarts.init(ref.current)
    const dims = [
      { name: '营收增长', max: 50, val: Math.min(Math.abs(data.revenue_yoy || 0), 50) },
      { name: 'ROE', max: 40, val: Math.min(data.roe || 0, 40) },
      { name: '毛利率', max: 100, val: data.gross_margin || 0 },
      { name: '净利率', max: 60, val: Math.min(data.net_margin || 0, 60) },
      { name: 'PE合理度', max: 100, val: Math.max(100 - (data.pe_percentile || 50), 0) },
    ]
    chart.setOption({
      radar: {
        indicator: dims.map(d => ({ name: d.name, max: d.max })),
        radius: '65%',
      },
      series: [{
        type: 'radar',
        data: [{ value: dims.map(d => d.val), name: data.name || code }],
        areaStyle: { opacity: 0.2 },
        lineStyle: { width: 2 },
      }],
      tooltip: {},
    })
    const onResize = () => chart.resize()
    window.addEventListener('resize', onResize)
    return () => { window.removeEventListener('resize', onResize); chart.dispose() }
  }, [data, code])

  if (!data) return <Spin size="small" />

  return (
    <div>
      {status && (status.mock || status.data_status !== 'ok') && (
        <Alert
          type={status.mock ? 'warning' : 'info'}
          showIcon
          style={{ marginBottom: 8 }}
          message={`基本面数据：${status.source || 'unknown'} / ${status.data_status || 'unknown'}`}
          description={status.message || '该模块使用接口返回的数据状态生成图表。'}
        />
      )}
      <div ref={ref} style={{ width: '100%', height: 260 }} />
      <Row gutter={8} style={{ marginTop: 4 }}>
        <Col span={6}><Statistic title="PE" value={data.pe || 0} precision={1} valueStyle={{ fontSize: 14 }} /></Col>
        <Col span={6}><Statistic title="PB" value={data.pb || 0} precision={1} valueStyle={{ fontSize: 14 }} /></Col>
        <Col span={6}><Statistic title="ROE" value={data.roe || 0} suffix="%" precision={1} valueStyle={{ fontSize: 14 }} /></Col>
        <Col span={6}><Statistic title="毛利率" value={data.gross_margin || 0} suffix="%" precision={1} valueStyle={{ fontSize: 14 }} /></Col>
      </Row>
      {data.data_source === 'mock' && <Tag color="orange" style={{ marginTop: 8, fontSize: 11 }}>示例数据</Tag>}
    </div>
  )
}

// ========== 估值分位简版 ==========
function ValuationBrief({ code }: { code: string }) {
  const [data, setData] = useState<AnyData>(null)
  const [status, setStatus] = useState<AnyData>(null)

  useEffect(() => {
    if (!code) return
    fetchApi<AnyData>(`/value/financial/${code}`)
      .then((r) => {
        setData(r.data || null)
        setStatus({ source: r.source, data_status: r.data_status, mock: r.mock, message: r.message })
      }).catch(() => { setData(null); setStatus(null) })
  }, [code])

  if (!data) return <Spin size="small" />

  const pePct = data.pe_percentile || 50
  const pbPct = data.pb_percentile || 50
  const barColor = (pct: number) => pct > 70 ? '#ef4444' : pct > 40 ? '#fa8c16' : '#22c55e'
  const barLabel = (pct: number) => pct > 70 ? '偏贵' : pct > 40 ? '合理' : '偏低'

  return (
    <div>
      {status && (status.mock || status.data_status !== 'ok' || status.source === 'tushare') && (
        <Alert
          type={status.mock ? 'warning' : 'info'}
          showIcon
          style={{ marginBottom: 8 }}
          message={`估值数据：${status.source || 'unknown'} / ${status.data_status || 'unknown'}`}
          description={status.source === 'tushare'
            ? 'PE/PB 历史分位暂未接历史估值序列，当前为参考占位口径，不可作为真实历史分位结论。'
            : (status.message || 'PE/PB 分位当前依赖后端口径。')}
        />
      )}
      <div style={{ marginBottom: 12 }}>
        <div style={{ fontSize: 12, color: '#999', marginBottom: 4 }}>PE 历史分位</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ flex: 1, background: '#f0f0f0', borderRadius: 4, height: 12, position: 'relative' }}>
            <div style={{ width: `${pePct}%`, height: '100%', borderRadius: 4, background: barColor(pePct), transition: 'width 0.3s' }} />
          </div>
          <span style={{ fontWeight: 600, color: barColor(pePct), minWidth: 50 }}>{pePct}% {barLabel(pePct)}</span>
        </div>
      </div>
      <div>
        <div style={{ fontSize: 12, color: '#999', marginBottom: 4 }}>PB 历史分位</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ flex: 1, background: '#f0f0f0', borderRadius: 4, height: 12, position: 'relative' }}>
            <div style={{ width: `${pbPct}%`, height: '100%', borderRadius: 4, background: barColor(pbPct), transition: 'width 0.3s' }} />
          </div>
          <span style={{ fontWeight: 600, color: barColor(pbPct), minWidth: 50 }}>{pbPct}% {barLabel(pbPct)}</span>
        </div>
      </div>
      <AskAIChip
        prompt={`${data.name || code} 当前 PE ${data.pe?.toFixed(1) || '—'}（历史分位 ${pePct}%），PB ${data.pb?.toFixed(1) || '—'}（分位 ${pbPct}%），ROE ${data.roe?.toFixed(1) || '—'}%。判断当前估值是否合理，给出 AI 参考建议（加仓/持有/减仓/剔除/观察）。`}
        label="AI 估值诊断"
      />
    </div>
  )
}

// ========== 主组件 ==========
export default function ValueWorkshopPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const tab = searchParams.get('tab') || 'workshop'
  const [selectedCode, setSelectedCode] = useState('600519')
  const [inputCode, setInputCode] = useState('')

  const handleSearch = () => {
    const code = inputCode.trim()
    if (/^\d{6}$/.test(code)) {
      setSelectedCode(code)
    } else {
      message.warning('请输入 6 位股票代码')
    }
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <h2 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
          <FundOutlined style={{ color: '#1677ff' }} /> 价值基本面
          <span style={{ fontSize: 13, color: '#999', fontWeight: 400 }}>· 持仓诊断与公司研究</span>
        </h2>
        <Space>
          <Input
            value={inputCode}
            onChange={e => setInputCode(e.target.value)}
            onPressEnter={handleSearch}
            placeholder="股票代码"
            style={{ width: 130 }}
            prefix={<SearchOutlined />}
            maxLength={6}
          />
          <Button onClick={handleSearch}>查询</Button>
          <Button size="small" icon={<RobotOutlined />}
            onClick={() => askAI(`生成价值基本面备忘录。当前研究标的 ${selectedCode}。格式：一、核心结论；二、基本面质量；三、财报变化；四、估值与安全边际；五、预期差；六、反向风险；七、跟踪指标；八、AI参考建议（加仓/持有/减仓/剔除/观察）。`)}>
            AI 备忘录
          </Button>
        </Space>
      </div>

      <Tabs
        activeKey={tab}
        onChange={(k) => setSearchParams({ tab: k }, { replace: true })}
        type="card"
        items={[
          {
            key: 'workshop',
            label: <span><FundOutlined /> 持仓诊断</span>,
            children: (
              <>
                {/* 个股选择条 */}
                <Card size="small" style={{ marginBottom: 16 }} bodyStyle={{ padding: '8px 16px' }}>
                  <Space wrap>
                    {DEFAULT_VALUE_STOCKS.map(s => (
                      <Tag key={s.code}
                        color={s.code === selectedCode ? 'blue' : 'default'}
                        style={{ cursor: 'pointer', fontWeight: s.code === selectedCode ? 700 : 400 }}
                        onClick={() => setSelectedCode(s.code)}
                      >
                        {s.name}
                      </Tag>
                    ))}
                  </Space>
                </Card>

                <Row gutter={16} style={{ marginBottom: 16 }}>
                  {/* 左：公司质量雷达 */}
                  <Col xs={24} lg={12}>
                    <Card size="small" title={<span><SafetyOutlined /> 公司质量雷达</span>}>
                      <QualityRadar code={selectedCode} />
                    </Card>
                  </Col>
                  {/* 右：估值分位 */}
                  <Col xs={24} lg={12}>
                    <Card size="small" title={<span><DollarOutlined /> 估值分位</span>} style={{ marginBottom: 16 }}>
                      <ValuationBrief code={selectedCode} />
                    </Card>
                    <Card size="small" title="快速操作">
                      <Space wrap>
                        <Link to={`/stock/${selectedCode}`}><Button>个股详情</Button></Link>
                        <Button onClick={() => askAI(`${selectedCode} 的 DCF 估值分析：假设未来 10 年自由现金流增长率 10%、折现率 8%、永续增长率 3%，计算合理估值区间，判断当前价格是否有安全边际。`)}>
                          DCF 估值
                        </Button>
                        <Button onClick={() => askAI(`查看 ${selectedCode} 最新卖方一致预期，判断 EPS 是上修还是下修趋势，预期差是正还是负。`)}>
                          预期修正
                        </Button>
                      </Space>
                    </Card>
                  </Col>
                </Row>
              </>
            ),
          },
          {
            key: 'portfolio',
            label: <span><FundOutlined /> 个股画像</span>,
            children: <Suspense fallback={fallback}><ValuePage /></Suspense>,
          },
          {
            key: 'valuation',
            label: <span><DollarOutlined /> 估值分析</span>,
            children: <Suspense fallback={fallback}><ValuationPage /></Suspense>,
          },
          {
            key: 'finance',
            label: <span><FileTextOutlined /> 财报追踪</span>,
            children: <Suspense fallback={fallback}><FinanceReportPage /></Suspense>,
          },
          {
            key: 'compare',
            label: <span><BarChartOutlined /> 公司对比</span>,
            children: <Suspense fallback={fallback}><FinanceComparePage /></Suspense>,
          },
          {
            key: 'expectation',
            label: <span><BarChartOutlined /> 预期差</span>,
            children: (
              <Card size="small" title="卖方预期修正跟踪">
                <div style={{ padding: '16px 0', color: '#666', fontSize: 13 }}>
                  <p>跟踪卖方一致预期的上修/下修趋势，判断市场是否低估或高估公司变化。</p>
                  <Space wrap>
                    {DEFAULT_VALUE_STOCKS.map(s => (
                      <Button key={s.code} size="small"
                        onClick={() => askAI(`查看 ${s.name}(${s.code}) 最新卖方一致预期。近3个月 EPS 预期是上修还是下修？目标价中位数是多少？当前股价相对目标价有多少空间？给出预期差判断。`)}
                      >{s.name} 预期修正</Button>
                    ))}
                  </Space>
                </div>
                <AskAIChip
                  prompt={`对比以下标的的卖方预期修正方向：${DEFAULT_VALUE_STOCKS.map(s => s.name).join('、')}。哪些公司近期 EPS 预期在上修？哪些在下修？给出预期差最大的公司和投资机会判断。`}
                  label="AI 预期差总览"
                />
              </Card>
            ),
          },
          {
            key: 'research',
            label: <span><ReadOutlined /> 研究证据</span>,
            children: <Suspense fallback={fallback}><ResearchPage /></Suspense>,
          },
        ]}
      />
      <AIBadge style={{ marginBottom: 8 }} />
      <AIDisclaimer variant="inline" />
    </div>
  )
}
