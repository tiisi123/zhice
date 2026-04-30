import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Card, Col, Row, Spin, Tag, Empty, Select, Space, Button, Progress, Alert, Tooltip, Statistic,
} from 'antd'
import { RobotOutlined, HistoryOutlined, AimOutlined, LineChartOutlined } from '@ant-design/icons'
import * as echarts from 'echarts'
import { Link } from 'react-router-dom'
import { fetchApi } from '../api/client'
import { askAI } from '../api/copilot'
import type { AnyData } from '../api/types'

interface SentimentRecord {
  date: string
  limit_up: number
  broken: number
  broken_rate: number
  max_board: number
  sentiment: string
  score: number
  up?: number
  down?: number
}

interface PhaseResp {
  phase: string
  confidence: number
  slope?: number
  basis: string
  recent?: SentimentRecord[]
}

interface SimilarMatch {
  date: string
  distance: number
  snapshot: { limit_up: number; broken: number; broken_rate: number; max_board: number; sentiment: string }
  forward: {
    days: number; dates: string[]
    limit_up_series: number[]; max_board_series: number[]; sentiment_series: string[]
    limit_up_avg: number | null; max_board_peak: number | null
  }
}

interface SimilarResp {
  target: SentimentRecord | null
  matches: SimilarMatch[]
  note?: string
}

// ========== 配色 ==========
const SENT_COLOR: Record<string, string> = {
  '冰点': '#1e40af', '低迷': '#3b82f6', '中性': '#a3a3a3', '回暖': '#fb923c', '高潮': '#ef4444',
}
const PHASE_THEME: Record<string, { color: string; emoji: string; desc: string }> = {
  '冰点': { color: '#1e40af', emoji: '🧊', desc: '市场极度低迷，涨停稀少，底部信号' },
  '筑底': { color: '#3b82f6', emoji: '⛰️', desc: '情绪自低位修复，涨停开始抬头' },
  '回升': { color: '#fb923c', emoji: '📈', desc: '涨停数稳步上行，高度逐步打开' },
  '高潮': { color: '#ef4444', emoji: '🚀', desc: '情绪高峰，封板率高，资金踊跃' },
  '顶背离': { color: '#c026d3', emoji: '⚠️', desc: '涨停见顶回落，谨防高位风险' },
  '退潮': { color: '#64748b', emoji: '🌧️', desc: '情绪下行，高度衰竭，防御为主' },
  '中性': { color: '#a3a3a3', emoji: '⚖️', desc: '震荡整理，方向不明' },
  '未知': { color: '#999', emoji: '❓', desc: '数据不足' },
}

