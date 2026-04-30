import { useEffect, useRef, useState, useCallback } from 'react'
import { Card, Col, Row, Statistic, Tag, Table, Spin, Tabs, DatePicker, Empty, Progress } from 'antd'
import { ArrowUpOutlined, ArrowDownOutlined, CaretUpFilled, CaretDownFilled } from '@ant-design/icons'
import * as echarts from 'echarts'
import dayjs from 'dayjs'
import { fetchApi } from '../api/client'
import type { MarketSummary, LadderData, LimitUpStock, RelayData } from '../api/types'

const sentimentColor: Record<string, string> = {
  '冰点': '#1890ff',
  '低迷': '#69c0ff',
  '中性': '#faad14',
  '回暖': '#fa8c16',
  '高潮': '#f5222d',
}

function DeltaBadge({ current, prev, suffix }: { current: number; prev?: number; suffix?: string }) {
  if (prev == null) return null
  const delta = current - prev
  if (delta === 0) return null
  const isUp = delta > 0
  return (
    <span style={{ fontSize: 12, color: isUp ? '#f5222d' : '#52c41a', marginLeft: 4 }}>
      {isUp ? <CaretUpFilled /> : <CaretDownFilled />}
      {Math.abs(delta).toFixed(suffix === '%' ? 1 : 0)}{suffix || ''}
    </span>
  )
}

function SummaryCards({ data }: { data: MarketSummary | null }) {
  if (!data) return <Spin />
  const prev = data.prev
  const items: { title: string; value: number; color?: string; prefix?: React.ReactNode; suffix?: string; prevKey?: keyof NonNullable<MarketSummary['prev']> }[] = [
    { title: '涨停', value: data.limit_up_count, color: '#f5222d', prefix: <ArrowUpOutlined />, prevKey: 'limit_up_count' },
    { title: '爆板', value: data.broken_count, color: '#faad14', prevKey: 'broken_count' },
    { title: '爆板率', value: data.broken_rate, suffix: '%', prevKey: 'broken_rate' },
    { title: '跌停', value: data.limit_down_count, color: '#52c41a', prefix: <ArrowDownOutlined /> },
    { title: '上涨', value: data.up_count, color: '#f5222d' },
    { title: '下跌', value: data.down_count, color: '#52c41a' },
    { title: '最高板', value: data.max_board, suffix: '板', prevKey: 'max_board' },
  ]
  return (
    <Row gutter={[12, 12]}>
      {items.map(item => (
        <Col span={3} key={item.title}>
          <Card size="small">
            <Statistic
              title={item.title}
              value={item.value}
              valueStyle={{ color: item.color, fontSize: 20 }}
              prefix={item.prefix}
              suffix={item.suffix}
              precision={item.suffix === '%' ? 1 : 0}
            />
            {item.prevKey && prev && (
              <DeltaBadge
                current={item.value}
                prev={prev[item.prevKey] as number}
                suffix={item.suffix === '%' ? '%' : undefined}
              />
            )}
          </Card>
        </Col>
      ))}
      <Col span={3}>
        <Card size="small">
          <div style={{ fontSize: 12, color: '#999', marginBottom: 4 }}>{'情绪'}</div>
          <Tag color={sentimentColor[data.sentiment_level] || '#999'} style={{ fontSize: 16, padding: '4px 12px' }}>
            {data.sentiment_level}
          </Tag>
          {prev?.sentiment_level && prev.sentiment_level !== data.sentiment_level && (
            <div style={{ fontSize: 11, color: '#999', marginTop: 4 }}>{'昨日'}: {prev.sentiment_level}</div>
          )}
        </Card>
      </Col>
    </Row>
  )
}

