import { useEffect, useState } from 'react'
import { Card, Tabs, Table, Tag, Space, Input, Button, Select, Typography, Timeline, Alert, Spin } from 'antd'
import { fetchApi } from '../api/client'
import Disclaimer from '../components/Disclaimer'
import type { AnyData } from '../api/types'

const { Title, Paragraph } = Typography

function AnnouncementsTab() {
  const [days, setDays] = useState(7)
  const [kind, setKind] = useState<string | undefined>()
  const [rows, setRows] = useState<AnyData[]>([])
  const [loading, setLoading] = useState(false)
  const [status, setStatus] = useState<AnyData>(null)

  const load = async () => {
    setLoading(true)
    try {
      const r = await fetchApi<{ items: AnyData[] }>('/research/announcements',
        { days: String(days), ...(kind ? { kind } : {}) })
      setRows(r.items)
      setStatus({ source: (r as AnyData).source, data_status: (r as AnyData).data_status, mock: (r as AnyData).mock, message: (r as AnyData).message })
    } finally { setLoading(false) }
  }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { void load() }, [days, kind])

  return (
    <div>
      <Space style={{ marginBottom: 12 }} wrap>
        <Select value={days} onChange={setDays} options={[3, 7, 14, 30].map((d) => ({ value: d, label: `近 ${d} 天` }))} />
        <Select
          allowClear value={kind} onChange={setKind}
          placeholder="公告类型"
          style={{ width: 160 }}
          options={['业绩预告','重大合同','股东增减持','回购预案','高管变动','资产重组','分红派息','定增/可转债'].map((k) => ({ value: k, label: k }))}
        />
        <Button onClick={load}>刷新</Button>
      </Space>
      {status && (
        <Alert
          type={status.mock ? 'warning' : 'info'}
          showIcon
          style={{ marginBottom: 12 }}
          message={`公告数据：${status.source || 'unknown'} / ${status.data_status || 'unknown'}`}
          description={status.message || '研究中心公告用于内测展示，生产以真实公告源为准。'}
        />
      )}
      <Table
        size="small" loading={loading} rowKey={(r, i) => `${r.date}-${r.code}-${i}`}
        pagination={{ pageSize: 20 }}
        dataSource={rows}
        columns={[
          { title: '日期', dataIndex: 'date', width: 110 },
          { title: '代码', dataIndex: 'code', width: 90 },
          { title: '名称', dataIndex: 'name', width: 120 },
          { title: '类别', dataIndex: 'kind', width: 120, render: (v: string, r: AnyData) => <Tag color={r.color}>{v}</Tag> },
          { title: '影响', dataIndex: 'impact', width: 80, render: (v: string) => <Tag color={v === '正面' ? 'red' : v === '负面' ? 'green' : 'default'}>{v}</Tag> },
          { title: '标题', dataIndex: 'title', ellipsis: true },
          { title: '摘要', dataIndex: 'summary', ellipsis: true },
        ]}
      />
    </div>
  )
}

function InterpretTab() {
  const [code, setCode] = useState('600519')
  const [data, setData] = useState<AnyData>(null)
  const [loading, setLoading] = useState(false)
  const [status, setStatus] = useState<AnyData>(null)

  const load = async () => {
    setLoading(true)
    try {
      const r = await fetchApi<AnyData>(`/research/interpret/${code}`)
      setData(r.data)
      setStatus({ source: r.source, data_status: r.data_status, mock: r.mock, message: r.message })
    } catch (e) {
      setData({ summary: '获取失败：' + (e as Error)?.message, highlights: [], risks: [] })
      setStatus(null)
    } finally { setLoading(false) }
  }

  return (
    <div>
      <Space style={{ marginBottom: 12 }}>
        <Input value={code} onChange={(e) => setCode(e.target.value)} style={{ width: 120 }} />
        <Button type="primary" onClick={load} loading={loading}>生成解读</Button>
      </Space>
      {loading && <Spin />}
      {status && (
        <Alert
          type={status.mock ? 'warning' : 'info'}
          showIcon
          style={{ marginBottom: 12 }}
          message={`解读基础数据：${status.source || 'unknown'} / ${status.data_status || 'unknown'}`}
          description={status.message || '解读为规则推演，需结合基础数据状态判断。'}
        />
      )}
      {data && !loading && (
        <Card>
          <pre style={{ whiteSpace: 'pre-wrap', fontSize: 13, lineHeight: 1.9 }}>{data.summary}</pre>
        </Card>
      )}
    </div>
  )
}

