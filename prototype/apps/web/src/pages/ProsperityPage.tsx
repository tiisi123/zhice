import { useEffect, useRef, useState } from 'react'
import { Card, Tabs, Table, Tag, Space, Button, Typography, Alert, Input, Spin, Row, Col, Statistic, Select, Progress, Timeline, Empty } from 'antd'
import * as echarts from 'echarts'
import { fetchApi } from '../api/client'
import { askAI } from '../api/copilot'
import { RobotOutlined } from '@ant-design/icons'
import AIBadge from '../components/AIBadge'
import type { AnyData, DataStatus } from '../api/types'
import { extractMeta } from '../api/useApiMeta'
import DataStatusBadge from '../components/DataStatusBadge'

const { Title, Paragraph } = Typography

function DiffusionTab() {
  const [data, setData] = useState<AnyData>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    setLoading(true)
    void fetchApi('/value/diffusion').then(setData).finally(() => setLoading(false))
  }, [])

  if (loading || !data) return <Spin />
  const meta = extractMeta(data)
  return (
    <div>
      <Alert
        type="info" showIcon style={{ marginBottom: 16 }}
        message={
          <Space size={8}>
            <span>景气扩散指数：<b style={{ fontSize: 20 }}>{data.diffusion_index}</b></span>
            <DataStatusBadge status={meta.data_status as DataStatus} source={meta.source} mock={meta.mock} />
          </Space>
        }
        description={`${data.interpretation}${data.message ? `（${data.message}）` : ''}`}
      />
      <Row gutter={12}>
        <Col span={8}><Card size="small"><Statistic title="上行行业数" value={data.up_count} valueStyle={{ color: '#f5222d' }} /></Card></Col>
        <Col span={8}><Card size="small"><Statistic title="下行行业数" value={data.down_count} valueStyle={{ color: '#389e0d' }} /></Card></Col>
        <Col span={8}><Card size="small"><Statistic title="合计" value={data.total || (data.up_count + data.down_count)} /></Card></Col>
      </Row>
    </div>
  )
}

function TurningTab() {
  const [rows, setRows] = useState<AnyData[]>([])
  useEffect(() => { void fetchApi<{ alerts: AnyData[] }>('/value/turning-points').then((r) => setRows(r.alerts)) }, [])
  return (
    <div>
      <Paragraph type="secondary">基于近 4 季度景气度数据侦测方向拐点，命中即输出预警。</Paragraph>
      <Table rowKey={(r, i) => `${r.industry}-${i}`} size="small" pagination={false} dataSource={rows}
        columns={[
          { title: '行业', dataIndex: 'industry', width: 160 },
          { title: '方向', dataIndex: 'direction', width: 120,
            render: (v: string) => <Tag color={/上行|转好|拐头向上/.test(v) ? 'red' : 'green'}>{v}</Tag> },
          { title: '前值', dataIndex: 'q3', width: 100, render: (v: AnyData, r: AnyData) => v ?? r.prev },
          { title: '现值', dataIndex: 'q4', width: 100, render: (v: AnyData, r: AnyData) => v ?? r.current },
          { title: '变化', dataIndex: 'change', align: 'right' as const },
        ]}
      />
    </div>
  )
}

function WeeklyReportTab() {
  const [data, setData] = useState<AnyData>(null)
  const [loading, setLoading] = useState(false)

  const gen = async () => {
    setLoading(true)
    try {
      const r = await fetchApi('/value/weekly-report')
      setData(r)
    } finally { setLoading(false) }
  }

  return (
    <div>
      <Button type="primary" onClick={gen} loading={loading}>生成本周景气度周报</Button>
      {data && (() => {
        const meta = extractMeta(data)
        return (
          <Card style={{ marginTop: 16 }}>
            <Alert
              type={meta.mock ? 'warning' : meta.data_status === 'unavailable' || meta.data_status === 'error' ? 'error' : meta.data_status === 'fallback' ? 'info' : 'success'}
              showIcon style={{ marginBottom: 12 }}
              message={
                <Space size={8}>
                  <span>{`扩散指数 ${data.diffusion?.diffusion_index}（${data.diffusion?.interpretation}）`}</span>
                  <DataStatusBadge status={meta.data_status as DataStatus} source={meta.source} mock={meta.mock} />
                </Space>
              }
              description={`上行 ${data.diffusion?.up_count} / 下行 ${data.diffusion?.down_count} · 拐点 ${data.turning_points?.length || 0} 个${data.message ? `（${data.message}）` : ''}`}
            />
            <pre style={{ whiteSpace: 'pre-wrap', fontSize: 13, lineHeight: 1.9 }}>{data.report}</pre>
          </Card>
        )
      })()}
    </div>
  )
}

