import { useEffect, useRef, useState } from 'react'
import { Alert, Card, Col, Row, Table, Statistic, Tag, Spin, Progress, Button, Space, Empty } from 'antd'
import { DollarOutlined, PieChartOutlined, RobotOutlined, RiseOutlined, FallOutlined } from '@ant-design/icons'
import * as echarts from 'echarts'
import { Link } from 'react-router-dom'
import { fetchApi } from '../api/client'
import { askAI } from '../api/copilot'
import type { PortfolioData, PortfolioStock, AnyData, DataStatus } from '../api/types'
import { extractMeta } from '../api/useApiMeta'
import DataStatusBadge from '../components/DataStatusBadge'

function PortfolioSummary({ data }: { data: PortfolioData }) {
  const pnlColor = data.total_pnl >= 0 ? '#f5222d' : '#52c41a'
  return (
    <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
      <Col xs={12} md={6}>
        <Card size="small" style={{ borderLeft: '3px solid #1677ff' }}>
          <Statistic title="总市值" value={(data.total_value / 1e4).toFixed(1)} suffix="万" valueStyle={{ fontSize: 24, fontWeight: 700 }} />
        </Card>
      </Col>
      <Col xs={12} md={6}>
        <Card size="small" style={{ borderLeft: `3px solid ${pnlColor}` }}>
          <Statistic title="总盈亏" value={(data.total_pnl / 1e4).toFixed(1)} suffix="万"
            prefix={data.total_pnl >= 0 ? <RiseOutlined /> : <FallOutlined />}
            valueStyle={{ fontSize: 24, fontWeight: 700, color: pnlColor }} />
        </Card>
      </Col>
      <Col xs={12} md={6}>
        <Card size="small" style={{ borderLeft: `3px solid ${pnlColor}` }}>
          <Statistic title="总收益率" value={(data.total_pnl_rate * 100).toFixed(2)} suffix="%"
            valueStyle={{ fontSize: 24, fontWeight: 700, color: pnlColor }} />
        </Card>
      </Col>
      <Col xs={12} md={6}>
        <Card size="small" style={{ borderLeft: '3px solid #722ed1' }}>
          <Statistic title="持仓数" value={data.stocks.length} suffix="只" valueStyle={{ fontSize: 24, fontWeight: 700 }} />
        </Card>
      </Col>
    </Row>
  )
}

function SectorPie({ stocks }: { stocks: PortfolioStock[] }) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!ref.current || !stocks.length) return
    const chart = echarts.init(ref.current)
    const data = stocks.map(s => ({ name: s.name, value: Math.round(s.market_value) }))
    chart.setOption({
      tooltip: { trigger: 'item', formatter: '{b}: {c}元 ({d}%)' },
      series: [{ type: 'pie', radius: ['35%', '65%'], data, label: { fontSize: 11 } }],
    })
    const onResize = () => chart.resize()
    window.addEventListener('resize', onResize)
    return () => { window.removeEventListener('resize', onResize); chart.dispose() }
  }, [stocks])
  return <div ref={ref} style={{ width: '100%', height: 240 }} />
}

