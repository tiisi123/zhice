import { useEffect, useRef, useState } from 'react'
import { Card, Col, Row, Table, Button, Select, Statistic, Input, Tag, message, Tabs, Space } from 'antd'
import { ThunderboltOutlined, RobotOutlined, DatabaseOutlined, ExperimentOutlined } from '@ant-design/icons'
import Markdown from 'react-markdown'
import * as echarts from 'echarts'
import { fetchApi, postApi } from '../api/client'
import { askAI } from '../api/copilot'
import Disclaimer from '../components/Disclaimer'
import type { AnyData } from '../api/types'

const { TextArea } = Input

const tradeCols = [
  { title: '日期', dataIndex: 'date', key: 'date', width: 100 },
  { title: '标的', dataIndex: 'stock', key: 'stock', width: 90 },
  { title: '持有', dataIndex: 'hold_days', key: 'hold', width: 60, render: (v: number) => `${v}天` },
  {
    title: '盈亏', dataIndex: 'pnl', key: 'pnl', width: 80,
    render: (v: number) => <span style={{ color: v >= 0 ? '#f5222d' : '#52c41a' }}>{v > 0 ? '+' : ''}{v.toFixed(2)}%</span>,
  },
  {
    title: '结果', dataIndex: 'result', key: 'result', width: 70,
    render: (v: string) => <Tag color={v === '盈利' ? 'red' : 'green'}>{v}</Tag>,
  },
]

