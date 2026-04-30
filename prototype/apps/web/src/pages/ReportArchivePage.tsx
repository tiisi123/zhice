import { useEffect, useState } from 'react'
import { Card, Table, Spin, Tag, Button, Empty, Timeline, Space, Input, Select } from 'antd'
import { FileTextOutlined, RobotOutlined, ReloadOutlined, SearchOutlined, HistoryOutlined } from '@ant-design/icons'
import { Link } from 'react-router-dom'
import Markdown from 'react-markdown'
import { fetchApi } from '../api/client'
import { askAI } from '../api/copilot'
import type { AnyData } from '../api/types'

const SENT_COLORS: Record<string, string> = { '冰点': 'blue', '低迷': 'cyan', '中性': 'default', '回暖': 'orange', '高潮': 'red' }

interface ArchiveItem {
  trade_date: string
  sentiment_level: string
  sentiment_score: number
  limit_up_count: number
  max_board: number
  broken_count: number
  broken_rate: number
  seal_success_rate: number
}

function MarketArchivePanel() {
  const [items, setItems] = useState<ArchiveItem[]>([])
  const [loading, setLoading] = useState(false)
  const [keyword, setKeyword] = useState('')
  const [sentiment, setSentiment] = useState<string>('')

  const load = () => {
    setLoading(true)
    const params = new URLSearchParams({ limit: '120' })
    if (keyword.trim()) params.set('keyword', keyword.trim())
    if (sentiment) params.set('sentiment', sentiment)
    fetchApi<{ items: ArchiveItem[] }>(`/market/archive?${params.toString()}`)
      .then(r => setItems(r.items || []))
      .catch(() => setItems([]))
      .finally(() => setLoading(false))
  }
  useEffect(() => { load() }, []) // eslint-disable-line

  return (
    <Card
      size="small"
      title={<span><HistoryOutlined style={{ color: '#1677ff' }} /> 历史复盘存档（M1-07）· 共 {items.length} 个交易日</span>}
      extra={
        <Space>
          <Input
            prefix={<SearchOutlined />}
            placeholder="日期或情绪关键词，如 2025-04 / 高潮"
            value={keyword}
            onChange={e => setKeyword(e.target.value)}
            onPressEnter={load}
            style={{ width: 240 }}
            allowClear
          />
          <Select
            placeholder="情绪过滤"
            style={{ width: 120 }}
            allowClear
            value={sentiment || undefined}
            onChange={v => setSentiment(v || '')}
            options={['高潮', '回暖', '中性', '低迷', '冰点'].map(v => ({ value: v, label: v }))}
          />
          <Button type="primary" onClick={load} loading={loading}>搜索</Button>
        </Space>
      }
    >
      <Table<ArchiveItem>
        size="small"
        loading={loading}
        rowKey="trade_date"
        dataSource={items}
        pagination={{ pageSize: 15, showSizeChanger: false }}
        columns={[
          {
            title: '交易日', dataIndex: 'trade_date', width: 110,
            render: (d: string) => <Link to={`/replay?date=${d}`}>{d}</Link>,
          },
          {
            title: '情绪', dataIndex: 'sentiment_level', width: 80,
            render: (s: string) => s ? <Tag color={SENT_COLORS[s]}>{s}</Tag> : '—',
          },
          { title: '情绪分', dataIndex: 'sentiment_score', width: 80, render: (v: number) => v?.toFixed?.(0) ?? v },
          { title: '涨停', dataIndex: 'limit_up_count', width: 70 },
          { title: '最高板', dataIndex: 'max_board', width: 80, render: (v: number) => v ? `${v}板` : '—' },
          { title: '炸板', dataIndex: 'broken_count', width: 70 },
          { title: '炸板率', dataIndex: 'broken_rate', width: 90, render: (v: number) => v ? `${v.toFixed?.(1)}%` : '—' },
          { title: '封板率', dataIndex: 'seal_success_rate', width: 90, render: (v: number) => v ? `${v.toFixed?.(1)}%` : '—' },
          {
            title: '操作', width: 100,
            render: (_: AnyData, r: ArchiveItem) => (
              <Button size="small" type="link"
                onClick={() => askAI(`回看 ${r.trade_date}：情绪${r.sentiment_level}（${r.sentiment_score}分），涨停${r.limit_up_count}最高${r.max_board}板，炸板率${r.broken_rate?.toFixed?.(1)}%。这一天的市场特征是什么？后续 5 日表现？`)}
              >AI 回看</Button>
            ),
          },
        ]}
      />
      {items.length === 0 && !loading && <Empty description="暂无存档。完成几次复盘后会自动累积。" />}
    </Card>
  )
}

