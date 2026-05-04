import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Card, Col, Row, Tag, Spin, Statistic, Button, Space, Empty, Tooltip, Alert, DatePicker, Radio, Tabs } from 'antd'
import {
  ArrowUpOutlined, FireOutlined, ThunderboltOutlined,
  RobotOutlined, CrownOutlined, DollarOutlined,
  RiseOutlined, BulbOutlined, AimOutlined,
} from '@ant-design/icons'
import * as echarts from 'echarts'
import dayjs from 'dayjs'
import { Link } from 'react-router-dom'
import { fetchApi } from '../api/client'
import { askAI } from '../api/copilot'
import AIDisclaimer from '../components/AIDisclaimer'
import AIBadge from '../components/AIBadge'
import type { MarketSummary, LadderData, LimitUpStock, AnyData, ApiMeta, DataStatus } from '../api/types'
import { extractMetaList } from '../api/useApiMeta'
import DataStatusBadge from '../components/DataStatusBadge'
import {
  AIInlineSummary, ContradictionAlert, DeltaIndicator,
  ProgressiveFold, AskAIChip, SectionHeader,
  type ContradictionRule,
} from '../components/smart'

// ========== 类型 ==========
interface SectorRaw {
  PlateName?: string
  concept_name?: string
  col2?: string
  ChangePercent?: number | string
  concept_increase?: number | string
  col4?: number | string
  MainForce?: number | string
  concept_net_amount?: number | string
  col7?: number | string
  Intensity?: number | string
  concept_intensity?: number | string
  col3?: number | string
  first_plate_name?: string
  stock_name?: string
  change_rate?: number | string
  intensity?: number | string
  net_flow?: number | string
}

interface RelayItem {
  from_tier: number; from_count: number; promoted: number; promoted_codes: string[]
  survived: number; broken: number; broken_codes: string[]; relay_rate: number
}
interface RelayResp { trade_date: string; prev_date: string | null; relay: RelayItem[]; note?: string }
interface SentimentHistPoint { date: string; score?: number; limit_up?: number; sentiment?: string }
interface CapitalItem { name: string; net_flow: number; amount: number; change: number; intensity: number }

// ========== 配色与工具 ==========
const SENT_THEME: Record<string, { bg: string; text: string; tag: string; emoji: string }> = {
  '冰点': { bg: 'linear-gradient(135deg,#1e3a8a,#3b82f6)', text: '#fff', tag: 'blue', emoji: '🧊' },
  '低迷': { bg: 'linear-gradient(135deg,#1e40af,#60a5fa)', text: '#fff', tag: 'cyan', emoji: '🌧️' },
  '中性': { bg: 'linear-gradient(135deg,#525252,#a3a3a3)', text: '#fff', tag: 'default', emoji: '⚖️' },
  '回暖': { bg: 'linear-gradient(135deg,#c2410c,#fb923c)', text: '#fff', tag: 'orange', emoji: '🔥' },
  '高潮': { bg: 'linear-gradient(135deg,#991b1b,#ef4444)', text: '#fff', tag: 'red', emoji: '🚀' },
}

function deltaTag(curr: number, prev: number | undefined, opts?: { invert?: boolean; suffix?: string; precision?: number }) {
  return <DeltaIndicator current={curr} prev={prev} invert={opts?.invert} suffix={opts?.suffix} precision={opts?.precision} />
}

function MetaStrip({ items }: { items: ApiMeta[] }) {
  if (!items.length) return null
  return (
    <Space wrap size={6} style={{ marginBottom: 12 }}>
      {items.map((m) => (
        <DataStatusBadge
          key={m.name ?? m.source}
          status={m.data_status as DataStatus}
          source={m.source}
          mock={m.mock}
        />
      ))}
    </Space>
  )
}

// ========== 矛盾信号规则 ==========
function buildContradictionRules(summary: MarketSummary | null, relay: RelayResp | null, capitalFlow: CapitalItem[] | null): ContradictionRule[] {
  if (!summary) return []
  const avgRelay = relay?.relay?.length ? relay.relay.reduce((s, r) => s + r.relay_rate, 0) / relay.relay.length : -1
  const topNetFlow = capitalFlow?.[0]?.net_flow ?? 0
  return [
    { condition: summary.sentiment_level === '回暖' && avgRelay >= 0 && avgRelay < 30, message: '情绪表面回暖但承接率仅 ' + avgRelay.toFixed(0) + '%，高度可能衰竭', severity: 'warning' },
    { condition: summary.limit_up_count > 50 && topNetFlow < 0, message: '涨停活跃但主力资金净流出，注意smart money动向', severity: 'warning' },
    { condition: summary.max_board >= 4 && summary.broken_rate > 40, message: '虽有 ' + summary.max_board + ' 板高度但炸板率 ' + summary.broken_rate.toFixed(1) + '%，封板质量差', severity: 'danger' },
    { condition: summary.sentiment_level === '高潮' && (summary.prev?.sentiment_level === '高潮'), message: '连续高潮第2日，历史上此后多进入顶背离', severity: 'warning' },
  ]
}

// ========== Section 0 · 三幕叙事头（一眼读懂今天） ==========
const SENT_TONE: Record<string, { act1: string; act3Mood: string }> = {
  '冰点': { act1: '市场打盹，多头消音', act3Mood: '冷处理，等待信号' },
  '低迷': { act1: '低气压笼罩，缩量阴跌', act3Mood: '保守为主，轻仓观察' },
  '中性': { act1: '多空僵持，结构分化', act3Mood: '看主线，不追高' },
  '回暖': { act1: '人气回流，赚钱效应抬头', act3Mood: '主线接力，谨慎乐观' },
  '高潮': { act1: '龙王登基，全场狂欢', act3Mood: '盛宴尾声，警惕分歧' },
}

