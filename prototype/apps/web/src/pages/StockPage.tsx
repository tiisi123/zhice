import { useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Card, Col, Row, Tag, Empty, Spin, Input, Button, Space, Statistic, Progress, Table, Alert } from 'antd'
import { RobotOutlined, SearchOutlined, ThunderboltOutlined, DollarOutlined, TeamOutlined, LineChartOutlined } from '@ant-design/icons'
import Markdown from 'react-markdown'
import { Link } from 'react-router-dom'
import * as echarts from 'echarts'
import { fetchApi } from '../api/client'
import { askAI } from '../api/copilot'
import AIDisclaimer from '../components/AIDisclaimer'
import AIBadge from '../components/AIBadge'
import MockBanner from '../components/MockBanner'
import { watchlistApi } from '../api/watchlist'
import { message as antMessage } from 'antd'
import { StarOutlined } from '@ant-design/icons'
import type { AnyData } from '../api/types'

const LABEL_COLORS: Record<string, string> = {
  '首板': '#fa8c16', '连板': '#f5222d', '炸板': '#faad14', '热股': '#1677ff',
}

function StockIdentity({ data }: { data: AnyData }) {
  const label = data.kline_label || '—'
  const bc = data.board_count || 0
  const cr = data.change_rate || 0
  const bgColor = bc >= 3 ? 'linear-gradient(135deg,#991b1b,#ef4444)' : bc >= 1 ? 'linear-gradient(135deg,#c2410c,#fb923c)' : cr >= 5 ? 'linear-gradient(135deg,#b45309,#f59e0b)' : 'linear-gradient(135deg,#374151,#6b7280)'

  return (
    <div style={{ background: bgColor, color: '#fff', borderRadius: 12, padding: 20, marginBottom: 16 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 32, fontWeight: 800 }}>{data.name}</span>
        <span style={{ fontSize: 16, opacity: 0.8 }}>{data.code}</span>
        <Tag color={LABEL_COLORS[label.includes('连板') ? '连板' : label] || '#666'} style={{ fontSize: 14, padding: '2px 10px' }}>{label}</Tag>
      </div>
      <div style={{ marginTop: 12, display: 'flex', gap: 24, flexWrap: 'wrap', fontSize: 15 }}>
        <span>涨幅 <b style={{ fontSize: 22 }}>{cr >= 0 ? '+' : ''}{cr.toFixed(2)}%</b></span>
        {bc > 0 && <span>连板 <b style={{ fontSize: 22 }}>{bc}</b> 板</span>}
        <span>{data.match_source ? '封板' : '最新交易日'} <b>{data.time || data.history?.daily?.at?.(-1)?.date || '—'}</b></span>
      </div>
    </div>
  )
}

function ReasonCard({ data }: { data: AnyData }) {
  const inPool = Boolean(data.intraday?.short_pool?.in_pool)
  return (
    <Card title={<span><ThunderboltOutlined style={{ color: '#fa8c16' }} /> 短线状态</span>} size="small" style={{ marginBottom: 16 }}>
      <div style={{ fontSize: 14, lineHeight: 2 }}>
        <div><b>盘中来源：</b><Tag color="blue">KPL 实时池</Tag><Tag>{data.intraday?.trade_date || '—'}</Tag></div>
        <div><b>短线池状态：</b>{inPool ? <Tag color="red">{data.kline_label}</Tag> : <Tag>未进入涨停/炸板/热股池</Tag>}</div>
        <div><b>核心催化：</b>{data.reason || (inPool ? '—' : '无短线池催化，转看 Tushare 历史行情/基本面。')}</div>
        <div>
          <b>所属题材：</b>
          {data.themes?.related_plates?.length > 0
            ? data.themes.related_plates.map((p: string, i: number) => (
                <Link key={i} to={`/theme?name=${encodeURIComponent(p)}`}><Tag color="blue" style={{ cursor: 'pointer' }}>{p}</Tag></Link>
              ))
            : '—'}
        </div>
        <div><b>主题材：</b><Tag color="orange">{data.themes?.main_theme || '—'}</Tag> · 热度 <b style={{ color: '#f5222d' }}>{data.themes?.hot_score || 0}</b></div>
      </div>
    </Card>
  )
}