function HistoricalCycleTab() {
  const [industry, setIndustry] = useState('半导体')
  const [data, setData] = useState<AnyData>(null)
  const chartRef = useRef<HTMLDivElement>(null)

  const load = async () => {
    const r = await fetchApi<AnyData>('/research/prosperity-cycle', { industry })
    setData(r)
  }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { void load() }, [])

  useEffect(() => {
    if (!data || !chartRef.current) return
    const chart = echarts.init(chartRef.current)
    chart.setOption({
      tooltip: { trigger: 'axis' },
      grid: { left: 40, right: 20, top: 20, bottom: 40 },
      xAxis: { type: 'category', data: data.trajectory.map((r: AnyData) => r.period), axisLabel: { fontSize: 10, rotate: 40 } },
      yAxis: { type: 'value', name: '景气度', min: 0, max: 100 },
      series: [{
        type: 'line', data: data.trajectory.map((r: AnyData) => r.score),
        smooth: true, areaStyle: { opacity: 0.2 }, itemStyle: { color: '#1677ff' },
        markLine: { data: [{ yAxis: data.current, name: '当前' }], lineStyle: { color: '#faad14' } },
      }],
    })
    const r = () => chart.resize()
    window.addEventListener('resize', r)
    return () => { window.removeEventListener('resize', r); chart.dispose() }
  }, [data])

  return (
    <div>
      <Space style={{ marginBottom: 12 }}>
        <Input value={industry} onChange={(e) => setIndustry(e.target.value)} placeholder="行业名" style={{ width: 180 }} />
        <Button type="primary" onClick={load}>查看历史景气周期</Button>
      </Space>
      {data && (() => {
        const meta = extractMeta(data)
        return (
          <>
            <Alert type="info" showIcon style={{ marginBottom: 12 }}
              message={
                <Space size={8}>
                  <span>当前 <b>{industry}</b> 景气度 <b>{data.current}</b>（近 8 年 <b>{data.percentile}%</b> 分位）</span>
                  <DataStatusBadge status={meta.data_status as DataStatus} source={meta.source} mock={meta.mock} />
                </Space>
              }
              description={`${data.interpretation}${data.message ? `（${data.message}）` : ''}`} />
            <Card size="small">
              <div ref={chartRef} style={{ width: '100%', height: 320 }} />
            </Card>
          </>
        )
      })()}
    </div>
  )
}

// ========== M4C-07 宏观-行业传导 ==========
const MACRO_OPTIONS = [
  { value: 'PMI上升', label: 'PMI 上升 · 制造业扩张' },
  { value: 'CPI上升', label: 'CPI 上升 · 通胀升温' },
  { value: '利率下调', label: '利率下调 · 流动性宽松' },
]

function MacroTransmissionTab() {
  const [change, setChange] = useState('PMI上升')
  const [chain, setChain] = useState<AnyData[]>([])
  const [loading, setLoading] = useState(false)

  const load = async (c: string) => {
    setLoading(true)
    try {
      const r = await fetchApi<{ transmission: AnyData[] }>(`/value/macro-transmission/${encodeURIComponent(c)}`)
      setChain(r.transmission || [])
    } finally { setLoading(false) }
  }
  useEffect(() => { void load(change) }, [change])

  const layerColor = (layer: string) =>
    layer.startsWith('宏观') ? '#1677ff'
      : layer.startsWith('中观') ? '#fa8c16'
      : layer.startsWith('微观') ? '#f5222d' : '#999'

  return (
    <div>
      <Paragraph type="secondary">
        AI 推演宏观信号沿「宏观 → 中观 → 微观」的传导路径与时滞，帮助你判断当前宏观变化对行业的影响节奏。
      </Paragraph>
      <Space wrap style={{ marginBottom: 16 }}>
        <Select
          value={change} onChange={setChange} options={MACRO_OPTIONS} style={{ width: 260 }}
        />
        <Button
          icon={<RobotOutlined />}
          onClick={() => askAI(`宏观信号【${change}】沿宏观→中观→微观的传导路径、时滞与历史相似时段表现，给出当前可关注的行业与个股线索。`)}
        >
          AI 深度解读
        </Button>
      </Space>
      {loading ? <Spin /> : chain.length === 0 ? <Empty /> : (
        <Card size="small">
          <Timeline
            items={chain.map((item: AnyData) => ({
              color: layerColor(item.layer || ''),
              children: (
                <div>
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
                    <Tag color={layerColor(item.layer)}>{item.layer}</Tag>
                    <span style={{ fontWeight: 600 }}>{item.signal}</span>
                  </div>
                  <div style={{ color: '#999', fontSize: 12, marginTop: 4 }}>
                    时滞：<b style={{ color: '#666' }}>{item.lag || '—'}</b>
                  </div>
                </div>
              ),
            }))}
          />
        </Card>
      )}
    </div>
  )
}

