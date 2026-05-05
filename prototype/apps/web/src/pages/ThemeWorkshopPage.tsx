import { useCallback, useEffect, useRef, useState } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import {
  Card, Col, Row, Tag, Spin, Tabs, Space, Button, Empty, Badge, message, Alert,
} from 'antd'
import {
  TagsOutlined, ThunderboltOutlined,
  FireOutlined, RobotOutlined, RiseOutlined, RadarChartOutlined,
} from '@ant-design/icons'
import * as echarts from 'echarts'
import { fetchApi } from '../api/client'
import { askAI } from '../api/copilot'
import AIDisclaimer from '../components/AIDisclaimer'
import AIBadge from '../components/AIBadge'
import { AskAIChip, SectionHeader } from '../components/smart'
import type { ApiMeta, DataStatus } from '../api/types'
import { extractMeta } from '../api/useApiMeta'
import DataStatusBadge from '../components/DataStatusBadge'

interface Sector {
  PlateID?: string
  PlateName?: string
  plate_name?: string
  concept_name?: string
  ChangePercent?: number
  change_percent?: number
  LimitUpNum?: number
  limit_up_num?: number
  MainForce?: number
  concept_net_amount?: number
  Intensity?: number
  concept_intensity?: number
  plate_id?: string
  first_plate_name?: string
  stock_name?: string
  change_rate?: number
  net_flow?: number
  intensity?: number
  is_new?: boolean; is_hot?: boolean; stage?: string
}

interface CycleItem {
  name: string; phase: string; icon: string; color: string
  score: number; appearance_days: number; trend: string
  today_limit_up: number; advice: string
}

interface NewsItem {
  id: string; title: string; summary: string; publish_time: string
  source: string; url: string; is_red: boolean
  matched_themes: string[]; stocks: { code: string; name: string }[]
}

interface DetailStock {
  SecurityCode?: string
  SecurityName?: string
  ChangePercent?: number
  stock_code?: string
  stock_name?: string
  change_rate?: number
  board_count?: number
}

function safeText(v: unknown, fallback = '—'): string {
  if (v === undefined || v === null || v === '') return fallback
  return String(v)
}
function safeNum(v: unknown, fallback = 0): number {
  const n = Number(v)
  return Number.isFinite(n) ? n : fallback
}
function pick(s: Sector): string {
  return s.first_plate_name || s.PlateName || s.plate_name || s.concept_name || s.stock_name || ''
}
function pickNum(s: Sector, key: keyof Sector): number {
  if (key === 'intensity') return safeNum(s.intensity ?? s.Intensity ?? s.concept_intensity)
  if (key === 'change_rate') return safeNum(s.change_rate ?? s.ChangePercent ?? s.change_percent)
  if (key === 'limit_up_num') return safeNum(s.limit_up_num ?? s.LimitUpNum)
  if (key === 'net_flow') return safeNum(s.net_flow ?? s.MainForce ?? s.concept_net_amount)
  return safeNum(s[key])
}

function plateId(s: Sector): string {
  return s.plate_id || s.PlateID || ''
}

function stockCode(s: DetailStock): string {
  return s.stock_code || s.SecurityCode || ''
}

function stockName(s: DetailStock): string {
  return s.stock_name || s.SecurityName || ''
}

function stockChange(s: DetailStock): number {
  return safeNum(s.change_rate ?? s.ChangePercent)
}