// ========== Section A · 周期相位 ==========
function SectionPhase({ phase, latest }: { phase: PhaseResp | null; latest: SentimentRecord | null }) {
  if (!phase) return <Card loading size="small" />
  const theme = PHASE_THEME[phase.phase] || PHASE_THEME['未知']
  const ORDER = ['冰点', '筑底', '回升', '高潮', '顶背离', '退潮']
  const curIdx = ORDER.indexOf(phase.phase)

  const aiPrompt = `当前市场处于【${phase.phase}】相位（置信度 ${(phase.confidence * 100).toFixed(0)}%），${phase.basis}。结合 A 股历史周期规律，后续 3-5 个交易日最可能的演绎路径？操作层面如何应对？`

  return (
    <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
      <Col xs={24} md={10}>
        <Card size="small" style={{ height: '100%', borderLeft: `4px solid ${theme.color}` }}>
          <div style={{ fontSize: 12, color: '#999' }}>当前周期相位</div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginTop: 4 }}>
            <span style={{ fontSize: 48, fontWeight: 800 }}>{theme.emoji}</span>
            <span style={{ fontSize: 32, fontWeight: 700, color: theme.color }}>{phase.phase}</span>
          </div>
          <div style={{ fontSize: 13, color: '#666', marginTop: 8 }}>{theme.desc}</div>
          <div style={{ marginTop: 12 }}>
            <div style={{ fontSize: 12, color: '#999', marginBottom: 4 }}>
              置信度 <b style={{ color: theme.color }}>{(phase.confidence * 100).toFixed(0)}%</b>
              {phase.slope !== undefined && (
                <span style={{ marginLeft: 8 }}>
                  趋势 {phase.slope > 0 ? '↑' : phase.slope < 0 ? '↓' : '→'} {phase.slope}
                </span>
              )}
            </div>
            <Progress percent={phase.confidence * 100} showInfo={false} strokeColor={theme.color} size="small" />
          </div>
          <div style={{ fontSize: 12, color: '#999', marginTop: 8, lineHeight: 1.5 }}>
            {phase.basis}
          </div>
          <Button type="primary" ghost block icon={<RobotOutlined />} style={{ marginTop: 12 }}
            onClick={() => askAI(aiPrompt)}
          >
            AI 解读当前相位
          </Button>
        </Card>
      </Col>
      <Col xs={24} md={14}>
        <Card size="small" title={<span><AimOutlined /> 周期相位轴</span>} style={{ height: '100%' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 0', position: 'relative' }}>
            {ORDER.map((p, i) => {
              const active = i === curIdx
              const past = i < curIdx
              const t = PHASE_THEME[p]
              return (
                <div key={p} style={{ textAlign: 'center', flex: 1, minWidth: 0 }}>
                  <div style={{
                    width: active ? 48 : 32, height: active ? 48 : 32,
                    lineHeight: `${active ? 48 : 32}px`, margin: '0 auto',
                    borderRadius: '50%', fontSize: active ? 22 : 16,
                    background: active ? t.color : past ? '#e5e7eb' : '#f3f4f6',
                    color: active ? '#fff' : '#999',
                    boxShadow: active ? `0 0 0 4px ${t.color}33` : 'none',
                    transition: 'all 0.3s',
                  }}>
                    {t.emoji}
                  </div>
                  <div style={{
                    fontSize: 12, marginTop: 6,
                    fontWeight: active ? 700 : 400,
                    color: active ? t.color : '#999',
                  }}>{p}</div>
                </div>
              )
            })}
          </div>
          {latest && (
            <Row gutter={8} style={{ marginTop: 16 }}>
              <Col span={6}><Statistic title="涨停" value={latest.limit_up} valueStyle={{ fontSize: 18, color: '#f5222d' }} /></Col>
              <Col span={6}><Statistic title="炸板率" value={latest.broken_rate} precision={1} suffix="%" valueStyle={{ fontSize: 18 }} /></Col>
              <Col span={6}><Statistic title="最高板" value={latest.max_board} suffix="板" valueStyle={{ fontSize: 18 }} /></Col>
              <Col span={6}><Statistic title="强度" value={latest.score} valueStyle={{ fontSize: 18 }} /></Col>
            </Row>
          )}
        </Card>
      </Col>
    </Row>
  )
}

