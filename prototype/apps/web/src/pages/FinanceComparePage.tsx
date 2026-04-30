import { useEffect, useRef, useState } from 'react'
import { Card, Input, Button, Space, Tag, Table, Empty, Spin, message, Alert, Row, Col } from 'antd'
import { CloseOutlined, PlusOutlined, BarChartOutlined, RobotOutlined } from '@ant-design/icons'
import * as echarts from 'echarts'
import { postApi } from '../api/client'
import { askAI } from '../api/copilot'
import AIDisclaimer from '../components/AIDisclaimer'

interface CompareRow {
  code: string
  name: string
  industry: string
  price: number
  change_rate: number
  pe_ttm: number
  pb: number
  market_cap: number
  circ_cap: number
  latest_period: string | null
  revenue: number
  net_profit: number
  roe: number
  eps: number
  gross_margin: number
  yoy_revenue: number
  yoy_profit: number
  trend_revenue: number[]
  trend_net_profit: number[]
  trend_roe: number[]
  trend_periods: string[]
}

interface CompareResp {
  rows: CompareRow[]
  rankings: Record<string, string[]>
  metric_labels: Record<string, string>
}

const fmtCap = (v: number) => v ? `${(v / 1e8).toFixed(1)}亿` : '—'
const fmtRev = (v: number) => v ? `${(v / 1e8).toFixed(2)}亿` : '—'
const fmtPct = (v: number) => v == null ? '—' : `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`

