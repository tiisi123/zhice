import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Card, Col, Row, Tag, Spin, Statistic, Badge, Switch, Tooltip, Space, Empty, Alert, Tabs, Table,
} from 'antd'
import AIBadge from '../components/AIBadge'
import {
  ThunderboltOutlined, FireOutlined, CrownOutlined,
  WarningOutlined, RiseOutlined, EyeOutlined,
} from '@ant-design/icons'
import * as echarts from 'echarts'
import { Link } from 'react-router-dom'
import { fetchApi } from '../api/client'
import { useMarketWS } from '../api/useMarketWS'
import type { LimitUpStock, AnyData, ApiMeta, DataStatus } from '../api/types'
import { extractErrorMeta, extractMetaList } from '../api/useApiMeta'
import {
  AskAIChip, SectionHeader,
} from '../components/smart'
import MockBanner from '../components/MockBanner'
import DataStatusBadge from '../components/DataStatusBadge'

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

interface ListResp<T> {
  data?: T[]
  source?: string
  data_status?: string
  mock?: boolean
  message?: string
}

function safeText(v: unknown, fallback = '—') {
  if (v === undefined || v === null || v === '') return fallback
  return String(v)
}

function safeNum(v: unknown, fallback = 0) {
  const n = Number(v)
  return Number.isFinite(n) ? n : fallback
}

function sectorName(s: SectorRaw) {
  return s.first_plate_name || s.PlateName || s.concept_name || s.stock_name || s.col2 || ''
}

function sectorIntensity(s?: SectorRaw) {
  return safeNum(s?.intensity ?? s?.Intensity ?? s?.concept_intensity ?? s?.col3)
}

function sectorChange(s?: SectorRaw) {
  return safeNum(s?.change_rate ?? s?.ChangePercent ?? s?.concept_increase ?? s?.col4)
}