// ========== Section B · 周期走势主图 ==========
function SectionCycleChart({ data }: { data: SentimentRecord[] }) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!ref.current || data.length === 0) return
    const chart = echarts.init(ref.current)
    const dates = data.map(d => d.date.slice(5))

    // 情绪背景填色区（markArea 按情绪段）
    const markAreas: AnyData[] = []
    let segStart = 0
    for (let i = 1; i <= data.length; i++) {
      if (i === data.length || data[i].sentiment !== data[segStart].sentiment) {
        const sent = data[segStart].sentiment
        markAreas.push([
          { xAxis: dates[segStart], itemStyle: { color: (SENT_COLOR[sent] || '#999') + '18' } },
          { xAxis: dates[Math.min(i - 1, dates.length - 1)] },
        ])
        segStart = i
      }
    }

    chart.setOption({
      tooltip: {
        trigger: 'axis',
        formatter: (params: AnyData) => {
          const idx = params[0].dataIndex
          const r = data[idx]
          return `${r.date}<br/>情绪: <b style="color:${SENT_COLOR[r.sentiment]||'#999'}">${r.sentiment}</b><br/>涨停: ${r.limit_up} · 炸板: ${r.broken}<br/>炸板率: ${r.broken_rate}% · 最高板: ${r.max_board}`
        },
      },
      legend: { data: ['涨停', '炸板率', '最高板'], bottom: 0, textStyle: { fontSize: 12 } },
      grid: { left: 48, right: 48, top: 16, bottom: 36 },
      xAxis: { type: 'category', data: dates, axisLabel: { fontSize: 10 } },
      yAxis: [
        { type: 'value', name: '涨停数', position: 'left', splitLine: { lineStyle: { type: 'dashed' } } },
        { type: 'value', name: '炸板率/最高板', position: 'right' },
      ],
      series: [
        {
          name: '涨停', type: 'bar', data: data.map(d => d.limit_up),
          itemStyle: {
            color: (p: AnyData) => SENT_COLOR[data[p.dataIndex].sentiment] || '#999',
            opacity: 0.75,
          },
          markArea: { silent: true, data: markAreas },
        },
        {
          name: '炸板率', type: 'line', yAxisIndex: 1, data: data.map(d => d.broken_rate),
          smooth: true, lineStyle: { color: '#722ed1', width: 2 }, itemStyle: { color: '#722ed1' }, symbol: 'none',
        },
        {
          name: '最高板', type: 'line', yAxisIndex: 1, data: data.map(d => d.max_board),
          smooth: true, lineStyle: { color: '#13c2c2', width: 2 }, itemStyle: { color: '#13c2c2' }, symbol: 'none',
        },
      ],
    })
    const onResize = () => chart.resize()
    window.addEventListener('resize', onResize)
    return () => { window.removeEventListener('resize', onResize); chart.dispose() }
  }, [data])

  return (
    <Card
      size="small"
      title={<span><LineChartOutlined /> 情绪周期走势（背景色标记情绪段）</span>}
      style={{ marginBottom: 16 }}
    >
      {data.length === 0 ? (
        <Empty description="暂无情绪历史数据。数据将在每日收盘后自动采集。" />
      ) : (
        <div ref={ref} style={{ width: '100%', height: 360 }} />
      )}
    </Card>
  )
}

// ========== Section C · 历史相似日 ==========
function SectionSimilar({ similar }: { similar: SimilarResp | null }) {
  if (!similar) return <Card loading size="small" title="历史相似日" />

  if (similar.note) {
    return (
      <Card size="small" title={<span><HistoryOutlined /> 历史相似日</span>} style={{ marginBottom: 16 }}>
        <Alert type="info" showIcon message="数据累积中" description={similar.note} />
      </Card>
    )
  }

  return (
    <Card size="small" title={<span><HistoryOutlined /> 历史相似日 · 基于多维度距离</span>} style={{ marginBottom: 16 }}>
      <div style={{ fontSize: 12, color: '#666', marginBottom: 10 }}>
        基于「涨停数 / 炸板率 / 最高板 / 情绪等级」四维特征匹配，Top {similar.matches.length} 最相似交易日：
      </div>
      <Row gutter={[12, 12]}>
        {similar.matches.map((m) => <SimilarCard key={m.date} match={m} />)}
      </Row>
      <div style={{ marginTop: 12 }}>
        <Button type="link" icon={<RobotOutlined />}
          onClick={() => askAI(`当前市场状态在历史上最相似的几天是 ${similar.matches.map(m => m.date).join('、')}，结合这些历史相似日的后续走势（${similar.matches.slice(0, 3).map(m => `${m.date} 后 ${m.forward.days}日平均涨停 ${m.forward.limit_up_avg}`).join('；')}），判断当前市场后续 3-5 日可能的演绎。`)}
        >
          让 AI 综合分析这些相似日
        </Button>
      </div>
    </Card>
  )
}

