import { useEffect, useState } from 'react'
import { Card, Col, Empty, Row, Space, Spin, Table, Tag, Tooltip } from 'antd'
import { FireOutlined } from '@ant-design/icons'
import { fetchApi } from '../api/client'
import { extractMeta } from '../api/useApiMeta'
import DataStatusBadge from './DataStatusBadge'
import type { AnyData, BoardReplayData, BoardReplayStock, DataStatus } from '../api/types'

interface Props {
  date: string
}

const TIER_CONFIG: { key: keyof BoardReplayData; label: string; color: string }[] = [
  { key: 'first_board', label: '首板', color: '#f5222d' },
  { key: 'consecutive', label: '连板', color: '#fa541c' },
  { key: 'broken', label: '炸板', color: '#8c8c8c' },
]

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
    title: '板数',
    dataIndex: 'board_count',
    width: 50,
    sorter: (a: BoardReplayStock, b: BoardReplayStock) => a.board_count - b.board_count,
  },
  {
    title: '封板时间',
    dataIndex: 'limit_time',
    width: 80,
  },
  {
    title: '封单(万)',
    dataIndex: 'seal_amount',
    width: 80,
    render: (v: number) => v ? (v / 10000).toFixed(0) : '-',
  },
  {
    title: '板块',
    dataIndex: 'sectors',
    ellipsis: true,
    render: (sectors: string[]) =>
      sectors.length > 0 ? (
        <Tooltip title={sectors.join('、')}>
          <Space size={2} wrap>
            {sectors.slice(0, 2).map((s) => (
              <Tag key={s} style={{ margin: 0 }}>{s}</Tag>
            ))}
            {sectors.length > 2 && <Tag style={{ margin: 0 }}>+{sectors.length - 2}</Tag>}
          </Space>
        </Tooltip>
      ) : '-',
  },
]

export default function BoardReplayPanel({ date }: Props) {
  const [data, setData] = useState<BoardReplayData | null>(null)
  const [raw, setRaw] = useState<AnyData>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    let active = true
    void (() => {
      setLoading(true)
      fetchApi<AnyData>(`/analysis/board-replay?date=${date}`)
        .then((res) => {
          if (!active) return
          setRaw(res)
          const d = res?.data
          if (d && (d.first_board || d.consecutive || d.broken)) {
            setData({
              first_board: d.first_board || [],
              consecutive: d.consecutive || [],
              broken: d.broken || [],
            })
          } else {
            setData(null)
          }
        })
        .catch(() => { if (active) { setData(null); setRaw(null) } })
        .finally(() => { if (active) setLoading(false) })
    })()
    return () => { active = false }
  }, [date])

  const meta = extractMeta(raw, '涨停复盘')

  if (loading) return <Card><Spin /></Card>

  return (
    <Card
      title={
        <Space>
          <FireOutlined style={{ color: '#f5222d' }} />
          <span>涨停复盘</span>
          <DataStatusBadge status={meta.data_status as DataStatus} source={meta.source} mock={meta.mock} size="small" />
        </Space>
      }
      size="small"
      style={{ marginBottom: 16 }}
    >
      {!data || (data.first_board.length === 0 && data.consecutive.length === 0 && data.broken.length === 0) ? (
        <Empty description="暂无涨停复盘数据" />
      ) : (
        <Row gutter={[12, 12]}>
          {TIER_CONFIG.map(({ key, label, color }) => {
            const stocks = data[key]
            if (stocks.length === 0) return null
            return (
              <Col xs={24} lg={8} key={key}>
                <div style={{ marginBottom: 4 }}>
                  <Tag color={color}>{label}</Tag>
                  <span style={{ fontSize: 12, color: '#999' }}>{stocks.length} 只</span>
                </div>
                <Table
                  dataSource={stocks}
                  columns={columns}
                  rowKey="stock_code"
                  size="small"
                  pagination={false}
                  scroll={{ x: 500 }}
                />
              </Col>
            )
          })}
        </Row>
      )}
    </Card>
  )
}
