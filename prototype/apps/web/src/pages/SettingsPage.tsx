import { useEffect, useState } from 'react'
import { Card, Table, Typography, Row, Col, Statistic, Space, Button } from 'antd'
import { fetchApi } from '../api/client'
import type { AnyData } from '../api/types'

const { Title } = Typography

export default function SettingsPage() {
  const [events, setEvents] = useState<AnyData[]>([])
  const [stats, setStats] = useState<{ event: string; cnt: number }[]>([])
  const [loading, setLoading] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const [e, s] = await Promise.all([
        fetchApi<{ events: AnyData[] }>('/events/mine', { limit: '100' }),
        fetchApi<{ stats: { event: string; cnt: number }[] }>('/events/stats', { days: '7' }),
      ])
      setEvents(e.events)
      setStats(s.stats)
    } finally { setLoading(false) }
  }

  useEffect(() => {
    let cancelled = false
    const run = async () => {
      setLoading(true)
      try {
        const [e, s] = await Promise.all([
          fetchApi<{ events: AnyData[] }>('/events/mine', { limit: '100' }),
          fetchApi<{ stats: { event: string; cnt: number }[] }>('/events/stats', { days: '7' }),
        ])
        if (!cancelled) {
          setEvents(e.events)
          setStats(s.stats)
        }
      } finally { if (!cancelled) setLoading(false) }
    }
    void run()
    return () => { cancelled = true }
  }, [])

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Title level={3} style={{ margin: 0 }}>我的使用统计</Title>
        <Button onClick={load}>刷新</Button>
      </Space>
      <Row gutter={12} style={{ marginBottom: 16 }}>
        {stats.slice(0, 4).map((s) => (
          <Col key={s.event} span={6}>
            <Card size="small"><Statistic title={s.event} value={s.cnt} /></Card>
          </Col>
        ))}
      </Row>
      <Card title="最近 100 条埋点">
        <Table
          size="small" loading={loading} rowKey={(_, i) => String(i)}
          pagination={{ pageSize: 20 }}
          dataSource={events}
          columns={[
            { title: '时间', dataIndex: 'created_at', width: 180 },
            { title: '事件', dataIndex: 'event', width: 160 },
            { title: '页面', dataIndex: 'page', width: 200 },
            { title: '属性', dataIndex: 'props', ellipsis: true },
          ]}
        />
      </Card>
    </div>
  )
}