function SimilarCard({ match }: { match: SimilarMatch }) {
  const ref = useRef<HTMLDivElement>(null)
  const snap = match.snapshot
  const fwd = match.forward

  useEffect(() => {
    if (!ref.current || !fwd.limit_up_series.length) return
    const chart = echarts.init(ref.current)
    chart.setOption({
      grid: { left: 24, right: 8, top: 8, bottom: 18 },
      xAxis: { type: 'category', data: fwd.dates.map(d => d.slice(5)), axisLabel: { fontSize: 9 } },
      yAxis: { type: 'value', axisLabel: { fontSize: 9 }, splitLine: { show: false } },
      series: [{
        type: 'line', smooth: true, showSymbol: false,
        data: fwd.limit_up_series,
        areaStyle: { opacity: 0.2 },
        itemStyle: { color: '#fa8c16' }, lineStyle: { width: 2 },
      }],
    })
    const onResize = () => chart.resize()
    window.addEventListener('resize', onResize)
    return () => { window.removeEventListener('resize', onResize); chart.dispose() }
  }, [fwd])

  return (
    <Col xs={24} md={12} lg={8}>
      <Card size="small" hoverable bodyStyle={{ padding: 12 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
          <b style={{ fontSize: 14 }}>{match.date}</b>
          <Tag color={SENT_COLOR[snap.sentiment] ? undefined : 'default'}
            style={{ backgroundColor: SENT_COLOR[snap.sentiment] || undefined, color: '#fff', border: 'none' }}>
            {snap.sentiment}
          </Tag>
        </div>
        <div style={{ fontSize: 12, color: '#666', marginTop: 4 }}>
          涨停 <b>{snap.limit_up}</b> · 炸板 {snap.broken} ({snap.broken_rate}%) · 最高 {snap.max_board}板
        </div>
        <div style={{ fontSize: 11, color: '#999', marginTop: 2 }}>相似度距离 {match.distance}</div>
        <div style={{ borderTop: '1px dashed #eee', marginTop: 8, paddingTop: 8 }}>
          <div style={{ fontSize: 12, color: '#666', marginBottom: 2 }}>
            后 {fwd.days} 日走势：均涨停 <b style={{ color: '#f5222d' }}>{fwd.limit_up_avg ?? '—'}</b>
            {fwd.max_board_peak !== null && <span> · 最高 <b>{fwd.max_board_peak}板</b></span>}
          </div>
          <div ref={ref} style={{ width: '100%', height: 56 }} />
          <div style={{ display: 'flex', gap: 2, marginTop: 4, flexWrap: 'wrap' }}>
            {fwd.sentiment_series.map((s, i) => (
              <Tooltip key={i} title={`${fwd.dates[i]}: ${s}`}>
                <div style={{
                  width: 10, height: 10, borderRadius: 2,
                  background: SENT_COLOR[s] || '#ddd',
                }} />
              </Tooltip>
            ))}
          </div>
        </div>
      </Card>
    </Col>
  )
}

// ========== Section D · 情绪段统计 ==========
function SectionStats({ data }: { data: SentimentRecord[] }) {
  const stats = useMemo(() => {
    const byPhase: Record<string, { count: number; luSum: number; mbSum: number; streaks: number[] }> = {}
    // 连续段长度
    let i = 0
    while (i < data.length) {
      const s = data[i].sentiment
      let j = i
      while (j < data.length && data[j].sentiment === s) j++
      if (!byPhase[s]) byPhase[s] = { count: 0, luSum: 0, mbSum: 0, streaks: [] }
      byPhase[s].streaks.push(j - i)
      for (let k = i; k < j; k++) {
        byPhase[s].count++
        byPhase[s].luSum += data[k].limit_up || 0
        byPhase[s].mbSum += data[k].max_board || 0
      }
      i = j
    }
    return Object.entries(byPhase).map(([name, v]) => ({
      name,
      days: v.count,
      avgLu: v.count ? Math.round(v.luSum / v.count * 10) / 10 : 0,
      avgMb: v.count ? Math.round(v.mbSum / v.count * 10) / 10 : 0,
      avgStreak: v.streaks.length ? Math.round(v.streaks.reduce((a, b) => a + b, 0) / v.streaks.length * 10) / 10 : 0,
    })).sort((a, b) => b.days - a.days)
  }, [data])

  if (data.length < 5) return null
  return (
    <Card size="small" title={<span>📊 情绪段统计（基于 {data.length} 日样本）</span>} style={{ marginBottom: 16 }}>
      <Row gutter={[12, 12]}>
        {stats.map(s => (
          <Col xs={12} md={6} lg={4} key={s.name}>
            <Card size="small" bodyStyle={{ padding: 10 }}
              style={{ borderTop: `3px solid ${SENT_COLOR[s.name] || '#999'}` }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: SENT_COLOR[s.name] || '#999' }}>{s.name}</div>
              <div style={{ fontSize: 11, color: '#999', marginTop: 4 }}>
                累计 <b style={{ color: '#262626' }}>{s.days}</b> 日
              </div>
              <div style={{ fontSize: 11, color: '#999' }}>
                平均每段 <b style={{ color: '#262626' }}>{s.avgStreak}</b> 日
              </div>
              <div style={{ fontSize: 11, color: '#999' }}>
                均涨停 <b style={{ color: '#f5222d' }}>{s.avgLu}</b> · 均最高 <b>{s.avgMb}</b>板
              </div>
            </Card>
          </Col>
        ))}
      </Row>
    </Card>
  )
}

// ========== 主组件 ==========
export default function SentimentPageV2() {
  const [data, setData] = useState<SentimentRecord[]>([])
  const [phase, setPhase] = useState<PhaseResp | null>(null)
  const [similar, setSimilar] = useState<SimilarResp | null>(null)
  const [loading, setLoading] = useState(true)
  const [days, setDays] = useState(30)

  useEffect(() => {
    setLoading(true)
    fetchApi<{ data: SentimentRecord[] }>(`/market/sentiment-history?days=${days}`)
      .then(r => setData(r.data || []))
      .catch(() => setData([]))
      .finally(() => setLoading(false))
  }, [days])

  useEffect(() => {
    fetchApi<PhaseResp>('/market/sentiment-phase').then(setPhase).catch(() => setPhase(null))
    fetchApi<SimilarResp>('/market/similar-days?top_k=6&forward=5').then(setSimilar).catch(() => setSimilar({ target: null, matches: [], note: '加载失败' }))
  }, [])

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '120px auto' }} />

  const latest = data.length > 0 ? data[data.length - 1] : null

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
        <h2 style={{ margin: 0 }}>情绪周期</h2>
        <Select
          value={days}
          onChange={setDays}
          style={{ width: 120 }}
          options={[
            { label: '近 10 天', value: 10 }, { label: '近 30 天', value: 30 },
            { label: '近 60 天', value: 60 }, { label: '近 120 天', value: 120 },
          ]}
        />
        <Space style={{ marginLeft: 'auto' }}>
          <Link to="/replay" style={{ fontSize: 12 }}>← 收盘复盘</Link>
          <Link to="/intraday" style={{ fontSize: 12 }}>盘中盯盘 →</Link>
          <Link to="/sentiment-legacy" style={{ fontSize: 12, color: '#999' }}>切换旧版 →</Link>
        </Space>
      </div>

      <SectionPhase phase={phase} latest={latest} />
      <SectionCycleChart data={data} />
      <SectionSimilar similar={similar} />
      <SectionStats data={data} />
    </div>
  )
}
