import { useEffect, useRef, useState } from 'react'
import { Button, Card, Col, Collapse, Empty, Row, Select, Space, Spin, Statistic, Table, Tag } from 'antd'
import { LineChartOutlined } from '@ant-design/icons'
import * as echarts from 'echarts'
import { fetchApi } from '../api/client'
import { extractMeta } from '../api/useApiMeta'
import DataStatusBadge from './DataStatusBadge'
import type { AnyData, DataStatus, EtfBacktestResult, EtfRebalanceAllocation } from '../api/types'

const YEARS_OPTIONS = [
  { label: '1年', value: 1 },
  { label: '2年', value: 2 },
  { label: '3年', value: 3 },
]

const MODE_OPTIONS = [
  { label: '自动', value: 'auto' },
  { label: '实盘数据', value: 'live' },
  { label: '演示数据', value: 'sample' },
]

const allocColumns = [
  {
    title: 'ETF',
    dataIndex: 'name',
    width: 120,
    render: (v: string, r: EtfRebalanceAllocation) => (
      <span>{v} <span style={{ color: '#999', fontSize: 11 }}>{r.code}</span></span>
    ),
  },
  {
    title: '权重',
    dataIndex: 'weight',
    width: 80,
    render: (v: number) => `${v}%`,
  },
]

export default function EtfBacktestPanel() {
  const [mode, setMode] = useState('auto')
  const [years, setYears] = useState(1)
  const [data, setData] = useState<EtfBacktestResult | null>(null)
  const [raw, setRaw] = useState<AnyData>(null)
  const [loading, setLoading] = useState(false)
  const chartRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let active = true
    void (() => {
      setLoading(true)
      const params = new URLSearchParams({ mode, years: String(years) })
      fetchApi<AnyData>(`/backtest/etf-rotation?${params}`)
        .then((res) => {
          if (!active) return
          setRaw(res)
          setData(res?.data ?? null)
        })
        .catch(() => {
          if (active) { setRaw(null); setData(null) }
        })
        .finally(() => { if (active) setLoading(false) })
    })()
    return () => { active = false }
  }, [mode, years])

  useEffect(() => {
    if (!data?.equity_curve?.length || !chartRef.current) return
    const chart = echarts.init(chartRef.current)
    const curve = data.equity_curve
    chart.setOption({
      tooltip: {
        trigger: 'axis',
        formatter: (p: AnyData) => `第${p[0].axisValue}天<br/>净值: ${p[0].value}`,
      },
      grid: { left: 50, right: 20, top: 20, bottom: 30 },
      xAxis: {
        type: 'category',
        data: curve.map((c) => String(c.day)),
        axisLabel: { fontSize: 10 },
      },
      yAxis: { type: 'value', name: '净值', axisLabel: { fontSize: 10 } },
      series: [{
        type: 'line',
        data: curve.map((c) => c.value),
        smooth: true,
        lineStyle: { width: 2 },
        areaStyle: { opacity: 0.15 },
        itemStyle: { color: '#1677ff' },
      }],
    })
    const onResize = () => chart.resize()
    window.addEventListener('resize', onResize)
    return () => { window.removeEventListener('resize', onResize); chart.dispose() }
  }, [data])

  const meta = extractMeta(raw, 'ETF轮动回测')

  return (
    <div>
      <Card size="small" style={{ marginBottom: 16 }}>
        <Space wrap>
          <Select
            size="small"
            value={mode}
            onChange={setMode}
            options={MODE_OPTIONS}
            style={{ width: 120 }}
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
            <Col span={5}>
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
            <Col span={5}>
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
            <Col span={5}>
              <Card size="small">
                <Statistic title="回撤" value={data.max_drawdown} suffix="%" precision={2} valueStyle={{ color: '#52c41a' }} />
              </Card>
            </Col>
            <Col span={5}>
              <Card size="small">
                <Statistic title="夏普" value={data.sharpe_ratio} precision={2} />
              </Card>
            </Col>
            <Col span={4}>
              <Card size="small">
                <Statistic title="调仓次数" value={data.total_trades} />
              </Card>
            </Col>
          </Row>

          <Card
            size="small"
            title={
              <Space>
                <LineChartOutlined style={{ color: '#1677ff' }} />
                <span>净值曲线 ({data.strategy_name} · {data.etf_count}只ETF)</span>
              </Space>
            }
            style={{ marginBottom: 16 }}
          >
            <div ref={chartRef} style={{ width: '100%', height: 300 }} />
          </Card>

          {data.rebalance_log.length > 0 && (
            <Card size="small" title={`调仓记录 (${data.rebalance_log.length}次)`}>
              <Collapse
                size="small"
                items={data.rebalance_log.map((entry, idx) => ({
                  key: String(idx),
                  label: (
                    <Space>
                      <Tag color="blue">第{entry.day}天</Tag>
                      <span style={{ fontSize: 12, color: '#666' }}>
                        {entry.allocations.length}只ETF
                      </span>
                    </Space>
                  ),
                  children: (
                    <Table
                      dataSource={entry.allocations}
                      columns={allocColumns}
                      rowKey="code"
                      size="small"
                      pagination={false}
                    />
                  ),
                }))}
              />
            </Card>
          )}
        </>
      )}
    </div>
  )
}