function HoldingsTable({ stocks }: { stocks: PortfolioStock[] }) {
  const cols = [
    { title: '代码', dataIndex: 'code', key: 'c', width: 75, render: (v: string) => <Link to={`/stock/${v}`}>{v}</Link> },
    { title: '名称', dataIndex: 'name', key: 'n', width: 80 },
    { title: '现价', dataIndex: 'price', key: 'p', width: 65, render: (v: number) => v.toFixed(2) },
    { title: '成本', dataIndex: 'cost', key: 'co', width: 65, render: (v: number) => v.toFixed(2) },
    { title: '盈亏', dataIndex: 'pnl', key: 'pn', width: 80,
      render: (v: number) => <span style={{ color: v >= 0 ? '#f5222d' : '#52c41a', fontWeight: 600 }}>{v >= 0 ? '+' : ''}{(v / 1e4).toFixed(1)}万</span> },
    { title: '收益率', dataIndex: 'pnl_rate', key: 'pr', width: 75,
      render: (v: number) => <span style={{ color: v >= 0 ? '#f5222d' : '#52c41a', fontWeight: 600 }}>{(v * 100).toFixed(1)}%</span> },
    { title: 'PE', dataIndex: 'pe', key: 'pe', width: 55 },
    { title: 'PE分位', dataIndex: 'pe_percentile', key: 'pp', width: 90,
      render: (v: number) => <Progress percent={v} size="small" strokeColor={v > 80 ? '#f5222d' : v > 50 ? '#fa8c16' : '#52c41a'} format={p => `${p}%`} /> },
    { title: 'ROE', dataIndex: 'roe', key: 'roe', width: 60, render: (v: number) => `${v}%` },
    { title: '股息率', dataIndex: 'div_yield', key: 'dy', width: 65, render: (v: number) => `${v}%` },
  ]
  return <Table dataSource={stocks} columns={cols} rowKey="code" size="small" pagination={false} />
}

export default function ValuePage() {
  const [data, setData] = useState<PortfolioData | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchApi<PortfolioData>('/growth/portfolio')
      .then(setData).catch(() => setData(null)).finally(() => setLoading(false))
  }, [])

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '120px auto' }} />
  if (!data) return <Empty description="暂无持仓数据" />

  const highPE = data.stocks.filter(s => s.pe_percentile > 80)
  const highDiv = data.stocks.reduce((best, s) => s.div_yield > (best?.div_yield || 0) ? s : best, data.stocks[0])

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
        <h2 style={{ margin: 0 }}><DollarOutlined style={{ color: '#1677ff' }} /> 价值 / 持仓</h2>
        {highPE.length > 0 && <Tag color="red">估值偏高：{highPE.map(s => s.name).join('、')}</Tag>}
      </div>

      {(data as AnyData).mock && (() => {
        const meta = extractMeta(data as AnyData)
        return (
          <Alert
            type="warning"
            showIcon
            style={{ marginBottom: 12 }}
            message={
              <Space size={8}>
                <span>当前持仓为示例数据</span>
                <DataStatusBadge status={meta.data_status as DataStatus} source={meta.source} mock={meta.mock} />
              </Space>
            }
            description={(data as AnyData).message || '真实用户持仓待接入。'}
          />
        )
      })()}

      <PortfolioSummary data={data} />

      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col xs={24} lg={16}>
          <Card title="持仓明细" size="small"><HoldingsTable stocks={data.stocks} /></Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card title={<span><PieChartOutlined /> 仓位分布</span>} size="small" bodyStyle={{ padding: 8 }}>
            <SectorPie stocks={data.stocks} />
          </Card>
        </Col>
      </Row>

      <Card size="small" title={<span><RobotOutlined style={{ color: '#1677ff' }} /> 向 AI 追问</span>}>
        <Space wrap>
          <Button type="primary" icon={<RobotOutlined />}
            onClick={() => askAI(`我的持仓：${data.stocks.map(s => `${s.name}(PE${s.pe},PE分位${s.pe_percentile}%,ROE${s.roe}%,收益${(s.pnl_rate * 100).toFixed(1)}%)`).join('、')}。总收益率${(data.total_pnl_rate * 100).toFixed(1)}%。诊断持仓健康度：哪些估值偏高应减仓？哪些有催化可加仓？`)}
          >
            组合诊断
          </Button>
          <Button onClick={() => askAI(`持仓中ROE最高的是${data.stocks.reduce((a, b) => a.roe > b.roe ? a : b).name}，股息率最高的是${highDiv.name}(${highDiv.div_yield}%)。从价值投资角度分析这两只的持有价值。`)}>
            价值分析
          </Button>
          <Button onClick={() => askAI('我的持仓是否过于集中？有没有行业分散和风格再平衡的建议？')}>
            再平衡建议
          </Button>
        </Space>
      </Card>

      <div style={{ marginTop: 12, color: '#999', fontSize: 11, textAlign: 'center' }}>以上分析仅供参考，不构成投资建议。</div>
    </div>
  )
}
