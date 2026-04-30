import { useEffect, useState } from 'react'
import { Card, Tabs, Select, Button, Table, Typography, Input, Space, Tag, Form, InputNumber, message, Alert } from 'antd'
import { fetchApi, postApi } from '../api/client'

const { Title, Paragraph } = Typography
const { TextArea } = Input

interface SimResult {
  trigger: string
  direct: { theme: string; probability: number; avg_lag_days: number }[]
  indirect: { theme: string; probability: number; avg_lag_days: number }[]
  known_themes: string[]
}

interface NoveltyRow {
  name?: string
  PlateName?: string
  id?: string
  novelty?: 'new' | 'existing' | 'revived'
  first_seen?: string
  LimitUpNum?: number
  ChangePercent?: number
}

function renderProb(p: number) {
  const pct = Math.round(p * 100)
  const color = p >= 0.6 ? 'red' : p >= 0.4 ? 'orange' : 'default'
  return <Tag color={color}>{pct}%</Tag>
}

function SimulateTab() {
  const [themes, setThemes] = useState<string[]>([])
  const [trigger, setTrigger] = useState<string | undefined>()
  const [result, setResult] = useState<SimResult | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    fetchApi<{ themes: string[] }>('/rotation/known-themes').then((r) => setThemes(r.themes))
  }, [])

  const run = async () => {
    if (!trigger) return
    setLoading(true)
    try {
      const r = await postApi<SimResult>('/rotation/simulate', { trigger_theme: trigger, days: 3 })
      setResult(r)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Select
          showSearch
          style={{ width: 260 }}
          placeholder="选择或输入触发题材"
          value={trigger}
          onChange={setTrigger}
          options={themes.map((t) => ({ value: t, label: t }))}
        />
        <Button type="primary" onClick={run} loading={loading} disabled={!trigger}>推演</Button>
      </Space>
      {result && (
        <>
          <Alert
            style={{ marginBottom: 12 }}
            type="info"
            message={<span>触发题材：<b>{result.trigger}</b>，模型基于产业链传导矩阵推演。</span>}
          />
          <Card title="一级传导（直接关联）" size="small" style={{ marginBottom: 12 }}>
            <Table
              size="small" pagination={false} rowKey="theme" dataSource={result.direct}
              columns={[
                { title: '跟涨题材', dataIndex: 'theme' },
                { title: '跟涨概率', dataIndex: 'probability', render: renderProb, align: 'right' },
                { title: '平均滞后(日)', dataIndex: 'avg_lag_days', align: 'right' },
              ]}
            />
          </Card>
          <Card title="二级传导（间接）" size="small">
            <Table
              size="small" pagination={false} rowKey="theme" dataSource={result.indirect}
              columns={[
                { title: '跟涨题材', dataIndex: 'theme' },
                { title: '跟涨概率', dataIndex: 'probability', render: renderProb, align: 'right' },
                { title: '累计滞后(日)', dataIndex: 'avg_lag_days', align: 'right' },
              ]}
            />
          </Card>
        </>
      )}
    </div>
  )
}

function NoveltyTab() {
  const [data, setData] = useState<NoveltyRow[]>([])
  const [loading, setLoading] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const r = await fetchApi<{ themes: NoveltyRow[] }>('/rotation/novelty', { days: '3' })
      setData(r.themes || [])
    } finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  return (
    <Card>
      <Table
        size="small"
        loading={loading}
        pagination={{ pageSize: 20 }}
        rowKey={(r) => r.PlateName || r.name || r.id || Math.random().toString()}
        dataSource={data}
        columns={[
          {
            title: '题材/板块',
            render: (_, r) => r.PlateName || r.name || r.id,
          },
          {
            title: '新旧',
            dataIndex: 'novelty',
            render: (v) => v === 'new' ? <Tag color="magenta">首次出现</Tag> : v === 'revived' ? <Tag color="volcano">重新激活</Tag> : <Tag>既有</Tag>,
          },
          { title: '首次出现', dataIndex: 'first_seen', width: 120 },
          { title: '涨停数', dataIndex: 'LimitUpNum', width: 80, align: 'right' as const },
          { title: '板块涨幅%', dataIndex: 'ChangePercent', width: 100, align: 'right' as const },
        ]}
      />
    </Card>
  )
}

