import { useEffect, useRef, useState } from 'react'
import { Button, Card, Col, Empty, Row, Select, Space, Spin, Statistic, Table, Tag } from 'antd'
import { LineChartOutlined } from '@ant-design/icons'
import * as echarts from 'echarts'
import { fetchApi } from '../api/client'
import { extractMeta } from '../api/useApiMeta'
import DataStatusBadge from './DataStatusBadge'
import type { AnyData, BoardBacktestResult, BoardBacktestTradeEntry, DataStatus } from '../api/types'

const SUB_STRATEGIES = [
  { label: '首板', value: '首板' },
  { label: '二板', value: '二板' },
  { label: '龙头', value: '龙头' },
]

const YEARS_OPTIONS = [
  { label: '1年', value: 1 },
  { label: '2年', value: 2 },
  { label: '3年', value: 3 },
]

const MODE_OPTIONS = [
  { label: '演示数据', value: 'sample' },
  { label: '实盘数据', value: 'live' },
]

const tradeCols = [
  { title: '日期', dataIndex: 'date', key: 'date', width: 100 },
  { title: '退出', dataIndex: 'exit_date', key: 'exit_date', width: 100 },
  {
    title: '标的',
    dataIndex: 'stock',
    key: 'stock',
    width: 90,
    render: (v: string, r: BoardBacktestTradeEntry) => (
      <span>
        {v} <span style={{ color: '#999', fontSize: 11 }}>{r.code}</span>
      </span>
    ),
  },
  { title: '方向', dataIndex: 'direction', key: 'direction', width: 60 },
  { title: '持有', dataIndex: 'hold_days', key: 'hold', width: 60, render: (v: number) => `${v}天` },
  {
    title: '盈亏',
    dataIndex: 'pnl',
    key: 'pnl',
    width: 80,
    sorter: (a: BoardBacktestTradeEntry, b: BoardBacktestTradeEntry) => a.pnl - b.pnl,
    render: (v: number) => (
      <span style={{ color: v >= 0 ? '#f5222d' : '#52c41a' }}>
        {v > 0 ? '+' : ''}{v.toFixed(2)}%
      </span>
    ),
  },
  {
    title: '结果',
    dataIndex: 'result',
    key: 'result',
    width: 70,
    render: (v: string) => <Tag color={v === '盈利' ? 'red' : 'green'}>{v}</Tag>,
  },
]

