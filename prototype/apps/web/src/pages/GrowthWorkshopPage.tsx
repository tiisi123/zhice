import { lazy, Suspense, useEffect, useRef, useState } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import { Alert, Card, Col, Row, Tag, Spin, Tabs, Space, Button, Empty } from 'antd'
import {
  RiseOutlined, SwapOutlined, HeatMapOutlined, ArrowUpOutlined, ArrowDownOutlined,
  MinusOutlined, RobotOutlined, AimOutlined, ThunderboltOutlined,
} from '@ant-design/icons'
import * as echarts from 'echarts'
import { fetchApi } from '../api/client'
import { askAI } from '../api/copilot'
import { AskAIChip } from '../components/smart'
import AIDisclaimer from '../components/AIDisclaimer'
import AIBadge from '../components/AIBadge'
import MockBanner from '../components/MockBanner'
import type { AnyData, DataStatus } from '../api/types'
import { extractMeta } from '../api/useApiMeta'
import DataStatusBadge from '../components/DataStatusBadge'

const ProsperityPage = lazy(() => import('./ProsperityPage'))
const EtfRotationPage = lazy(() => import('./EtfRotationPage'))
const fallback = <div style={{ padding: 48, textAlign: 'center' }}><Spin size="large" /></div>

const DIR_ICON: Record<string, React.ReactNode> = {
  up: <ArrowUpOutlined style={{ color: '#f5222d' }} />,
  down: <ArrowDownOutlined style={{ color: '#52c41a' }} />,
  flat: <MinusOutlined style={{ color: '#999' }} />,
}

const DEFAULT_GROWTH_STOCKS = [
  { code: '300750', name: '宁德时代', tag: '新能源龙头' },
  { code: '688981', name: '中芯国际', tag: '半导体制造' },
  { code: '002371', name: '北方华创', tag: '半导体设备' },
  { code: '300308', name: '中际旭创', tag: 'AI算力/光模块' },
  { code: '600276', name: '恒瑞医药', tag: '创新药' },
]

// ========== 景气热力图（嵌入版）==========
function InlineHeatmap({ industries }: { industries: AnyData[] }) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!ref.current || !industries.length) return
    const chart = echarts.init(ref.current)
    const quarters = ['Q1', 'Q2', 'Q3', 'Q4']
    const names = industries.map(d => d.industry)
    const heatData: number[][] = []
    industries.forEach((d, yi) => {
      ;[d.q1, d.q2, d.q3, d.q4].forEach((v, xi) => { heatData.push([xi, yi, v]) })
    })
    chart.setOption({
      tooltip: { formatter: (p: AnyData) => `${names[p.value[1]]} ${quarters[p.value[0]]}: ${p.value[2]}` },
      grid: { left: 90, right: 50, top: 10, bottom: 50 },
      xAxis: { type: 'category', data: quarters },
      yAxis: { type: 'category', data: names, axisLabel: { fontSize: 11 } },
      visualMap: { min: 20, max: 100, calculable: true, orient: 'horizontal', left: 'center', bottom: 0, inRange: { color: ['#52c41a', '#faad14', '#f5222d'] } },
      series: [{ type: 'heatmap', data: heatData, label: { show: true, fontSize: 11 } }],
    })
    const onResize = () => chart.resize()
    window.addEventListener('resize', onResize)
    return () => { window.removeEventListener('resize', onResize); chart.dispose() }
  }, [industries])
  return <div ref={ref} style={{ width: '100%', height: Math.max(industries.length * 36 + 70, 300) }} />
}