// ========== M4C-08 产业链景气传导 ==========
const CHAIN_OPTIONS = [
  { value: '半导体', label: '半导体' },
  { value: '新能源车', label: '新能源车' },
  { value: 'AI人工智能', label: 'AI 人工智能' },
]

function ChainProsperityTab() {
  const [chainName, setChainName] = useState('半导体')
  const [streams, setStreams] = useState<AnyData[]>([])
  const [loading, setLoading] = useState(false)

  const load = async (n: string) => {
    setLoading(true)
    try {
      const r = await fetchApi<{ streams: AnyData[] }>(`/value/chain-prosperity/${encodeURIComponent(n)}`)
      setStreams(r.streams || [])
    } catch { setStreams([]) } finally { setLoading(false) }
  }
  useEffect(() => { void load(chainName) }, [chainName])

  const tone = (p: number) => p >= 80 ? '#f5222d' : p >= 65 ? '#fa8c16' : p >= 50 ? '#faad14' : '#52c41a'
  const label = (p: number) => p >= 80 ? '高景气' : p >= 65 ? '景气回升' : p >= 50 ? '中性' : '承压'

  return (
    <div>
      <Paragraph type="secondary">
        从上游 → 中游 → 下游对比同一产业链的景气度高度差，识别"上热下冷 / 下热上冷"的传导错位机会。
      </Paragraph>
      <Space wrap style={{ marginBottom: 16 }}>
        <Select
          value={chainName} onChange={setChainName} options={CHAIN_OPTIONS} style={{ width: 220 }}
        />
        <Button
          icon={<RobotOutlined />}
          onClick={() => askAI(`产业链【${chainName}】上中下游当前景气度对比：${streams.map((s: AnyData) => `${s.stream}=${s.prosperity}`).join('、')}。请分析传导节奏、最具弹性的环节与对应龙头标的。`)}
        >
          AI 解读传导
        </Button>
      </Space>
      {loading ? <Spin /> : streams.length === 0 ? <Empty description="暂无该产业链的景气传导数据" /> : (
        <Row gutter={[12, 12]}>
          {streams.map((s: AnyData, i: number) => (
            <Col key={s.stream} xs={24} md={8}>
              <Card size="small" hoverable>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                  <span style={{ fontSize: 12, color: '#999' }}>第 {i + 1} 段</span>
                  <Tag color={tone(s.prosperity)}>{label(s.prosperity)}</Tag>
                </div>
                <div style={{ fontSize: 16, fontWeight: 700, margin: '8px 0' }}>{s.stream}</div>
                <Progress
                  percent={s.prosperity} strokeColor={tone(s.prosperity)}
                  format={(v) => <span style={{ fontSize: 13 }}>{v}</span>}
                />
                <div style={{ fontSize: 12, color: '#666', marginTop: 8, lineHeight: 1.6 }}>
                  {s.signal}
                </div>
              </Card>
            </Col>
          ))}
        </Row>
      )}
      {streams.length >= 2 && (
        <Alert
          type="info" showIcon style={{ marginTop: 16 }}
          message={(() => {
            const top = [...streams].sort((a, b) => b.prosperity - a.prosperity)[0]
            const bot = [...streams].sort((a, b) => a.prosperity - b.prosperity)[0]
            const gap = top.prosperity - bot.prosperity
            return `传导错位：${top.stream}（${top.prosperity}）领先 ${bot.stream}（${bot.prosperity}）${gap} 分${gap >= 20 ? '，错位明显，存在落后段补涨预期' : '，传导较均衡'}。`
          })()}
        />
      )}
    </div>
  )
}

export default function ProsperityPage() {
  return (
    <div>
      <AIBadge style={{ marginBottom: 8 }} />
      <Title level={3}>景气度中心</Title>
      <Paragraph type="secondary">覆盖：扩散指数 · 拐点预警 · 宏观传导 · 产业链传导 · AI 周报 · 历史周期回看。</Paragraph>
      <Tabs
        items={[
          { key: 'diff', label: 'M4C-06 扩散指数', children: <DiffusionTab /> },
          { key: 'turn', label: 'M4C-04 拐点预警', children: <TurningTab /> },
          { key: 'macro', label: 'M4C-07 宏观传导', children: <MacroTransmissionTab /> },
          { key: 'chain', label: 'M4C-08 产业链景气', children: <ChainProsperityTab /> },
          { key: 'weekly', label: 'M4C-09 AI 周报', children: <WeeklyReportTab /> },
          { key: 'hist', label: 'M4C-10 历史周期', children: <HistoricalCycleTab /> },
        ]}
      />
    </div>
  )
}