function AltDataTab() {
  const [industry, setIndustry] = useState<string | undefined>()
  const [rows, setRows] = useState<AnyData[]>([])
  const [status, setStatus] = useState<AnyData>(null)

  const load = async () => {
    const r = await fetchApi<{ items: AnyData[] }>('/research/alt-data', industry ? { industry } : undefined)
    setRows(r.items)
    setStatus({ source: (r as AnyData).source, data_status: (r as AnyData).data_status, mock: (r as AnyData).mock, message: (r as AnyData).message })
  }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { void load() }, [industry])

  return (
    <div>
      <Space style={{ marginBottom: 12 }}>
        <Select
          allowClear placeholder="筛选行业" value={industry} onChange={setIndustry} style={{ width: 180 }}
          options={['物流','能源','科技','半导体','锂电','农业','新能源车','家电','医药'].map((i) => ({ value: i, label: i }))}
        />
      </Space>
      {status && (
        <Alert
          type={status.mock ? 'warning' : 'info'}
          showIcon
          style={{ marginBottom: 12 }}
          message={`另类数据：${status.source || 'unknown'} / ${status.data_status || 'unknown'}`}
          description={status.message || '另类数据如为样例，不可作为真实投研结论。'}
        />
      )}
      <Table
        rowKey="name" size="small" pagination={false} dataSource={rows}
        columns={[
          { title: '指标', dataIndex: 'name' },
          { title: '行业', dataIndex: 'industry' },
          { title: '最新值', dataIndex: 'value', align: 'right' as const },
          { title: '同比%', dataIndex: 'yoy', align: 'right' as const,
            render: (v: number) => <span style={{ color: v >= 0 ? '#f5222d' : '#389e0d' }}>{v}</span> },
          { title: '近期变化', dataIndex: 'delta', align: 'right' as const,
            render: (v: number) => <Tag color={v >= 0 ? 'red' : 'green'}>{v > 0 ? '+' : ''}{v}</Tag> },
          { title: '趋势', dataIndex: 'trend',
            render: (v: string) => v === 'up' ? <Tag color="red">↑ 上行</Tag> : v === 'down' ? <Tag color="green">↓ 下行</Tag> : <Tag>→ 横盘</Tag> },
        ]}
      />
      <Alert style={{ marginTop: 12 }} type="info" showIcon
        message="另类数据示例：物流/用电/招聘/晶圆价格/船运指数等，真实接入需对接官方/商业数据源。" />
    </div>
  )
}

function SellsideTab() {
  const [code, setCode] = useState('600519')
  const [rows, setRows] = useState<AnyData[]>([])
  const [status, setStatus] = useState<AnyData>(null)

  const load = async () => {
    const r = await fetchApi<{ timeline: AnyData[] }>(`/research/sellside/${code}`)
    setRows(r.timeline)
    setStatus({ source: (r as AnyData).source, data_status: (r as AnyData).data_status, mock: (r as AnyData).mock, message: (r as AnyData).message })
  }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { void load() }, [code])

  return (
    <div>
      <Space style={{ marginBottom: 12 }}>
        <Input value={code} onChange={(e) => setCode(e.target.value)} style={{ width: 120 }} />
        <Button type="primary" onClick={load}>查看时间线</Button>
      </Space>
      {status && (
        <Alert
          type={status.mock ? 'warning' : 'info'}
          showIcon
          style={{ marginBottom: 12 }}
          message={`卖方预期：${status.source || 'unknown'} / ${status.data_status || 'unknown'}`}
          description={status.message || '卖方预期时间线需以真实研报源为准。'}
        />
      )}
      <Timeline
        items={rows.map((r) => ({
          color: r.direction === 'up' ? 'red' : r.direction === 'down' ? 'green' : 'blue',
          children: (
            <div>
              <b>{r.date}</b> · <Tag>{r.broker}</Tag>
              <Tag color={r.direction === 'up' ? 'red' : r.direction === 'down' ? 'green' : 'default'}>{r.action}</Tag>
              <span>目标价 {r.target_price} / EPS 调整 {r.eps_revision > 0 ? '+' : ''}{r.eps_revision}</span>
            </div>
          ),
        }))}
      />
    </div>
  )
}

export default function ResearchPage() {
  return (
    <div>
      <Title level={3}>研究中心</Title>
      <Disclaimer kind="ai" />
      <Paragraph type="secondary">覆盖：公司公告 · AI 财报解读 · 另类数据 · 卖方预期时间线。</Paragraph>
      <Tabs
        items={[
          { key: 'ann', label: 'M4D-03 公告监控', children: <AnnouncementsTab /> },
          { key: 'int', label: 'M4D-05 AI 财报解读', children: <InterpretTab /> },
          { key: 'alt', label: 'M4D-08 另类数据', children: <AltDataTab /> },
          { key: 'ss', label: 'M4D-11 卖方预期时间线', children: <SellsideTab /> },
        ]}
      />
    </div>
  )
}