export default function BoardBacktestPanel() {
  const [subStrategy, setSubStrategy] = useState('首板')
  const [mode, setMode] = useState('sample')
  const [years, setYears] = useState(1)
  const [data, setData] = useState<BoardBacktestResult | null>(null)
  const [raw, setRaw] = useState<AnyData>(null)
  const [loading, setLoading] = useState(false)
  const chartRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let active = true
    setLoading(true)
    const params = new URLSearchParams({
      sub_strategy: subStrategy,
      mode,
      years: String(years),
    })
    fetchApi<AnyData>(`/backtest/board-strategy?${params}`)
      .then((res) => {
        if (!active) return
        setRaw(res)
        setData(res?.data ?? null)
      })
      .catch(() => {
        if (active) {
          setRaw(null)
          setData(null)
        }
      })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [subStrategy, mode, years])

  useEffect(() => {
    if (!data?.equity_curve?.length || !chartRef.current) return
    const chart = echarts.init(chartRef.current)
    const curve = data.equity_curve
    chart.setOption({
      tooltip: {
        trigger: 'axis',
        formatter: (p: AnyData) => `${p[0].axisValue}<br/>净值: ${p[0].value}`,
      },
      grid: { left: 50, right: 20, top: 20, bottom: 30 },
      xAxis: {
        type: 'category',
        data: curve.map((c) => c.date.slice(5)),
        axisLabel: { fontSize: 10 },
      },
      yAxis: { type: 'value', name: '净值', axisLabel: { fontSize: 10 } },
      series: [{
        type: 'line',
        data: curve.map((c) => c.value),
        smooth: true,
        lineStyle: { width: 2 },
        areaStyle: { opacity: 0.15 },
        itemStyle: { color: '#722ed1' },
      }],
    })
    const onResize = () => chart.resize()
    window.addEventListener('resize', onResize)
    return () => { window.removeEventListener('resize', onResize); chart.dispose() }
  }, [data])

  const meta = extractMeta(raw, '打板回测')

  return (
    <div>
      <Card size="small" style={{ marginBottom: 16 }}>
        <Space wrap>
          <span style={{ fontWeight: 500 }}>子策略:</span>
          {SUB_STRATEGIES.map(({ label, value }) => (
            <Button
              key={value}
              type={subStrategy === value ? 'primary' : 'default'}
              size="small"
              onClick={() => setSubStrategy(value)}
            >
              {label}
            </Button>
          ))}
          <Select
            size="small"
            value={mode}
            onChange={setMode}
            options={MODE_OPTIONS}
            style={{ width: 110 }}
          />
          {YEARS_OPTIONS.map(({ label, value }) => (
            <Button
              key={value}
              type={years === value ? 'primary' : 'default'}
              size="small"
              onClick={() => setYears(value)}
              ghost={years === value}
            >
              {label}
            </Button>
          ))}
          <DataStatusBadge
            status={meta.data_status as DataStatus}
            source={meta.source}
            mock={meta.mock}
            size="small"
          />
        </Space>
      </Card>

      {loading ? (
        <Card><Spin /></Card>
      ) : !data ? (
        <Card><Empty description="暂无回测数据" /></Card>
      ) : (
        <>
          <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
            <Col span={4}>
              <Card size="small">
                <Statistic
                  title="总收益"
                  value={data.total_return}
                  suffix="%"
                  precision={2}
                  valueStyle={{ color: data.total_return >= 0 ? '#f5222d' : '#52c41a' }}
                />
              </Card>
            </Col>
            <Col span={4}>
              <Card size="small">
                <Statistic
                  title="年化"
                  value={data.annualized_return}
                  suffix="%"
                  precision={2}
                  valueStyle={{ color: data.annualized_return >= 0 ? '#f5222d' : '#52c41a' }}
                />
              </Card>
            </Col>
            <Col span={4}>
              <Card size="small">
                <Statistic title="回撤" value={data.max_drawdown} suffix="%" precision={2} valueStyle={{ color: '#52c41a' }} />
              </Card>
            </Col>
            <Col span={3}>
              <Card size="small">
                <Statistic title="夏普" value={data.sharpe_ratio} precision={2} />
              </Card>
            </Col>
            <Col span={3}>
              <Card size="small">
                <Statistic title="胜率" value={data.win_rate} suffix="%" precision={1} />
              </Card>
            </Col>
            <Col span={3}>
              <Card size="small">
                <Statistic title="盈亏比" value={data.profit_loss_ratio} precision={2} />
              </Card>
            </Col>
            <Col span={3}>
              <Card size="small">
                <Statistic title="最大连亏" value={data.max_consecutive_loss} suffix="次" />
              </Card>
            </Col>
          </Row>

          <Card
            size="small"
            title={
              <Space>
                <LineChartOutlined style={{ color: '#722ed1' }} />
                <span>净值曲线 ({data.strategy_name})</span>
              </Space>
            }
            style={{ marginBottom: 16 }}
          >
            <div ref={chartRef} style={{ width: '100%', height: 300 }} />
          </Card>

          <Card
            size="small"
            title={`交易记录 (${data.total_trades}笔 · 胜${data.win_trades}负${data.loss_trades} · 均持${data.avg_hold_days.toFixed(1)}天)`}
          >
            <Table
              dataSource={data.trade_log}
              columns={tradeCols}
              rowKey={(_, i) => String(i)}
              size="small"
              pagination={{ pageSize: 10, showSizeChanger: false }}
              scroll={{ y: 300 }}
            />
          </Card>
        </>
      )}
    </div>
  )
}
