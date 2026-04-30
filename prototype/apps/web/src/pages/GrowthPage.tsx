import { useEffect, useState, useRef } from 'react'
import { Card, Col, Row, Table, Tag, Spin, Statistic, Select, Tabs, Button, Space, Empty } from 'antd'
import { ArrowUpOutlined, ArrowDownOutlined, MinusOutlined, RobotOutlined, DashboardOutlined, HeatMapOutlined, SwapOutlined } from '@ant-design/icons'
import * as echarts from 'echarts'
import { fetchApi } from '../api/client'
import { askAI } from '../api/copilot'
import MockBanner from '../components/MockBanner'
import type { ReactNode } from 'react'
import type { AnyData } from '../api/types'

const dirIcon: Record<string, ReactNode> = {
  up: <ArrowUpOutlined style={{ color: '#f5222d' }} />,
  down: <ArrowDownOutlined style={{ color: '#52c41a' }} />,
  flat: <MinusOutlined style={{ color: '#999' }} />,
}

function MacroCards({ data }: { data: AnyData[] }) {
  const key3 = data.filter(d => ['PMI', 'CPI', '社融'].includes(d.name)).slice(0, 3)
  if (key3.length === 0) return null
  return (
    <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
      {key3.map(d => (
        <Col xs={24} md={8} key={d.name}>
          <Card size="small" style={{ borderLeft: `3px solid ${d.direction === 'up' ? '#f5222d' : d.direction === 'down' ? '#52c41a' : '#d9d9d9'}` }}>
            <Statistic
              title={<span>{d.name} <span style={{ fontSize: 11, color: '#999' }}>({d.date})</span></span>}
              value={d.value} suffix={d.unit}
              valueStyle={{ fontSize: 24, fontWeight: 700 }}
              prefix={dirIcon[d.direction]}
            />
            <div style={{ fontSize: 12, color: '#999', marginTop: 4 }}>前值 {d.prev}{d.unit}</div>
          </Card>
        </Col>
      ))}
    </Row>
  )
}

function HeatmapChart({ industries }: { industries: AnyData[] }) {
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
      grid: { left: 90, right: 50, top: 10, bottom: 60 },
      xAxis: { type: 'category', data: quarters },
      yAxis: { type: 'category', data: names, axisLabel: { fontSize: 11 } },
      visualMap: { min: 20, max: 100, calculable: true, orient: 'horizontal', left: 'center', bottom: 0, inRange: { color: ['#52c41a', '#faad14', '#f5222d'] } },
      series: [{ type: 'heatmap', data: heatData, label: { show: true, fontSize: 11 } }],
    })
    const onResize = () => chart.resize()
    window.addEventListener('resize', onResize)
    return () => { window.removeEventListener('resize', onResize); chart.dispose() }
  }, [industries])
  return <div ref={ref} style={{ width: '100%', height: 460 }} />
}

function RotationPanel({ industries: _industries }: { industries: AnyData[] }) {
  const [src, setSrc] = useState('半导体')
  const [rotation, setRotation] = useState<AnyData>(null)
  const sources = ['半导体', 'AI/算力', '新能源车', '军工', '医药生物']

  useEffect(() => {
    fetchApi<AnyData>(`/growth/rotation?source=${encodeURIComponent(src)}`).then(setRotation).catch(() => setRotation(null))
  }, [src])

  return (
    <Card size="small" title={<span><SwapOutlined style={{ color: '#722ed1' }} /> 轮动推演</span>}
      extra={<Select value={src} onChange={setSrc} size="small" style={{ width: 120 }} options={sources.map(n => ({ label: n, value: n }))} />}
    >
      {rotation?.targets?.length > 0 ? (
        <Space direction="vertical" size={8} style={{ width: '100%' }}>
          {rotation.targets.map((t: AnyData, i: number) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 0', borderBottom: '1px solid #f0f0f0' }}>
              <Tag color="blue">{src}</Tag>
              <span style={{ fontSize: 16, color: '#999' }}>→</span>
              <Tag color="orange">{t.target}</Tag>
              <span style={{ fontWeight: 700, color: '#fa8c16' }}>{t.probability}%</span>
              <span style={{ color: '#999', fontSize: 12 }}>滞后 {t.lag_days} 天</span>
            </div>
          ))}
        </Space>
      ) : <Empty description="暂无轮动数据" />}
      <div style={{ marginTop: 12 }}>
        <Button type="link" icon={<RobotOutlined />} onClick={() => askAI(`当前从【${src}】出发的行业轮动路径是什么？${rotation?.targets?.length > 0 ? `最可能传导到${rotation.targets[0].target}（概率${rotation.targets[0].probability}%，滞后${rotation.targets[0].lag_days}天）` : ''}。分析轮动逻辑和时机。`)}>
          AI 解读轮动
        </Button>
      </div>
    </Card>
  )
}