const ladderColumns = [
  { title: '代码', dataIndex: 'stock_code', key: 'code', width: 80 },
  { title: '名称', dataIndex: 'stock_name', key: 'name', width: 80,
    render: (v: string, r: LimitUpStock) => (
      <span style={{ fontWeight: r.is_leader ? 700 : 400, color: r.is_leader ? '#f5222d' : undefined }}>
        {v}{r.is_leader ? ' *' : ''}
      </span>
    ),
  },
  { title: '涨幅', dataIndex: 'change_rate', key: 'change', width: 70,
    render: (v: number) => <span style={{ color: v >= 0 ? '#f5222d' : '#52c41a' }}>{v?.toFixed(2)}%</span>,
  },
  { title: '题材', dataIndex: 'first_plate_name', key: 'plate', width: 120, ellipsis: true },
  { title: '原因', dataIndex: 'reason', key: 'reason', ellipsis: true },
  { title: '封板时间', dataIndex: 'time', key: 'time', width: 80 },
]

function parseTierNum(tier: string): number {
  const m = tier.match(/\d+/)
  return m ? parseInt(m[0], 10) : 0
}

function BoardLadder({ data, error }: { data: LadderData | null; error: boolean }) {
  if (error) return <Card size="small"><Empty description={'连板天梯加载失败'} /></Card>
  if (!data) return <Spin />
  const tiers = Object.entries(data.tiers).sort(([a], [b]) => parseTierNum(b) - parseTierNum(a))
  return (
    <Card title={`连板天梯 (${data.total}只)`} size="small">
      {tiers.map(([tier, stocks]) => (
        <div key={tier} style={{ marginBottom: 12 }}>
          <Tag color="red" style={{ marginBottom: 4, fontSize: 14, fontWeight: 700 }}>{tier} ({stocks.length})</Tag>
          <Table
            dataSource={stocks}
            columns={ladderColumns}
            rowKey="stock_code"
            size="small"
            pagination={false}
            style={{ marginTop: 4 }}
          />
        </div>
      ))}
    </Card>
  )
}

function RelayCard({ data, error }: { data: RelayData | null; error: boolean }) {
  if (error) return <Empty description={'接力转化加载失败'} />
  if (!data) return <Spin />
  if (!data.relay || data.relay.length === 0) {
    return <Empty description={data.note || '暂无接力数据'} />
  }

  const columns = [
    {
      title: '昨日板数', dataIndex: 'from_tier', key: 'tier', width: 80,
      render: (v: number) => <Tag color="blue">{v}板</Tag>,
    },
    { title: '昨日数量', dataIndex: 'from_count', key: 'count', width: 80 },
    {
      title: '晋级', dataIndex: 'promoted', key: 'promoted', width: 60,
      render: (v: number) => <span style={{ color: '#f5222d', fontWeight: 600 }}>{v}</span>,
    },
    {
      title: '存活', dataIndex: 'survived', key: 'survived', width: 60,
      render: (v: number) => <span style={{ color: '#faad14' }}>{v}</span>,
    },
    {
      title: '爆板', dataIndex: 'broken', key: 'broken', width: 60,
      render: (v: number) => <span style={{ color: '#52c41a' }}>{v}</span>,
    },
    {
      title: '接力率', dataIndex: 'relay_rate', key: 'rate', width: 120,
      render: (v: number) => (
        <Progress
          percent={v}
          size="small"
          strokeColor={v >= 50 ? '#f5222d' : v >= 30 ? '#faad14' : '#52c41a'}
          format={pct => `${pct?.toFixed(1)}%`}
        />
      ),
    },
  ]

  return (
    <div>
      <div style={{ fontSize: 12, color: '#999', marginBottom: 8 }}>
        {data.prev_date} → {data.trade_date}
      </div>
      <Table
        dataSource={data.relay}
        columns={columns}
        rowKey="from_tier"
        size="small"
        pagination={false}
      />
    </div>
  )
}

function SectorRanking({ data, error }: { data: any[] | null; error: boolean }) {
  if (error) return <Empty description={'板块排行加载失败'} />
  if (!data) return <Spin />
  const cols = [
    { title: '板块', key: 'name', width: 120, ellipsis: true,
      render: (_: any, row: any) => row.PlateName || row.concept_name || row.col2 || row[1] || '—',
    },
    { title: '强度', key: 'intensity', width: 60,
      render: (_: any, row: any) => row.Intensity || row.concept_intensity || row.col3 || row[2] || '—',
    },
    { title: '涨幅', key: 'change', width: 70,
      render: (_: any, row: any) => {
        const n = parseFloat(row.ChangePercent || row.concept_increase || row.col4 || row[3]) || 0
        return <span style={{ color: n >= 0 ? '#f5222d' : '#52c41a' }}>{n.toFixed(2)}%</span>
      },
    },
  ]
  return (
    <Table dataSource={data.slice(0, 20)} columns={cols} rowKey={(_, i) => String(i)} size="small" pagination={false} />
  )
}

