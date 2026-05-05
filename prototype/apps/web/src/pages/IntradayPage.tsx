import { useEffect, useMemo, useState } from 'react'
import { Card, Col, Row, Table, Tag, Spin, Badge, Switch, Tooltip, Statistic, Empty, Alert } from 'antd'
import { ArrowUpOutlined, WarningOutlined, FireOutlined, ThunderboltOutlined, RobotOutlined, RiseOutlined } from '@ant-design/icons'
import { Link } from 'react-router-dom'
import { fetchApi } from '../api/client'
import { askAI } from '../api/copilot'
import { useMarketWS } from '../api/useMarketWS'
import type { LimitUpStock, AnyData } from '../api/types'
import MockBanner from '../components/MockBanner'

function DashboardCards({ limitUp, broken, hot: _hot }: { limitUp: LimitUpStock[]; broken: LimitUpStock[]; hot: AnyData[] }) {
  const sealRate = limitUp.length + broken.length > 0
    ? Math.round(limitUp.length / (limitUp.length + broken.length) * 100) : 0
  const maxBoard = Math.max(0, ...limitUp.map(s => s.board_count || 0))

  return (
    <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
      <Col xs={12} md={6}>
        <Card size="small" style={{ borderLeft: '3px solid #f5222d' }}>
          <Statistic title={<span><ArrowUpOutlined /> 涨停</span>} value={limitUp.length} valueStyle={{ color: '#f5222d', fontSize: 28, fontWeight: 700 }} suffix="只" />
        </Card>
      </Col>
      <Col xs={12} md={6}>
        <Card size="small" style={{ borderLeft: '3px solid #fa8c16' }}>
          <Statistic title={<span><WarningOutlined /> 炸板</span>} value={broken.length} valueStyle={{ color: '#fa8c16', fontSize: 28, fontWeight: 700 }} suffix="只" />
        </Card>
      </Col>
      <Col xs={12} md={6}>
        <Card size="small" style={{ borderLeft: '3px solid #1677ff' }}>
          <Statistic
            title="封板成功率"
            value={sealRate}
            valueStyle={{ color: sealRate >= 70 ? '#52c41a' : sealRate >= 50 ? '#fa8c16' : '#f5222d', fontSize: 28, fontWeight: 700 }}
            suffix="%"
          />
        </Card>
      </Col>
      <Col xs={12} md={6}>
        <Card size="small" style={{ borderLeft: '3px solid #722ed1' }}>
          <Statistic
            title={<span><ThunderboltOutlined /> 最高板</span>}
            value={maxBoard}
            valueStyle={{ color: maxBoard >= 5 ? '#f5222d' : maxBoard >= 3 ? '#fa8c16' : '#262626', fontSize: 28, fontWeight: 700 }}
            suffix="板"
          />
        </Card>
      </Col>
    </Row>
  )
}

function LimitUpTable({ data }: { data: LimitUpStock[] }) {
  const columns = [
    { title: '代码', dataIndex: 'stock_code', key: 'c', width: 75,
      render: (v: string) => <Link to={`/stock/${v}`} style={{ fontWeight: 500 }}>{v}</Link>,
    },
    { title: '名称', dataIndex: 'stock_name', key: 'n', width: 80,
      render: (v: string, r: LimitUpStock) => (
        <Link to={`/stock/${r.stock_code}`}>
          {r.board_count >= 3 ? <span style={{ color: '#f5222d', fontWeight: 700 }}>{v}</span> : v}
        </Link>
      ),
    },
    { title: '连板', dataIndex: 'board_count', key: 'b', width: 55, sorter: (a: AnyData, b: AnyData) => (a.board_count || 0) - (b.board_count || 0), defaultSortOrder: 'descend' as const,
      render: (v: number) => v >= 2 ? <Tag color={v >= 4 ? 'red' : v >= 2 ? 'orange' : 'default'}>{v}板</Tag> : <span style={{ color: '#999' }}>首板</span>,
    },
    { title: '涨幅', dataIndex: 'change_rate', key: 'ch', width: 65,
      render: (v: number) => <span style={{ color: '#f5222d', fontWeight: 600 }}>{(v || 0).toFixed(2)}%</span>,
    },
    { title: '换手', dataIndex: 'turnover_ratio', key: 't', width: 60,
      render: (v: number) => <span style={{ color: (v || 0) > 15 ? '#fa8c16' : '#666' }}>{(v || 0).toFixed(1)}%</span>,
    },
    { title: '题材', dataIndex: 'first_plate_name', key: 'p', width: 100, ellipsis: true,
      render: (v: string) => v ? <Tag color="blue">{v}</Tag> : '—',
    },
    { title: '封板时间', dataIndex: 'time', key: 'tm', width: 75,
      render: (v: string) => <span style={{ fontSize: 12, color: '#666' }}>{v || '—'}</span>,
    },
    { title: '', key: 'ai', width: 40,
      render: (_: AnyData, r: LimitUpStock) => (
        <Tooltip title="问 AI">
          <RobotOutlined
            style={{ color: '#1677ff', cursor: 'pointer' }}
            onClick={() => askAI(`个股【${r.stock_name}(${r.stock_code})】今日${r.board_count >= 2 ? r.board_count + '连板' : '首板'}涨停，题材「${r.first_plate_name}」，分析涨停原因、明日溢价预期和操作建议。`)}
          />
        </Tooltip>
      ),
    },
  ]

  return (
    <Table
      dataSource={data}
      columns={columns}
      rowKey="stock_code"
      size="small"
      pagination={{ pageSize: 30, showSizeChanger: false, showTotal: t => `共 ${t} 只` }}
      scroll={{ y: 480 }}
    />
  )
}

