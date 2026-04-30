import { useEffect, useRef, useState } from 'react'
import { Alert, Card, Table, Tag, Spin, Statistic, Row, Col, Button, Space, Select, Empty } from 'antd'
import { PieChartOutlined, RobotOutlined, ExperimentOutlined } from '@ant-design/icons'
import * as echarts from 'echarts'
import { Link } from 'react-router-dom'
import { fetchApi } from '../api/client'
import { askAI } from '../api/copilot'
import MockBanner from '../components/MockBanner'
import type { AnyData } from '../api/types'

const REASON_THEME: Record<string, { color: string; tagColor: string; icon: string }> = {
  '抛压': { color: '#cf1322', tagColor: 'red', icon: '📉' },
  '撤单': { color: '#d46b08', tagColor: 'orange', icon: '🔙' },
  '大盘': { color: '#096dd9', tagColor: 'blue', icon: '📊' },
  '跟风不足': { color: '#531dab', tagColor: 'purple', icon: '🐢' },
  '消息利空': { color: '#d4380d', tagColor: 'volcano', icon: '💥' },
  '尾盘': { color: '#d4b106', tagColor: 'gold', icon: '🌅' },
  '其他': { color: '#8c8c8c', tagColor: 'default', icon: '❓' },
}

function safeNum(v: unknown, fallback = 0) {
  const n = Number(v)
  return Number.isFinite(n) ? n : fallback
}

function normalizeCase(item: AnyData) {
  return {
    ...item,
    stock_code: item.stock_code ?? item.SecurityCode,
    stock_name: item.stock_name ?? item.SecurityName,
    first_plate_name: item.first_plate_name ?? item.PlateName ?? item.plate_name ?? item.concept_name ?? item.plate,
    change_rate: safeNum(item.change_rate ?? item.ChangePercent, item.change_rate),
    board_count: safeNum(item.board_count, item.board_count),
  }
}

function normalizeBrokenData(payload: AnyData) {
  const byReason = payload?.by_reason || {}
  const nextByReason = Object.fromEntries(Object.entries(byReason).map(([reason, value]: [string, AnyData]) => [
    reason,
    {
      ...value,
      cases: (value?.cases || []).map(normalizeCase),
    },
  ]))
  return { ...payload, by_reason: nextByReason }
}

function PieChart({ byReason }: { byReason: Record<string, { count: number }> }) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!ref.current) return
    const chart = echarts.init(ref.current)
    const data = Object.entries(byReason).map(([name, { count }]) => ({
      name, value: count, itemStyle: { color: REASON_THEME[name]?.color || '#8c8c8c' },
    }))
    chart.setOption({
      tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
      series: [{ type: 'pie', radius: ['40%', '70%'], data, label: { fontSize: 12 }, emphasis: { itemStyle: { shadowBlur: 10 } } }],
    })
    const onResize = () => chart.resize()
    window.addEventListener('resize', onResize)
    return () => { window.removeEventListener('resize', onResize); chart.dispose() }
  }, [byReason])
  return <div ref={ref} style={{ width: '100%', height: 220 }} />
}