// ========== 题材热力气泡图 ==========
function ThemeHeatBubble({ sectors, cycles, onSelect }: {
  sectors: Sector[]; cycles: Record<string, CycleItem>; onSelect: (name: string) => void
}) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!ref.current || !sectors.length) return
    const chart = echarts.init(ref.current)
    const PHASE_COLOR: Record<string, string> = {
      '发酵': '#22c55e', '启动': '#3b82f6', '高潮': '#ef4444',
      '退潮': '#f97316', '冷却': '#8b5cf6', '中性': '#999',
    }
    const data = sectors.slice(0, 30).map(s => {
      const name = pick(s)
      const change = pickNum(s, 'change_rate')
      const intensity = pickNum(s, 'intensity')
      const luNum = pickNum(s, 'limit_up_num')
      const cycle = cycles[name]
      const phase = cycle?.phase || s.stage || '中性'
      return {
        name,
        value: [change, intensity, Math.max(luNum * 8, 12)],
        itemStyle: { color: PHASE_COLOR[phase] || '#999', opacity: 0.75 },
        label: { show: luNum >= 2, formatter: name, fontSize: 11 },
      }
    })

    chart.setOption({
      tooltip: {
        formatter: (p: AnyData) => {
          const d = p.data
          const cycle = cycles[d.name]
          return `<b>${d.name}</b><br/>涨幅 ${d.value[0].toFixed(2)}% · 强度 ${d.value[1].toFixed(0)}<br/>${cycle ? `${cycle.icon} ${cycle.phase} · 活跃${cycle.appearance_days}日` : ''}`
        },
      },
      grid: { left: 50, right: 20, top: 20, bottom: 40 },
      xAxis: { name: '涨幅%', nameLocation: 'middle', nameGap: 25, splitLine: { lineStyle: { type: 'dashed' } } },
      yAxis: { name: '强度', nameLocation: 'middle', nameGap: 35, splitLine: { lineStyle: { type: 'dashed' } } },
      series: [{
        type: 'scatter', symbolSize: (d: number[]) => d[2],
        data,
        emphasis: { itemStyle: { borderWidth: 2, borderColor: '#333' } },
      }],
    })
    chart.on('click', (p: AnyData) => { if (p.data?.name) onSelect(p.data.name) })
    const onResize = () => chart.resize()
    window.addEventListener('resize', onResize)
    return () => { window.removeEventListener('resize', onResize); chart.dispose() }
  }, [sectors, cycles, onSelect])

  return <div ref={ref} style={{ width: '100%', height: 320 }} />
}