// ========== 拐点雷达 ==========
function TurningPointRadar({ industries }: { industries: AnyData[] }) {
  const turning = industries.filter(d => {
    const q3 = d.q3 || 0, q4 = d.q4 || 0
    return (q4 - q3 >= 8 && d.trend === 'up') || (q3 - q4 >= 8 && d.trend === 'down')
  }).sort((a, b) => Math.abs((b.q4 || 0) - (b.q3 || 0)) - Math.abs((a.q4 || 0) - (a.q3 || 0)))

  if (turning.length === 0) return <Empty description="当前无明显拐点行业" image={Empty.PRESENTED_IMAGE_SIMPLE} />

  return (
    <div>
      {turning.map(d => {
        const delta = (d.q4 || 0) - (d.q3 || 0)
        const isUp = delta > 0
        return (
          <div key={d.industry} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 0', borderBottom: '1px solid #f5f5f5' }}>
            <Tag color={isUp ? 'red' : 'green'} style={{ fontWeight: 700, minWidth: 50, textAlign: 'center' }}>
              {isUp ? '↑ 转好' : '↓ 转弱'}
            </Tag>
            <span style={{ fontWeight: 600, flex: 1 }}>{d.industry}</span>
            <span style={{ fontSize: 12, color: '#666' }}>
              Q3 {d.q3} → Q4 {d.q4}
            </span>
            <span style={{ fontWeight: 700, color: isUp ? '#f5222d' : '#52c41a' }}>
              {isUp ? '+' : ''}{delta}
            </span>
          </div>
        )
      })}
      <AskAIChip
        prompt={`当前出现景气拐点的行业：${turning.map(d => `${d.industry}(Q3=${d.q3}→Q4=${d.q4})`).join('、')}。分析哪些拐点最可靠，哪些只是短期反弹，给出配置优先级。`}
        label="AI 解读拐点"
      />
    </div>
  )
}

// ========== 产业链传导 ==========
function SupplyChainTransmission() {
  const [src, setSrc] = useState('半导体')
  const [rotation, setRotation] = useState<AnyData>(null)
  const sources = ['半导体', 'AI/算力', '新能源车', '军工', '医药生物', '消费电子']

  useEffect(() => {
    fetchApi<AnyData>(`/growth/rotation?source=${encodeURIComponent(src)}`)
      .then(setRotation).catch(() => setRotation(null))
  }, [src])

  return (
    <Card size="small" title={<span><SwapOutlined style={{ color: '#722ed1' }} /> 产业链传导</span>}
      extra={
        <Space size={4} wrap>
          {sources.map(s => (
            <Tag key={s} color={s === src ? 'blue' : 'default'} style={{ cursor: 'pointer' }}
              onClick={() => setSrc(s)}>{s}</Tag>
          ))}
        </Space>
      }
    >
      {rotation?.targets?.length > 0 ? (
        rotation.targets.map((t: AnyData, i: number) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 0', borderBottom: '1px solid #f5f5f5' }}>
            <Tag color="blue">{src}</Tag>
            <span style={{ color: '#999' }}>→</span>
            <Tag color="orange">{t.target}</Tag>
            <span style={{ fontWeight: 700, color: t.probability >= 60 ? '#f5222d' : '#fa8c16' }}>{t.probability}%</span>
            <span style={{ fontSize: 12, color: '#999' }}>滞后 {t.lag_days} 天</span>
          </div>
        ))
      ) : <Empty description="暂无传导数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />}
      <AskAIChip
        prompt={`从【${src}】出发的产业链传导路径：${rotation?.targets?.map((t: AnyData) => `${t.target}(概率${t.probability}%,滞后${t.lag_days}天)`).join('→') || '暂无'}。分析传导逻辑和最佳介入时机。`}
        label="AI 传导分析"
      />
    </Card>
  )
}