function SourceCard({ data }: { data: AnyData }) {
  const daily = data.history?.daily || []
  const latest = daily[daily.length - 1] || {}
  return (
    <Card title="数据来源与可分析范围" size="small" style={{ marginBottom: 16 }}>
      <Space direction="vertical" size={6} style={{ width: '100%' }}>
        {(data.data_sources || []).map((s: AnyData) => (
          <div key={`${s.name}-${s.source}`} style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
            <span>{s.name}</span>
            <span><Tag color={s.source === 'tushare' ? 'purple' : 'blue'}>{s.source}</Tag><Tag>{s.status}</Tag></span>
          </div>
        ))}
        <div style={{ fontSize: 12, color: '#666' }}>
          任何 A 股代码均可分析；历史行情、估值和基本资料走 Tushare，盘中实时行情走 KPL 全市场排行，涨停/炸板/热股是 KPL 事件标签。
        </div>
        {data.intraday?.realtime?.stock_code && (
          <div style={{ fontSize: 12, color: '#666' }}>
            KPL 实时：现价 {data.intraday.realtime.price ?? '—'}，涨幅 {data.intraday.realtime.change_rate ?? '—'}%，
            换手 {data.intraday.realtime.turnover_ratio ?? '—'}%，额 {data.intraday.realtime.amount ? (data.intraday.realtime.amount / 1e8).toFixed(2) + '亿' : '—'}
          </div>
        )}
        {latest.date && (
          <div style={{ fontSize: 12, color: '#666' }}>
            Tushare 最新交易日：{latest.date}，收盘 {latest.close ?? '—'}，涨跌幅 {latest.pct_chg ?? '—'}%
          </div>
        )}
      </Space>
    </Card>
  )
}

function CapitalCard({ cf }: { cf: AnyData }) {
  if (!cf) return <Card size="small"><Empty description="暂无资金数据" /></Card>
  const turnover = cf.turnover_ratio || 0
  const cap = cf.non_restricted_capital || 0
  const net = cf.estimated_net_inflow || 0

  return (
    <Card title={<span><DollarOutlined style={{ color: '#1677ff' }} /> 资金画像</span>} size="small" style={{ marginBottom: 16 }}>
      <Row gutter={[12, 12]}>
        <Col span={12}>
          <div style={{ fontSize: 12, color: '#999' }}>换手率</div>
          <Progress percent={Math.min(turnover, 30) / 30 * 100} showInfo={false} strokeColor={turnover > 15 ? '#fa8c16' : '#1677ff'} size="small" />
          <div style={{ fontSize: 14, fontWeight: 600 }}>{turnover.toFixed(1)}%</div>
        </Col>
        <Col span={12}>
          <Statistic title="流通市值" value={cap > 0 ? (cap / 1e8).toFixed(1) : '—'} suffix="亿" valueStyle={{ fontSize: 16 }} />
        </Col>
        <Col span={12}>
          <Statistic title="估算净流入" value={net ? (net / 1e4).toFixed(0) : '—'} suffix="万" valueStyle={{ color: net > 0 ? '#f5222d' : '#52c41a', fontSize: 16 }} />
        </Col>
        <Col span={12}>
          <Statistic title="总市值" value={cf.total_capital > 0 ? (cf.total_capital / 1e8).toFixed(1) : '—'} suffix="亿" valueStyle={{ fontSize: 16 }} />
        </Col>
      </Row>
    </Card>
  )
}