// ========== 题材排行列表 ==========
function ThemeRankList({ sectors, cycles, selected, onSelect }: {
  sectors: Sector[]; cycles: Record<string, CycleItem>; selected: string; onSelect: (name: string) => void
}) {
  const PHASE_COLOR: Record<string, string> = {
    '发酵': 'green', '启动': 'blue', '高潮': 'red',
    '退潮': 'orange', '冷却': 'purple', '中性': 'default',
  }
  return (
    <div style={{ maxHeight: 520, overflow: 'auto' }}>
      {sectors.slice(0, 20).map((s, i) => {
        const name = pick(s)
        const change = pickNum(s, 'change_rate')
        const luNum = pickNum(s, 'limit_up_num')
        const netFlow = pickNum(s, 'net_flow')
        const cycle = cycles[name]
        const isSelected = name === selected
        return (
          <div
            key={name || i}
            onClick={() => onSelect(name)}
            style={{
              padding: '8px 12px', cursor: 'pointer', borderRadius: 6,
              borderBottom: '1px solid #f5f5f5',
              background: isSelected ? '#e6f4ff' : 'transparent',
              transition: 'background 0.15s',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Badge count={i + 1} style={{
                backgroundColor: i < 3 ? '#f5222d' : i < 6 ? '#fa8c16' : '#d9d9d9',
                fontSize: 11,
              }} />
              <span style={{ fontWeight: 600, fontSize: 14, flex: 1 }}>{name}</span>
              <span style={{ color: change >= 0 ? '#f5222d' : '#52c41a', fontWeight: 600 }}>
                {change >= 0 ? '+' : ''}{change.toFixed(2)}%
              </span>
            </div>
            <div style={{ display: 'flex', gap: 6, marginTop: 4, flexWrap: 'wrap' }}>
              {cycle && (
                <Tag color={PHASE_COLOR[cycle.phase] || 'default'} style={{ fontSize: 11 }}>
                  {cycle.icon} {cycle.phase}
                </Tag>
              )}
              {luNum > 0 && <Tag style={{ fontSize: 11 }}>涨停 {luNum}</Tag>}
              {s.is_new && <Tag color="cyan" style={{ fontSize: 11 }}>新题材</Tag>}
              <span style={{ fontSize: 11, color: netFlow >= 0 ? '#f5222d' : '#52c41a' }}>
                主力 {netFlow >= 0 ? '+' : ''}{(netFlow / 1e8).toFixed(1)}亿
              </span>
            </div>
          </div>
        )
      })}
    </div>
  )
}

// ========== 题材详情面板 ==========
function ThemeDetailPanel({ name, cycles }: { name: string; cycles: Record<string, CycleItem> }) {
  const [stocks, setStocks] = useState<DetailStock[]>([])
  const [loading, setLoading] = useState(false)
  const [cycle, setCycle] = useState<AnyData>(null)
  const cycle0 = cycles[name]

  useEffect(() => {
    if (!name) return
    let cancelled = false
    const run = async () => {
      setLoading(true)
      setStocks([])
      try {
        const [cycleRes, secRes] = await Promise.allSettled([
          fetchApi<AnyData>(`/theme/cycle/${encodeURIComponent(name)}?days=10`),
          fetchApi<{ data: DetailStock[] }>(`/theme/sectors`),
        ])
        if (cancelled) return
        setCycle(cycleRes.status === 'fulfilled' ? cycleRes.value : null)
        if (secRes.status === 'fulfilled') {
          const sec = (secRes.value.data || []).find((s: AnyData) => pick(s as Sector) === name)
          if (sec) {
            const pid = plateId(sec as Sector)
            if (pid) {
              try {
                const r = await fetchApi<{ data: DetailStock[] }>(`/theme/sectors/${pid}`)
                if (!cancelled) setStocks(r.data || [])
              } catch { if (!cancelled) setStocks([]) }
            }
          }
        }
      } catch { /* ignore */ }
      if (!cancelled) setLoading(false)
    }
    void run()
    return () => { cancelled = true }
  }, [name])

  if (!name) return <Card size="small"><Empty description="点击左侧题材查看详情" /></Card>

  const sorted = [...stocks].sort((a, b) => (b.board_count || 0) - (a.board_count || 0))
  const ROLE_STYLE: Record<string, { color: string; label: string }> = {
    dragon: { color: '#f5222d', label: '龙头' },
    zhongjun: { color: '#fa8c16', label: '中军' },
    follower: { color: '#1677ff', label: '跟风' },
  }

  const dragon = sorted[0]
  const zhongjun = sorted.find(s => (s.board_count || 0) >= 2 && s !== dragon)
  const followers = sorted.filter(s => s !== dragon && s !== zhongjun).slice(0, 8)

  return (
    <Card size="small" title={<span><FireOutlined style={{ color: '#f5222d' }} /> {name}</span>}
      loading={loading}
      extra={cycle0 && <Tag color={cycle0.color}>{cycle0.icon} {cycle0.phase}</Tag>}
    >
      {cycle && (
        <div style={{ marginBottom: 12, padding: 8, background: '#fafafa', borderRadius: 6, fontSize: 12, lineHeight: 1.8 }}>
          <div>活跃 <b>{cycle.appearance_days}</b> 天 · 趋势 <b>{cycle.trend}</b> · 热度 <b>{cycle.score}</b></div>
          <div style={{ color: '#666' }}>{cycle.advice}</div>
        </div>
      )}

      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>龙头梯队</div>
      {dragon && (
        <div style={{ marginBottom: 6 }}>
          <Tag color={ROLE_STYLE.dragon.color}>{ROLE_STYLE.dragon.label}</Tag>
          <Link to={`/stock/${stockCode(dragon)}`}>
            {safeText(stockName(dragon))}
          </Link>
          <span style={{ marginLeft: 8, color: '#f5222d' }}>
            +{stockChange(dragon).toFixed(2)}%
          </span>
          {dragon.board_count && dragon.board_count > 0 && <Tag color="red" style={{ marginLeft: 4 }}>{dragon.board_count}板</Tag>}
        </div>
      )}
      {zhongjun && (
        <div style={{ marginBottom: 6 }}>
          <Tag color={ROLE_STYLE.zhongjun.color}>{ROLE_STYLE.zhongjun.label}</Tag>
          <Link to={`/stock/${stockCode(zhongjun)}`}>
            {safeText(stockName(zhongjun))}
          </Link>
        </div>
      )}
      {followers.length > 0 && (
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginBottom: 8 }}>
          {followers.map((s, i) => (
            <Link key={i} to={`/stock/${stockCode(s)}`}>
              <Tag>{safeText(stockName(s))}</Tag>
            </Link>
          ))}
        </div>
      )}

      <AskAIChip
        prompt={`深度分析题材【${name}】：当前阶段${cycle0?.phase || ''}，核心驱动逻辑、产业链上下游、龙头${dragon ? safeText(stockName(dragon), '') : ''}的后续空间判断，以及明天该题材还能否延续。`}
        label="AI 深度解读"
      />
    </Card>
  )
}

