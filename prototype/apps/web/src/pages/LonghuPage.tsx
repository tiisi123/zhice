import { useEffect, useState } from 'react'
import { Alert, Card, Table, Tag, Space, DatePicker, Button, Input, Empty } from 'antd'
import { ReloadOutlined, SearchOutlined } from '@ant-design/icons'
import dayjs, { Dayjs } from 'dayjs'
import { fetchApi } from '../api/client'
import type { AnyData } from '../api/types'

interface SeatRow {
  seat: string
  alias: string | null
  buy: number
  sell: number
  net: number
  count: number
  stocks: { code?: string; name?: string; stock_code?: string; stock_name?: string; SecurityCode?: string; SecurityName?: string; buy: number; sell: number }[]
}

interface ApiMeta {
  source?: string
  data_status?: string
  mock?: boolean
  message?: string
}

function fmt(v: unknown) {
  const n = Number(v)
  if (!Number.isFinite(n)) return '—'
  const v2 = n
  if (Math.abs(v2) >= 1e8) return (v2 / 1e8).toFixed(2) + '亿'
  if (Math.abs(v2) >= 1e4) return (v2 / 1e4).toFixed(1) + '万'
  return v2.toFixed(0)
}

function stockCode(row: SeatRow['stocks'][number]) {
  return row.stock_code || row.code || row.SecurityCode || ''
}

function stockName(row: SeatRow['stocks'][number]) {
  return row.stock_name || row.name || row.SecurityName || '—'
}

export default function LonghuPage() {
  const [date, setDate] = useState<Dayjs>(dayjs())
  const [rows, setRows] = useState<SeatRow[]>([])
  const [loading, setLoading] = useState(false)
  const [filter, setFilter] = useState('')
  const [meta, setMeta] = useState<ApiMeta>({})
  const [err, setErr] = useState('')

  const load = async () => {
    setLoading(true)
    try {
      const r = await fetchApi<{ rank: SeatRow[]; note?: string; source?: string; data_status?: string; mock?: boolean; message?: string }>('/longhu/rank', { date: date.format('YYYY-MM-DD'), top: '50' })
      setRows(r.rank || [])
      setErr('')
      setMeta({ source: r.source, data_status: r.data_status, mock: r.mock, message: r.message || r.note })
    } catch {
      setRows([])
      setErr('龙虎榜接口不可用，当前不展示席位数据。')
      setMeta({})
    } finally {
      setLoading(false)
    }
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { void load() }, [date])

  const filtered = filter ? rows.filter((r) => (r.alias || '').includes(filter) || r.seat.includes(filter)) : rows

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <DatePicker value={date} onChange={(d) => d && setDate(d)} />
        <Input
          prefix={<SearchOutlined />}
          placeholder="席位/别名"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          allowClear
        />
        <Button icon={<ReloadOutlined />} onClick={load}>刷新</Button>
      </Space>
      {err ? (
        <Alert type="error" showIcon message={err} style={{ marginBottom: 12 }} />
      ) : (
        <Alert
          type={meta.mock ? 'warning' : rows.length ? 'info' : 'warning'}
          showIcon
          message={`数据源：${meta.source || '未知源'} / 状态：${meta.data_status || '未知状态'}${meta.mock ? ' / mock' : ''}`}
          description={meta.data_status === 'empty' ? '真实空状态：KPL 龙虎榜接口暂无返回，当前不展示示例席位。' : meta.message}
          style={{ marginBottom: 12 }}
        />
      )}
      <Card>
        <Table
          rowKey="seat"
          dataSource={filtered}
          loading={loading}
          pagination={{ pageSize: 20 }}
          size="small"
          expandable={{
            expandedRowRender: (r) => (
              <Table
                size="small"
                pagination={false}
                rowKey={(row) => stockCode(row)}
                dataSource={r.stocks}
                locale={{ emptyText: <Empty description="暂无上榜个股" /> }}
                columns={[
                  { title: '代码', width: 100, render: (_: AnyData, row: AnyData) => stockCode(row) || '—' },
                  { title: '名称', width: 140, render: (_: AnyData, row: AnyData) => stockName(row) },
                  { title: '买入', dataIndex: 'buy', render: (v) => fmt(v), align: 'right' as const },
                  { title: '卖出', dataIndex: 'sell', render: (v) => fmt(v), align: 'right' as const },
                  { title: '净额', render: (_: AnyData, row: AnyData) => {
                    const net = Number(row.buy) - Number(row.sell)
                    return <span style={{ color: net >= 0 ? '#f5222d' : '#389e0d' }}>{fmt(net)}</span>
                  }, align: 'right' as const },
                ]}
              />
            ),
          }}
          columns={[
            { title: '席位', dataIndex: 'seat', width: 320 },
            {
              title: '别名', dataIndex: 'alias', width: 110,
              render: (v) => v ? <Tag color="geekblue">{v}</Tag> : <span style={{ color: '#bbb' }}>—</span>,
            },
            { title: '买入', dataIndex: 'buy', width: 110, render: fmt, align: 'right' },
            { title: '卖出', dataIndex: 'sell', width: 110, render: fmt, align: 'right' },
            {
              title: '净额', dataIndex: 'net', width: 130, align: 'right',
              render: (v) => <b style={{ color: v >= 0 ? '#f5222d' : '#389e0d' }}>{fmt(v)}</b>,
              sorter: (a: SeatRow, b: SeatRow) => a.net - b.net,
              defaultSortOrder: 'descend' as const,
            },
            { title: '上榜数', dataIndex: 'count', width: 80, align: 'right' },
          ]}
          locale={{ emptyText: <Empty description={filter ? '无匹配席位' : '暂无龙虎榜席位数据'} /> }}
        />
      </Card>
    </div>
  )
}
