import { useEffect, useMemo, useRef, useState } from 'react'
import { Alert, Card, Col, Row, Select, Spin, Statistic, Table, Tabs, Tag } from 'antd'
import * as echarts from 'echarts'
import { fetchApi } from '../api/client'

type StageType = '加速' | '启动' | '蓄势' | '分歧' | '退潮'

interface EtfMetric {
  code: string
  name: string
  theme: string
  last_price: number
  change_1d: number
  change_5d: number
  flow_1d: number
  flow_3d: number
  flow_5d: number
  turn_ratio: number
  volatility: number
  breakout: boolean
  capital_score: number
  start_score: number
  stage: StageType | string
  stage_reason: string
  signal_state: string
  risk_thresholds: { entry: number; watch: number; exit: number }
}

interface RotationLink {
  source_name: string
  target_name: string
  value: number
  probability: number
  lag_days: number
  signal: string
  overnight_priority: boolean
}

interface TrajectoryLink extends RotationLink {
  target_code: string
  target_stage: string
  target_score: number
  target_signal_state: string
}

interface HeatmapItem {
  name: string
  scores: number[]
}

interface DashboardData {
  as_of: string
  data_mode: string
  data_status?: string
  source?: string
  mock?: boolean
  message?: string
  source_code: string
  source_name: string
  summary: {
    etf_count: number
    net_flow_1d: number
    net_flow_5d: number
    startup_count: number
    risk_on_ratio: number
  }
  evaluation: {
    rotation_accuracy: number
    attribution_return_1d: number
    attribution_return_5d: number
  }
  stage_distribution: Record<string, number>
  etfs: EtfMetric[]
  links: RotationLink[]
  trajectory: TrajectoryLink[]
  heatmap: { dates: string[]; items: HeatmapItem[] }
}

const stageColor: Record<string, string> = {
  加速: '#f5222d', 启动: '#fa8c16', 蓄势: '#1677ff', 分歧: '#13c2c2', 退潮: '#8c8c8c',
}

const signalColor: Record<string, string> = {
  执行: 'red', 观察: 'gold', 回避: 'default',
}

function createsCycle(graph: Map<string, Set<string>>, source: string, target: string): boolean {
  if (source === target) return true
  const stack = [target]
  const visited = new Set<string>()
  while (stack.length) {
    const node = stack.pop()!
    if (node === source) return true
    if (visited.has(node)) continue
    visited.add(node)
    graph.get(node)?.forEach((n) => { if (!visited.has(n)) stack.push(n) })
  }
  return false
}

interface SankeyLink { source: string; target: string; value: number; probability: number; lag_days: number; signal: string; overnight_priority: boolean }

function toDagLinks(rawLinks: SankeyLink[]): SankeyLink[] {
  const sorted = [...rawLinks].sort((a, b) => b.value - a.value || b.probability - a.probability)
  const graph = new Map<string, Set<string>>()
  const dag: SankeyLink[] = []
  for (const link of sorted) {
    if (!link.source || !link.target || link.source === link.target) continue
    if (createsCycle(graph, link.source, link.target)) continue
    const set = graph.get(link.source) || new Set()
    set.add(link.target)
    graph.set(link.source, set)
    dag.push(link)
  }
  return dag
}

const tableColumns = [
  {
    title: 'ETF', key: 'name', width: 160,
    render: (_: any, r: EtfMetric) => (
      <div>
        <div style={{ fontWeight: 600 }}>{r.name}</div>
        <div style={{ color: '#999', fontSize: 12 }}>{r.code} · {r.theme}</div>
      </div>
    ),
  },
  {
    title: '1D涨跌', dataIndex: 'change_1d', key: 'change_1d', width: 80,
    render: (v: number) => <span style={{ color: v >= 0 ? '#f5222d' : '#52c41a' }}>{v.toFixed(2)}%</span>,
  },
  {
    title: '5D涨跌', dataIndex: 'change_5d', key: 'change_5d', width: 80,
    render: (v: number) => <span style={{ color: v >= 0 ? '#f5222d' : '#52c41a' }}>{v.toFixed(2)}%</span>,
  },
  {
    title: '3日资金', dataIndex: 'flow_3d', key: 'flow_3d', width: 80,
    render: (v: number) => <span style={{ color: v >= 0 ? '#cf1322' : '#389e0d' }}>{v.toFixed(1)}</span>,
  },
  { title: '资金分', dataIndex: 'capital_score', key: 'capital_score', width: 70 },
  {
    title: '启动分', dataIndex: 'start_score', key: 'start_score', width: 70,
    sorter: (a: EtfMetric, b: EtfMetric) => a.start_score - b.start_score,
  },
  { title: '波动率', dataIndex: 'volatility', key: 'volatility', width: 70 },
  {
    title: '状态', dataIndex: 'signal_state', key: 'signal_state', width: 70,
    render: (v: string) => <Tag color={signalColor[v] || 'default'}>{v}</Tag>,
  },
  {
    title: '阶段', dataIndex: 'stage', key: 'stage', width: 70,
    render: (v: string) => <Tag color={stageColor[v] || '#999'}>{v}</Tag>,
  },
  { title: '判定依据', dataIndex: 'stage_reason', key: 'stage_reason', ellipsis: true },
]