export default function FinanceComparePage() {
  const [codes, setCodes] = useState<string[]>(['600519', '000858'])
  const [input, setInput] = useState('')
  const [data, setData] = useState<CompareResp | null>(null)
  const [loading, setLoading] = useState(false)
  const radarRef = useRef<HTMLDivElement>(null)
  const lineRef = useRef<HTMLDivElement>(null)

  const addCode = () => {
    const c = input.trim()
    if (!/^\d{6}$/.test(c)) { message.warning('请输入 6 位股票代码'); return }
    if (codes.includes(c)) { message.info('已添加'); return }
    if (codes.length >= 5) { message.warning('最多对比 5 只'); return }
    setCodes([...codes, c])
    setInput('')
  }
  const removeCode = (c: string) => setCodes(codes.filter(x => x !== c))

  const run = async () => {
    if (codes.length < 2) { message.warning('至少 2 只股票'); return }
    setLoading(true)
    try {
      const r = await postApi<CompareResp>('/finance/compare', { codes })
      setData(r)
    } catch (e: any) {
      message.error(e?.message || '对比失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { run() }, []) // eslint-disable-line

  // 雷达图
  useEffect(() => {
    if (!data || !radarRef.current) return
    const chart = echarts.init(radarRef.current)
    const indicators = [
      { name: 'ROE', max: Math.max(...data.rows.map(r => r.roe || 0), 30) },
      { name: '营收同比', max: Math.max(...data.rows.map(r => r.yoy_revenue || 0), 50) },
      { name: '净利同比', max: Math.max(...data.rows.map(r => r.yoy_profit || 0), 50) },
      { name: '毛利率', max: Math.max(...data.rows.map(r => r.gross_margin || 0), 60) },
      { name: '低估(1/PE)', max: 0.2 },
    ]
    chart.setOption({
      tooltip: {},
      legend: { data: data.rows.map(r => r.name), bottom: 0 },
      radar: { indicator: indicators, radius: '65%' },
      series: [{
        type: 'radar',
        data: data.rows.map(r => ({
          name: r.name,
          value: [
            r.roe || 0,
            r.yoy_revenue || 0,
            r.yoy_profit || 0,
            r.gross_margin || 0,
            r.pe_ttm > 0 ? +(1 / r.pe_ttm).toFixed(4) : 0,
          ],
        })),
      }],
    })
    const onResize = () => chart.resize()
    window.addEventListener('resize', onResize)
    return () => { window.removeEventListener('resize', onResize); chart.dispose() }
  }, [data])

  // 营收趋势折线
  useEffect(() => {
    if (!data || !lineRef.current) return
    const chart = echarts.init(lineRef.current)
    // 用每一只股票自己的 periods 做 X 轴并集（按时间正序）
    const allPeriods = Array.from(new Set(data.rows.flatMap(r => r.trend_periods))).sort()
    chart.setOption({
      tooltip: { trigger: 'axis' },
      legend: { data: data.rows.map(r => r.name), top: 0 },
      grid: { left: 50, right: 30, top: 40, bottom: 30 },
      xAxis: { type: 'category', data: allPeriods, axisLabel: { fontSize: 11 } },
      yAxis: { type: 'value', name: '营收(亿)', axisLabel: { formatter: (v: number) => (v / 1e8).toFixed(0) } },
      series: data.rows.map(r => {
        const map = new Map<string, number>()
        r.trend_periods.forEach((p, i) => map.set(p, r.trend_revenue[i] || 0))
        return {
          name: r.name, type: 'line', smooth: true,
          data: allPeriods.map(p => map.get(p) || null),
          connectNulls: true,
        }
      }),
    })
    const onResize = () => chart.resize()
    window.addEventListener('resize', onResize)
    return () => { window.removeEventListener('resize', onResize); chart.dispose() }
  }, [data])

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
        <h2 style={{ margin: 0 }}><BarChartOutlined style={{ color: '#1677ff' }} /> 多公司财务对比（M4D-04 / M4D-06）</h2>
      </div>

      <Card size="small" style={{ marginBottom: 16 }}>
        <Space wrap>
          {codes.map(c => (
            <Tag key={c} closable closeIcon={<CloseOutlined />} onClose={() => removeCode(c)}
              color="blue" style={{ fontSize: 13, padding: '4px 8px' }}>
              {c}
            </Tag>
          ))}
          <Input
            placeholder="6 位代码，如 600519"
            value={input}
            onChange={e => setInput(e.target.value)}
            onPressEnter={addCode}
            style={{ width: 160 }}
            maxLength={6}
          />
          <Button icon={<PlusOutlined />} onClick={addCode}>添加</Button>
          <Button type="primary" loading={loading} onClick={run}>开始对比（{codes.length}/5）</Button>
        </Space>
      </Card>

      {loading && <div style={{ textAlign: 'center', padding: 60 }}><Spin size="large" /></div>}

      {data && data.rows.length > 0 && (
        <>
          <Row gutter={16}>
            <Col xs={24} lg={10}>
              <Card size="small" title="综合能力雷达图" style={{ marginBottom: 16 }}>
                <div ref={radarRef} style={{ width: '100%', height: 320 }} />
              </Card>
            </Col>
            <Col xs={24} lg={14}>
              <Card size="small" title="营收趋势对比" style={{ marginBottom: 16 }}>
                <div ref={lineRef} style={{ width: '100%', height: 320 }} />
              </Card>
            </Col>
          </Row>

          <Card size="small" title="核心指标对比" style={{ marginBottom: 16 }}>
            <Table<CompareRow>
              dataSource={data.rows}
              rowKey="code"
              size="small"
              pagination={false}
              scroll={{ x: 1200 }}
              columns={[
                { title: '代码', dataIndex: 'code', width: 80 },
                { title: '名称', dataIndex: 'name', width: 100, render: (v, r) => <b>{v || r.code}</b> },
                { title: '行业', dataIndex: 'industry', width: 100, ellipsis: true },
                { title: '现价', dataIndex: 'price', width: 80, render: (v: number) => v?.toFixed?.(2) },
                {
                  title: '涨跌', dataIndex: 'change_rate', width: 80,
                  render: (v: number) => <span style={{ color: v >= 0 ? '#f5222d' : '#52c41a' }}>{fmtPct(v)}</span>,
                },
                { title: 'PE-TTM', dataIndex: 'pe_ttm', width: 80, render: (v: number) => v?.toFixed?.(2) || '—' },
                { title: 'PB', dataIndex: 'pb', width: 70, render: (v: number) => v?.toFixed?.(2) || '—' },
                { title: '总市值', dataIndex: 'market_cap', width: 90, render: fmtCap },
                { title: '报告期', dataIndex: 'latest_period', width: 100 },
                { title: '营收', dataIndex: 'revenue', width: 90, render: fmtRev },
                { title: '净利', dataIndex: 'net_profit', width: 90, render: fmtRev },
                { title: 'ROE%', dataIndex: 'roe', width: 80, render: (v: number) => v?.toFixed?.(2) },
                { title: '毛利率%', dataIndex: 'gross_margin', width: 80, render: (v: number) => v?.toFixed?.(2) },
                {
                  title: '营收同比', dataIndex: 'yoy_revenue', width: 90,
                  render: (v: number) => <span style={{ color: v >= 0 ? '#f5222d' : '#52c41a' }}>{fmtPct(v)}</span>,
                },
                {
                  title: '净利同比', dataIndex: 'yoy_profit', width: 90,
                  render: (v: number) => <span style={{ color: v >= 0 ? '#f5222d' : '#52c41a' }}>{fmtPct(v)}</span>,
                },
              ]}
            />
          </Card>

          <Card size="small" title="单项排名" style={{ marginBottom: 16 }}>
            <Row gutter={[12, 12]}>
              {Object.entries(data.rankings).map(([k, ranked]) => (
                <Col key={k} xs={24} md={12} lg={8}>
                  <div style={{ background: '#fafafa', padding: 10, borderRadius: 4 }}>
                    <div style={{ fontWeight: 600, marginBottom: 6 }}>{data.metric_labels[k] || k}</div>
                    {ranked.map((c, i) => {
                      const r = data.rows.find(x => x.code === c)
                      return (
                        <div key={c} style={{ fontSize: 12, lineHeight: 1.8 }}>
                          <Tag color={i === 0 ? 'gold' : i === 1 ? 'blue' : 'default'}>#{i + 1}</Tag>
                          {r?.name || c}
                        </div>
                      )
                    })}
                  </div>
                </Col>
              ))}
            </Row>
          </Card>

          <Card size="small" title={<span><RobotOutlined style={{ color: '#1677ff' }} /> AI 横向对比</span>}>
            <Space wrap>
              <Button type="primary" icon={<RobotOutlined />}
                onClick={() => askAI(`请对以下公司做横向对比并给出投资倾向：${data.rows.map(r => `${r.name}(${r.code}): PE ${r.pe_ttm?.toFixed(1)}, ROE ${r.roe?.toFixed(1)}%, 营收同比 ${r.yoy_revenue?.toFixed(1)}%, 净利同比 ${r.yoy_profit?.toFixed(1)}%, 毛利率 ${r.gross_margin?.toFixed(1)}%`).join('；')}。从估值/成长/质量三维度评分（0-10），最后给出排序与买入建议。`)}>
                生成对比报告
              </Button>
              <Button onClick={() => askAI(`这几家公司（${data.rows.map(r => r.name).join('、')}）的护城河和行业地位有哪些差异？谁更值得长期持有？`)}>
                护城河分析
              </Button>
            </Space>
            <AIDisclaimer variant="inline" />
          </Card>
        </>
      )}

      {data && data.rows.length === 0 && (
        <Card><Empty description="无对比数据" /></Card>
      )}

      <Alert
        type="info" showIcon style={{ marginTop: 12 }}
        message="数据来源：东方财富（dfcf）公开接口"
        description="财务摘要按报告期倒序，最新一期可能为业绩预告或快报，正式年报以审计版为准。"
      />
    </div>
  )
}