function ReasonCards({ byReason }: { byReason: Record<string, { count: number; cases: AnyData[] }> }) {
  const entries = Object.entries(byReason).sort(([, a], [, b]) => b.count - a.count)
  return (
    <Row gutter={[12, 12]}>
      {entries.map(([reason, { count, cases }]) => {
        const theme = REASON_THEME[reason] || REASON_THEME['其他']
        const top = cases[0]
        return (
          <Col xs={12} md={8} lg={4} key={reason}>
            <Card size="small" style={{ borderTop: `3px solid ${theme.color}` }} bodyStyle={{ padding: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
                <span style={{ fontSize: 18 }}>{theme.icon}</span>
                <Tag color={theme.tagColor}>{reason}</Tag>
              </div>
              <Statistic value={count} suffix="只" valueStyle={{ fontSize: 22, fontWeight: 700, color: theme.color }} />
              {top && (
                <div style={{ marginTop: 6, fontSize: 12, color: '#666' }}>
                  典型：<Link to={`/stock/${top.stock_code}`}>{top.stock_name}</Link>
                  <span style={{ marginLeft: 4, color: '#fa8c16' }}>{top.broken_time}</span>
                </div>
              )}
            </Card>
          </Col>
        )
      })}
    </Row>
  )
}

export default function BrokenCasesPage() {
  const [data, setData] = useState<AnyData>(null)
  const [loading, setLoading] = useState(true)
  const [recs, setRecs] = useState<string[]>([])
  const [filterReason, setFilterReason] = useState<string>('all')
  const [isMock, setIsMock] = useState(false)
  const [err, setErr] = useState('')
  const [meta, setMeta] = useState<{ source?: string; data_status?: string; mock?: boolean; message?: string }>({})

  useEffect(() => {
    fetchApi<AnyData>('/analysis/broken-cases')
      .then(d => {
        setData(normalizeBrokenData(d))
        setIsMock(!!d.mock)
        setMeta({ source: d.source, data_status: d.data_status, mock: d.mock, message: d.message })
        setErr('')
      })
      .catch(() => {
        setMeta({})
        setErr('炸板案例接口不可用，当前不展示案例数据。')
      })
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (!data) return
    const total = data.total || 0
    const sentiment = total > 20 ? '高潮' : total > 10 ? '回暖' : total > 5 ? '中性' : '低迷'
    const maxBoard = Math.max(0, ...Object.values(data.by_reason || {}).flatMap((r: AnyData) => (r.cases || []).map((c: AnyData) => c.board_count || 0)))
    fetchApi<{ recommendations: string[] }>(`/analysis/strategy-recommend?sentiment=${sentiment}&max_board=${maxBoard}`)
      .then(res => setRecs(res.recommendations || []))
      .catch(() => {})
  }, [data])

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '120px auto' }} />

  const byReason = data?.by_reason || {}
  const allCases: AnyData[] = Object.values(byReason).flatMap((r: AnyData) => r.cases || [])
  const filteredCases = filterReason === 'all' ? allCases : (byReason[filterReason]?.cases || [])
  const isEmpty = !err && allCases.length === 0

  const columns = [
    { title: '代码', dataIndex: 'stock_code', key: 'stock_code', width: 75, render: (v: string) => <Link to={`/stock/${v}`}>{v}</Link> },
    { title: '名称', dataIndex: 'stock_name', key: 'stock_name', width: 80, render: (v: string, r: AnyData) => <Link to={`/stock/${r.stock_code}`} style={{ fontWeight: r.board_count >= 2 ? 700 : 400 }}>{v}</Link> },
    { title: '连板', dataIndex: 'board_count', key: 'b', width: 50, render: (v: number) => v >= 2 ? <Tag color="red">{v}板</Tag> : <span>{v || 1}</span> },
    { title: '涨幅', dataIndex: 'change_rate', key: 'ch', width: 65, render: (v: number) => {
      const n = safeNum(v)
      return <span style={{ color: n >= 0 ? '#f5222d' : '#52c41a' }}>{n.toFixed(2)}%</span>
    } },
    { title: '原因', dataIndex: 'reason_type', key: 'rt', width: 80, render: (v: string) => <Tag color={REASON_THEME[v]?.tagColor || 'default'}>{v || '—'}</Tag> },
    { title: '详情', dataIndex: 'reason_raw', key: 'rr', ellipsis: true, render: (v: string) => v || '—' },
    { title: '题材', dataIndex: 'first_plate_name', key: 'p', width: 90, ellipsis: true, render: (v: string) => v || '—' },
    { title: '时间', dataIndex: 'broken_time', key: 't', width: 65, render: (v: string) => <span style={{ fontSize: 12, color: '#666' }}>{v}</span> },
  ]

  return (
    <div>
      <MockBanner show={isMock} />
      {err && <Alert type="error" showIcon message={err} style={{ marginBottom: 12 }} />}
      {isEmpty && <Alert type="info" showIcon message="暂无炸板案例" description="接口返回真实空状态，未展示示例案例。" style={{ marginBottom: 12 }} />}
      {!err && (
        <Alert
          type={meta.mock ? 'warning' : meta.data_status === 'empty' ? 'info' : 'success'}
          showIcon
          message={`数据源：${meta.source || '未知源'} / 状态：${meta.data_status || '未知状态'}${meta.mock ? ' / mock' : ''}`}
          description={meta.message}
          style={{ marginBottom: 12 }}
        />
      )}

      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 16 }}>
        <Statistic title="炸板" value={data?.total || 0} suffix="只" valueStyle={{ color: '#fa8c16', fontSize: 20 }} />
      </div>

      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col xs={24} lg={16}><ReasonCards byReason={byReason} /></Col>
        <Col xs={24} lg={8}>
          <Card size="small" title={<span><PieChartOutlined /> 原因分布</span>} bodyStyle={{ padding: 8 }}>
            {Object.keys(byReason).length > 0 ? <PieChart byReason={byReason} /> : <Empty description="暂无原因分布" />}
          </Card>
        </Col>
      </Row>

      {recs.length > 0 && (
        <Card size="small" style={{ marginBottom: 16, borderLeft: '4px solid #1677ff' }}>
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 6 }}><ExperimentOutlined style={{ color: '#1677ff' }} /> 策略推荐</div>
          <Space wrap>{recs.map((r, i) => <Tag key={i} color="blue" style={{ fontSize: 13, padding: '4px 12px' }}>{r}</Tag>)}</Space>
        </Card>
      )}

      <Card
        size="small"
        title={<span>案例详情 ({filteredCases.length})</span>}
        extra={
          <Select value={filterReason} onChange={setFilterReason} size="small" style={{ width: 120 }}
            options={[{ value: 'all', label: '全部原因' }, ...Object.keys(byReason).map(r => ({ value: r, label: r }))]}
          />
        }
        style={{ marginBottom: 16 }}
      >
        <Table dataSource={filteredCases} columns={columns} rowKey={(r, i) => r.stock_code || String(i)} size="small" pagination={{ pageSize: 20 }} locale={{ emptyText: <Empty description="暂无案例详情" /> }} />
      </Card>

      <Card size="small" title={<span><RobotOutlined style={{ color: '#1677ff' }} /> 向 AI 追问</span>}>
        <Space wrap>
          <Button type="primary" icon={<RobotOutlined />}
            onClick={() => { const topReason = Object.entries(byReason).sort(([, a]: AnyData, [, b]: AnyData) => b.count - a.count)[0]; askAI(`今日炸板 ${data?.total || 0} 只，最多的原因是【${topReason?.[0] || '未知'}】(${(topReason?.[1] as AnyData)?.count || 0}只)。分析炸板集中原因、对市场情绪的影响，以及明日操作策略。`) }}
          >
            炸板深度分析
          </Button>
          <Button onClick={() => askAI('今日高位板（2板以上）炸板的股票有哪些特征？是系统性风险还是个股问题？')}>高位炸板风险</Button>
          <Button onClick={() => askAI('炸板后次日反包的概率有多大？什么条件下值得参与炸板反包？')}>炸板反包策略</Button>
        </Space>
      </Card>

      <div style={{ marginTop: 12, color: '#999', fontSize: 11, textAlign: 'center' }}>以上分析仅供参考，不构成投资建议。</div>
    </div>
  )
}