interface CapitalItem {
  name: string
  net_flow: number
  amount: number
  change: number
}

function CapitalFlowChart({ data, error }: { data: CapitalItem[] | null; error: boolean }) {
  const chartRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!chartRef.current || !data || data.length === 0) return
    const chart = echarts.init(chartRef.current)
    const top15 = data.slice(0, 15)
    chart.setOption({
      tooltip: {
        trigger: 'axis',
        formatter: (params: any) => {
          const p = params[0]
          const item = top15[p.dataIndex]
          const netStr = Math.abs(item.net_flow) >= 1e8
            ? `${(item.net_flow / 1e8).toFixed(2)}亿`
            : `${(item.net_flow / 1e4).toFixed(0)}万`
          return `${item.name}<br/>主力净额: ${netStr}<br/>涨幅: ${item.change.toFixed(2)}%`
        },
      },
      grid: { left: 80, right: 20, top: 10, bottom: 30 },
      xAxis: { type: 'value', axisLabel: { formatter: (v: number) => `${(v / 1e8).toFixed(1)}亿` } },
      yAxis: { type: 'category', data: top15.map(d => d.name).reverse(), axisLabel: { fontSize: 11 } },
      series: [{
        type: 'bar',
        data: top15.map(d => d.net_flow).reverse(),
        itemStyle: {
          color: (params: any) => params.value >= 0 ? '#f5222d' : '#52c41a',
        },
      }],
    })
    const onResize = () => chart.resize()
    window.addEventListener('resize', onResize)
    return () => { window.removeEventListener('resize', onResize); chart.dispose() }
  }, [data])

  if (error) return <Empty description={'资金流向加载失败'} />
  if (!data) return <Spin />
  return <div ref={chartRef} style={{ width: '100%', height: 380 }} />
}

interface RotationPoint {
  name: string
  change: number
  intensity: number
  net_flow: number
}

function RotationScatter({ data, error }: { data: RotationPoint[] | null; error: boolean }) {
  const chartRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!chartRef.current || !data || data.length === 0) return
    const chart = echarts.init(chartRef.current)
    chart.setOption({
      tooltip: {
        formatter: (params: any) => {
          const d = params.data
          return `${d[3]}<br/>涨幅: ${d[0].toFixed(2)}%<br/>强度: ${d[1]}<br/>净额: ${(d[2] / 1e8).toFixed(2)}亿`
        },
      },
      grid: { left: 60, right: 30, top: 30, bottom: 50 },
      xAxis: {
        name: '涨幅%',
        nameLocation: 'center',
        nameGap: 30,
        splitLine: { show: true, lineStyle: { type: 'dashed' } },
      },
      yAxis: {
        name: '强度',
        nameLocation: 'center',
        nameGap: 40,
        splitLine: { show: true, lineStyle: { type: 'dashed' } },
      },
      series: [{
        type: 'scatter',
        symbolSize: (val: number[]) => Math.min(Math.max(Math.abs(val[2]) / 1e7, 6), 30),
        data: data.map(d => [d.change, d.intensity, d.net_flow, d.name]),
        itemStyle: {
          color: (params: any) => params.data[0] >= 0 ? '#f5222d' : '#52c41a',
          opacity: 0.7,
        },
        label: {
          show: true,
          position: 'right',
          formatter: (params: any) => params.data[3],
          fontSize: 10,
          color: '#666',
        },
      }],
    })
    const onResize = () => chart.resize()
    window.addEventListener('resize', onResize)
    return () => { window.removeEventListener('resize', onResize); chart.dispose() }
  }, [data])

  if (error) return <Empty description={'板块轮动加载失败'} />
  if (!data) return <Spin />
  return <div ref={chartRef} style={{ width: '100%', height: 380 }} />
}