export default function StrategyPage() {
  const [templates, setTemplates] = useState<Record<string, AnyData>>({})
  const [selectedTemplate, setSelectedTemplate] = useState('')
  const [nlInput, setNlInput] = useState('')
  const [dslResult, setDslResult] = useState<string | null>(null)
  const [backtestResult, setBtResult] = useState<AnyData>(null)
  const [analysis, setAnalysis] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [compareList, setCompareList] = useState<AnyData[]>([])
  const [comparingKey, setComparingKey] = useState<string | null>(null)
  const chartRef = useRef<HTMLDivElement>(null)

  const addToCompare = async (name: string) => {
    if (compareList.some((c) => c.strategy_name === name)) {
      setCompareList(compareList.filter((c) => c.strategy_name !== name))
      return
    }
    setComparingKey(name)
    try {
      const data = await postApi<AnyData>(`/strategy/run-template?template_name=${encodeURIComponent(name)}&years=3`)
      if (data.result) setCompareList((prev) => [...prev, data.result])
      else message.warning(data.message || '真实历史行情不可用')
    } catch (e) {
      message.error((e as Error)?.message || '回测失败')
    }
    setComparingKey(null)
  }

  useEffect(() => {
    fetchApi<{ templates: Record<string, unknown> }>('/strategy/templates')
      .then(res => setTemplates(res.templates))
      .catch(console.error)
  }, [])

  useEffect(() => {
    if (!backtestResult?.equity_curve || !chartRef.current) return
    const chart = echarts.init(chartRef.current)
    const curve = backtestResult.equity_curve
    chart.setOption({
      tooltip: { trigger: 'axis', formatter: (p: AnyData) => `${p[0].axisValue}<br/>净值: ${p[0].value}` },
      grid: { left: 50, right: 20, top: 20, bottom: 30 },
      xAxis: { type: 'category', data: curve.map((c: AnyData) => c.date.slice(5)), axisLabel: { fontSize: 10 } },
      yAxis: { type: 'value', name: '净值', axisLabel: { fontSize: 10 } },
      series: [{
        type: 'line',
        data: curve.map((c: AnyData) => c.value),
        smooth: true,
        lineStyle: { width: 2 },
        areaStyle: { opacity: 0.15 },
        itemStyle: { color: '#1677ff' },
      }],
    })
    const onResize = () => chart.resize()
    window.addEventListener('resize', onResize)
    return () => { window.removeEventListener('resize', onResize); chart.dispose() }
  }, [backtestResult])

  const runTemplate = async () => {
    if (!selectedTemplate) return
    setLoading(true)
    try {
      const data = await postApi<AnyData>(
        `/strategy/run-template?template_name=${encodeURIComponent(selectedTemplate)}&years=3`
      )
      if (!data.result) {
        setBtResult(null)
        setAnalysis(null)
        message.warning(data.message || '真实历史行情不可用')
        return
      }
      setBtResult(data.result)
      setAnalysis(data.analysis)
    } catch (e) {
      message.error((e as Error)?.message || '回测失败')
    }
    setLoading(false)
  }

  const generateDSL = async () => {
    if (!nlInput.trim()) return
    setLoading(true)
    try {
      const data = await postApi<AnyData>('/ai/strategy-dsl', { text: nlInput })
      setDslResult(data.dsl)
    } catch (e) {
      message.error((e as Error)?.message || '策略生成失败')
    }
    setLoading(false)
  }

  const bt = backtestResult

  return (
    <div>
      <Disclaimer kind="backtest" />
      <Row gutter={16}>
        <Col span={10}>
          <Card title="模板回测" size="small" style={{ marginBottom: 16 }}>
            <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
              <Select
                style={{ flex: 1 }}
                placeholder="选择策略模板"
                value={selectedTemplate || undefined}
                onChange={setSelectedTemplate}
                options={Object.keys(templates).map(k => ({ label: k, value: k }))}
              />
              <Button type="primary" icon={<ThunderboltOutlined />} onClick={runTemplate} loading={loading}>
                回测
              </Button>
            </div>
            {selectedTemplate && templates[selectedTemplate] && (
              <pre style={{ fontSize: 11, background: '#f6f8fa', padding: 8, borderRadius: 4, maxHeight: 180, overflow: 'auto' }}>
                {JSON.stringify(templates[selectedTemplate], null, 2)}
              </pre>
            )}
          </Card>

          <Card title="自然语言生成策略" size="small">
            <TextArea
              value={nlInput}
              onChange={e => setNlInput(e.target.value)}
              placeholder="例如：选3连板以上的龙头股，在分歧转一致时买入，止盈15%止损5%，持有不超过3天"
              rows={3}
            />
            <Button type="primary" onClick={generateDSL} loading={loading} style={{ marginTop: 8 }} block>
              生成策略 DSL
            </Button>
            {dslResult && (
              <pre style={{ fontSize: 11, background: '#f6f8fa', padding: 8, borderRadius: 4, marginTop: 8, maxHeight: 200, overflow: 'auto' }}>
                {dslResult}
              </pre>
            )}
          </Card>
        </Col>

        <Col span={14}>
          {bt ? (
            <>
              <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
                <Col span={4}><Card size="small"><Statistic title="总收益" value={bt.total_return} suffix="%" precision={2} valueStyle={{ color: bt.total_return >= 0 ? '#f5222d' : '#52c41a' }} /></Card></Col>
                <Col span={4}><Card size="small"><Statistic title="年化" value={bt.annualized_return} suffix="%" precision={2} valueStyle={{ color: bt.annualized_return >= 0 ? '#f5222d' : '#52c41a' }} /></Card></Col>
                <Col span={4}><Card size="small"><Statistic title="回撤" value={bt.max_drawdown} suffix="%" precision={2} valueStyle={{ color: '#52c41a' }} /></Card></Col>
                <Col span={4}><Card size="small"><Statistic title="夏普" value={bt.sharpe_ratio} precision={2} /></Card></Col>
                <Col span={4}><Card size="small"><Statistic title="胜率" value={bt.win_rate} suffix="%" precision={1} /></Card></Col>
                <Col span={4}><Card size="small"><Statistic title="盈亏比" value={bt.profit_loss_ratio} precision={2} /></Card></Col>
              </Row>

              <Card size="small" style={{ marginBottom: 16 }}>
                <Tabs type="card" size="small" items={[
                  {
                    key: 'curve',
                    label: `净值曲线 (${bt.strategy_name})`,
                    children: <div ref={chartRef} style={{ width: '100%', height: 300 }} />,
                  },
                  {
                    key: 'trades',
                    label: `交易记录 (${bt.total_trades}笔)`,
                    children: (
                      <Table
                        dataSource={bt.trade_log || []}
                        columns={tradeCols}
                        rowKey={(_, i) => String(i)}
                        size="small"
                        pagination={{ pageSize: 10, showSizeChanger: false }}
                        scroll={{ y: 250 }}
                      />
                    ),
                  },
                ]} />
              </Card>

              {bt.data_source && (
                <div style={{ marginBottom: 8 }}>
                  <Tag color={bt.data_source === 'tushare' ? 'green' : 'orange'} icon={bt.data_source === 'tushare' ? <DatabaseOutlined /> : <ExperimentOutlined />}>
                    {bt.data_source === 'tushare' ? '基于 TuShare 真实历史行情' : `数据源：${bt.data_source}`}
                  </Tag>
                </div>
              )}

              {analysis && (
                <Card title="AI 策略分析" size="small" style={{ marginBottom: 16 }}>
                  <div style={{ fontSize: 13, lineHeight: 1.8 }}><Markdown>{analysis}</Markdown></div>
                </Card>
              )}

              <Card size="small" title={<span><RobotOutlined style={{ color: '#1677ff' }} /> 向 AI 追问</span>}>
                <Space wrap>
                  <Button type="primary" icon={<RobotOutlined />}
                    onClick={() => askAI(`策略「${bt.strategy_name}」回测结果：总收益${bt.total_return?.toFixed(1)}%，夏普${bt.sharpe_ratio?.toFixed(2)}，胜率${bt.win_rate?.toFixed(1)}%，最大回撤${bt.max_drawdown?.toFixed(1)}%，盈亏比${bt.profit_loss_ratio?.toFixed(2)}。深度分析策略表现，指出优劣势和改进方向。`)}
                  >
                    策略诊断
                  </Button>
                  <Button onClick={() => askAI(`策略「${bt.strategy_name}」适合什么市场环境？当前市场环境下是否适用？`)}>适用性分析</Button>
                  <Button onClick={() => askAI(`如何优化策略「${bt.strategy_name}」的止盈止损参数？给出具体建议。`)}>参数优化建议</Button>
                </Space>
              </Card>
            </>
          ) : (
            <Card size="small" style={{ textAlign: 'center', padding: 60 }}>
              <p style={{ color: '#999' }}>选择策略模板后运行回测，或用自然语言生成策略</p>
            </Card>
          )}
        </Col>
      </Row>
      <Card title="策略对比分析" size="small" style={{ marginTop: 16 }}>
        <div style={{ marginBottom: 8, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {Object.keys(templates).map((k) => (
            <Button
              key={k} size="small"
              type={compareList.some((c) => c.strategy_name === k) ? 'primary' : 'default'}
              loading={comparingKey === k}
              onClick={() => addToCompare(k)}
            >
              {k}
            </Button>
          ))}
          {compareList.length > 0 && <Button size="small" danger onClick={() => setCompareList([])}>清空</Button>}
        </div>
        {compareList.length > 0 && (
          <Table
            dataSource={compareList}
            rowKey="strategy_name"
            size="small"
            pagination={false}
            columns={[
              { title: '策略', dataIndex: 'strategy_name', width: 160 },
              { title: '总收益', dataIndex: 'total_return', width: 80, render: (v: number) => <span style={{ color: v >= 0 ? '#f5222d' : '#52c41a' }}>{v.toFixed(2)}%</span>, sorter: (a: AnyData, b: AnyData) => a.total_return - b.total_return },
              { title: '年化', dataIndex: 'annualized_return', width: 80, render: (v: number) => `${v.toFixed(2)}%` },
              { title: '回撤', dataIndex: 'max_drawdown', width: 70, render: (v: number) => <span style={{ color: '#52c41a' }}>{v.toFixed(2)}%</span> },
              { title: '夏普', dataIndex: 'sharpe_ratio', width: 70, render: (v: number) => v.toFixed(2), sorter: (a: AnyData, b: AnyData) => a.sharpe_ratio - b.sharpe_ratio },
              { title: '胜率', dataIndex: 'win_rate', width: 70, render: (v: number) => `${v.toFixed(1)}%` },
              { title: '盈亏比', dataIndex: 'profit_loss_ratio', width: 70, render: (v: number) => v.toFixed(2) },
              { title: '交易数', dataIndex: 'total_trades', width: 70 },
              { title: 'Calmar', dataIndex: 'calmar_ratio', width: 70, render: (v: number) => v.toFixed(2) },
            ]}
          />
        )}
      </Card>
      <div style={{ marginTop: 16, color: '#faad14', fontSize: 12 }}>
        当前回测仅在真实历史行情可用时展示，结果仅供参考，不构成投资建议。
      </div>
    </div>
  )
}