function BrokenPanel({ data }: { data: LimitUpStock[] }) {
  if (data.length === 0) return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无炸板" />
  return (
    <div>
      {data.slice(0, 8).map(s => (
        <div key={s.stock_code} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: '1px solid #f0f0f0' }}>
          <div>
            <Link to={`/stock/${s.stock_code}`} style={{ fontWeight: 600 }}>{s.stock_name}</Link>
            <span style={{ color: '#999', fontSize: 12, marginLeft: 6 }}>{s.stock_code}</span>
            {(s.board_count || 0) >= 2 && <Tag color="orange" style={{ marginLeft: 6 }}>{s.board_count}板</Tag>}
          </div>
          <div style={{ textAlign: 'right' }}>
            <span style={{ color: '#fa8c16', fontWeight: 600 }}>{(s.change_rate || 0).toFixed(2)}%</span>
            <div style={{ fontSize: 11, color: '#999' }}>{s.time || ''}</div>
          </div>
        </div>
      ))}
      {data.length > 8 && <div style={{ textAlign: 'center', padding: 8, color: '#999', fontSize: 12 }}>还有 {data.length - 8} 只...</div>}
    </div>
  )
}

function HotStockPanel({ data }: { data: AnyData[] }) {
  if (data.length === 0) return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无热股" />
  return (
    <div>
      {data.slice(0, 8).map((s, i) => (
        <div key={s.stock_code || i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 0', borderBottom: '1px solid #f5f5f5' }}>
          <div>
            <Link to={`/stock/${s.stock_code}`} style={{ fontWeight: 500 }}>{s.stock_name || s.prod_name || '—'}</Link>
            {(s.plate_name || s.first_plate_name) && <Tag color="cyan" style={{ marginLeft: 6, fontSize: 11 }}>{s.plate_name || s.first_plate_name}</Tag>}
          </div>
          <span style={{ color: (s.change_rate || 0) >= 0 ? '#f5222d' : '#52c41a', fontWeight: 600, fontSize: 13 }}>
            {(s.change_rate || 0).toFixed(2)}%
          </span>
        </div>
      ))}
    </div>
  )
}

export default function IntradayPage() {
  const [httpLimitUp, setLimitUp] = useState<LimitUpStock[]>([])
  const [httpBroken, setBroken] = useState<LimitUpStock[]>([])
  const [httpHot, setHot] = useState<AnyData[]>([])
  const [_httpAnomaly, setAnomaly] = useState<AnyData[]>([])
  const [loading, setLoading] = useState(true)
  const [autoRefresh, setAutoRefresh] = useState(false)
  const [isMock, setIsMock] = useState(false)
  const [errMsg, setErrMsg] = useState('')

  const ws = useMarketWS(autoRefresh)

  const limitUp = ws.connected && ws.limitUp.length ? ws.limitUp : httpLimitUp
  const broken = ws.connected && ws.broken.length ? ws.broken : httpBroken
  const hot = ws.connected && ws.hot.length ? ws.hot : httpHot

  useEffect(() => {
    const load = async () => {
      setLoading(true)
      const safe = async <T,>(p: Promise<T>) => { try { return await p } catch { return null } }
      const [lu, br, hs, an] = await Promise.all([
        safe(fetchApi<{ data: LimitUpStock[]; mock?: boolean }>('/market/limit-up')),
        safe(fetchApi<{ data: LimitUpStock[]; mock?: boolean }>('/market/broken')),
        safe(fetchApi<{ data: AnyData[]; mock?: boolean }>('/market/hot-stocks')),
        safe(fetchApi<{ data: AnyData[] }>('/market/anomaly')),
      ])
      if (!lu && !br && !hs && !an) {
        setErrMsg('后端 API 不可达，请确认服务已启动。')
      } else {
        setErrMsg('')
      }
      setLimitUp(lu?.data || [])
      setBroken(br?.data || [])
      setHot(hs?.data || [])
      setAnomaly(an?.data || [])
      setIsMock(!!(lu?.mock || br?.mock))
      setLoading(false)
    }
    void load()
  }, [])

  const tierSummary = useMemo(() => {
    const tiers: Record<number, number> = {}
    limitUp.forEach(s => { const n = s.board_count || 1; tiers[n] = (tiers[n] || 0) + 1 })
    return Object.entries(tiers).sort(([a], [b]) => Number(b) - Number(a))
  }, [limitUp])

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '120px auto' }} />

  return (
    <div>
      <MockBanner show={isMock} />
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <h2 style={{ margin: 0 }}>盘中盯盘</h2>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 13, color: '#666' }}>实时推送</span>
          <Switch checked={autoRefresh} onChange={setAutoRefresh} size="small" />
          {autoRefresh && (
            <Tooltip title={ws.connected ? 'WebSocket 已连接，3秒刷新' : '正在重连...'}>
              <Badge status={ws.connected ? 'success' : 'warning'} text={ws.connected ? '已连接' : '重连中'} />
            </Tooltip>
          )}
        </div>
      </div>

      {errMsg && <Alert type="error" showIcon closable message={errMsg} style={{ marginBottom: 12 }} />}

      <DashboardCards limitUp={limitUp} broken={broken} hot={hot} />

      {tierSummary.length > 0 && (
        <div style={{ marginBottom: 16, display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <span style={{ fontSize: 13, color: '#666' }}>梯队分布：</span>
          {tierSummary.map(([n, c]) => (
            <Tag key={n} color={Number(n) >= 4 ? 'red' : Number(n) >= 2 ? 'orange' : 'default'}>
              {n}板 × {c}
            </Tag>
          ))}
        </div>
      )}

      <Row gutter={16}>
        <Col xs={24} lg={14}>
          <Card
            title={<span><RiseOutlined style={{ color: '#f5222d' }} /> 涨停监控 · {limitUp.length} 只</span>}
            size="small"
            extra={
              <Tooltip title="AI 分析今日涨停特征">
                <RobotOutlined
                  style={{ color: '#1677ff', cursor: 'pointer', fontSize: 16 }}
                  onClick={() => {
                    const top3 = limitUp.filter(s => (s.board_count || 0) >= 2).slice(0, 3).map(s => s.stock_name).join('、')
                    askAI(`今日涨停 ${limitUp.length} 只，最高 ${Math.max(0, ...limitUp.map(s => s.board_count || 0))} 板，高位股${top3 || '无'}。分析今日涨停板块特征、资金偏好和后市研判。`)
                  }}
                />
              </Tooltip>
            }
          >
            <LimitUpTable data={limitUp} />
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card
            title={<span><WarningOutlined style={{ color: '#fa8c16' }} /> 炸板预警 · {broken.length} 只</span>}
            size="small"
            style={{ marginBottom: 16 }}
            extra={broken.length > 0 ? (
              <Tooltip title="AI 分析炸板原因">
                <RobotOutlined
                  style={{ color: '#1677ff', cursor: 'pointer' }}
                  onClick={() => askAI(`今日炸板 ${broken.length} 只，分析炸板集中原因和对市场情绪的影响。`)}
                />
              </Tooltip>
            ) : undefined}
          >
            <BrokenPanel data={broken} />
          </Card>
          <Card
            title={<span><FireOutlined style={{ color: '#f5222d' }} /> 热股雷达 · {hot.length} 只</span>}
            size="small"
          >
            <HotStockPanel data={hot} />
          </Card>
        </Col>
      </Row>
    </div>
  )
}