export default function ReplayPage() {
  const [selectedDate, setSelectedDate] = useState<string>(dayjs().format('YYYY-MM-DD'))
  const [summary, setSummary] = useState<MarketSummary | null>(null)
  const [ladder, setLadder] = useState<LadderData | null>(null)
  const [relay, setRelay] = useState<RelayData | null>(null)
  const [sectors, setSectors] = useState<any[] | null>(null)
  const [capitalFlow, setCapitalFlow] = useState<CapitalItem[] | null>(null)
  const [rotation, setRotation] = useState<RotationPoint[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [errors, setErrors] = useState({ summary: false, ladder: false, relay: false, sectors: false, capital: false, rotation: false })

  const loadData = useCallback((date: string) => {
    setLoading(true)
    setSummary(null); setLadder(null); setRelay(null); setSectors(null); setCapitalFlow(null); setRotation(null)
    setErrors({ summary: false, ladder: false, relay: false, sectors: false, capital: false, rotation: false })

    const q = `?date=${date}`
    Promise.allSettled([
      fetchApi<MarketSummary>(`/market/summary${q}`),
      fetchApi<LadderData>(`/market/ladder${q}`),
      fetchApi<RelayData>(`/market/ladder-relay${q}`),
      fetchApi<{ data: any[] }>(`/market/sectors${q}`),
      fetchApi<{ data: CapitalItem[] }>(`/market/capital-flow${q}`),
      fetchApi<{ data: RotationPoint[] }>(`/market/rotation${q}`),
    ]).then(([s, l, r, sec, cf, rot]) => {
      if (s.status === 'fulfilled') setSummary(s.value); else setErrors(e => ({ ...e, summary: true }))
      if (l.status === 'fulfilled') setLadder(l.value); else setErrors(e => ({ ...e, ladder: true }))
      if (r.status === 'fulfilled') setRelay(r.value); else setErrors(e => ({ ...e, relay: true }))
      if (sec.status === 'fulfilled') setSectors(sec.value.data); else setErrors(e => ({ ...e, sectors: true }))
      if (cf.status === 'fulfilled') setCapitalFlow(cf.value.data); else setErrors(e => ({ ...e, capital: true }))
      if (rot.status === 'fulfilled') setRotation(rot.value.data); else setErrors(e => ({ ...e, rotation: true }))
    }).finally(() => setLoading(false))
  }, [])

  useEffect(() => { loadData(selectedDate) }, [selectedDate, loadData])

  return (
    <div>
      <Row align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <DatePicker
            value={dayjs(selectedDate)}
            onChange={d => d && setSelectedDate(d.format('YYYY-MM-DD'))}
            allowClear={false}
            style={{ width: 160 }}
          />
        </Col>
        <Col style={{ marginLeft: 12, fontSize: 13, color: '#999' }}>
          {summary?.prev_date && `对比日: ${summary.prev_date}`}
        </Col>
      </Row>

      {loading && <Spin size="large" style={{ display: 'block', margin: '60px auto' }} />}

      {!loading && (
        <>
          <SummaryCards data={summary} />
          <Row gutter={16} style={{ marginTop: 16 }}>
            <Col span={16}>
              <BoardLadder data={ladder} error={errors.ladder} />
              <Card title={'接力转化率'} size="small" style={{ marginTop: 16 }}>
                <RelayCard data={relay} error={errors.relay} />
              </Card>
            </Col>
            <Col span={8}>
              <Card size="small">
                <Tabs
                  type="card"
                  size="small"
                  items={[
                    { key: 'sectors', label: '主线题材', children: <SectorRanking data={sectors} error={errors.sectors} /> },
                    { key: 'capital', label: '资金流向', children: <CapitalFlowChart data={capitalFlow} error={errors.capital} /> },
                    { key: 'rotation', label: '板块轮动', children: <RotationScatter data={rotation} error={errors.rotation} /> },
                  ]}
                />
              </Card>
            </Col>
          </Row>
        </>
      )}
    </div>
  )
}