function GapTab() {
  const [news, setNews] = useState('')
  const [changeRate, setChangeRate] = useState(5)
  const [volRatio, setVolRatio] = useState(1.2)
  const [result, setResult] = useState<{ impact: number; reaction: number; gap: number; label: string } | null>(null)

  const run = async () => {
    if (!news.trim()) { message.warning('请输入消息/事件'); return }
    const r = await postApi('/rotation/expectation-gap', { news, change_rate: changeRate, vol_ratio: volRatio })
    setResult(r)
  }

  return (
    <Card>
      <Paragraph type="secondary">输入利好消息 + 股价/量能反应，量化「预期差」。</Paragraph>
      <Form layout="vertical" style={{ maxWidth: 640 }}>
        <Form.Item label="消息/事件描述">
          <TextArea rows={3} value={news} onChange={(e) => setNews(e.target.value)} placeholder="例：某公司获得政府大额补贴订单..." />
        </Form.Item>
        <Form.Item label="次日涨幅(%)">
          <InputNumber value={changeRate} onChange={(v) => setChangeRate(v ?? 0)} />
        </Form.Item>
        <Form.Item label="量比">
          <InputNumber value={volRatio} step={0.1} onChange={(v) => setVolRatio(v ?? 1)} />
        </Form.Item>
        <Button type="primary" onClick={run}>评估</Button>
      </Form>
      {result && (
        <Alert
          style={{ marginTop: 16 }}
          type={result.gap > 0.25 ? 'success' : result.gap < -0.25 ? 'warning' : 'info'}
          showIcon
          message={result.label}
          description={
            <Space size="large">
              <span>利好强度：<b>{result.impact}</b></span>
              <span>股价反应：<b>{result.reaction}</b></span>
              <span>预期差：<b>{result.gap}</b></span>
            </Space>
          }
        />
      )}
    </Card>
  )
}

function ThemeHistoryTab() {
  const [theme, setTheme] = useState('')
  const [data, setData] = useState<{ date: string; intensity: number; change_rate: number }[]>([])
  const [loading, setLoading] = useState(false)

  const run = async () => {
    if (!theme.trim()) return
    setLoading(true)
    try {
      const r = await fetchApi<{ trajectory: any[] }>(`/rotation/theme-history/${encodeURIComponent(theme)}`, { days: '90' })
      setData(r.trajectory || [])
    } finally { setLoading(false) }
  }

  return (
    <Card>
      <Space style={{ marginBottom: 16 }}>
        <Input placeholder="题材名，如 AI算力" value={theme} onChange={(e) => setTheme(e.target.value)} onPressEnter={run} style={{ width: 220 }} />
        <Button type="primary" onClick={run} loading={loading}>查看历史轨迹</Button>
      </Space>
      <Table
        size="small" pagination={{ pageSize: 30 }} rowKey="date" dataSource={data}
        columns={[
          { title: '日期', dataIndex: 'date', width: 120 },
          { title: '板块强度', dataIndex: 'intensity', align: 'right' },
          { title: '涨幅%', dataIndex: 'change_rate', align: 'right' },
        ]}
      />
    </Card>
  )
}

export default function RotationPage() {
  return (
    <div>
      <Title level={3}>轮动推演 / 题材工坊</Title>
      <Tabs
        items={[
          { key: 'sim', label: '轮动推演模拟', children: <SimulateTab /> },
          { key: 'novelty', label: '新题材识别', children: <NoveltyTab /> },
          { key: 'gap', label: '预期差评估', children: <GapTab /> },
          { key: 'history', label: '题材历史复盘', children: <ThemeHistoryTab /> },
        ]}
      />
    </div>
  )
}
