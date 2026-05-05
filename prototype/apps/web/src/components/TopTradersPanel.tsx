import { useEffect, useState } from 'react'
import { Card, Empty, Space, Spin, Table, Tag, Tooltip } from 'antd'
import { CrownOutlined } from '@ant-design/icons'
import { fetchApi } from '../api/client'
import { extractMeta } from '../api/useApiMeta'
import DataStatusBadge from './DataStatusBadge'
import type { AnyData, DataStatus, EnrichedSeat, TopTraderStock } from '../api/types'

interface Props {
  date: string
}

function renderSeats(seats: EnrichedSeat[]) {
  if (!seats || seats.length === 0) return '-'
  return (
    <Space size={2} wrap>
      {seats.map((s, i) => (
        <Tag
          key={`${s.name}-${i}`}
          color={s.famous_alias ? 'volcano' : undefined}
          style={{ margin: 0 }}
        >
          {s.famous_alias || s.name}
        </Tag>
      ))}
    </Space>
  )
}

const columns = [
  {
    title: '代码',
    dataIndex: 'stock_code',
    width: 90,
    render: (v: string) => <span style={{ fontFamily: 'monospace' }}>{v}</span>,
  },
  { title: '名称', dataIndex: 'stock_name', width: 80 },
  {
    title: '涨幅',
    dataIndex: 'change_rate',
    width: 70,
    render: (v: number) => (
      <span style={{ color: v >= 0 ? '#f5222d' : '#52c41a' }}>
        {(v * 100).toFixed(2)}%
      </span>
    ),
  },
  {
    title: '净买入(万)',
    dataIndex: 'net_amount',
    width: 90,
    sorter: (a: TopTraderStock, b: TopTraderStock) => a.net_amount - b.net_amount,
    render: (v: number) => {
      const val = (v / 10000).toFixed(0)
      return <span style={{ color: v >= 0 ? '#f5222d' : '#52c41a' }}>{val}</span>
    },
  },
  {
    title: '成交额(万)',
    dataIndex: 'amount',
    width: 90,
    render: (v: number) => (v / 10000).toFixed(0),
  },
  {
    title: '换手率',
    dataIndex: 'turnover_ratio',
    width: 70,
    render: (v: number) => v ? `${(v * 100).toFixed(1)}%` : '-',
  },
  {
    title: '概念',
    dataIndex: 'concepts',
    ellipsis: true,
    render: (concepts: string[]) =>
      concepts && concepts.length > 0 ? (
        <Tooltip title={concepts.join('、')}>
          <Space size={2} wrap>
            {concepts.slice(0, 2).map((c) => (
              <Tag key={c} style={{ margin: 0 }}>{c}</Tag>
            ))}
            {concepts.length > 2 && <Tag style={{ margin: 0 }}>+{concepts.length - 2}</Tag>}
          </Space>
        </Tooltip>
      ) : '-',
  },
  {
    title: '买方席位',
    dataIndex: 'buy_seats',
    width: 160,
    render: renderSeats,
  },
  {
    title: '卖方席位',
    dataIndex: 'sell_seats',
    width: 160,
    render: renderSeats,
  },
]

export default function TopTradersPanel({ date }: Props) {
  const [stocks, setStocks] = useState<TopTraderStock[]>([])
  const [raw, setRaw] = useState<AnyData>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    let active = true
    void (() => {
      setLoading(true)
      fetchApi<AnyData>(`/analysis/top-traders?date=${date}`)
        .then((res) => {
          if (!active) return
          setRaw(res)
          const d = res?.data
          setStocks(Array.isArray(d) ? d : [])
        })
        .catch(() => { if (active) { setStocks([]); setRaw(null) } })
        .finally(() => { if (active) setLoading(false) })
    })()
    return () => { active = false }
  }, [date])

  const meta = extractMeta(raw, '游资席位')

  if (loading) return <Card><Spin /></Card>

  return (
    <Card
      title={
        <Space>
          <CrownOutlined style={{ color: '#fa8c16' }} />
          <span>游资席位</span>
          <DataStatusBadge status={meta.data_status as DataStatus} source={meta.source} mock={meta.mock} size="small" />
        </Space>
      }
      size="small"
      style={{ marginBottom: 16 }}
    >
      {stocks.length === 0 ? (
        <Empty description="暂无龙虎榜数据" />
      ) : (
        <Table
          dataSource={stocks}
          columns={columns}
          rowKey="stock_code"
          size="small"
          pagination={stocks.length > 20 ? { pageSize: 20 } : false}
          scroll={{ x: 900 }}
        />
      )}
    </Card>
  )
}