// PRD M4A-06: 强势股模式匹配
function PatternMatchCard({ code, name }: { code: string; name: string }) {
  const [data, setData] = useState<AnyData>(null)
  const [loading, setLoading] = useState(false)
  const chartRef = useRef<HTMLDivElement>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)

  useEffect(() => {
    if (!code) return
    let cancelled = false
    const run = async () => {
      setLoading(true)
      try {
        const r = await fetchApi<AnyData>(`/stock/${code}/pattern-match?top_k=5`)
        if (!cancelled) { setData(r); setSelectedId(r?.matches?.[0]?.id || null) }
      } catch {
        if (!cancelled) setData(null)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void run()
    return () => { cancelled = true }
  }, [code])

  useEffect(() => {
    if (!chartRef.current || !data?.query_seq) return
    const selected = (data.matches || []).find((m: AnyData) => m.id === selectedId) || data.matches?.[0]
    const chart = echarts.init(chartRef.current)
    chart.setOption({
      tooltip: { trigger: 'axis' },
      legend: { data: ['当前个股', selected ? selected.name : '历史相似'], textStyle: { fontSize: 11 } },
      grid: { left: 40, right: 20, top: 32, bottom: 30 },
      xAxis: { type: 'category', data: Array.from({ length: data.query_seq.length }, (_, i) => `D${i + 1}`), axisLabel: { fontSize: 9 } },
      yAxis: { type: 'value', name: '%', axisLabel: { fontSize: 10 } },
      series: [
        { name: '当前个股', type: 'line', data: data.query_seq, smooth: true, lineStyle: { color: '#1677ff', width: 2 }, itemStyle: { color: '#1677ff' } },
        ...(selected ? [{ name: selected.name, type: 'line' as const, data: selected.seq, smooth: true, lineStyle: { color: '#f5222d', width: 2, type: 'dashed' as const }, itemStyle: { color: '#f5222d' } }] : []),
      ],
    })
    const onResize = () => chart.resize()
    window.addEventListener('resize', onResize)
    return () => { window.removeEventListener('resize', onResize); chart.dispose() }
  }, [data, selectedId])

  return (
    <Card
      title={<span><LineChartOutlined style={{ color: '#f5222d' }} /> K 线形态匹配（M4A-06）</span>}
      size="small" style={{ marginBottom: 16 }}
      extra={<Button size="small" type="link" icon={<RobotOutlined />}
        onClick={() => askAI(`${name}(${code}) 当前 K 线形态最相似的历史牛股是 ${data?.matches?.[0]?.stock}，相似度 ${data?.matches?.[0]?.similarity}%。分析两者的相似点与差异，给出操作建议。`)}>AI 解读</Button>}
    >
      {loading ? <Spin /> : !data || !data.matches?.length ? <Empty description={data?.message || '暂无形态匹配数据'} /> : (
        <>
          <div ref={chartRef} style={{ width: '100%', height: 240 }} />
          {data.outlook && (
            <Alert
              type="info" showIcon style={{ margin: '8px 0' }}
              message={<>
                Top {data.matches.length} 历史相似形态加权预测：
                <b style={{ color: '#f5222d' }}> 5 日 {data.outlook.expected_d5 >= 0 ? '+' : ''}{data.outlook.expected_d5}%</b> ·
                <b style={{ color: '#f5222d' }}> 10 日 {data.outlook.expected_d10 >= 0 ? '+' : ''}{data.outlook.expected_d10}%</b> ·
                <b style={{ color: '#f5222d' }}> 20 日 {data.outlook.expected_d20 >= 0 ? '+' : ''}{data.outlook.expected_d20}%</b>
                {' · '}胜率 <b>{data.outlook.avg_win_rate}%</b>
              </>}
            />
          )}
          <Table
            size="small" pagination={false} rowKey="id"
            dataSource={data.matches}
            onRow={(r: AnyData) => ({ onClick: () => setSelectedId(r.id), style: { cursor: 'pointer', background: r.id === selectedId ? '#fff7e6' : undefined } })}
            columns={[
              { title: '形态', dataIndex: 'name', width: 130 },
              { title: '历史样本', dataIndex: 'stock', width: 120 },
              { title: '相似度', dataIndex: 'similarity', width: 80, render: (v: number) => <Tag color={v >= 80 ? 'red' : v >= 60 ? 'orange' : 'default'}>{v}%</Tag> },
              { title: '5日', dataIndex: ['future', 'd5'], width: 60, align: 'right' as const, render: (v: number) => <span style={{ color: v >= 0 ? '#f5222d' : '#52c41a' }}>{v >= 0 ? '+' : ''}{v}%</span> },
              { title: '10日', dataIndex: ['future', 'd10'], width: 60, align: 'right' as const, render: (v: number) => <span style={{ color: v >= 0 ? '#f5222d' : '#52c41a' }}>{v >= 0 ? '+' : ''}{v}%</span> },
              { title: '20日', dataIndex: ['future', 'd20'], width: 60, align: 'right' as const, render: (v: number) => <span style={{ color: v >= 0 ? '#f5222d' : '#52c41a' }}>{v >= 0 ? '+' : ''}{v}%</span> },
              { title: '胜率', dataIndex: ['future', 'win_rate'], width: 60, align: 'right' as const, render: (v: number) => `${v}%` },
            ]}
          />
          <AIBadge style={{ marginBottom: 8 }} />
          <AIDisclaimer variant="inline" />
        </>
      )}
    </Card>
  )
}

function LinkedStocks({ stocks }: { stocks: AnyData[] }) {
  if (!stocks || stocks.length === 0) return null
  return (
    <Card title={<span><TeamOutlined style={{ color: '#722ed1' }} /> 同题材联动</span>} size="small" style={{ marginBottom: 16 }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        {stocks.map(s => (
          <Link key={s.code} to={`/stock/${s.code}`}>
            <Tag color={s.board_count >= 2 ? 'red' : s.board_count >= 1 ? 'orange' : 'default'} style={{ fontSize: 13, padding: '4px 10px' }}>
              {s.name} {s.board_count > 0 ? `${s.board_count}板` : ''}
              <span style={{ color: s.change_rate >= 0 ? '#f5222d' : '#52c41a', marginLeft: 6 }}>{(s.change_rate || 0).toFixed(2)}%</span>
            </Tag>
          </Link>
        ))}
      </div>
    </Card>
  )
}

export default function StockPage() {
  const { code: routeCode } = useParams()
  const [code, setCode] = useState(routeCode || '600519')
  const [inputCode, setInputCode] = useState(routeCode || '600519')
  const [data, setData] = useState<AnyData>(null)
  const [insight, setInsight] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [insightLoading, setInsightLoading] = useState(false)

  const load = async (c: string) => {
    if (!c.trim()) return
    setLoading(true); setInsight(null)
    try {
      const detail = await fetchApi<AnyData>(`/stock/${c}`)
      setData(detail)
    } catch { setData(null) }
    setLoading(false)
  }

  useEffect(() => {
    if (routeCode) {
      const sync = () => { setCode(routeCode); setInputCode(routeCode) }
      sync()
    }
  }, [routeCode])
  useEffect(() => {
    if (code) {
      const run = async () => { await load(code) }
      void run()
    }
  }, [code])

  useEffect(() => {
    if (data?.found && code) {
      let cancelled = false
      const run = async () => {
        setInsightLoading(true)
        try {
          const r = await fetchApi<AnyData>(`/ai/stock-insight/${code}`)
          if (!cancelled) setInsight(r.report)
        } catch {
          if (!cancelled) setInsight(null)
        } finally {
          if (!cancelled) setInsightLoading(false)
        }
      }
      void run()
      return () => { cancelled = true }
    }
  }, [data, code])

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '120px auto' }} />

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
        <h2 style={{ margin: 0 }}>个股分析</h2>
        <Input
          value={inputCode} onChange={e => setInputCode(e.target.value)}
          onPressEnter={() => setCode(inputCode)}
          style={{ width: 130 }} placeholder="股票代码" prefix={<SearchOutlined />}
        />
        <Button type="primary" onClick={() => setCode(inputCode)}>查询</Button>
        {data?.found && (
          <Button
            icon={<StarOutlined />}
            onClick={async () => {
              try {
                await watchlistApi.add({
                  code: data.code, name: data.name || '',
                  alert_limit_up: true, alert_broken: true,
                })
                antMessage.success(`已加入研究池：${data.name || data.code}`)
              } catch (e) {
                if (String((e as Error)?.message || '').includes('已在')) antMessage.info('该股票已在研究池中')
                else antMessage.error('加入失败，请确认已登录')
              }
            }}
          >加入研究池</Button>
        )}
        <MockBanner show={!!data?.mock} />
      </div>

      {!data && <Card><Empty description="请输入股票代码后查询" /></Card>}
      {data && !data.found && <Card><Empty description={data.message || '未找到该股票数据'} /></Card>}

      {data?.found && (
        <>
          <StockIdentity data={data} />
          <Row gutter={16}>
            <Col xs={24} lg={12}>
              <SourceCard data={data} />
              <ReasonCard data={data} />
              <CapitalCard cf={data.capital_flow} />
            </Col>
            <Col xs={24} lg={12}>
              <LinkedStocks stocks={data.linked_stocks} />
              <Card
                title={<span><RobotOutlined style={{ color: '#1677ff' }} /> AI 洞察</span>}
                size="small"
                loading={insightLoading}
              >
                {insight ? (
                  <div style={{ fontSize: 13, lineHeight: 1.8 }}><Markdown>{insight}</Markdown></div>
                ) : (
                  <Empty description="AI 分析加载中..." />
                )}
              </Card>
            </Col>
          </Row>

          <PatternMatchCard code={data.code} name={data.name} />

          <Card size="small" title={<span><RobotOutlined style={{ color: '#1677ff' }} /> 向 AI 追问</span>} style={{ marginTop: 16 }}>
            <Space wrap>
              <Button type="primary" icon={<RobotOutlined />}
                onClick={() => askAI(`深度分析【${data.name}(${data.code})】：${data.board_count >= 2 ? data.board_count + '连板' : '首板'}涨停，题材「${data.themes?.main_theme}」，换手${data.capital_flow?.turnover_ratio}%。分析：1)涨停核心驱动 2)明日溢价预期 3)同题材谁更强。`)}
              >
                深度分析
              </Button>
              <Button onClick={() => askAI(`${data.name}所在的「${data.themes?.main_theme}」题材，处于什么阶段？明日是否还有延续性？`)}>题材延续性</Button>
              <Button onClick={() => askAI(`${data.name}的换手率${data.capital_flow?.turnover_ratio}%，流通市值${data.capital_flow?.non_restricted_capital ? (data.capital_flow.non_restricted_capital / 1e8).toFixed(0) + '亿' : '—'}，这种资金结构意味着什么？是否健康？`)}>资金解读</Button>
            </Space>
          </Card>

          <div style={{ fontSize: 11, color: '#999', textAlign: 'center', marginTop: 16, borderTop: '1px solid #f0f0f0', paddingTop: 8 }}>
            本内容仅为个股公开信息分析汇总，非荐股建议。投资决策请独立判断。
          </div>
        </>
      )}
    </div>
  )
}