function CompareTab({ industries }: { industries: AnyData[] }) {
  const [selected, setSelected] = useState<string[]>(['半导体', 'AI/算力', '新能源车'])
  const [compared, setCompared] = useState<AnyData[]>([])
  const chartRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (selected.length < 2) return
    fetchApi<{ compared: AnyData[] }>(`/growth/prosperity/compare?names=${selected.join(',')}`).then(r => setCompared(r.compared)).catch(() => {})
  }, [selected])

  useEffect(() => {
    if (!chartRef.current || !compared.length) return
    const chart = echarts.init(chartRef.current)
    chart.setOption({
      tooltip: { trigger: 'axis' },
      legend: { data: compared.map(d => d.industry), bottom: 0 },
      grid: { left: 50, right: 20, top: 20, bottom: 40 },
      xAxis: { type: 'category', data: ['Q1', 'Q2', 'Q3', 'Q4'] },
      yAxis: { type: 'value', name: '景气度' },
      series: compared.map(d => ({ name: d.industry, type: 'line', data: [d.q1, d.q2, d.q3, d.q4], smooth: true, lineStyle: { width: 2 } })),
    })
    const onResize = () => chart.resize()
    window.addEventListener('resize', onResize)
    return () => { window.removeEventListener('resize', onResize); chart.dispose() }
  }, [compared])

  return (
    <div>
      <Select mode="multiple" value={selected} onChange={setSelected} style={{ width: '100%', marginBottom: 12 }}
        options={industries.map((d: AnyData) => ({ label: d.industry, value: d.industry }))} placeholder="选择行业对比（至少2个）" />
      {compared.length > 0 && <div ref={chartRef} style={{ width: '100%', height: 360 }} />}
      <Button type="link" icon={<RobotOutlined />} style={{ marginTop: 8 }}
        onClick={() => askAI(`对比行业景气度：${selected.join('、')}。哪个行业Q4景气度最高？哪个行业拐点最明显？给出投资优先级排序。`)}>
        AI 对比分析
      </Button>
    </div>
  )
}

export default function GrowthPage() {
  const [macro, setMacro] = useState<AnyData[]>([])
  const [industries, setIndustries] = useState<AnyData[]>([])
  const [loading, setLoading] = useState(true)
  const [isMock, setIsMock] = useState(false)

  useEffect(() => {
    setLoading(true)
    void Promise.all([
      fetchApi<{ indicators: AnyData[] }>('/growth/macro'),
      fetchApi<{ industries: AnyData[] }>('/growth/prosperity'),
    ]).then(([m, p]) => {
      setMacro(m.indicators); setIndustries(p.industries)
      setIsMock(m.indicators?.some((i: AnyData) => i.data_source === 'mock'))
    })
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '120px auto' }} />

  const topIndustry = industries.reduce((best, d) => d.q4 > (best?.q4 || 0) ? d : best, industries[0])

  return (
    <div>
      <MockBanner show={isMock} />
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
        <h2 style={{ margin: 0 }}><DashboardOutlined style={{ color: '#722ed1' }} /> 景气度分析</h2>
        {topIndustry && <Tag color="red">最强行业：{topIndustry.industry}（Q4 景气 {topIndustry.q4}）</Tag>}
      </div>

      <MacroCards data={macro} />

      <Tabs type="card" items={[
        {
          key: 'overview', label: '景气总览',
          children: (
            <Row gutter={16}>
              <Col xs={24} lg={14}>
                <Card title={<span><HeatMapOutlined /> 行业景气度热力图</span>} size="small" bodyStyle={{ padding: 8 }}>
                  {industries.length > 0 ? <HeatmapChart industries={industries} /> : <Empty />}
                </Card>
              </Col>
              <Col xs={24} lg={10}>
                <RotationPanel industries={industries} />
              </Col>
            </Row>
          ),
        },
        { key: 'compare', label: '行业比较', children: <CompareTab industries={industries} /> },
        {
          key: 'macro', label: '宏观数据',
          children: (
            <Table dataSource={macro} columns={[
              { title: '指标', dataIndex: 'name', key: 'n', width: 120 },
              { title: '最新值', key: 'v', width: 100, render: (_: AnyData, r: AnyData) => <span style={{ fontWeight: 600 }}>{r.value}{r.unit}</span> },
              { title: '前值', key: 'p', width: 100, render: (_: AnyData, r: AnyData) => `${r.prev}${r.unit}` },
              { title: '趋势', dataIndex: 'direction', key: 'd', width: 60, render: (v: string) => dirIcon[v] },
              { title: '日期', dataIndex: 'date', key: 'dt', width: 100 },
            ]} rowKey="name" size="small" pagination={false} />
          ),
        },
      ]} />

      <Card size="small" title={<span><RobotOutlined style={{ color: '#1677ff' }} /> 向 AI 追问</span>} style={{ marginTop: 16 }}>
        <Space wrap>
          <Button type="primary" icon={<RobotOutlined />}
            onClick={() => askAI(`当前宏观环境：${macro.slice(0, 3).map(d => `${d.name} ${d.value}${d.unit}(${d.direction === 'up' ? '↑' : d.direction === 'down' ? '↓' : '→'})`).join('，')}。最强行业${topIndustry?.industry}(景气${topIndustry?.q4})。分析宏观对行业的传导路径和投资方向。`)}
          >
            宏观→行业传导
          </Button>
          <Button onClick={() => askAI('哪些行业Q3到Q4景气度出现拐点？拐点的前兆信号有哪些？')}>拐点预警</Button>
          <Button onClick={() => askAI('当前最应该配置哪个行业？从宏观、中观、估值三个维度给出理由。')}>配置建议</Button>
        </Space>
      </Card>

      <div style={{ marginTop: 12, color: '#999', fontSize: 11, textAlign: 'center' }}>以上分析仅供参考，不构成投资建议。</div>
    </div>
  )
}