function SectionStoryline({
  summary, sectors, ladder, relay,
}: {
  summary: MarketSummary
  sectors: SectorRaw[]
  ladder: LadderData | null
  relay: RelayResp | null
}) {
  const tone = SENT_TONE[summary.sentiment_level] || SENT_TONE['中性']
  const lu = summary.limit_up_count
  const luPrev = summary.prev?.limit_up_count
  const luDelta = luPrev !== undefined ? lu - luPrev : 0
  const mb = summary.max_board

  const top1 = useMemo(() => {
    if (!sectors.length) return null
    const arr = sectors.map(s => ({
      name: pickName(s),
      intensity: pickNum(s, 'intensity'),
      change: pickNum(s, 'change_rate'),
    })).filter(s => s.name !== '—').sort((a, b) => b.intensity - a.intensity)
    return arr[0] || null
  }, [sectors])

  const topLeader = useMemo(() => {
    if (!ladder || !top1) return null
    let best: LimitUpStock | null = null
    Object.values(ladder.tiers).forEach(stocks => {
      stocks.forEach(s => {
        if (s.first_plate_name === top1.name) {
          if (!best || (s.board_count || 1) > (best.board_count || 1)) best = s
        }
      })
    })
    return best as LimitUpStock | null
  }, [ladder, top1])

  const avgRelay = useMemo(() => {
    if (!relay?.relay?.length) return null
    return relay.relay.reduce((s, r) => s + r.relay_rate, 0) / relay.relay.length
  }, [relay])

  const tomorrowCount = useMemo(() => {
    if (!ladder || !top1) return 0
    let n = 0
    Object.values(ladder.tiers).forEach(stocks => {
      stocks.forEach(s => {
        const b = s.board_count || 1
        if (b >= 1 && b <= 2 && s.first_plate_name === top1.name) n++
      })
    })
    return n
  }, [ladder, top1])

  const aiPrompt = `把今日 A 股复盘讲成一段 80 字以内的故事：情绪【${summary.sentiment_level}】，涨停 ${lu} 家（较昨日${luDelta >= 0 ? '+' : ''}${luDelta}），最高 ${mb} 板${top1 ? `，主线【${top1.name}】强度 ${top1.intensity.toFixed(0)}` : ''}${topLeader ? `（龙头 ${(topLeader as LimitUpStock).stock_name} ${(topLeader as LimitUpStock).board_count}板）` : ''}${avgRelay !== null ? `，平均承接率 ${avgRelay.toFixed(0)}%` : ''}。要有画面感、不要罗列数字。`

  const Act = ({ icon, label, color, title, sub, foot }: {
    icon: React.ReactNode; label: string; color: string; title: React.ReactNode; sub: React.ReactNode; foot?: React.ReactNode
  }) => (
    <div style={{
      flex: 1, minWidth: 0, background: '#fff', borderRadius: 12,
      border: `1px solid ${color}22`, padding: '14px 16px', position: 'relative',
      boxShadow: `0 2px 8px ${color}14`,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <span style={{
          width: 28, height: 28, borderRadius: 8, background: `${color}18`, color,
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: 14,
        }}>{icon}</span>
        <span style={{ fontSize: 12, color: '#999', letterSpacing: 1 }}>{label}</span>
      </div>
      <div style={{ fontSize: 16, fontWeight: 700, color: '#262626', lineHeight: 1.4, marginBottom: 4 }}>{title}</div>
      <div style={{ fontSize: 12, color: '#666', lineHeight: 1.6 }}>{sub}</div>
      {foot && <div style={{ marginTop: 8 }}>{foot}</div>}
    </div>
  )

  return (
    <div style={{
      background: 'linear-gradient(135deg,#fff7e6 0%, #fff 60%)',
      border: '1px solid #ffe7ba', borderRadius: 14, padding: 16, marginBottom: 16,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 12 }}>
        <div>
          <span style={{ fontSize: 15, fontWeight: 700, color: '#262626' }}>📖 今日故事线</span>
          <span style={{ marginLeft: 10, fontSize: 12, color: '#999' }}>三幕看懂当日盘面</span>
        </div>
        <Button size="small" type="link" icon={<RobotOutlined />} onClick={() => askAI(aiPrompt)}>
          让 AI 讲给我听
        </Button>
      </div>
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        <Act
          icon={<BulbOutlined />} label="ACT 1 · 开局" color="#1677ff"
          title={tone.act1}
          sub={<>涨停 <b style={{ color: '#f5222d' }}>{lu}</b> 家 · 最高 <b>{mb}</b> 板</>}
          foot={luPrev !== undefined && (
            <Tag color={luDelta >= 0 ? 'red' : 'green'} style={{ margin: 0 }}>
              较昨日 {luDelta >= 0 ? '+' : ''}{luDelta}
            </Tag>
          )}
        />
        <Act
          icon={<FireOutlined />} label="ACT 2 · 主角" color="#fa541c"
          title={top1 ? top1.name : '主线尚未明确'}
          sub={top1 ? <>强度 <b>{top1.intensity.toFixed(0)}</b> · 板块涨幅 <b style={{ color: top1.change >= 0 ? '#f5222d' : '#52c41a' }}>{top1.change >= 0 ? '+' : ''}{top1.change.toFixed(2)}%</b></> : '资金分散，无明显合力'}
          foot={topLeader && (
            <Link to={`/stock/${(topLeader as LimitUpStock).stock_code}`}>
              <Tag color="red" icon={<CrownOutlined />} style={{ margin: 0 }}>
                {(topLeader as LimitUpStock).stock_name} {(topLeader as LimitUpStock).board_count}板
              </Tag>
            </Link>
          )}
        />
        <Act
          icon={<AimOutlined />} label="ACT 3 · 落幕 / 明日" color="#13c2c2"
          title={tone.act3Mood}
          sub={
            <>
              {avgRelay !== null
                ? <>平均承接 <b style={{ color: avgRelay >= 50 ? '#f5222d' : avgRelay >= 30 ? '#fa8c16' : '#52c41a' }}>{avgRelay.toFixed(0)}%</b></>
                : <>承接数据待累积</>}
              {' · '}主线接力候选 <b>{tomorrowCount}</b> 只
            </>
          }
        />
      </div>
    </div>
  )
}

// ========== 五步作战流卡片 ==========
function getSentimentLabel(level: string): { label: string; color: string } {
  const map: Record<string, { label: string; color: string }> = {
    '冰点': { label: '冰点', color: '#3b82f6' },
    '低迷': { label: '低迷', color: '#60a5fa' },
    '中性': { label: '中性', color: '#a3a3a3' },
    '回暖': { label: '回暖', color: '#fb923c' },
    '高潮': { label: '高潮', color: '#ef4444' },
  }
  return map[level] || { label: level || '未知', color: '#a3a3a3' }
}

function getRiskSignal(brokenRate: number, highBoardBroken: number): { label: string; color: string } {
  if (brokenRate > 40 || highBoardBroken >= 3) return { label: '高风险', color: '#ef4444' }
  if (brokenRate > 25 || highBoardBroken >= 2) return { label: '中风险', color: '#f97316' }
  return { label: '低风险', color: '#22c55e' }
}

function BattleFlowCards({ summary, sectors, ladder, brokenData, strategy }: {
  summary: MarketSummary
  sectors: SectorRaw[]
  ladder: LadderData | null
  brokenData: AnyData
  strategy: AnyData
}) {
  const step1 = useMemo(() => {
    const sent = getSentimentLabel(summary.sentiment_level)
    return {
      title: '情绪',
      icon: '🌡️',
      metric: sent.label,
      metricColor: sent.color,
      desc: `涨停 ${summary.limit_up_count} · 炸板率 ${(summary.broken_rate || 0).toFixed(0)}%`,
    }
  }, [summary])

  const step2 = useMemo(() => {
    const top3 = sectors
      .map(s => ({ name: pickName(s), intensity: pickNum(s, 'intensity'), change: pickNum(s, 'change_rate') }))
      .filter(s => s.name !== '—')
      .sort((a, b) => b.intensity - a.intensity)
      .slice(0, 3)
    return {
      title: '主线',
      icon: '🔥',
      metric: top3[0]?.name || '未明确',
      metricColor: '#fa541c',
      desc: top3.length > 0
        ? top3.map(t => `${t.name} ${t.intensity.toFixed(0)}`).join(' / ')
        : '无明显合力',
    }
  }, [sectors])

  const step3 = useMemo(() => {
    if (!ladder) return { title: '龙头', icon: '👑', metric: '—', metricColor: '#f5222d', desc: '天梯数据加载中' }
    let best: LimitUpStock | null = null
    let bestBoard = 0
    Object.values(ladder.tiers).forEach(stocks => {
      stocks.forEach(s => {
        const bc = s.board_count || 1
        if (bc > bestBoard) { best = s; bestBoard = bc }
      })
    })
    if (!best) return { title: '龙头', icon: '👑', metric: '暂无', metricColor: '#999', desc: '无涨停个股' }
    const b = best as LimitUpStock
    return {
      title: '龙头',
      icon: '👑',
      metric: `${b.stock_name} ${bestBoard}板`,
      metricColor: '#f5222d',
      desc: b.first_plate_name ? `所属 ${b.first_plate_name}` : '',
    }
  }, [ladder])

  const step4 = useMemo(() => {
    const brRate = summary.broken_rate || 0
    const highBoardBroken = brokenData?.by_reason
      ? Object.values(brokenData.by_reason).flatMap((d: AnyData) =>
          (d.cases || []).filter((c: AnyData) => (c.board_count || 0) >= 2)
        ).length
      : 0
    const risk = getRiskSignal(brRate, highBoardBroken)
    return {
      title: '风险',
      icon: '⚠️',
      metric: risk.label,
      metricColor: risk.color,
      desc: `炸板率 ${brRate.toFixed(0)}% · 高位炸板 ${highBoardBroken}`,
    }
  }, [summary, brokenData])

  const step5 = useMemo(() => {
    const scenarios = strategy?.scenarios
    if (!scenarios) return { title: '次日', icon: '📋', metric: '策略加载中', metricColor: '#1677ff', desc: '' }
    const lines: string[] = []
    if (scenarios.premium?.stocks?.length) lines.push(`溢价 ${scenarios.premium.stocks.length} 只`)
    if (scenarios.dip?.stocks?.length) lines.push(`低吸 ${scenarios.dip.stocks.length} 只`)
    if (scenarios.ladder?.stocks?.length) lines.push(`排板 ${scenarios.ladder.stocks.length} 只`)
    return {
      title: '次日',
      icon: '📋',
      metric: strategy.overall_advice || '三场景就绪',
      metricColor: '#1677ff',
      desc: lines.join(' · ') || '候选池生成中',
    }
  }, [strategy])

  const steps = [step1, step2, step3, step4, step5]
  const STEP_COLORS = ['#3b82f6', '#fa541c', '#f5222d', '#f97316', '#1677ff']

  return (
    <div style={{
      background: 'linear-gradient(135deg, #f0f5ff 0%, #fff 60%)',
      border: '1px solid #d6e4ff', borderRadius: 14, padding: 16, marginBottom: 16,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <span style={{ fontSize: 15, fontWeight: 700, color: '#262626' }}>🗺️ 五步作战流</span>
        <span style={{ fontSize: 12, color: '#999' }}>情绪 → 主线 → 龙头 → 风险 → 次日</span>
      </div>
      <div style={{ display: 'flex', gap: 0, flexWrap: 'wrap' }}>
        {steps.map((s, i) => (
          <div key={s.title} style={{ display: 'flex', alignItems: 'stretch', flex: 1, minWidth: 140 }}>
            <div style={{
              flex: 1, background: '#fff', borderRadius: 10,
              border: `1px solid ${STEP_COLORS[i]}22`, padding: '12px 14px',
              boxShadow: `0 2px 6px ${STEP_COLORS[i]}10`, position: 'relative',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
                <span style={{
                  width: 22, height: 22, borderRadius: '50%', background: STEP_COLORS[i],
                  color: '#fff', display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 11, fontWeight: 700,
                }}>{i + 1}</span>
                <span style={{ fontSize: 13, fontWeight: 600, color: '#555' }}>{s.icon} {s.title}</span>
              </div>
              <div style={{ fontSize: 15, fontWeight: 700, color: s.metricColor, lineHeight: 1.3, marginBottom: 4 }}>
                {s.metric}
              </div>
              <div style={{ fontSize: 11, color: '#888', lineHeight: 1.5 }}>{s.desc}</div>
              {i === 4 && <AIBadge style={{ marginTop: 6 }} />}
            </div>
            {i < 4 && (
              <div style={{
                display: 'flex', alignItems: 'center', padding: '0 4px',
                color: '#bbb', fontSize: 16, fontWeight: 700, flexShrink: 0,
              }}>→</div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

// ========== Section A · 市场温度 ==========
function SectionTemperature({ summary }: { summary: MarketSummary }) {
  const theme = SENT_THEME[summary.sentiment_level] || SENT_THEME['中性']
  const prev = summary.prev || {}
  const lu = summary.limit_up_count
  const luPrev = prev.limit_up_count
  const br = summary.broken_rate
  const brPrev = prev.broken_rate
  const mb = summary.max_board
  const mbPrev = prev.max_board
  const seal = summary.seal_success_rate ?? 0
  const sealPrev = prev.seal_success_rate

  const sentimentChanged = prev.sentiment_level && prev.sentiment_level !== summary.sentiment_level
  const aiPrompt = `今日市场情绪【${summary.sentiment_level}】（涨停 ${lu} 家，最高板 ${mb}，封板成功率 ${seal}%${sentimentChanged ? `，从昨日【${prev.sentiment_level}】切换` : ''}），请基于历史相似日的特征，分析后市 1-3 个交易日演绎概率与重点关注方向。`

  return (
    <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
      <Col xs={24} md={8}>
        <div style={{
          background: theme.bg, color: theme.text, borderRadius: 12, padding: 20,
          minHeight: 220, position: 'relative', overflow: 'hidden',
        }}>
          <div style={{ fontSize: 13, opacity: 0.8 }}>今日市场温度</div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginTop: 6 }}>
            <span style={{ fontSize: 56, fontWeight: 800, lineHeight: 1 }}>{theme.emoji}</span>
            <span style={{ fontSize: 36, fontWeight: 700 }}>{summary.sentiment_level}</span>
          </div>
          {sentimentChanged && (
            <div style={{ marginTop: 8, fontSize: 12, opacity: 0.85 }}>
              较昨日「{prev.sentiment_level}」{lu > (luPrev ?? lu) ? '↑ 升温' : '↓ 降温'}
            </div>
          )}
          <div style={{ marginTop: 16, fontSize: 13, lineHeight: 1.7, opacity: 0.95 }}>
            涨停 <b>{lu}</b> · 最高 <b>{mb}板</b> · 封板成功 <b>{seal.toFixed(1)}%</b>
          </div>
          <Button
            ghost block style={{ marginTop: 16, borderColor: 'rgba(255,255,255,0.4)' }}
            icon={<RobotOutlined />}
            onClick={() => askAI(aiPrompt)}
          >
            AI 解读
          </Button>
        </div>
      </Col>
      <Col xs={24} md={16}>
        <Row gutter={[12, 12]}>
          <Col xs={12} md={6}>
            <Card size="small">
              <Statistic title="涨停" value={lu} valueStyle={{ color: '#f5222d' }} prefix={<ArrowUpOutlined />} />
              <div style={{ marginTop: 4 }}>{deltaTag(lu, luPrev)}</div>
            </Card>
          </Col>
          <Col xs={12} md={6}>
            <Card size="small">
              <Statistic
                title="炸板率" value={br} precision={1} suffix="%"
                valueStyle={{ color: br > 35 ? '#f5222d' : br > 20 ? '#faad14' : '#52c41a' }}
              />
              <div style={{ marginTop: 4 }}>{deltaTag(br, brPrev, { invert: true, suffix: 'pt', precision: 1 })}</div>
            </Card>
          </Col>
          <Col xs={12} md={6}>
            <Card size="small">
              <Statistic
                title="最高板" value={mb} suffix="板"
                valueStyle={{ color: mb >= 6 ? '#f5222d' : mb >= 4 ? '#fa8c16' : '#262626' }}
              />
              <div style={{ marginTop: 4 }}>{deltaTag(mb, mbPrev, { suffix: '板' })}</div>
            </Card>
          </Col>
          <Col xs={12} md={6}>
            <Tooltip title="涨停 / (涨停 + 炸板)，反映多头封板能力">
              <Card size="small">
                <Statistic
                  title="封板成功率" value={seal} precision={1} suffix="%"
                  valueStyle={{ color: seal >= 75 ? '#f5222d' : seal >= 60 ? '#fa8c16' : '#52c41a' }}
                />
                <div style={{ marginTop: 4 }}>{deltaTag(seal, sealPrev, { suffix: 'pt', precision: 1 })}</div>
              </Card>
            </Tooltip>
          </Col>
          <Col span={24}>
            <SentimentMiniChart />
          </Col>
        </Row>
      </Col>
    </Row>
  )
}

function SentimentMiniChart() {
  const ref = useRef<HTMLDivElement>(null)
  const [data, setData] = useState<SentimentHistPoint[] | null>(null)

  useEffect(() => {
    fetchApi<{ data: SentimentHistPoint[] }>('/market/sentiment-history?days=30')
      .then(r => setData(r.data || []))
      .catch(() => setData([]))
  }, [])

  useEffect(() => {
    if (!ref.current || !data || data.length === 0) return
    const chart = echarts.init(ref.current)
    chart.setOption({
      grid: { left: 36, right: 12, top: 8, bottom: 24 },
      tooltip: {
        trigger: 'axis',
        formatter: (ps: AnyData) => {
          const p = ps[0]; const d = data[p.dataIndex]
          return `${d.date}<br/>涨停 ${d.limit_up ?? '—'} · 情绪 ${d.sentiment ?? '—'}`
        },
      },
      xAxis: { type: 'category', data: data.map(d => d.date.slice(5)), axisLabel: { fontSize: 10 } },
      yAxis: { type: 'value', axisLabel: { fontSize: 10 } },
      series: [{
        type: 'line', smooth: true, showSymbol: false,
        data: data.map(d => d.limit_up ?? 0),
        areaStyle: { opacity: 0.15 },
        lineStyle: { width: 2 },
        itemStyle: { color: '#fa8c16' },
      }],
    })
    const onResize = () => chart.resize()
    window.addEventListener('resize', onResize)
    return () => { window.removeEventListener('resize', onResize); chart.dispose() }
  }, [data])

  if (data === null) return <Card size="small" style={{ height: 110 }}><Spin /></Card>
  if (data.length === 0) return (
    <Card size="small" style={{ height: 110 }}>
      <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="情绪历史累积中" />
    </Card>
  )
  return (
    <Card size="small" title={<span style={{ fontSize: 12, color: '#666' }}>近 30 日涨停趋势</span>} bodyStyle={{ padding: 4 }}>
      <div ref={ref} style={{ width: '100%', height: 110 }} />
    </Card>
  )
}

// ========== Section B · 主线题材 ==========
function safeNum(v: unknown, fallback = 0) {
  const n = Number(v)
  return Number.isFinite(n) ? n : fallback
}
function pickName(s: SectorRaw) { return s.first_plate_name || s.PlateName || s.concept_name || s.stock_name || s.col2 || '—' }
function pickNum(s: SectorRaw, key: keyof SectorRaw) {
  if (key === 'intensity') return safeNum(s.intensity ?? s.Intensity ?? s.concept_intensity ?? s.col3)
  if (key === 'change_rate') return safeNum(s.change_rate ?? s.ChangePercent ?? s.concept_increase ?? s.col4)
  if (key === 'net_flow') return safeNum(s.net_flow ?? s.MainForce ?? s.concept_net_amount ?? s.col7)
  return safeNum(s[key])
}

interface ThemeCycleItem {
  name: string
  phase: string
  icon: string
  color: string
  score: number
  appearance_days: number
  trend: string
  today_limit_up: number
  advice: string
}

function SectionThemes({ sectors, ladder }: { sectors: SectorRaw[]; ladder: LadderData | null }) {
  const top3 = useMemo(() => sectors
    .map(s => ({
      name: pickName(s),
      intensity: pickNum(s, 'intensity'),
      change: pickNum(s, 'change_rate'),
      net_flow: pickNum(s, 'net_flow'),
    }))
    .filter(s => s.name !== '—')
    .sort((a, b) => b.intensity - a.intensity)
    .slice(0, 3), [sectors])

  // PRD M4B-08：批量获取 Top10 题材的周期阶段
  const [cycles, setCycles] = useState<Record<string, ThemeCycleItem>>({})
  useEffect(() => {
    if (top3.length === 0) return
    fetchApi<{ items: ThemeCycleItem[] }>('/theme/cycle-batch?top=10')
      .then(r => {
        const m: Record<string, ThemeCycleItem> = {}
        for (const it of r.items || []) m[it.name] = it
        setCycles(m)
      })
      .catch(() => setCycles({}))
  }, [top3.length])

  const themeMembers = useMemo(() => {
    if (!ladder) return new Map<string, LimitUpStock[]>()
    const m = new Map<string, LimitUpStock[]>()
    Object.values(ladder.tiers).forEach((stocks) => {
      stocks.forEach(s => {
        const key = s.first_plate_name || ''
        if (!key) return
        if (!m.has(key)) m.set(key, [])
        m.get(key)!.push(s)
      })
    })
    return m
  }, [ladder])

  return (
    <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
      <Col xs={24} lg={14}>
        <SectionHeader icon={<FireOutlined />} title="今日主线 Top 3" />
        {top3.length === 0 && <Empty description="暂无主线数据" />}
        <Space direction="vertical" size={12} style={{ width: '100%' }}>
          {top3.map((t, i) => {
            const members = themeMembers.get(t.name) || []
            const sortedByBoard = [...members].sort((a, b) => (b.board_count || 1) - (a.board_count || 1))
            const leader = sortedByBoard.find(m => m.is_leader) || sortedByBoard[0]


            return (
              <Card key={t.name} size="small" hoverable bodyStyle={{ padding: 14 }}>
                <Row gutter={12} align="middle">
                  <Col flex="none" style={{ width: 36 }}>
                    <div style={{
                      background: i === 0 ? '#f5222d' : i === 1 ? '#fa8c16' : '#faad14',
                      color: '#fff', borderRadius: 8, padding: '6px 0', textAlign: 'center', fontWeight: 700,
                    }}>{i + 1}</div>
                  </Col>
                  <Col flex="auto" style={{ minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
                      <Link to={`/theme?name=${encodeURIComponent(t.name)}`} style={{ fontWeight: 700, fontSize: 16 }}>
                        {t.name}
                      </Link>
                      <Tag color="orange">强度 {t.intensity.toFixed(1)}</Tag>
                      {cycles[t.name] && (
                        <Tooltip title={`${cycles[t.name].advice}（活跃 ${cycles[t.name].appearance_days} 日，趋势${cycles[t.name].trend}，热度${cycles[t.name].score}）`}>
                          <Tag color={cycles[t.name].color} style={{ cursor: 'help', fontWeight: 600 }}>
                            {cycles[t.name].icon} {cycles[t.name].phase}
                          </Tag>
                        </Tooltip>
                      )}
                      <span style={{ color: t.change >= 0 ? '#f5222d' : '#52c41a', fontWeight: 600 }}>
                        {t.change >= 0 ? '+' : ''}{t.change.toFixed(2)}%
                      </span>
                      <span style={{ color: t.net_flow >= 0 ? '#f5222d' : '#52c41a', fontSize: 13 }}>
                        主力 {t.net_flow >= 0 ? '+' : ''}{(t.net_flow / 1e8).toFixed(2)}亿
                      </span>
                    </div>
                    <div style={{ marginTop: 8, fontSize: 13, color: '#555' }}>
                      {leader && (
                        <span>
                          <CrownOutlined style={{ color: '#f5222d' }} />{' '}
                          <Link to={`/stock/${leader.stock_code}`} style={{ fontWeight: 600 }}>
                            {leader.stock_name}
                          </Link>
                          {' '}<Tag color="red">{leader.board_count || 1}板</Tag>
                          <span style={{ color: '#999' }}> · 涨停 {members.length} 只</span>
                        </span>
                      )}
                      {!leader && <span style={{ color: '#999' }}>暂无涨停成员</span>}
                    </div>
                    {members.length > 0 && (() => {
                      const dragon = sortedByBoard[0]
                      const zhongjun = members.find(m => (m.board_count || 1) >= 2 && m !== dragon && (m.non_restricted_capital || 0) > 5e9)
                      const followers = members.filter(m => (m.board_count || 1) === 1 && m !== dragon && m !== zhongjun).slice(0, 3)
                      const laggards = members.filter(m => (m.change_rate || 0) < 5).slice(0, 2)
                      const ROLE_STYLE: Record<string, { color: string; label: string }> = {
                        dragon: { color: '#f5222d', label: '龙头' },
                        zhongjun: { color: '#fa8c16', label: '中军' },
                        follower: { color: '#1677ff', label: '跟风' },
                        laggard: { color: '#8c8c8c', label: '掉队' },
                      }
                      const renderRole = (stock: LimitUpStock | undefined, role: string) => {
                        if (!stock) return null
                        const s = ROLE_STYLE[role]
                        return (
                          <span key={stock.stock_code} style={{ display: 'inline-flex', alignItems: 'center', gap: 4, marginRight: 12 }}>
                            <Tag color={s.color} style={{ margin: 0, fontSize: 11 }}>{s.label}</Tag>
                            <Link to={`/stock/${stock.stock_code}`} style={{ fontSize: 12 }}>{stock.stock_name}</Link>
                            <span style={{ fontSize: 11, color: '#999' }}>{stock.board_count || 1}板</span>
                          </span>
                        )
                      }
                      return (
                        <div style={{ marginTop: 8, display: 'flex', gap: 4, flexWrap: 'wrap', alignItems: 'center' }}>
                          {renderRole(dragon, 'dragon')}
                          {renderRole(zhongjun, 'zhongjun')}
                          {followers.map(f => renderRole(f, 'follower'))}
                          {laggards.map(l => renderRole(l, 'laggard'))}
                        </div>
                      )
                    })()}
                  </Col>
                  <Col flex="none">
                    <AskAIChip
                      prompt={`深度解读今日主线【${t.name}】：核心驱动逻辑、产业链上下游、龙头股${leader ? `（${leader.stock_name}）` : ''}的题材深度，以及明日延续性判断。`}
                      label="AI 解读"
                    />
                  </Col>
                </Row>
              </Card>
            )
          })}
        </Space>
      </Col>
      <Col xs={24} lg={10}>
        <Card
          size="small"
          title={<span style={{ fontSize: 14 }}>板块涨幅 × 主力净流入</span>}
          bodyStyle={{ padding: 8 }}
        >
          <RotationScatter sectors={sectors} />
        </Card>
      </Col>
    </Row>
  )
}

// PRD M2-01: 板块轮动时序图，支持 1/3/5/10 日视角
const ROTATION_WINDOWS = [
  { value: 1, label: '当日' },
  { value: 3, label: '3 日' },
  { value: 5, label: '5 日' },
  { value: 10, label: '10 日' },
]

function RotationScatter({ sectors }: { sectors: SectorRaw[] }) {
  const ref = useRef<HTMLDivElement>(null)
  const [window_, setWindow] = useState(1)
  const [multiDay, setMultiDay] = useState<{ name: string; change: number; net_flow: number; intensity: number }[] | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (window_ === 1) { setMultiDay(null); return }
    setLoading(true)
    fetchApi<{ data: AnyData[] }>(`/market/rotation?window=${window_}`)
      .then(r => setMultiDay(r.data || []))
      .catch(() => setMultiDay([]))
      .finally(() => setLoading(false))
  }, [window_])

  useEffect(() => {
    if (!ref.current) return
    const src = window_ === 1
      ? sectors.slice(0, 40).map(s => ({
          name: pickName(s),
          change: pickNum(s, 'change_rate'),
          net_flow: pickNum(s, 'net_flow'),
          intensity: pickNum(s, 'intensity'),
        }))
      : (multiDay || []).slice(0, 40)
    const points = src
    const chart = echarts.init(ref.current)
    chart.setOption({
      tooltip: {
        formatter: (p: AnyData) => {
          const d = p.data
          return `${d[3]}<br/>涨幅: ${d[0].toFixed(2)}%<br/>主力: ${(d[1] / 1e8).toFixed(2)}亿<br/>强度: ${d[2]}`
        },
      },
      grid: { left: 50, right: 16, top: 16, bottom: 36 },
      xAxis: {
        name: '涨幅%', nameLocation: 'center', nameGap: 22,
        axisLabel: { fontSize: 10 },
        splitLine: { lineStyle: { type: 'dashed' } },
      },
      yAxis: {
        name: '主力净流入', nameLocation: 'center', nameGap: 38,
        axisLabel: { fontSize: 10, formatter: (v: number) => `${(v / 1e8).toFixed(1)}亿` },
        splitLine: { lineStyle: { type: 'dashed' } },
      },
      series: [{
        type: 'scatter',
        symbolSize: (d: number[]) => Math.min(Math.max(d[2] / 2, 8), 28),
        data: points.map(p => [p.change, p.net_flow, p.intensity, p.name]),
        itemStyle: {
          color: (p: AnyData) => p.data[0] >= 0 ? '#f5222d' : '#52c41a', opacity: 0.7,
        },
        label: {
          show: true, position: 'right', fontSize: 10, color: '#666',
          formatter: (p: AnyData) => p.data[3],
        },
      }],
    })
    const onResize = () => chart.resize()
    window.addEventListener('resize', onResize)
    return () => { window.removeEventListener('resize', onResize); chart.dispose() }
  }, [sectors, multiDay, window_])

  const noData = (window_ === 1 && (!sectors || sectors.length === 0))
    || (window_ > 1 && (!loading && (!multiDay || multiDay.length === 0)))

  return (
    <div>
      <Radio.Group
        size="small" value={window_} onChange={e => setWindow(e.target.value)}
        style={{ marginBottom: 8 }}
        options={ROTATION_WINDOWS} optionType="button"
      />
      {loading ? <Spin /> : noData ? <Empty description="暂无板块数据" /> :
        <div ref={ref} style={{ width: '100%', height: 360 }} />}
    </div>
  )
}

// ========== Section C · 连板梯队 + 接力 ==========
function LadderPyramid({ tiers }: { tiers: { n: number; stocks: LimitUpStock[] }[] }) {
  const ref = useRef<HTMLDivElement>(null)
  const highTiers = tiers.filter(t => t.n >= 2).sort((a, b) => b.n - a.n)

  useEffect(() => {
    if (!ref.current || !highTiers.length) return
    const chart = echarts.init(ref.current)
    const maxCount = Math.max(...highTiers.map(t => t.stocks.length), 1)
    chart.setOption({
      tooltip: {
        trigger: 'axis', axisPointer: { type: 'shadow' },
        formatter: (p: AnyData) => {
          const d = p[0]
          const tier = highTiers[d.dataIndex]
          if (!tier) return ''
          const names = tier.stocks.slice(0, 5).map(s => s.stock_name).join('、')
          return `<b>${tier.n}板</b>（${tier.stocks.length}只）<br/>${names}${tier.stocks.length > 5 ? '...' : ''}`
        },
      },
      grid: { left: 50, right: 20, top: 8, bottom: 24 },
      xAxis: { type: 'value', max: maxCount, show: false },
      yAxis: {
        type: 'category',
        data: highTiers.map(t => `${t.n}板`),
        axisLabel: { fontSize: 13, fontWeight: 700 },
        axisTick: { show: false },
        axisLine: { show: false },
      },
      series: [{
        type: 'bar',
        data: highTiers.map(t => ({
          value: t.stocks.length,
          itemStyle: {
            color: t.n >= 5 ? '#ef4444' : t.n >= 3 ? '#fb923c' : '#faad14',
            borderRadius: [0, 4, 4, 0],
          },
        })),
        barMaxWidth: 28,
        label: {
          show: true, position: 'right', fontSize: 12, fontWeight: 600,
          formatter: (p: AnyData) => {
            const tier = highTiers[p.dataIndex]
            const leader = tier?.stocks.find((s: LimitUpStock) => s.is_leader) || tier?.stocks[0]
            return leader ? `${p.value}只  ${leader.stock_name}` : `${p.value}只`
          },
        },
      }],
    })
    const onResize = () => chart.resize()
    window.addEventListener('resize', onResize)
    return () => { window.removeEventListener('resize', onResize); chart.dispose() }
  }, [highTiers])

  if (!highTiers.length) return null
  return <div ref={ref} style={{ width: '100%', height: Math.max(highTiers.length * 40 + 32, 120) }} />
}

function SectionLadder({ ladder, relay }: { ladder: LadderData | null; relay: RelayResp | null }) {
  if (!ladder) return <Spin />
  const tiers = Object.entries(ladder.tiers)
    .map(([k, v]) => ({ tier: k, n: parseInt(k) || 1, stocks: v }))
    .filter(t => t.n >= 1)
    .sort((a, b) => b.n - a.n)

  const relayMap = new Map<number, RelayItem>()
  ;(relay?.relay || []).forEach(r => relayMap.set(r.from_tier + 1, r))

  return (
    <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
      <Col xs={24} lg={14}>
        <SectionHeader icon={<ThunderboltOutlined style={{ color: '#fa8c16' }} />} title="连板天梯" subtitle={`共 ${ladder.total} 只`} />
        <Card size="small" style={{ marginBottom: 12 }} bodyStyle={{ padding: 8 }}>
          <LadderPyramid tiers={tiers} />
        </Card>
        <Space direction="vertical" size={8} style={{ width: '100%' }}>
          {tiers.filter(t => t.n >= 2).map(t => {
            const leader = t.stocks.find(s => s.is_leader) || t.stocks[0]
            const relayInfo = relayMap.get(t.n)
            return (
              <Card key={t.tier} size="small" bodyStyle={{ padding: 12 }}>
                <Row gutter={12} align="middle">
                  <Col flex="none" style={{ width: 64 }}>
                    <div style={{
                      background: t.n >= 5 ? '#f5222d' : t.n >= 3 ? '#fa8c16' : '#faad14',
                      color: '#fff', borderRadius: 8, padding: '8px 0', textAlign: 'center',
                    }}>
                      <div style={{ fontSize: 18, fontWeight: 700, lineHeight: 1 }}>{t.n}板</div>
                      <div style={{ fontSize: 11, opacity: 0.9 }}>{t.stocks.length} 只</div>
                    </div>
                  </Col>
                  <Col flex="auto" style={{ minWidth: 0 }}>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                      {t.stocks.slice(0, 6).map(s => (
                        <Link key={s.stock_code} to={`/stock/${s.stock_code}`}>
                          <Tag color={s.is_leader ? 'red' : 'default'} style={{ fontSize: 12 }}>
                            {s.is_leader && <CrownOutlined />} {s.stock_name}
                            <span style={{ color: '#999', marginLeft: 4 }}>{s.first_plate_name}</span>
                          </Tag>
                        </Link>
                      ))}
                      {t.stocks.length > 6 && <Tag>+{t.stocks.length - 6}</Tag>}
                    </div>
                    {relayInfo && (
                      <div style={{ marginTop: 8, fontSize: 12, color: '#666' }}>
                        承接：昨日 {relayInfo.from_tier}板 {relayInfo.from_count}只 → 今日 {t.n}板 晋级 {relayInfo.promoted}只 ·
                        <span style={{
                          color: relayInfo.relay_rate >= 60 ? '#f5222d' : relayInfo.relay_rate >= 30 ? '#fa8c16' : '#52c41a',
                          fontWeight: 600, marginLeft: 4,
                        }}>承接率 {relayInfo.relay_rate}%</span>
                      </div>
                    )}
                  </Col>
                  {t.n >= 4 && (
                    <Col flex="none">
                      <AskAIChip
                        prompt={`今日最高 ${t.n} 板（龙头：${leader?.stock_name}），历史上同等高度（≥${t.n}板）出现后 1-3 日 A 股市场表现规律？是否有梯队衰竭信号？`}
                        label="问 AI"
                      />
                    </Col>
                  )}
                </Row>
              </Card>
            )
          })}
          {/* 1板区域：展示 Tag 列表 */}
          {tiers.filter(t => t.n === 1).map(t => (
            <Card key={t.tier} size="small" bodyStyle={{ padding: 10 }}>
              <Row align="middle" gutter={12}>
                <Col flex="none" style={{ width: 64 }}>
                  <div style={{ background: '#fafafa', border: '1px solid #eee', borderRadius: 6, padding: '6px 0', textAlign: 'center' }}>
                    <div style={{ fontSize: 14, fontWeight: 600 }}>1板</div>
                    <div style={{ fontSize: 11, color: '#999' }}>{t.stocks.length} 只</div>
                  </div>
                </Col>
                <Col flex="auto" style={{ minWidth: 0 }}>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                    {t.stocks.slice(0, 20).map(s => (
                      <Link key={s.stock_code} to={`/stock/${s.stock_code}`}>
                        <Tag style={{ fontSize: 11, margin: 0 }}>{s.stock_name}</Tag>
                      </Link>
                    ))}
                    {t.stocks.length > 20 && (
                      <Tag style={{ fontSize: 11, color: '#999', margin: 0 }}>+{t.stocks.length - 20}</Tag>
                    )}
                  </div>
                </Col>
              </Row>
            </Card>
          ))}
        </Space>
      </Col>
      <Col xs={24} lg={10}>
        <RelayPanel relay={relay} />
      </Col>
    </Row>
  )
}

function RelayPanel({ relay }: { relay: RelayResp | null }) {
  if (!relay) return <Card size="small" loading title="接力转化漏斗" />
  if (!relay.prev_date || relay.relay.length === 0) {
    return (
      <Card size="small" title={<span><RiseOutlined /> 接力转化漏斗</span>}>
        <Alert
          type="info" showIcon message="数据累积中"
          description={relay.note || '需累积 ≥2 个交易日的梯队快照后启用。系统会自动落盘，明日即可查看。'}
        />
      </Card>
    )
  }
  const items = [...relay.relay].filter(r => r.from_count >= 1 && r.from_tier >= 1).sort((a, b) => b.from_tier - a.from_tier)
  return (
    <Card size="small" title={<span><RiseOutlined /> 接力转化漏斗 · 昨日 {relay.prev_date} → 今日</span>}>
      <Space direction="vertical" size={6} style={{ width: '100%' }}>
        {items.map(r => {
          const color = r.relay_rate >= 60 ? '#f5222d' : r.relay_rate >= 30 ? '#fa8c16' : '#52c41a'
          return (
            <div key={r.from_tier} style={{ borderLeft: `3px solid ${color}`, paddingLeft: 10 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                <span style={{ fontSize: 13 }}>
                  <b>{r.from_tier}板 → {r.from_tier + 1}板</b>
                  <span style={{ color: '#999', marginLeft: 8 }}>{r.from_count} 只</span>
                </span>
                <span style={{ color, fontSize: 16, fontWeight: 700 }}>{r.relay_rate}%</span>
              </div>
              <div style={{ fontSize: 12, color: '#666', marginTop: 2 }}>
                晋级 {r.promoted} · 留板 {r.survived} · 断板 {r.broken}
              </div>
            </div>
          )
        })}
        <div style={{ marginTop: 8, fontSize: 11, color: '#999', borderTop: '1px dashed #eee', paddingTop: 6 }}>
          ≥60% 高度延续 / 30-60% 震荡分化 / &lt;30% 高度衰竭
        </div>
      </Space>
    </Card>
  )
}

// ========== Section D · 资金信号（M1-04: 支持 1/5/10/20/60 日多周期） ==========
const CAPITAL_WINDOWS = [
  { value: 1, label: '当日' },
  { value: 5, label: '近 5 日' },
  { value: 10, label: '近 10 日' },
  { value: 20, label: '近 20 日' },
  { value: 60, label: '近 60 日' },
]

function SectionCapitalFlow({ data, date }: { data: CapitalItem[] | null; date: string }) {
  const chartRef = useRef<HTMLDivElement>(null)
  const [window_, setWindow] = useState(1)
  const [items, setItems] = useState<CapitalItem[] | null>(data)
  const [loading, setLoading] = useState(false)

  // 当日数据由父组件传入；多周期时单独拉
  useEffect(() => { if (window_ === 1) setItems(data) }, [data, window_])
  useEffect(() => {
    if (window_ === 1) return
    setLoading(true)
    fetchApi<{ data: CapitalItem[] }>(`/market/capital-flow?date=${date}&window=${window_}`)
      .then(r => setItems(r.data || []))
      .catch(() => setItems([]))
      .finally(() => setLoading(false))
  }, [window_, date])

  useEffect(() => {
    if (!chartRef.current || !items || items.length === 0) return
    const top = items.slice(0, 10)
    const chart = echarts.init(chartRef.current)
    chart.setOption({
      tooltip: {
        trigger: 'axis',
        formatter: (params: AnyData) => {
          const p = params[0]
          const item = top[p.dataIndex]
          const netStr = Math.abs(item.net_flow) >= 1e8
            ? `${(item.net_flow / 1e8).toFixed(2)}亿`
            : `${(item.net_flow / 1e4).toFixed(0)}万`
          return `${item.name}<br/>主力净额: ${netStr}<br/>涨幅: ${item.change.toFixed(2)}%`
        },
      },
      grid: { left: 80, right: 20, top: 10, bottom: 30 },
      xAxis: { type: 'value', axisLabel: { formatter: (v: number) => `${(v / 1e8).toFixed(1)}亿` } },
      yAxis: { type: 'category', data: top.map(d => d.name).reverse(), axisLabel: { fontSize: 11 } },
      series: [{
        type: 'bar',
        data: top.map(d => d.net_flow).reverse(),
        itemStyle: {
          color: (params: AnyData) => params.value >= 0 ? '#f5222d' : '#52c41a',
        },
        barWidth: 16,
      }],
    })
    const onResize = () => chart.resize()
    window.addEventListener('resize', onResize)
    return () => { window.removeEventListener('resize', onResize); chart.dispose() }
  }, [items])

  const subtitle = window_ === 1 ? '主力净流入 Top 10（当日）' : `主力净流入 Top 10（${CAPITAL_WINDOWS.find(o => o.value === window_)?.label}累计）`

  return (
    <div style={{ marginBottom: 16 }}>
      <ProgressiveFold id="replay-capital" label="展开资金信号" count={items?.length} defaultOpen={false}>
        <SectionHeader icon={<DollarOutlined style={{ color: '#1677ff' }} />} title="资金信号" subtitle={subtitle} />
        <Card size="small" bodyStyle={{ padding: 8 }}>
          <Radio.Group
            size="small" value={window_} onChange={e => setWindow(e.target.value)}
            style={{ marginBottom: 8 }}
            options={CAPITAL_WINDOWS} optionType="button"
          />
          {loading ? <Spin /> : !items ? <Spin /> : items.length === 0 ? <Empty description="暂无资金数据" /> : (
            <div ref={chartRef} style={{ width: '100%', height: 300 }} />
          )}
        </Card>
      </ProgressiveFold>
    </div>
  )
}

// ========== Section E · 明日策略（PRD M4A-08：溢价/低吸/排板 三场景） ==========
interface ScenarioStock {
  stock_code: string
  stock_name: string
  board_count: number
  theme: string
  reason: string
}

interface NextDayScenario {
  name: string
  icon: string
  logic: string
  stocks: ScenarioStock[]
  watch_signal: string
  risk: string
  confidence: number
}

interface NextDayStrategy {
  sentiment: string
  max_board: number
  top_themes: string[]
  scenarios: { premium: NextDayScenario; dip: NextDayScenario; ladder: NextDayScenario }
  overall_advice: string
  disclaimer: string
}

const SCENARIO_COLORS: Record<string, { border: string; bg: string; tag: string }> = {
  premium: { border: '#f5222d', bg: '#fff1f0', tag: 'red' },
  dip: { border: '#fa8c16', bg: '#fff7e6', tag: 'orange' },
  ladder: { border: '#1677ff', bg: '#e6f4ff', tag: 'blue' },
}

function ScenarioCard({ data, scenarioKey }: { data: NextDayScenario; scenarioKey: string }) {
  const c = SCENARIO_COLORS[scenarioKey] || SCENARIO_COLORS.premium
  const confColor = data.confidence >= 65 ? '#f5222d' : data.confidence >= 45 ? '#fa8c16' : '#999'

  return (
    <Card
      size="small"
      style={{ borderTop: `3px solid ${c.border}`, height: '100%' }}
      bodyStyle={{ padding: 12 }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 8 }}>
        <span style={{ fontSize: 16, fontWeight: 700 }}>
          <span style={{ marginRight: 6 }}>{data.icon}</span>{data.name}
        </span>
        <Tag color={c.tag}>置信度 <b style={{ color: confColor }}>{data.confidence}</b></Tag>
      </div>
      <div style={{ background: c.bg, padding: '6px 10px', borderRadius: 4, marginBottom: 8, fontSize: 12, lineHeight: 1.7 }}>
        {data.logic}
      </div>
      <div style={{ marginBottom: 6 }}>
        <span style={{ fontSize: 12, color: '#999' }}>候选标的（{data.stocks.length}）</span>
      </div>
      {data.stocks.length === 0 ? (
        <div style={{ fontSize: 12, color: '#bbb', padding: '8px 0' }}>暂无符合条件的候选</div>
      ) : (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 8 }}>
          {data.stocks.slice(0, 6).map((s, i) => (
            <Link key={s.stock_code || `${s.stock_name}-${i}`} to={`/stock/${s.stock_code || ''}`}>
              <Tag color={c.tag} style={{ margin: 0, fontSize: 11 }}>
                {s.stock_name || '—'} {safeNum(s.board_count, 0)}板
              </Tag>
            </Link>
          ))}
        </div>
      )}
      <div style={{ borderTop: '1px dashed #eee', paddingTop: 6, fontSize: 11, lineHeight: 1.7, color: '#555' }}>
        <div><b>📍 触发：</b>{data.watch_signal}</div>
        <div style={{ marginTop: 3 }}><b style={{ color: '#cf1322' }}>⚠️ 风险：</b>{data.risk}</div>
      </div>
    </Card>
  )
}

function SectionTomorrow({ summary, ladder: _ladder, sectors, date }: {
  summary: MarketSummary
  ladder: LadderData | null
  sectors: SectorRaw[]
  date: string
}) {
  const [strategy, setStrategy] = useState<NextDayStrategy | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    setLoading(true)
    fetchApi<NextDayStrategy>(`/market/next-day-strategy?date=${date}`)
      .then(setStrategy)
      .catch(() => setStrategy(null))
      .finally(() => setLoading(false))
  }, [date])

  const top3Names = useMemo(() => sectors.slice(0, 3).map(pickName), [sectors])

  return (
    <Card
      title={<span><RobotOutlined style={{ color: '#1677ff' }} /> 明日策略 · 三场景推演（M4A-08）</span>}
      size="small"
      style={{ marginBottom: 16 }}
      extra={strategy && <Tag color="blue" style={{ fontSize: 11 }}>{strategy.overall_advice}</Tag>}
    >
      {loading ? <Spin /> : !strategy ? (
        <Empty description="次日策略加载中..." />
      ) : (
        <Row gutter={[12, 12]}>
          <Col xs={24} md={8}>
            <ScenarioCard data={strategy.scenarios.premium} scenarioKey="premium" />
          </Col>
          <Col xs={24} md={8}>
            <ScenarioCard data={strategy.scenarios.dip} scenarioKey="dip" />
          </Col>
          <Col xs={24} md={8}>
            <ScenarioCard data={strategy.scenarios.ladder} scenarioKey="ladder" />
          </Col>
        </Row>
      )}

      <div style={{ borderTop: '1px dashed #eee', marginTop: 14, paddingTop: 12 }}>
        <div style={{ fontSize: 13, color: '#666', marginBottom: 8 }}>向 AI 追问</div>
        <Space wrap>
          <Button
            type="primary" icon={<RobotOutlined />}
            onClick={() => askAI(`基于今日复盘（情绪${summary.sentiment_level}，涨停${summary.limit_up_count}，最高${summary.max_board}板，主线${top3Names.filter(Boolean).join('/')}），三场景策略：溢价候选${strategy?.scenarios.premium.stocks.map(s => s.stock_name).join('/')}；低吸候选${strategy?.scenarios.dip.stocks.map(s => s.stock_name).join('/')}；排板候选${strategy?.scenarios.ladder.stocks.map(s => s.stock_name).join('/')}。给出明日开盘的具体操作时机和仓位建议。`)}
          >
            AI 解读三场景
          </Button>
          <Button onClick={() => askAI(`今日 3 大主线（${top3Names.filter(Boolean).join('、')}）的延续性如何判断？哪条最值得明日跟踪？`)}>
            主线延续性
          </Button>
          <Button onClick={() => askAI('今日炸板高位股的炸板原因分析，是否存在系统性风险信号？')}>
            炸板风险
          </Button>
          <Button onClick={() => askAI(`历史上情绪【${summary.sentiment_level}】+ 最高${summary.max_board}板 的相似交易日有哪些？后续 3 日市场怎么走？`)}>
            历史相似日
          </Button>
        </Space>
      </div>
      <AIBadge style={{ marginBottom: 8 }} />
      <AIDisclaimer variant="compact" />
    </Card>
  )
}

// ========== Section 新增：今日结论条 ==========
function SectionConclusionBar({ summary, sectors, phase }: {
  summary: MarketSummary; sectors: SectorRaw[]; phase: AnyData
}) {
  const sent = summary.sentiment_level || '中性'
  const theme = SENT_THEME[sent] || SENT_THEME['中性']
  const top1 = sectors[0] ? pickName(sectors[0]) : '暂无'
  const top2 = sectors[1] ? pickName(sectors[1]) : ''
  const phaseLabel = phase?.phase || '未知'
  const maxB = summary.max_board || 0
  const brRate = summary.broken_rate || 0

  const canDo = sent === '高潮' || sent === '回暖'
    ? '可以做，跟随主线' : sent === '中性'
    ? '观望为主，精选个股' : '谨慎，控制仓位'

  const risk = brRate > 35
    ? `炸板率 ${brRate.toFixed(0)}%，高位风险扩散`
    : maxB <= 2
    ? '无明确高度，梯队断层'
    : '风险可控'

  return (
    <Card
      size="small"
      style={{ marginBottom: 16, borderLeft: `4px solid ${theme.tag === 'red' ? '#ef4444' : theme.tag === 'orange' ? '#fb923c' : '#3b82f6'}` }}
      bodyStyle={{ padding: '12px 16px' }}
    >
      <Row gutter={16}>
        <Col xs={24} md={5}>
          <div style={{ fontSize: 12, color: '#999' }}>能不能做</div>
          <div style={{ fontSize: 15, fontWeight: 600 }}>{theme.emoji} {canDo}</div>
        </Col>
        <Col xs={24} md={5}>
          <div style={{ fontSize: 12, color: '#999' }}>主线题材</div>
          <div style={{ fontSize: 15, fontWeight: 600 }}>{top1}{top2 ? ` / ${top2}` : ''}</div>
        </Col>
        <Col xs={24} md={4}>
          <div style={{ fontSize: 12, color: '#999' }}>龙头高度</div>
          <div style={{ fontSize: 15, fontWeight: 600 }}>{maxB} 板</div>
        </Col>
        <Col xs={24} md={5}>
          <div style={{ fontSize: 12, color: '#999' }}>风险信号</div>
          <div style={{ fontSize: 15, fontWeight: 600, color: brRate > 35 ? '#ef4444' : '#333' }}>{risk}</div>
        </Col>
        <Col xs={24} md={5}>
          <div style={{ fontSize: 12, color: '#999' }}>情绪周期</div>
          <div style={{ fontSize: 15, fontWeight: 600 }}>{phaseLabel}</div>
        </Col>
      </Row>
    </Card>
  )
}

// ========== Section 新增：情绪周期相位 ==========
function SectionSentimentPhase({ phase }: { phase: AnyData }) {
  if (!phase) return null
  const PHASES = ['冰点', '筑底', '回升', '高潮', '顶背离', '退潮']
  const currentIdx = PHASES.indexOf(phase.phase)
  const PHASE_META: Record<string, { color: string; emoji: string; position: string; action: string }> = {
    '冰点': { color: '#3b82f6', emoji: '🧊', position: '空仓或极轻仓', action: '等待修复信号，不参与' },
    '筑底': { color: '#60a5fa', emoji: '🌱', position: '轻仓试错（1-2成）', action: '小仓观察新主线首板' },
    '回升': { color: '#22c55e', emoji: '📈', position: '中仓（3-5成）', action: '关注1进2、2进3承接' },
    '高潮': { color: '#ef4444', emoji: '🚀', position: '标准仓位（5-7成）', action: '跟随核心龙头和补涨' },
    '顶背离': { color: '#f97316', emoji: '⚡', position: '减仓至3成以下', action: '不追高，兑现获利盘' },
    '退潮': { color: '#8b5cf6', emoji: '🌊', position: '空仓或极轻仓', action: '降仓回避，等待冰点' },
  }
  const current = PHASE_META[phase.phase] || PHASE_META['筑底']

  return (
    <Card size="small" title={<SectionHeader title="情绪周期" icon={<RiseOutlined />} />} style={{ marginBottom: 16 }}>
      {/* 圆环流程图 */}
      <div style={{ position: 'relative', margin: '0 auto 16px', maxWidth: 360 }}>
        <svg viewBox="0 0 360 180" style={{ width: '100%', height: 'auto' }}>
          {PHASES.map((p, i) => {
            const angle = -180 + (i / (PHASES.length - 1)) * 180
            const rad = (angle * Math.PI) / 180
            const cx = 180 + 130 * Math.cos(rad)
            const cy = 160 + 130 * Math.sin(rad)
            const meta = PHASE_META[p]
            const isActive = i === currentIdx
            const isPast = i < currentIdx
            return (
              <g key={p}>
                {i > 0 && (() => {
                  const prevAngle = -180 + ((i - 1) / (PHASES.length - 1)) * 180
                  const prevRad = (prevAngle * Math.PI) / 180
                  const px = 180 + 130 * Math.cos(prevRad)
                  const py = 160 + 130 * Math.sin(prevRad)
                  return <line x1={px} y1={py} x2={cx} y2={cy} stroke={isPast || isActive ? meta.color : '#e5e7eb'} strokeWidth={isPast || isActive ? 3 : 1.5} strokeDasharray={isPast || isActive ? '' : '4 4'} />
                })()}
                <circle cx={cx} cy={cy} r={isActive ? 22 : 14} fill={isActive ? meta.color : isPast ? meta.color : '#f5f5f5'} opacity={isActive ? 1 : isPast ? 0.4 : 0.3} stroke={isActive ? meta.color : 'none'} strokeWidth={isActive ? 3 : 0} />
                {isActive && <circle cx={cx} cy={cy} r={26} fill="none" stroke={meta.color} strokeWidth={2} opacity={0.3} />}
                <text x={cx} y={isActive ? cy - 30 : cy - 20} textAnchor="middle" fontSize={isActive ? 13 : 10} fontWeight={isActive ? 700 : 400} fill={isActive ? meta.color : '#999'}>{p}</text>
                <text x={cx} y={cy + 5} textAnchor="middle" fontSize={isActive ? 16 : 12}>{meta.emoji}</text>
              </g>
            )
          })}
        </svg>
      </div>

      {/* 仓位与打法建议 */}
      <div style={{ display: 'flex', gap: 16, marginBottom: 12 }}>
        <div style={{ flex: 1, padding: '8px 12px', background: '#fafafa', borderRadius: 6, borderLeft: `3px solid ${current.color}` }}>
          <div style={{ fontSize: 11, color: '#999' }}>参考仓位</div>
          <div style={{ fontSize: 14, fontWeight: 600, color: current.color }}>{current.position}</div>
        </div>
        <div style={{ flex: 1, padding: '8px 12px', background: '#fafafa', borderRadius: 6, borderLeft: `3px solid ${current.color}` }}>
          <div style={{ fontSize: 11, color: '#999' }}>打法建议</div>
          <div style={{ fontSize: 14, fontWeight: 600 }}>{current.action}</div>
        </div>
      </div>

      <div style={{ fontSize: 12, color: '#666', marginBottom: 8 }}>
        置信度 {((phase.confidence || 0) * 100).toFixed(0)}% · 斜率 {phase.slope?.toFixed(1) || '0'}/日 · {phase.basis || ''}
      </div>
      <div style={{ fontSize: 11, color: '#fa8c16', marginBottom: 8 }}>
        仅供研究参考，不构成投资建议。实际操作请结合个人风险承受能力。
      </div>
      <AskAIChip prompt={`当前情绪周期处于「${phase.phase}」阶段，置信度 ${((phase.confidence || 0) * 100).toFixed(0)}%。根据历史规律，这个阶段后面通常如何演化？仓位和策略上应该注意什么？`} label="AI 解读周期" />
    </Card>
  )
}

// ========== Section 新增：风险雷达 ==========
function SectionRiskRadar({ summary, brokenData }: { summary: MarketSummary; brokenData: AnyData }) {
  const byReason = brokenData?.by_reason || {}
  const total = brokenData?.total || 0
  const reasons = Object.entries(byReason).map(([reason, data]: [string, AnyData]) => ({
    reason,
    count: data.count || 0,
    pct: total > 0 ? Math.round((data.count || 0) / total * 100) : 0,
  })).sort((a, b) => b.count - a.count)

  const highBoardBroken = Object.values(byReason).flatMap((d: AnyData) =>
    (d.cases || []).filter((c: AnyData) => (c.board_count || 0) >= 2)
  ).length
  const brRate = summary.broken_rate || 0
  const riskLevel = brRate > 40 ? 'high' : brRate > 25 ? 'medium' : 'low'
  const RISK_COLOR = { high: '#ef4444', medium: '#f97316', low: '#22c55e' }
  const RISK_LABEL = { high: '高风险', medium: '中风险', low: '低风险' }

  return (
    <Card
      size="small"
      title={<SectionHeader title="风险雷达" icon={<AimOutlined />} />}
      extra={<Tag color={RISK_COLOR[riskLevel]}>{RISK_LABEL[riskLevel]}</Tag>}
      style={{ marginBottom: 16 }}
    >
      <Row gutter={16}>
        <Col xs={12} md={6}>
          <Statistic title="炸板总数" value={total} valueStyle={{ color: '#fa8c16' }} />
        </Col>
        <Col xs={12} md={6}>
          <Statistic title="炸板率" value={brRate} suffix="%" precision={1}
            valueStyle={{ color: brRate > 35 ? '#ef4444' : '#333' }} />
        </Col>
        <Col xs={12} md={6}>
          <Statistic title="高位炸板(2板+)" value={highBoardBroken}
            valueStyle={{ color: highBoardBroken > 3 ? '#ef4444' : '#333' }} />
        </Col>
        <Col xs={12} md={6}>
          <Statistic title="封板率" value={summary.seal_success_rate || 0} suffix="%" precision={1}
            valueStyle={{ color: (summary.seal_success_rate || 0) < 60 ? '#ef4444' : '#22c55e' }} />
        </Col>
      </Row>
      {reasons.length > 0 && (
        <div style={{ marginTop: 12 }}>
          <div style={{ fontSize: 12, color: '#999', marginBottom: 6 }}>炸板归因</div>
          <Space wrap>
            {reasons.slice(0, 6).map(r => (
              <Tag key={r.reason} color={r.count >= 3 ? 'red' : 'default'}>
                {r.reason} {r.count}只({r.pct}%)
              </Tag>
            ))}
          </Space>
        </div>
      )}
      <AskAIChip prompt={`今日炸板 ${total} 只，炸板率 ${brRate.toFixed(1)}%，高位炸板 ${highBoardBroken} 只。炸板归因：${reasons.map(r => `${r.reason}${r.count}只`).join('、')}。分析风险扩散程度，判断明天是否可能进一步恶化。`} label="AI 风险解读" />
    </Card>
  )
}

// ========== Section 新增：次日观察池 ==========
function SectionWatchlist({ strategy }: { strategy: AnyData }) {
  if (!strategy) return null
  const scenarios = strategy.scenarios || strategy
  const premium = scenarios.premium || scenarios.溢价 || {}
  const dip = scenarios.dip || scenarios.低吸 || {}
  const ladder = scenarios.ladder || scenarios.接力 || {}

  const renderPool = (title: string, icon: React.ReactNode, color: string, data: AnyData) => {
    const candidates = data?.stocks || []
    if (!candidates.length && !data?.condition) return null
    return (
      <Card size="small" title={<span style={{ color }}>{icon} {title}</span>} style={{ flex: 1, minWidth: 200 }}>
        {data?.condition && <div style={{ fontSize: 12, color: '#666', marginBottom: 6 }}>触发：{data.condition}</div>}
        {data?.invalidate && <div style={{ fontSize: 12, color: '#999', marginBottom: 6 }}>失效：{data.invalidate}</div>}
        {candidates.map((s: AnyData, i: number) => (
          <div key={i} style={{ padding: '4px 0', borderBottom: '1px solid #f5f5f5' }}>
            <Link to={`/stock/${s.stock_code || ''}`} style={{ fontWeight: 600 }}>
              {s.stock_name || '—'}
            </Link>
            {s.reason && <span style={{ marginLeft: 8, fontSize: 12, color: '#666' }}>{s.reason}</span>}
          </div>
        ))}
      </Card>
    )
  }

  return (
    <Card
      size="small"
      title={<SectionHeader title="次日观察池" icon={<BulbOutlined />} />}
      style={{ marginBottom: 16 }}
    >
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        {renderPool('可打板', <ThunderboltOutlined />, '#ef4444', premium)}
        {renderPool('可低吸', <RiseOutlined />, '#22c55e', dip)}
        {renderPool('接力观察', <FireOutlined />, '#f97316', ladder)}
      </div>
      <AIDisclaimer variant="inline" />
    </Card>
  )
}

// ========== 主组件 ==========
export default function ReplayPageV2() {
  const [selectedDate, setSelectedDate] = useState(dayjs().format('YYYY-MM-DD'))
  const [summary, setSummary] = useState<MarketSummary | null>(null)
  const [ladder, setLadder] = useState<LadderData | null>(null)
  const [sectors, setSectors] = useState<SectorRaw[]>([])
  const [relay, setRelay] = useState<RelayResp | null>(null)
  const [capitalFlow, setCapitalFlow] = useState<CapitalItem[] | null>(null)
  const [phase, setPhase] = useState<AnyData>(null)
  const [brokenData, setBrokenData] = useState<AnyData>(null)
  const [strategy, setStrategy] = useState<AnyData>(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState('')
  const [apiMeta, setApiMeta] = useState<ApiMeta[]>([])

  const loadData = useCallback((date: string) => {
    setLoading(true)
    setErr('')
    setSummary(null); setLadder(null); setSectors([]); setRelay(null); setCapitalFlow(null)
    setPhase(null); setBrokenData(null); setStrategy(null)
    setApiMeta([])

    const q = `?date=${date}`
    Promise.all([
      fetchApi<MarketSummary>(`/market/summary${q}`),
      fetchApi<LadderData>(`/market/ladder${q}`).catch(() => null),
      fetchApi<{ data: SectorRaw[] }>(`/market/sectors${q}`).catch(() => ({ data: [] })),
      fetchApi<RelayResp>(`/market/ladder-relay${q}`).catch(() => null),
      fetchApi<{ data: CapitalItem[] }>(`/market/capital-flow${q}`).catch(() => ({ data: [] })),
      fetchApi<AnyData>('/market/sentiment-phase').catch(() => null),
      fetchApi<AnyData>(`/analysis/broken-cases${q}`).catch(() => null),
      fetchApi<AnyData>(`/market/next-day-strategy${q}`).catch(() => null),
    ])
      .then(([s, l, sec, r, cf, ph, br, st]) => {
        const validSummary = s && (s as AnyData).data_status !== 'unavailable' && (s as AnyData).limit_up_count != null ? s : null
        const validLadder = l && (l as AnyData).data_status !== 'unavailable' && (l as AnyData).tiers ? l : null
        setSummary(validSummary); setLadder(validLadder); setSectors(sec?.data || []); setRelay(r)
        setCapitalFlow(cf?.data || [])
        setPhase(ph); setBrokenData(br); setStrategy(st)
        setApiMeta(extractMetaList([
          { name: '市场总览', resp: s },
          { name: '连板天梯', resp: l },
          { name: '题材', resp: sec },
          { name: '接力', resp: r },
          { name: '资金', resp: cf },
          { name: '情绪', resp: ph },
          { name: '炸板', resp: br },
          { name: '明日策略', resp: st },
        ]))
      })
      .catch(() => setErr('复盘接口不可用，当前不展示复盘数据。'))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { loadData(selectedDate) }, [selectedDate, loadData])

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '120px auto' }} />
  if (err) return <Alert type="error" showIcon message={err} />
  if (!summary) return <Empty description="接口返回真实空状态，暂无复盘总览" />

  const isMock = apiMeta.some((m) => m.mock)

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <h2 style={{ margin: 0 }}>收盘复盘</h2>
          <DatePicker
            value={dayjs(selectedDate)}
            onChange={d => d && setSelectedDate(d.format('YYYY-MM-DD'))}
            allowClear={false}
            size="small"
          />
        </div>
        <Space size={8}>
          {summary.prev_date && <span style={{ color: '#999', fontSize: 12 }}>对比 {summary.prev_date}</span>}
          <Link to="/replay-legacy" style={{ fontSize: 12, color: '#999' }}>旧版 →</Link>
        </Space>
      </div>
      {isMock && <Alert type="warning" showIcon message="接口标记为 mock" description="当前复盘页存在 mock 标记，请确认后端数据源。" style={{ marginBottom: 12 }} />}
      <MetaStrip items={apiMeta} />

      <SectionConclusionBar summary={summary} sectors={sectors} phase={phase} />

      {/* 横向导航（规范 Section 4.1） */}
      <Tabs
        size="small" type="line" style={{ marginBottom: 16 }}
        onChange={(k) => document.getElementById(`replay-${k}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
        items={[
          { key: 'overview', label: '今日总览' },
          { key: 'temperature', label: '情绪温度' },
          { key: 'ladder', label: '连板天梯' },
          { key: 'themes', label: '主线题材' },
          { key: 'risk', label: '风险验证' },
          { key: 'plan', label: '次日计划' },
        ]}
      />

      <div data-feature="AI-Headline" data-feature-name="AI 一句话速报">
        <AIInlineSummary endpoint="/ai/headline" params={{ date: selectedDate }} />
      </div>
      <div data-feature="Storyline" data-feature-name="今日故事线（三幕叙事）">
        <SectionStoryline summary={summary} sectors={sectors} ladder={ladder} relay={relay} />
      </div>
      <div data-feature="BattleFlow" data-feature-name="五步作战流">
        <BattleFlowCards summary={summary} sectors={sectors} ladder={ladder} brokenData={brokenData} strategy={strategy} />
      </div>
      <div data-feature="Contradiction" data-feature-name="矛盾信号告警">
        <ContradictionAlert rules={buildContradictionRules(summary, relay, capitalFlow)} />
      </div>

      <div id="replay-temperature">
        <Row gutter={16}>
          <Col xs={24} lg={16}>
            <SectionTemperature summary={summary} />
          </Col>
          <Col xs={24} lg={8}>
            <SectionSentimentPhase phase={phase} />
          </Col>
        </Row>
      </div>

      <div id="replay-themes">
        <SectionThemes sectors={sectors} ladder={ladder} />
      </div>
      <div id="replay-ladder">
        <SectionLadder ladder={ladder} relay={relay} />
      </div>
      <div id="replay-risk">
        <SectionRiskRadar summary={summary} brokenData={brokenData} />
      </div>

      <Row gutter={16}>
        <Col xs={24} lg={12}>
          <SectionCapitalFlow data={capitalFlow} date={selectedDate} />
        </Col>
        <Col xs={24} lg={12}>
          <SectionWatchlist strategy={strategy} />
        </Col>
      </Row>

      <div id="replay-plan">
        <SectionTomorrow summary={summary} ladder={ladder} sectors={sectors} date={selectedDate} />
      </div>
    </div>
  )
}