export default function EtfRotationPage() {
  const [loading, setLoading] = useState(true)
  const [sourceCode, setSourceCode] = useState('512480')
  const [dataMode, setDataMode] = useState<'auto' | 'live' | 'sample'>('auto')
  const [dashboard, setDashboard] = useState<DashboardData | null>(null)
  const [activeTab, setActiveTab] = useState('sankey')
  const sankeyRef = useRef<HTMLDivElement>(null)
  const heatmapRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let active = true
    setLoading(true)
    fetchApi<DashboardData>('/etf/rotation/dashboard', { source: sourceCode, mode: dataMode })
      .then((res) => { if (active) { setDashboard(res); if (res.source_code) setSourceCode(res.source_code) } })
      .catch(() => { if (active) setDashboard(null) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [sourceCode, dataMode])

  useEffect(() => {
    if (!dashboard || !sankeyRef.current) return
    const chart = echarts.init(sankeyRef.current)

    const nodes = dashboard.etfs.map((e) => ({
      name: e.name,
      itemStyle: { color: stageColor[e.stage] || '#1677ff' },
      value: e.start_score,
      stage: e.stage,
      signal_state: e.signal_state,
    }))
    const rawLinks = dashboard.links.map((l) => ({
      source: l.source_name, target: l.target_name, value: l.value,
      probability: l.probability, lag_days: l.lag_days, signal: l.signal,
      overnight_priority: l.overnight_priority,
    }))
    const links = toDagLinks(rawLinks)

    chart.setOption({
      tooltip: {
        trigger: 'item',
        formatter: (p: any) => {
          if (p.dataType === 'edge') {
            const d = p.data
            return `${d.source} → ${d.target}<br/>强度: ${d.value}<br/>概率: ${d.probability}%<br/>滞后: ${d.lag_days}天`
          }
          const d = p.data
          return `${d.name}<br/>启动分: ${d.value}<br/>阶段: ${d.stage}`
        },
      },
      series: [{
        type: 'sankey', layout: 'none', emphasis: { focus: 'adjacency' },
        data: nodes, links,
        nodeWidth: 16, nodeGap: 18,
        lineStyle: { color: 'source', curveness: 0.45, opacity: 0.35 },
        label: { color: '#222', fontSize: 12 },
      }],
    })

    const onResize = () => chart.resize()
    window.addEventListener('resize', onResize)
    return () => { window.removeEventListener('resize', onResize); chart.dispose() }
  }, [dashboard])

  useEffect(() => {
    if (!dashboard || !heatmapRef.current) return
    const chart = echarts.init(heatmapRef.current)

    const heatRows = dashboard.heatmap.items.slice(0, 10)
    const heatData: number[][] = []
    heatRows.forEach((row, yi) => {
      row.scores.forEach((score, xi) => { heatData.push([xi, yi, score]) })
    })

    chart.setOption({
      tooltip: {
        formatter: (p: any) => {
          const [xi, yi, score] = p.value
          return `${heatRows[yi].name}<br/>${dashboard.heatmap.dates[xi]}<br/>启动分: ${score}`
        },
      },
      grid: { left: 90, right: 20, top: 10, bottom: 60 },
      xAxis: { type: 'category', data: dashboard.heatmap.dates.map((d) => d.slice(5)) },
      yAxis: { type: 'category', data: heatRows.map((r) => r.name) },
      visualMap: {
        min: 0, max: 100, calculable: true, orient: 'horizontal', left: 'center', bottom: 0,
        inRange: { color: ['#c8d9ff', '#5b8ff9', '#f6bd16', '#e86452'] },
      },
      series: [{ type: 'heatmap', data: heatData, label: { show: true, fontSize: 10, color: '#111' } }],
    })

    const onResize = () => chart.resize()
    window.addEventListener('resize', onResize)
    return () => { window.removeEventListener('resize', onResize); chart.dispose() }
  }, [dashboard])

  useEffect(() => {
    setTimeout(() => {
      if (activeTab === 'sankey' && sankeyRef.current) {
        echarts.getInstanceByDom(sankeyRef.current)?.resize()
      }
      if (activeTab === 'heatmap' && heatmapRef.current) {
        echarts.getInstanceByDom(heatmapRef.current)?.resize()
      }
    }, 50)
  }, [activeTab])

  const stageTags = useMemo(() => {
    if (!dashboard) return []
    return ['加速', '启动', '蓄势', '分歧', '退潮']
      .filter((s) => dashboard.stage_distribution[s])
      .map((s) => ({ stage: s, count: dashboard.stage_distribution[s] }))
  }, [dashboard])

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />
  if (!dashboard) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />

  const { summary: s, evaluation: ev } = dashboard

  return (
    <div>
      <Alert
        type={dashboard.mock ? 'warning' : dashboard.data_status === 'partial' ? 'info' : 'success'}
        showIcon
        style={{ marginBottom: 12 }}
        message={`ETF 数据状态：${dashboard.source || dashboard.data_mode} / ${dashboard.data_status || dashboard.data_mode}`}
        description={dashboard.message || 'ETF 看板包含行情数据、资金 proxy 和规则评分，推演结果仅供研究参考。'}
      />

      <Row gutter={[16, 16]}>
        <Col span={4}><Card size="small"><Statistic title="ETF池" value={s.etf_count} /></Card></Col>
        <Col span={4}><Card size="small"><Statistic title="当日净流入" value={s.net_flow_1d} suffix="亿" precision={2} /></Card></Col>
        <Col span={4}><Card size="small"><Statistic title="5日净流入" value={s.net_flow_5d} suffix="亿" precision={2} /></Card></Col>
        <Col span={4}><Card size="small"><Statistic title="启动/加速" value={s.startup_count} /></Card></Col>
        <Col span={4}>
          <Card size="small">
            <Statistic title="轮动正确率" value={ev.rotation_accuracy} suffix="%" precision={1} valueStyle={{ color: ev.rotation_accuracy >= 50 ? '#f5222d' : '#52c41a' }} />
          </Card>
        </Col>
        <Col span={4}>
          <Card size="small">
            <Statistic title="归因收益(5D)" value={ev.attribution_return_5d} suffix="%" precision={2} valueStyle={{ color: ev.attribution_return_5d >= 0 ? '#cf1322' : '#389e0d' }} />
          </Card>
        </Col>
      </Row>

      <Row gutter={16} style={{ marginTop: 16 }}>
        <Col span={16}>
          <Card size="small">
            <Tabs type="card" size="small" activeKey={activeTab} onChange={setActiveTab} destroyInactiveTabPane={false} items={[
              {
                key: 'sankey', label: '资金轮动轨迹',
                children: <div ref={sankeyRef} style={{ width: '100%', height: 420 }} />,
              },
              {
                key: 'heatmap', label: '启动阶段热力',
                children: <div ref={heatmapRef} style={{ width: '100%', height: 420 }} />,
              },
            ]} />
          </Card>
        </Col>
        <Col span={8}>
          <Card
            title="轮动推演（Top5）"
            size="small"
            extra={
              <Select
                value={sourceCode}
                onChange={setSourceCode}
                style={{ width: 160 }}
                size="small"
                options={dashboard.etfs.map((e) => ({ label: `${e.name}(${e.code})`, value: e.code }))}
              />
            }
          >
            {dashboard.trajectory.map((item, idx) => (
              <div key={`${item.target_code}-${idx}`} style={{ marginBottom: 8, fontSize: 13 }}>
                <Tag color="geekblue">{dashboard.source_name}</Tag> → <Tag color="orange">{item.target_name}</Tag>
                <span style={{ marginLeft: 6 }}>概率 {item.probability}%</span>
                <span style={{ marginLeft: 8, color: '#999' }}>滞后 {item.lag_days}天</span>
                <Tag color={signalColor[item.target_signal_state] || 'default'} style={{ marginLeft: 8 }}>
                  {item.target_signal_state}
                </Tag>
              </div>
            ))}
            <div style={{ marginTop: 8, color: '#faad14', fontSize: 12 }}>
              推演为统计迁移概率，不构成投资建议。
            </div>
          </Card>
          <Card title="阶段分布" size="small" style={{ marginTop: 16 }}>
            {stageTags.map((item) => (
              <Tag key={item.stage} color={stageColor[item.stage] || '#999'} style={{ marginBottom: 6 }}>
                {item.stage}：{item.count}
              </Tag>
            ))}
          </Card>
        </Col>
      </Row>

      <Card
        title="ETF 轮动打分榜"
        size="small"
        style={{ marginTop: 16 }}
        extra={
          <Select
            value={dataMode}
            onChange={setDataMode}
            size="small"
            style={{ width: 100 }}
            options={[
              { label: 'auto', value: 'auto' },
              { label: 'live', value: 'live' },
              { label: 'sample', value: 'sample' },
            ]}
          />
        }
      >
        <Table
          dataSource={dashboard.etfs}
          columns={tableColumns}
          rowKey="code"
          size="small"
          pagination={{ pageSize: 15, showSizeChanger: false }}
        />
      </Card>
    </div>
  )
}