// ========== 事件快讯精简版 ==========
function EventTimeline({ onSelectTheme }: { onSelectTheme?: (name: string) => void }) {
  const [items, setItems] = useState<NewsItem[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchApi<{ items: NewsItem[] }>('/news/timeline?n=30&important_only=true')
      .then(r => setItems(r.items || []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <Spin size="small" />

  return (
    <div style={{ maxHeight: 400, overflow: 'auto' }}>
      {items.length === 0 && <Empty description="暂无重要快讯" image={Empty.PRESENTED_IMAGE_SIMPLE} />}
      {items.slice(0, 15).map(n => (
        <div key={n.id} style={{ padding: '6px 0', borderBottom: '1px dashed #f0f0f0', fontSize: 12 }}>
          <span style={{ color: '#999', marginRight: 8 }}>{(n.publish_time || '').slice(11, 16)}</span>
          {n.is_red && <Tag color="red" style={{ fontSize: 10 }}>重要</Tag>}
          <span style={{ fontWeight: n.is_red ? 600 : 400 }}>{n.title}</span>
          {n.matched_themes?.slice(0, 2).map(t => (
            <Tag key={t} color="orange" style={{ fontSize: 10, marginLeft: 4, cursor: onSelectTheme ? 'pointer' : 'default' }}
              onClick={() => onSelectTheme?.(t)}>{t}</Tag>
          ))}
        </div>
      ))}
    </div>
  )
}

// ========== 题材周期雷达分布 ==========
const PHASE_DEFS: { key: string; label: string; color: string; icon: string }[] = [
  { key: '发酵', label: '发酵', color: '#22c55e', icon: '🌱' },
  { key: '启动', label: '启动', color: '#3b82f6', icon: '🚀' },
  { key: '高潮', label: '高潮', color: '#ef4444', icon: '🔥' },
  { key: '退潮', label: '退潮', color: '#f97316', icon: '🌊' },
  { key: '冷却', label: '冷却', color: '#8b5cf6', icon: '❄️' },
  { key: '中性', label: '中性', color: '#999', icon: '⚪' },
]

function CycleRadarView({ cycles }: { cycles: Record<string, CycleItem> }) {
  const items = Object.values(cycles)
  const total = items.length || 1

  const grouped: Record<string, CycleItem[]> = {}
  for (const def of PHASE_DEFS) grouped[def.key] = []
  for (const c of items) {
    const phase = c.phase || '中性'
    if (!grouped[phase]) grouped[phase] = []
    grouped[phase].push(c)
  }

  return (
    <div>
      <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>
        <RadarChartOutlined style={{ marginRight: 6, color: '#1677ff' }} />
        题材周期雷达 · 6 阶段分布
      </div>

      <Row gutter={[12, 12]} style={{ marginBottom: 20 }}>
        {PHASE_DEFS.map(def => {
          const count = grouped[def.key]?.length || 0
          const pct = ((count / total) * 100).toFixed(1)
          return (
            <Col key={def.key} xs={12} sm={8} md={4}>
              <Card size="small" bodyStyle={{ textAlign: 'center', padding: '12px 8px' }}
                style={{ borderTop: `3px solid ${def.color}` }}>
                <div style={{ fontSize: 20 }}>{def.icon}</div>
                <div style={{ fontSize: 13, fontWeight: 600, color: def.color }}>{def.label}</div>
                <div style={{ fontSize: 22, fontWeight: 700 }}>{count}</div>
                <div style={{ fontSize: 11, color: '#999' }}>{pct}%</div>
              </Card>
            </Col>
          )
        })}
      </Row>

      {PHASE_DEFS.map(def => {
        const list = grouped[def.key] || []
        if (list.length === 0) return null
        return (
          <div key={def.key} style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 6, color: def.color }}>
              {def.icon} {def.label}
              <Tag color="default" style={{ marginLeft: 8, fontSize: 11 }}>{list.length} 个</Tag>
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {list.sort((a, b) => b.score - a.score).map(c => (
                <Card key={c.name} size="small" bodyStyle={{ padding: '8px 12px' }}
                  style={{ minWidth: 180, flex: '0 0 auto' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span style={{ fontWeight: 600, fontSize: 13 }}>{c.name}</span>
                    {c.trend === 'new' && <Tag color="cyan" style={{ fontSize: 10 }}>新题材</Tag>}
                  </div>
                  <div style={{ fontSize: 11, color: '#666', marginTop: 4 }}>
                    热度 {c.score} · 趋势 {c.trend} · 活跃 {c.appearance_days}天
                  </div>
                  <div style={{ fontSize: 11, color: '#999', marginTop: 2 }}>{c.advice}</div>
                </Card>
              ))}
            </div>
          </div>
        )
      })}

      {items.length === 0 && <Empty description="暂无题材周期数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />}
    </div>
  )
}

// ========== 主组件 ==========
export default function ThemeWorkshopPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const tab = searchParams.get('tab') || 'sectors'
  const [sectors, setSectors] = useState<Sector[]>([])
  const [cycles, setCycles] = useState<Record<string, CycleItem>>({})
  const [selected, setSelected] = useState('')
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState('')
  const [meta, setMeta] = useState<ApiMeta | null>(null)

  useEffect(() => {
    let cancelled = false
    const run = async () => {
      setLoading(true)
      setErr('')
      setMeta(null)
      try {
        const [sec, cyc] = await Promise.all([
          fetchApi<{ data: Sector[]; source?: string; data_status?: string; mock?: boolean; message?: string }>('/theme/sectors'),
          fetchApi<{ items: CycleItem[] }>('/theme/cycle-batch?top=20'),
        ])
        if (cancelled) return
        const data = (sec.data || []).sort((a, b) =>
          pickNum(b, 'intensity') - pickNum(a, 'intensity')
        )
        setSectors(data)
        setMeta(extractMeta(sec))
        const m: Record<string, CycleItem> = {}
        for (const c of cyc.items || []) m[c.name] = c
        setCycles(m)
        if (data.length > 0 && !selected) {
          setSelected(pick(data[0]))
        }
      } catch {
        if (!cancelled) {
          const msg = '题材接口不可用，当前不展示题材数据。'
          setErr(msg)
          message.error(msg)
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void run()
    return () => { cancelled = true }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleSelect = useCallback((name: string) => setSelected(name), [])

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '120px auto' }} />

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <h2 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
          <TagsOutlined style={{ color: '#1677ff' }} /> 题材工坊
          <span style={{ fontSize: 13, color: '#999', fontWeight: 400 }}>· 主线挖掘与推演</span>
        </h2>
        <Space>
          <Tag color="blue">{sectors.length} 个活跃题材</Tag>
          <Button size="small" icon={<RobotOutlined />}
            onClick={() => askAI(`今日活跃题材 Top5：${sectors.slice(0, 5).map(pick).filter(Boolean).join('、') || '暂无'}。分析哪个是真正主线、哪个是跟风，明天最可能延续的是哪条线。`)}
          >AI 判断主线</Button>
        </Space>
      </div>
      {err && <Alert type="error" showIcon message={err} style={{ marginBottom: 12 }} />}
      {!err && sectors.length === 0 && <Alert type="info" showIcon message="暂无题材数据" description="接口返回真实空状态，未展示示例题材。" style={{ marginBottom: 12 }} />}
      {!err && meta && (
        <Alert
          type={meta.mock ? 'warning' : meta.data_status === 'unavailable' || meta.data_status === 'error' ? 'error' : meta.data_status === 'empty' ? 'info' : 'success'}
          showIcon
          message={
            <DataStatusBadge status={meta.data_status as DataStatus} source={meta.source} mock={meta.mock} />
          }
          description={meta.message}
          style={{ marginBottom: 12 }}
        />
      )}

      <Tabs
        activeKey={tab}
        onChange={(k) => setSearchParams({ tab: k }, { replace: true })}
        type="card"
        items={[
          {
            key: 'events',
            label: <span><ThunderboltOutlined /> 事件时间线</span>,
            children: <HotEventsInline />,
          },
          {
            key: 'sectors',
            label: <span><FireOutlined /> 板块强度</span>,
            children: (
              <>
                {meta && (
                  <div style={{ marginBottom: 12 }}>
                    <DataStatusBadge status={meta.data_status as DataStatus} source={meta.source} mock={meta.mock} />
                  </div>
                )}
                <Card size="small" title={<SectionHeader icon={<RiseOutlined />} title="题材热力图" subtitle="气泡大小=涨停数 颜色=周期阶段" />} style={{ marginBottom: 16 }} bodyStyle={{ padding: 8 }}>
                  <ThemeHeatBubble sectors={sectors} cycles={cycles} onSelect={handleSelect} />
                </Card>

                <Row gutter={16}>
                  <Col xs={24} lg={8}>
                    <Card size="small" title="题材排行" bodyStyle={{ padding: 0 }}>
                      <ThemeRankList sectors={sectors} cycles={cycles} selected={selected} onSelect={handleSelect} />
                    </Card>
                  </Col>
                  <Col xs={24} lg={9}>
                    <ThemeDetailPanel name={selected} cycles={cycles} />
                  </Col>
                  <Col xs={24} lg={7}>
                    <Card size="small" title={<span><ThunderboltOutlined /> 事件快讯</span>}>
                      <EventTimeline onSelectTheme={handleSelect} />
                    </Card>
                  </Col>
                </Row>
              </>
            ),
          },
          {
            key: 'rotation',
            label: <span><RiseOutlined /> 轮动推演</span>,
            children: <RotationInline />,
          },
          {
            key: 'cycle',
            label: <span><RadarChartOutlined /> 题材周期</span>,
            children: (
              <>
                {meta && (
                  <div style={{ marginBottom: 12 }}>
                    <DataStatusBadge status={meta.data_status as DataStatus} source={meta.source} mock={meta.mock} />
                  </div>
                )}
                <CycleRadarView cycles={cycles} />
              </>
            ),
          },
        ]}
      />
      <AIBadge style={{ marginBottom: 8 }} />
      <AIDisclaimer variant="inline" />
    </div>
  )
}

import { lazy, Suspense } from 'react'
import type { AnyData } from '../api/types'
const HotEventsPageLazy = lazy(() => import('./HotEventsPage'))
const RotationPageLazy = lazy(() => import('./RotationPage'))
const fallback = <div style={{ padding: 48, textAlign: 'center' }}><Spin size="large" /></div>
function HotEventsInline() { return <Suspense fallback={fallback}><HotEventsPageLazy /></Suspense> }
function RotationInline() { return <Suspense fallback={fallback}><RotationPageLazy /></Suspense> }