export default function ReportArchivePage() {
  const [reports, setReports] = useState<AnyData[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedReport, setSelectedReport] = useState<AnyData>(null)

  const loadReports = () => {
    setLoading(true)
    fetchApi<{ reports: AnyData[] }>('/analysis/report-archive')
      .then(res => setReports(res.reports || []))
      .catch(console.error)
      .finally(() => setLoading(false))
  }

  useEffect(() => { loadReports() }, [])

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '120px auto' }} />

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h2 style={{ margin: 0 }}><FileTextOutlined style={{ color: '#1677ff' }} /> 复盘报告存档</h2>
        <Button icon={<ReloadOutlined />} onClick={loadReports} size="small">刷新</Button>
      </div>

      {/* PRD M1-07：市场快照存档（按日期/情绪搜索） */}
      <div style={{ marginBottom: 16 }}>
        <MarketArchivePanel />
      </div>

      {reports.length === 0 ? (
        <Card size="small"><Empty description="暂无存档报告。在 AI Copilot 中生成复盘报告后点击「保存」按钮即可存档。" /></Card>
      ) : (
        <div style={{ display: 'flex', gap: 16 }}>
          <Card size="small" style={{ flex: 1 }} title={`共 ${reports.length} 篇报告`}>
            <Timeline
              items={reports.slice().reverse().map(r => ({
                color: SENT_COLORS[r.sentiment] || 'gray',
                children: (
                  <div style={{ cursor: 'pointer', padding: '4px 0' }} onClick={() => setSelectedReport(r)}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <b>{r.trade_date}</b>
                      {r.sentiment && <Tag color={SENT_COLORS[r.sentiment]}>{r.sentiment}</Tag>}
                    </div>
                    <div style={{ fontSize: 12, color: '#666', marginTop: 2 }}>
                      涨停 {r.limit_up || '—'} · 炸板 {r.broken || '—'}
                    </div>
                  </div>
                ),
              }))}
            />
          </Card>

          <Card size="small" style={{ flex: 2 }}
            title={selectedReport ? `${selectedReport.trade_date} 复盘报告` : '选择报告查看'}
            extra={selectedReport && (
              <Button type="link" icon={<RobotOutlined />}
                onClick={() => askAI(`基于这篇复盘报告（${selectedReport.trade_date}，情绪${selectedReport.sentiment}，涨停${selectedReport.limit_up}），分析报告中提到的主线是否延续，给出后续跟踪建议。`)}
              >AI 追踪</Button>
            )}
          >
            {selectedReport ? (
              <div style={{ maxHeight: 500, overflow: 'auto', fontSize: 13, lineHeight: 1.8 }}>
                <Markdown>{selectedReport.report}</Markdown>
              </div>
            ) : (
              <Empty description="点击左侧时间线查看报告详情" />
            )}
          </Card>
        </div>
      )}

      {reports.length >= 3 && (
        <Card size="small" title={<span><RobotOutlined style={{ color: '#1677ff' }} /> 向 AI 追问</span>} style={{ marginTop: 16 }}>
          <Space wrap>
            <Button type="primary" icon={<RobotOutlined />}
              onClick={() => {
                const recent = reports.slice(-5)
                const summary = recent.map(r => `${r.trade_date}(${r.sentiment},涨停${r.limit_up})`).join('、')
                askAI(`最近5天复盘：${summary}。总结市场趋势，判断情绪方向，给出下周操作建议。`)
              }}>
              周趋势总结
            </Button>
            <Button onClick={() => askAI('分析最近存档的复盘报告，哪些主线题材反复出现？有没有持续性最强的方向？')}>
              主线追踪
            </Button>
          </Space>
        </Card>
      )}

      <div style={{ marginTop: 12, color: '#999', fontSize: 11, textAlign: 'center' }}>以上分析仅供参考，不构成投资建议。</div>
    </div>
  )
}