function normalizeStock<T>(item: T): T {
  const it = item as AnyData
  const stock_code = it.stock_code ?? it.SecurityCode
  const stock_name = it.stock_name ?? it.SecurityName
  return {
    ...it,
    stock_code,
    stock_name,
    first_plate_name: it.first_plate_name ?? it.PlateName ?? it.plate_name ?? it.concept_name,
    change_rate: safeNum(it.change_rate ?? it.ChangePercent, it.change_rate),
    turnover_ratio: safeNum(it.turnover_ratio, it.turnover_ratio),
    board_count: safeNum(it.board_count, it.board_count),
    reason: it.reason ?? it.combined_reason ?? '',
  } as T
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

// 将 HH:MM:SS 或 HHMMSS 归一化为分钟数 (0-1440)
function toMinutes(t: string | null | undefined): number | null {
  if (!t) return null
  const s = String(t).trim()
  let h: number
  let m: number
  if (s.includes(':')) {
    const ps = s.split(':')
    h = parseInt(ps[0]) || 0
    m = parseInt(ps[1]) || 0
  } else if (/^\d{6}$/.test(s)) {
    h = parseInt(s.slice(0, 2)); m = parseInt(s.slice(2, 4))
  } else if (/^\d{4}$/.test(s)) {
    h = parseInt(s.slice(0, 2)); m = parseInt(s.slice(2, 4))
  } else {
    return null
  }
  return h * 60 + m
}

// 分时桶：9:30-11:30 / 13:00-15:00，每 15min 一桶
const SESSION_BUCKETS: Array<{ label: string; from: number; to: number }> = []
for (let t = 9 * 60 + 30; t < 11 * 60 + 30; t += 15) {
  SESSION_BUCKETS.push({ label: `${Math.floor(t / 60)}:${String(t % 60).padStart(2, '0')}`, from: t, to: t + 15 })
}
for (let t = 13 * 60; t < 15 * 60; t += 15) {
  SESSION_BUCKETS.push({ label: `${Math.floor(t / 60)}:${String(t % 60).padStart(2, '0')}`, from: t, to: t + 15 })
}

// ========== Section A · 盘中温度 ==========
function SectionPulse({ limitUp, broken }: { limitUp: LimitUpStock[]; broken: LimitUpStock[] }) {
  const luCount = limitUp.length
  const brCount = broken.length
  const brRate = luCount + brCount > 0 ? (brCount / (luCount + brCount)) * 100 : 0
  const sealRate = luCount + brCount > 0 ? (luCount / (luCount + brCount)) * 100 : 0
  const maxBoard = limitUp.reduce((mx, s) => Math.max(mx, s.board_count || 1), 0)

  const now = new Date()
  const nowMin = now.getHours() * 60 + now.getMinutes()

  // 情绪速判
  let temperature: { label: string; color: string; emoji: string }
  if (luCount >= 80 && brRate < 20) temperature = { label: '高潮', color: '#ef4444', emoji: '🚀' }
  else if (luCount >= 50 && brRate < 30) temperature = { label: '回暖', color: '#fb923c', emoji: '🔥' }
  else if (brRate > 40 || luCount < 15) temperature = { label: '低迷', color: '#3b82f6', emoji: '🧊' }
  else temperature = { label: '中性', color: '#a3a3a3', emoji: '⚖️' }

  return (
    <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
      <Col xs={24} md={6}>
        <Card size="small" style={{ height: '100%', borderLeft: `4px solid ${temperature.color}` }}>
          <div style={{ fontSize: 12, color: '#999' }}>盘中温度</div>
          <div style={{ fontSize: 32, fontWeight: 800, color: temperature.color }}>
            {temperature.emoji} {temperature.label}
          </div>
          <div style={{ fontSize: 12, color: '#666', marginTop: 4 }}>
            当前 {now.getHours()}:{String(now.getMinutes()).padStart(2, '0')}
            {nowMin >= 14 * 60 + 30 && <Tag color="orange" style={{ marginLeft: 6 }}>尾盘</Tag>}
            {nowMin >= 9 * 60 + 30 && nowMin < 10 * 60 && <Tag color="red" style={{ marginLeft: 6 }}>开盘半小时</Tag>}
          </div>
        </Card>
      </Col>
      <Col xs={12} md={4}>
        <Card size="small"><Statistic title="涨停" value={luCount} valueStyle={{ color: '#f5222d' }} /></Card>
      </Col>
      <Col xs={12} md={4}>
        <Card size="small"><Statistic title="炸板" value={brCount} valueStyle={{ color: '#fa8c16' }} /></Card>
      </Col>
      <Col xs={12} md={4}>
        <Tooltip title="涨停 / (涨停 + 炸板)">
          <Card size="small"><Statistic title="封板率" value={sealRate} precision={1} suffix="%" valueStyle={{ color: sealRate >= 70 ? '#f5222d' : sealRate >= 50 ? '#fa8c16' : '#52c41a' }} /></Card>
        </Tooltip>
      </Col>
      <Col xs={12} md={6}>
        <Card size="small"><Statistic title="最高板" value={maxBoard} suffix="板" valueStyle={{ color: maxBoard >= 6 ? '#f5222d' : maxBoard >= 4 ? '#fa8c16' : '#262626' }} /></Card>
      </Col>
      <Col span={24}>
        <PulseChart limitUp={limitUp} broken={broken} nowMin={nowMin} />
      </Col>
    </Row>
  )
}

// 分时涨停/炸板节奏柱状图
function PulseChart({ limitUp, broken, nowMin }: { limitUp: LimitUpStock[]; broken: LimitUpStock[]; nowMin: number }) {
  const ref = useRef<HTMLDivElement>(null)

  const { luBuckets, brBuckets, cum } = useMemo(() => {
    const lu = new Array(SESSION_BUCKETS.length).fill(0)
    const br = new Array(SESSION_BUCKETS.length).fill(0)
    limitUp.forEach(s => {
      const m = toMinutes(s.time); if (m === null) return
      const idx = SESSION_BUCKETS.findIndex(b => m >= b.from && m < b.to)
      if (idx >= 0) lu[idx]++
    })
    broken.forEach(s => {
      const m = toMinutes(s.time); if (m === null) return
      const idx = SESSION_BUCKETS.findIndex(b => m >= b.from && m < b.to)
      if (idx >= 0) br[idx]++
    })
    const cumArr = lu.reduce<number[]>((arr, v) => { arr.push((arr.at(-1) ?? 0) + v); return arr }, [])
    return { luBuckets: lu, brBuckets: br, cum: cumArr }
  }, [limitUp, broken])

  useEffect(() => {
    if (!ref.current) return
    const chart = echarts.init(ref.current)
    const labels = SESSION_BUCKETS.map(b => b.label)
    const nowIdx = SESSION_BUCKETS.findIndex(b => nowMin >= b.from && nowMin < b.to)

    chart.setOption({
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      legend: { data: ['涨停', '炸板', '累计涨停'], top: 0, right: 0, textStyle: { fontSize: 11 } },
      grid: { left: 36, right: 48, top: 28, bottom: 32 },
      xAxis: { type: 'category', data: labels, axisLabel: { fontSize: 10, interval: 1 } },
      yAxis: [
        { type: 'value', name: '单桶', axisLabel: { fontSize: 10 }, splitLine: { lineStyle: { type: 'dashed' } } },
        { type: 'value', name: '累计', axisLabel: { fontSize: 10 }, splitLine: { show: false } },
      ],
      series: [
        { name: '涨停', type: 'bar', data: luBuckets, itemStyle: { color: '#f5222d' }, barMaxWidth: 16 },
        { name: '炸板', type: 'bar', data: brBuckets, itemStyle: { color: '#faad14' }, barMaxWidth: 16 },
        {
          name: '累计涨停', type: 'line', yAxisIndex: 1, data: cum, smooth: true,
          itemStyle: { color: '#1677ff' }, lineStyle: { width: 2 }, symbol: 'circle', symbolSize: 4,
          markLine: nowIdx >= 0 ? {
            silent: true, symbol: 'none',
            lineStyle: { color: '#999', type: 'dashed' },
            data: [{ xAxis: labels[nowIdx], label: { formatter: '现在', fontSize: 10 } }],
          } : undefined,
        },
      ],
    })
    const onResize = () => chart.resize()
    window.addEventListener('resize', onResize)
    return () => { window.removeEventListener('resize', onResize); chart.dispose() }
  }, [luBuckets, brBuckets, cum, nowMin])

  return (
    <Card size="small" title={<span style={{ fontSize: 13 }}><RiseOutlined /> 分时涨停节奏（15min 桶）</span>} bodyStyle={{ padding: 6 }}>
      <div ref={ref} style={{ width: '100%', height: 220 }} />
    </Card>
  )
}

// ========== 龙头状态判定 ==========
function getLeaderStatus(stock: LimitUpStock, broken: LimitUpStock[]): { label: string; color: string } {
  const isBroken = broken.some(b => b.stock_code === stock.stock_code)
  if (isBroken) return { label: '危险', color: '#ef4444' }
  const bc = stock.board_count || 1
  const turnover = stock.turnover_ratio || 0
  if (bc >= 3 && turnover > 15) return { label: '分歧', color: '#f97316' }
  if (bc >= 2) return { label: '正常', color: '#22c55e' }
  return { label: '观察', color: '#999' }
}

// ========== Section B · 龙头聚焦 + 活跃主线 ==========
function SectionLeaders({ limitUp, broken, sectors }: { limitUp: LimitUpStock[]; broken: LimitUpStock[]; sectors: SectorRaw[] }) {
  const leaders = useMemo(() =>
    [...limitUp].filter(s => (s.board_count || 1) >= 3)
      .sort((a, b) => (b.board_count || 1) - (a.board_count || 1))
      .slice(0, 6),
    [limitUp])

  // 活跃主线：按"该题材在今日涨停中的成员数"排序
  const topThemes = useMemo(() => {
    const map = new Map<string, { name: string; members: LimitUpStock[]; intensity: number; change: number }>()
    limitUp.forEach(s => {
      const key = s.first_plate_name
      if (!key) return
      if (!map.has(key)) {
        const sec = sectors.find(x => sectorName(x) === key)
        map.set(key, {
          name: key, members: [],
          intensity: sectorIntensity(sec),
          change: sectorChange(sec),
        })
      }
      map.get(key)!.members.push(s)
    })
    return Array.from(map.values()).sort((a, b) => b.members.length - a.members.length).slice(0, 3)
  }, [limitUp, sectors])

  return (
    <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
      <Col xs={24} lg={14}>
        <SectionHeader icon={<CrownOutlined />} title="龙头聚焦" subtitle="≥3 板" />
        {leaders.length === 0 ? (
          <Card size="small"><Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="今日尚无 3 板及以上个股" /></Card>
        ) : (
          <Row gutter={[10, 10]}>
            {leaders.map(s => {
              const status = getLeaderStatus(s, broken)
              return (
              <Col xs={24} sm={12} key={s.stock_code}>
                <Card size="small" hoverable bodyStyle={{ padding: 12 }} style={{ borderLeft: `3px solid ${status.color}` }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Link to={`/stock/${s.stock_code}`} style={{ fontWeight: 700, fontSize: 15 }}>
                      {s.stock_name}
                    </Link>
                    <Space size={4}>
                      <Tag color={status.color} style={{ fontSize: 11, fontWeight: 600, margin: 0 }}>{status.label}</Tag>
                      <Tag color="red" style={{ margin: 0 }}>{s.board_count}板</Tag>
                    </Space>
                  </div>
                  <div style={{ fontSize: 12, color: '#666', marginTop: 4 }}>
                    {s.first_plate_name || '—'} · 封板 {s.time || '—'}
                  </div>
                  <div style={{ fontSize: 12, color: '#999', marginTop: 4, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {s.reason || s.combined_reason || '—'}
                  </div>
                  <div style={{ marginTop: 4 }}>
                    <AskAIChip prompt={`深度解析【${s.stock_name}(${s.stock_code})】今日 ${s.board_count} 板的题材逻辑（${s.first_plate_name || '—'}），当前状态「${status.label}」，判断明日延续性。`} label="AI 解析" />
                  </div>
                </Card>
              </Col>
            )})}

          </Row>
        )}
      </Col>
      <Col xs={24} lg={10}>
        <SectionHeader icon={<FireOutlined style={{ color: '#fa8c16' }} />} title="活跃主线" subtitle="按涨停成员数" />
        {topThemes.length === 0 ? (
          <Card size="small"><Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无主线数据" /></Card>
        ) : (
          <Space direction="vertical" size={10} style={{ width: '100%' }}>
            {topThemes.map((t, i) => {
              const leader = [...t.members].sort((a, b) => (b.board_count || 1) - (a.board_count || 1))[0]
              return (
                <Card key={t.name} size="small" bodyStyle={{ padding: 12 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{
                      background: i === 0 ? '#f5222d' : i === 1 ? '#fa8c16' : '#faad14',
                      color: '#fff', borderRadius: 4, padding: '0 6px', fontSize: 12, fontWeight: 700,
                    }}>#{i + 1}</span>
                    <Link to={`/theme?name=${encodeURIComponent(t.name)}`} style={{ fontWeight: 700 }}>{t.name}</Link>
                    {t.change !== 0 && (
                      <span style={{ color: t.change >= 0 ? '#f5222d' : '#52c41a', fontSize: 12 }}>
                        {t.change >= 0 ? '+' : ''}{t.change.toFixed(2)}%
                      </span>
                    )}
                  </div>
                  <div style={{ fontSize: 12, color: '#666', marginTop: 4 }}>
                    涨停 {t.members.length} 只
                    {leader && <> · 龙头 <Link to={`/stock/${leader.stock_code}`}>{leader.stock_name}</Link> <Tag color="red">{leader.board_count || 1}板</Tag></>}
                  </div>
                  <div style={{ marginTop: 2 }}>
                    <AskAIChip prompt={`今日盘中【${t.name}】题材有 ${t.members.length} 只涨停${leader ? `，龙头 ${leader.stock_name} ${leader.board_count || 1}板` : ''}，分析该题材的催化剂、持续性与介入机会。`} label="AI 解读" />
                  </div>
                </Card>
              )
            })}
          </Space>
        )}
      </Col>
    </Row>
  )
}

// ========== Section D · 风险提示 ==========
function SectionRisk({ broken, limitUp, anomaly }: { broken: LimitUpStock[]; limitUp: LimitUpStock[]; anomaly: AnyData[] }) {
  const now = new Date()
  const nowMin = now.getHours() * 60 + now.getMinutes()
  const isEndSession = nowMin >= 14 * 60 + 30 && nowMin < 15 * 60

  // 高位断板：炸板且板数 >=2
  const highBroken = broken.filter(s => (s.board_count || 0) >= 2)
  // 近 15 分钟炸板 — 密集警示
  const recentBroken = broken.filter(s => {
    const m = toMinutes(s.time)
    return m !== null && nowMin - m <= 15
  })

  // 近 15 分钟涨停（加速信号）
  const recentLu = limitUp.filter(s => {
    const m = toMinutes(s.time)
    return m !== null && nowMin - m <= 15
  })
  const totalEvents = limitUp.length + broken.length
  const brokenRate = totalEvents > 0 ? broken.length / totalEvents * 100 : 0
  const maxBoard = limitUp.reduce((m, s) => Math.max(m, s.board_count || 1), 0)
  const opportunityText = limitUp.length >= 80 && brokenRate < 30
    ? `涨停 ${limitUp.length} 只，炸板率 ${brokenRate.toFixed(1)}%，短线情绪偏强，机会集中在主线前排。`
    : limitUp.length >= 40
      ? `涨停 ${limitUp.length} 只，炸板率 ${brokenRate.toFixed(1)}%，有活跃度但需筛强度。`
      : `涨停 ${limitUp.length} 只，市场机会偏少，优先观察不追高。`
  const riskText = highBroken.length > 0
    ? `高位断板 ${highBroken.length} 只，注意高度衰竭。`
    : broken.length > 0
      ? `炸板 ${broken.length} 只但暂无 2 板以上高位断板。`
      : `暂无炸板池风险样本。`
  const anomalyText = anomaly.length > 0
    ? `异动流 ${anomaly.length} 条，可结合热点榜确认资金方向。`
    : '异动接口当前无返回，主要参考涨停/炸板池。'

  return (
    <Card
      size="small"
      title={<span><WarningOutlined style={{ color: '#fa8c16' }} /> 风险与机会提示</span>}
      style={{ marginBottom: 16 }}
    >
      <Row gutter={[12, 12]}>
        <Col xs={24} md={8}>
          <Card size="small" type="inner" title="⚡ 高位断板" headStyle={{ padding: '4px 10px' }} bodyStyle={{ padding: 8 }}>
            {highBroken.length === 0 ? <span style={{ color: '#bbb', fontSize: 12 }}>暂无 2 板以上断板</span> : (
              <Space direction="vertical" size={4} style={{ width: '100%' }}>
                {highBroken.slice(0, 5).map(s => (
                  <div key={s.stock_code} style={{ fontSize: 12 }}>
                    <Link to={`/stock/${s.stock_code}`}>{s.stock_name}</Link>
                    <Tag color="orange" style={{ marginLeft: 4 }}>{s.board_count}板</Tag>
                    <span style={{ color: '#999', marginLeft: 4 }}>{s.time}</span>
                  </div>
                ))}
                {highBroken.length >= 3 && (
                  <AskAIChip
                    prompt={`当前有 ${highBroken.length} 只 2 板及以上高位断板（${highBroken.slice(0,3).map(s=>s.stock_name).join('、')} 等），这是否预示着高度衰竭或资金出逃？`}
                    label="问 AI 风险"
                  />
                )}
              </Space>
            )}
            <div style={{ marginTop: 6, fontSize: 12, color: '#666' }}>{riskText}</div>
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card size="small" type="inner" title="🔥 近 15min 涨停加速" headStyle={{ padding: '4px 10px' }} bodyStyle={{ padding: 8 }}>
            {recentLu.length === 0 ? <span style={{ color: '#bbb', fontSize: 12 }}>暂无最新涨停</span> : (
              <div style={{ fontSize: 12 }}>
                <b style={{ fontSize: 16, color: '#f5222d' }}>{recentLu.length}</b> 只
                <div style={{ marginTop: 4 }}>
                  {recentLu.slice(0, 4).map(s => (
                    <Tag key={s.stock_code} color="red" style={{ marginBottom: 2 }}>
                      {s.stock_name} {s.board_count && s.board_count > 1 ? `${s.board_count}板` : ''}
                    </Tag>
                  ))}
                </div>
              </div>
            )}
            <div style={{ marginTop: 6, fontSize: 12, color: '#666' }}>{opportunityText}</div>
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card size="small" type="inner" title={`⏰ ${isEndSession ? '尾盘防炸' : '时段提示'}`} headStyle={{ padding: '4px 10px' }} bodyStyle={{ padding: 8 }}>
            {isEndSession ? (
              <Alert type="warning" showIcon message="尾盘 14:30 后" description="警惕高位股获利盘砸盘；次新/低位首板反而安全" style={{ fontSize: 12 }} />
            ) : recentBroken.length >= 3 ? (
              <Alert type="error" showIcon message={`近 15min 炸板 ${recentBroken.length} 只`} description="短时密集炸板，市场情绪转弱" style={{ fontSize: 12 }} />
            ) : (
              <span style={{ fontSize: 12, color: '#666' }}>
                最高 {maxBoard} 板 · {anomalyText}
              </span>
            )}
          </Card>
        </Col>
      </Row>
    </Card>
  )
}

// ========== Section C · 异动流（保留表格，加 AI 追问） ==========
function AnomalyFlows({ limitUp, broken, hot, anomaly }: {
  limitUp: LimitUpStock[]; broken: LimitUpStock[]; hot: AnyData[]; anomaly: AnyData[]
}) {
  const luCols: AnyData[] = [
    { title: '代码', dataIndex: 'stock_code', width: 76, render: safeText },
    { title: '名称', dataIndex: 'stock_name', width: 80,
      render: (v: string, r: LimitUpStock) => <Link to={`/stock/${r.stock_code}`}>{safeText(v)}</Link> },
    { title: '连板', dataIndex: 'board_count', width: 60,
      render: (v: number) => v > 1 ? <Tag color="red">{v}板</Tag> : <Tag>{v || 1}</Tag> },
    { title: '题材', dataIndex: 'first_plate_name', ellipsis: true, render: safeText },
    { title: '封板', dataIndex: 'time', width: 76, render: safeText },
  ]
  const brCols: AnyData[] = [
    { title: '代码', dataIndex: 'stock_code', width: 76, render: safeText },
    { title: '名称', dataIndex: 'stock_name', width: 80,
      render: (v: string, r: LimitUpStock) => <Link to={`/stock/${r.stock_code}`}>{safeText(v)}</Link> },
    { title: '连板', dataIndex: 'board_count', width: 60,
      render: (v: number) => v > 1 ? <Tag color="orange">{v}板</Tag> : <Tag>{v || 1}</Tag> },
    { title: '题材', dataIndex: 'first_plate_name', ellipsis: true, render: safeText },
    { title: '炸板', dataIndex: 'time', width: 76, render: safeText },
  ]
  const hotCols: AnyData[] = [
    { title: '代码', dataIndex: 'stock_code', width: 76, render: safeText },
    { title: '名称', dataIndex: 'stock_name', width: 80, render: safeText },
    { title: '涨幅', dataIndex: 'change_rate', width: 70,
      render: (v: number) => {
        const n = safeNum(v)
        return <span style={{ color: n >= 0 ? '#f5222d' : '#52c41a' }}>{n.toFixed(2)}%</span>
      } },
    { title: '题材', dataIndex: 'first_plate_name', ellipsis: true, render: safeText },
    { title: '时间', dataIndex: 'time', width: 76, render: safeText },
  ]
  const anomCols: AnyData[] = [
    { title: '代码', dataIndex: 'stock_code', width: 76, render: safeText },
    { title: '名称', dataIndex: 'stock_name', width: 80, render: safeText },
    { title: '状态', width: 70, render: (_: AnyData, r: AnyData) => {
      const s = safeText(r.data_status || r.status, '')
      const c: Record<string, string> = { '涨停': 'red', '炸板': 'orange', '跌停': 'green' }
      return <Tag color={c[s] || 'default'}>{s || '—'}</Tag>
    } },
    { title: '内容', dataIndex: 'reason', ellipsis: true, render: safeText },
    { title: '时间', dataIndex: 'time', width: 76, render: safeText },
  ]

  return (
    <Card size="small" title={<span><ThunderboltOutlined /> 实时异动流</span>} bodyStyle={{ padding: 8 }}>
      <Tabs
        type="card" size="small"
        items={[
          { key: 'lu', label: <span><Badge status="processing" color="red" /> 涨停 ({limitUp.length})</span>,
            children: <Table size="small" dataSource={limitUp} columns={luCols} rowKey="stock_code" pagination={{ pageSize: 20, showSizeChanger: false }} scroll={{ y: 320 }} /> },
          { key: 'br', label: `炸板 (${broken.length})`,
            children: <Table size="small" dataSource={broken} columns={brCols} rowKey="stock_code" pagination={{ pageSize: 20, showSizeChanger: false }} scroll={{ y: 320 }} /> },
          { key: 'hot', label: `热股 (${hot.length})`,
            children: <Table size="small" dataSource={hot} columns={hotCols} rowKey={(r, i) => r.stock_code || String(i)} pagination={{ pageSize: 20, showSizeChanger: false }} scroll={{ y: 320 }} locale={{ emptyText: <Empty description="暂无热股数据" /> }} /> },
          { key: 'anom', label: `异动 (${anomaly.length})`,
            children: <Table size="small" dataSource={anomaly} columns={anomCols} rowKey={(r, i) => r.stock_code || String(i)} pagination={{ pageSize: 20, showSizeChanger: false }} scroll={{ y: 320 }} locale={{ emptyText: <Empty description="暂无异动数据" /> }} /> },
        ]}
      />
    </Card>
  )
}

// ========== 主组件 ==========
export default function IntradayPageV2() {
  const [httpLimitUp, setLimitUp] = useState<LimitUpStock[]>([])
  const [httpBroken, setBroken] = useState<LimitUpStock[]>([])
  const [httpHot, setHot] = useState<AnyData[]>([])
  const [httpAnomaly, setAnomaly] = useState<AnyData[]>([])
  const [sectors, setSectors] = useState<SectorRaw[]>([])
  const [loading, setLoading] = useState(true)
  const [autoRefresh, setAutoRefresh] = useState(false)
  const [errMsg, setErrMsg] = useState('')
  const [isMock, setIsMock] = useState(false)
  const [meta, setMeta] = useState<ApiMeta[]>([])

  const ws = useMarketWS(autoRefresh)

  const limitUp = ws.connected && ws.limitUp.length ? ws.limitUp : httpLimitUp
  const broken = ws.connected && ws.broken.length ? ws.broken : httpBroken
  const hot = ws.connected && ws.hot.length ? ws.hot : httpHot
  const anomaly = ws.connected && ws.anomaly.length ? ws.anomaly : httpAnomaly

  useEffect(() => {
    const load = async () => {
      setLoading(true)
      const safe = async <T,>(name: string, p: Promise<T>) => {
        try { return await p } catch (e) { return { __err: true, __meta: extractErrorMeta(e, name) } as AnyData }
      }
      const [lu, br, hs, an, sec] = await Promise.all([
        safe('涨停池', fetchApi<ListResp<LimitUpStock>>('/market/limit-up')),
        safe('炸板池', fetchApi<ListResp<LimitUpStock>>('/market/broken')),
        safe('热股', fetchApi<ListResp<AnyData>>('/market/hot-stocks')),
        safe('异动', fetchApi<ListResp<AnyData>>('/market/anomaly')),
        safe('题材', fetchApi<ListResp<SectorRaw>>('/market/sectors')),
      ])
      const errs = [lu, br, hs, an].filter((x: AnyData) => x?.__err)
      if (errs.length === 4) setErrMsg(`盘中接口不可用：${((errs[0] as AnyData).__meta as ApiMeta)?.message || '请求失败'}`)
      else setErrMsg('')
      setLimitUp(((lu as AnyData).data || []).map(normalizeStock))
      setBroken(((br as AnyData).data || []).map(normalizeStock))
      setHot(((hs as AnyData).data || []).map(normalizeStock))
      setAnomaly(((an as AnyData).data || []).map(normalizeStock))
      setSectors((sec as AnyData).data || [])
      const okMeta = extractMetaList([
        { name: '涨停池', resp: lu },
        { name: '炸板池', resp: br },
        { name: '热股', resp: hs },
        { name: '异动', resp: an },
        { name: '题材', resp: sec },
      ])
      const errMeta = [lu, br, hs, an, sec]
        .map((x: AnyData) => x?.__meta as ApiMeta | undefined)
        .filter((m): m is ApiMeta => Boolean(m))
      const nextMeta = [...okMeta, ...errMeta]
      setMeta(nextMeta)
      setIsMock(nextMeta.some((m) => m.mock))
      setLoading(false)
    }
    void load()
  }, [])

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '120px auto' }} />

  const isEmpty = !limitUp.length && !broken.length && !hot.length && !anomaly.length

  return (
    <div>
      <MockBanner show={isMock} />
      <AIBadge style={{ marginBottom: 8 }} />
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12, flexWrap: 'wrap', gap: 8 }}>
        <h2 style={{ margin: 0 }}>盘中盯盘 · {new Date().toLocaleDateString('zh-CN')}</h2>
        <Space>
          <span style={{ color: '#666', fontSize: 12 }}>实时推送 (3s)</span>
          <Switch checked={autoRefresh} onChange={setAutoRefresh} size="small" />
          {autoRefresh && (
            <Tooltip title={ws.connected ? 'WebSocket 已连接' : '正在重连...'}>
              <Badge status={ws.connected ? 'success' : 'warning'} text={ws.connected ? '已连接' : '重连中'} />
            </Tooltip>
          )}
          <Link to="/intraday-legacy" style={{ fontSize: 12, color: '#999' }}>切换旧版 →</Link>
        </Space>
      </div>
      {errMsg && <Alert type="error" showIcon closable message={errMsg} style={{ marginBottom: 12 }} />}
      {!errMsg && isEmpty && (
        <Alert type="info" showIcon message="今日暂无盘中短线数据" description="接口返回真实空状态，页面不展示示例行情。" style={{ marginBottom: 12 }} />
      )}
      <MetaStrip items={meta} />

      {/* 高位风险灯 */}
      {(() => {
        const brRate = limitUp.length + broken.length > 0
          ? broken.length / (limitUp.length + broken.length) * 100 : 0
        const highBroken = broken.filter(s => (s.board_count || 0) >= 2).length
        const riskLevel = brRate > 40 || highBroken >= 3 ? 'high'
          : brRate > 25 || highBroken >= 1 ? 'medium' : 'low'
        const RISK = {
          high: { color: '#ef4444', bg: '#fef2f2', label: '高风险 · 炸板扩散，回避追高', icon: '🔴' },
          medium: { color: '#f97316', bg: '#fff7ed', label: '中风险 · 精选为主，控制仓位', icon: '🟡' },
          low: { color: '#22c55e', bg: '#f0fdf4', label: '低风险 · 情绪正常，可跟主线', icon: '🟢' },
        }
        const r = RISK[riskLevel]
        return (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 12, padding: '8px 16px', marginBottom: 12,
            background: r.bg, borderRadius: 8, borderLeft: `4px solid ${r.color}`,
          }}>
            <span style={{ fontSize: 20 }}>{r.icon}</span>
            <span style={{ fontWeight: 600, color: r.color }}>{r.label}</span>
            <span style={{ fontSize: 12, color: '#666' }}>
              炸板率 {brRate.toFixed(0)}% · 高位炸板 {highBroken} 只
            </span>
            <Link to="/watchlist" style={{ marginLeft: 'auto', fontSize: 12 }}>
              观察池触发 →
            </Link>
          </div>
        )
      })()}

      <Tabs
        size="small" type="line" style={{ marginBottom: 12 }}
        onChange={(k) => document.getElementById(`intraday-${k}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
        items={[
          { key: 'pulse', label: '盘中脉搏' },
          { key: 'leaders', label: '龙头监控' },
          { key: 'anomaly', label: '异动流' },
          { key: 'risk', label: '炸板预警' },
          { key: 'watchlist', label: '观察池' },
        ]}
      />
      <div id="intraday-pulse"><SectionPulse limitUp={limitUp} broken={broken} /></div>
      <div id="intraday-leaders"><SectionLeaders limitUp={limitUp} broken={broken} sectors={sectors} /></div>
      <div id="intraday-anomaly"><AnomalyFlows limitUp={limitUp} broken={broken} hot={hot} anomaly={anomaly} /></div>
      <div id="intraday-risk"><SectionRisk broken={broken} limitUp={limitUp} anomaly={anomaly} /></div>
      <div id="intraday-watchlist">
        <Card size="small" title={<span><EyeOutlined /> 观察池</span>} style={{ marginBottom: 16 }}>
          <Link to="/research-pool">查看完整研究池 →</Link>
        </Card>
      </div>
    </div>
  )
}