// ========== 主组件 ==========
export default function GrowthWorkshopPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const tab = searchParams.get('tab') || 'workshop'
  const [macro, setMacro] = useState<AnyData[]>([])
  const [industries, setIndustries] = useState<AnyData[]>([])
  const [loading, setLoading] = useState(true)
  const [isMock, setIsMock] = useState(false)
  const [dataStatus, setDataStatus] = useState<AnyData[]>([])

  useEffect(() => {
    void (async () => {
      setLoading(true)
      void Promise.all([
        fetchApi<{ indicators: AnyData[] }>('/growth/macro').catch(() => ({ indicators: [] })),
        fetchApi<{ industries: AnyData[] }>('/growth/prosperity').catch(() => ({ industries: [] })),
      ]).then(([m, p]) => {
        setMacro(m.indicators || [])
        setIndustries(p.industries || [])
        setIsMock(Boolean((m as AnyData).mock || (p as AnyData).mock || m.indicators?.some((i: AnyData) => i.data_source === 'mock')))
        setDataStatus([
          { label: '宏观', ...extractMeta(m) },
          { label: '景气', ...extractMeta(p) },
        ])
      }).finally(() => setLoading(false))
    })()
  }, [])

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '120px auto' }} />

  const topUp = industries.filter(i => i.trend === 'up').sort((a, b) => (b.q4 || 0) - (a.q4 || 0))
  const pmi = macro.find(m => m.name === 'PMI')
  const flowSupport = (pmi?.value || 0) > 50 ? '流动性支持成长' : (pmi?.value || 0) < 49 ? '流动性偏紧，成长承压' : '流动性中性'

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <h2 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
          <RiseOutlined style={{ color: '#f5222d' }} /> 成长景气
          <span style={{ fontSize: 13, color: '#999', fontWeight: 400 }}>· 行业配置与景气拐点</span>
        </h2>
        <Button size="small" icon={<RobotOutlined />}
          onClick={() => askAI(`生成成长配置备忘录。格式：一、成长风格结论；二、景气上行行业（${topUp.slice(0,3).map(i=>i.industry).join('、')}）；三、拐点行业；四、ETF/资金确认；五、候选公司；六、反向风险；七、AI参考建议。当前PMI ${pmi?.value || '—'}，${flowSupport}。`)}>
          AI 成长备忘录
        </Button>
      </div>

      <MockBanner show={isMock} />
      {dataStatus.length > 0 && (
        <Alert
          type={isMock ? 'warning' : 'info'}
          showIcon
          style={{ marginBottom: 12 }}
          message="数据状态"
          description={
            <Space size={[8, 8]} wrap>
              {dataStatus.map(s => (
                <Space key={s.label} size={6}>
                  <span>{s.label}</span>
                  <DataStatusBadge status={s.data_status as DataStatus} source={s.source} mock={s.mock} size="small" />
                  {s.message && <span style={{ color: '#666' }}>{s.message}</span>}
                </Space>
              ))}
            </Space>
          }
        />
      )}

      {/* 顶部结论条 */}
      <Card size="small" style={{ marginBottom: 16, borderLeft: '4px solid #f5222d' }} bodyStyle={{ padding: '12px 16px' }}>
        <Row gutter={16}>
          <Col xs={24} md={6}>
            <div style={{ fontSize: 12, color: '#999' }}>流动性判断</div>
            <div style={{ fontSize: 14, fontWeight: 600 }}>{flowSupport}</div>
          </Col>
          <Col xs={24} md={6}>
            <div style={{ fontSize: 12, color: '#999' }}>景气最强</div>
            <div style={{ fontSize: 14, fontWeight: 600 }}>{topUp[0]?.industry || '—'} ({topUp[0]?.q4 || '—'})</div>
          </Col>
          <Col xs={24} md={6}>
            <div style={{ fontSize: 12, color: '#999' }}>PMI</div>
            <div style={{ fontSize: 14, fontWeight: 600 }}>{pmi?.value || '—'} {pmi && DIR_ICON[pmi.direction]}</div>
          </Col>
          <Col xs={24} md={6}>
            <div style={{ fontSize: 12, color: '#999' }}>上行行业数</div>
            <div style={{ fontSize: 14, fontWeight: 600 }}>{topUp.length} / {industries.length}</div>
          </Col>
        </Row>
      </Card>

      <Tabs
        activeKey={tab}
        onChange={(k) => setSearchParams({ tab: k }, { replace: true })}
        type="card"
        size="small"
        items={[
          {
            key: 'workshop',
            label: <span><RiseOutlined /> 宏观灯塔</span>,
            children: (
              <Row gutter={16}>
                <Col xs={24} lg={12}>
                  <Card size="small" title="宏观指标" style={{ marginBottom: 16 }}>
                    {macro.length === 0 ? <Empty description="暂无" /> : macro.map(m => (
                      <div key={m.name} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid #f5f5f5' }}>
                        <span style={{ fontWeight: 500 }}>{m.name}</span>
                        <Space size={8}>
                          <span style={{ fontWeight: 600 }}>{m.value}{m.unit}</span>
                          {DIR_ICON[m.direction]}
                          <span style={{ fontSize: 11, color: '#999' }}>前值 {m.prev}</span>
                        </Space>
                      </div>
                    ))}
                  </Card>
                </Col>
                <Col xs={24} lg={12}>
                  <Card size="small" title="流动性与风格判断">
                    <div style={{ padding: '12px 0', fontSize: 15, fontWeight: 600, color: (pmi?.value || 0) > 50 ? '#f5222d' : '#1677ff' }}>
                      {flowSupport}
                    </div>
                    <AskAIChip prompt={`当前PMI ${pmi?.value || '—'}，宏观指标：${macro.map(d => `${d.name}=${d.value}${d.unit}`).join('，')}。分析流动性环境是否支持成长股估值扩张，还是更适合红利/价值防御。`} label="AI 宏观判断" />
                  </Card>
                </Col>
              </Row>
            ),
          },
          {
            key: 'heatmap',
            label: <span><HeatMapOutlined /> 景气热力</span>,
            children: (
              <Card size="small" title={<span><HeatMapOutlined /> 行业景气度热力图</span>} bodyStyle={{ padding: 8 }}>
                {industries.length > 0 ? <InlineHeatmap industries={industries} /> : <Empty />}
              </Card>
            ),
          },
          {
            key: 'turning',
            label: <span><AimOutlined /> 拐点预警</span>,
            children: (
              <Row gutter={16}>
                <Col xs={24} lg={12}>
                  <Card size="small" title="拐点雷达（Q3→Q4 变化>=8）">
                    <TurningPointRadar industries={industries} />
                  </Card>
                </Col>
                <Col xs={24} lg={12}>
                  <Suspense fallback={fallback}><ProsperityPage /></Suspense>
                </Col>
              </Row>
            ),
          },
          {
            key: 'chain',
            label: <span><SwapOutlined /> 产业链传导</span>,
            children: <SupplyChainTransmission />,
          },
          {
            key: 'etf',
            label: <span><SwapOutlined /> ETF 映射</span>,
            children: <Suspense fallback={fallback}><EtfRotationPage /></Suspense>,
          },
          {
            key: 'candidates',
            label: <span><ThunderboltOutlined /> 成长候选池</span>,
            children: (
              <Card size="small" title={<span><ThunderboltOutlined style={{ color: '#f5222d' }} /> 成长候选池</span>}
                extra={<Link to="/watchlist" style={{ fontSize: 12 }}>加入研究池 →</Link>}
              >
                <Row gutter={[12, 12]}>
                  {DEFAULT_GROWTH_STOCKS.map(s => (
                    <Col xs={12} md={4} key={s.code}>
                      <Card size="small" hoverable bodyStyle={{ padding: 10, textAlign: 'center' }}>
                        <Link to={`/stock/${s.code}`} style={{ fontWeight: 600 }}>{s.name}</Link>
                        <div><Tag style={{ fontSize: 11, marginTop: 4 }}>{s.tag}</Tag></div>
                      </Card>
                    </Col>
                  ))}
                </Row>
                <AskAIChip prompt={`分析以下成长候选标的：${DEFAULT_GROWTH_STOCKS.map(s => s.name).join('、')}。从行业景气、公司竞争力、估值三个维度评估，给出配置优先级排序和AI参考建议。`} label="AI 候选评估" />
              </Card>
            ),
          },
        ]}
      />
      <AIBadge style={{ marginBottom: 8 }} />
      <AIDisclaimer variant="inline" />
    </div>
  )
}
