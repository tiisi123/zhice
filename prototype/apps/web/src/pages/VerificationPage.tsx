import { lazy, Suspense, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Alert, Card, Col, Row, Tabs, Spin, Statistic, Tag, Space, Button, Table, Empty, message } from 'antd'
import {
  WarningOutlined, AuditOutlined, HistoryOutlined,
  AimOutlined, SafetyOutlined, ExperimentOutlined,
} from '@ant-design/icons'
import { fetchApi, postApi } from '../api/client'
import { AskAIChip } from '../components/smart'
import AIDisclaimer from '../components/AIDisclaimer'
import type { AnyData } from '../api/types'

const BrokenCasesPage = lazy(() => import('./BrokenCasesPage'))
const LonghuPage = lazy(() => import('./LonghuPage'))
const SentimentPageV2 = lazy(() => import('./SentimentPageV2'))

const fallback = (
  <div style={{ padding: 48, textAlign: 'center' }}>
    <Spin size="large" />
  </div>
)

function safeNum(v: unknown, fallback = 0) {
  const n = Number(v)
  return Number.isFinite(n) ? n : fallback
}

interface RiskOverview {
  broken_total: number
  broken_rate: number
  seal_rate: number
  high_board_broken: number
  top_reasons: [string, number][]
  risk_level: 'high' | 'medium' | 'low'
}

interface ApiMeta {
  name: string
  source?: string
  data_status?: string
  mock?: boolean
  message?: string
}

function RiskDashboard() {
  const [data, setData] = useState<RiskOverview | null>(null)
  const [phase, setPhase] = useState<AnyData>(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState('')
  const [meta, setMeta] = useState<ApiMeta[]>([])

  useEffect(() => {
    Promise.all([
      fetchApi<AnyData>('/analysis/broken-cases'),
      fetchApi<AnyData>('/market/summary'),
      fetchApi<AnyData>('/market/sentiment-phase').catch(() => null),
    ]).then(([broken, summary, ph]) => {
      setPhase(ph)
      setMeta([
        { name: '炸板', source: broken?.source, data_status: broken?.data_status, mock: broken?.mock, message: broken?.message },
        { name: '市场', source: summary?.source, data_status: summary?.data_status, mock: summary?.mock, message: summary?.message },
        { name: '情绪', source: ph?.source, data_status: ph?.data_status, mock: ph?.mock, message: ph?.message },
      ].filter((m) => m.source || m.data_status || m.mock !== undefined))
      if (!broken || !summary) { setData(null); return }
      const byReason = broken.by_reason || {}
      const total = broken.total || 0
      const brRate = summary.broken_rate || 0
      const sealRate = summary.seal_success_rate || 0
      const highBoardBroken = Object.values(byReason).flatMap((d: AnyData) =>
        (d.cases || []).filter((c: AnyData) => (c.board_count || 0) >= 2)
      ).length
      const topReasons: [string, number][] = Object.entries(byReason)
        .map(([reason, d]: [string, AnyData]) => [reason, d.count || 0] as [string, number])
        .sort((a, b) => b[1] - a[1])
        .slice(0, 5)
      setData({
        broken_total: total, broken_rate: brRate, seal_rate: sealRate,
        high_board_broken: highBoardBroken, top_reasons: topReasons,
        risk_level: brRate > 40 ? 'high' : brRate > 25 ? 'medium' : 'low',
      })
      setErr('')
    }).catch(() => {
      setData(null)
      setMeta([])
      setErr('风险总览接口不可用，当前不展示风险总览。')
    }).finally(() => setLoading(false))
  }, [])

  if (loading) return <Spin />
  if (err) return <Alert type="error" showIcon message={err} style={{ marginBottom: 16 }} />

  const RISK_COLOR = { high: '#ef4444', medium: '#f97316', low: '#22c55e' }
  const RISK_LABEL = { high: '高风险 — 谨慎操作', medium: '中风险 — 精选为主', low: '低风险 — 可积极参与' }

  return (
    <Card
      size="small"
      style={{ marginBottom: 16, borderLeft: `4px solid ${data ? RISK_COLOR[data.risk_level] : '#999'}` }}
    >
      {meta.length > 0 && (
        <Space wrap size={6} style={{ marginBottom: 12 }}>
          {meta.map((m) => (
            <Tag key={m.name} color={m.mock ? 'red' : m.data_status === 'empty' ? 'default' : m.data_status === 'ok' ? 'green' : 'orange'}>
              {m.name}: {m.source || '未知源'} / {m.data_status || '未知状态'}{m.mock ? ' / mock' : ''}
            </Tag>
          ))}
        </Space>
      )}
      <Row gutter={16} align="middle">
        <Col xs={24} md={5}>
          <div style={{ fontSize: 12, color: '#999' }}>今日风险评级</div>
          <div style={{
            fontSize: 18, fontWeight: 700,
            color: data ? RISK_COLOR[data.risk_level] : '#999',
          }}>
            {data ? (
              <><SafetyOutlined /> {RISK_LABEL[data.risk_level]}</>
            ) : '暂无风险数据'}
          </div>
        </Col>
        {data && (
          <>
            <Col xs={12} md={4}>
              <Statistic title="炸板数" value={data.broken_total} valueStyle={{ color: '#fa8c16', fontSize: 20 }} />
            </Col>
            <Col xs={12} md={4}>
              <Statistic title="炸板率" value={data.broken_rate} suffix="%" precision={1}
                valueStyle={{ color: data.broken_rate > 35 ? '#ef4444' : '#333', fontSize: 20 }} />
            </Col>
            <Col xs={12} md={4}>
              <Statistic title="封板率" value={data.seal_rate} suffix="%" precision={1}
                valueStyle={{ color: data.seal_rate < 60 ? '#ef4444' : '#22c55e', fontSize: 20 }} />
            </Col>
            <Col xs={12} md={3}>
              <Statistic title="高位炸板" value={data.high_board_broken}
                valueStyle={{ color: data.high_board_broken > 3 ? '#ef4444' : '#333', fontSize: 20 }} />
            </Col>
            <Col xs={24} md={4}>
              <div style={{ fontSize: 12, color: '#999', marginBottom: 4 }}>炸板归因</div>
              <Space wrap size={4}>
                {data.top_reasons.map(([reason, count]) => (
                  <Tag key={reason} color={count >= 3 ? 'red' : 'default'} style={{ fontSize: 11 }}>
                    {reason} {count}
                  </Tag>
                ))}
              </Space>
            </Col>
          </>
        )}
      </Row>
      {phase && (
        <div style={{ marginTop: 8, fontSize: 12, color: '#666' }}>
          情绪周期：<Tag color="blue">{phase.phase}</Tag>
          置信度 {((phase.confidence || 0) * 100).toFixed(0)}%
        </div>
      )}
      <AskAIChip
        prompt={`今日炸板 ${data?.broken_total || 0} 只，炸板率 ${data?.broken_rate?.toFixed(1) || 0}%，高位炸板 ${data?.high_board_broken || 0} 只。风险评级 ${data?.risk_level || ''}。分析风险是否在扩散，明天是否可能进一步恶化，给出操作建议。`}
        label="AI 风险研判"
      />
    </Card>
  )
}

const STRATEGY_NOTES: Record<string, { desc: string; suit: string; risk: string }> = {
  '龙头打板': {
    desc: '主线龙头首次涨停日打板，次日溢价卖出',
    suit: '高潮/主升阶段',
    risk: '封不住或次日低开',
  },
  '首板接力': {
    desc: '昨日首板今日二板接力',
    suit: '回升/高潮阶段',
    risk: '承接率低时失败率高',
  },
  '龙头分歧低吸': {
    desc: '龙头连板后首次分歧低吸，等待转一致',
    suit: '高潮/顶背离阶段',
    risk: '主线退潮则分歧变崩溃',
  },
  '炸板反包': {
    desc: '前日涨停炸板后低开，次日反包涨停',
    suit: '回升/主升阶段',
    risk: '题材退潮则无反包动力',
  },
  '低位首板': {
    desc: '低位/新题材首次涨停，博弈新主线启动',
    suit: '筑底/回升阶段',
    risk: '题材证伪或情绪恶化',
  },
}

interface StrategyBacktest {
  strategy_name: string
  total_return: number
  annualized_return: number
  max_drawdown: number
  sharpe_ratio: number
  win_rate: number
  profit_loss_ratio: number
  total_trades: number
  data_source?: string
}

function StrategyTemplatesTab() {
  const [templates, setTemplates] = useState<Record<string, AnyData>>({})
  const [results, setResults] = useState<Record<string, StrategyBacktest>>({})
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(false)
  const [running, setRunning] = useState<string | null>(null)

  useEffect(() => {
    fetchApi<{ templates: Record<string, AnyData> }>('/strategy/templates')
      .then((r) => setTemplates(r.templates || {}))
      .catch((e: AnyData) => message.error((e as Error)?.message || '策略模板加载失败'))
  }, [])

  const names = Object.keys(templates)

  const runTemplate = async (name: string) => {
    setRunning(name)
    try {
      const r = await fetchApi<AnyData>('/market/sentiment-phase').catch(() => null)
      const data = await postApi<{ result: StrategyBacktest | null; data_status?: string; message?: string }>(`/strategy/run-template?template_name=${encodeURIComponent(name)}&years=3`)
      if (!data.result) {
        setErrors((prev) => ({ ...prev, [name]: data.message || '真实历史行情不可用' }))
        setResults((prev) => {
          const next = { ...prev }
          delete next[name]
          return next
        })
        message.warning(data.message || '真实历史行情不可用')
        return
      }
      const result = data.result
      setResults((prev) => ({ ...prev, [name]: result }))
      setErrors((prev) => {
        const next = { ...prev }
        delete next[name]
        return next
      })
      if (r?.phase) message.success(`已按近 3 年数据回测：${name}（当前情绪 ${r.phase}）`)
    } catch (e) {
      message.error((e as Error)?.message || '回测失败')
    } finally {
      setRunning(null)
    }
  }

  const runAll = async () => {
    setLoading(true)
    try {
      const next: Record<string, StrategyBacktest> = {}
      const nextErrors: Record<string, string> = {}
      for (const name of names) {
        const data = await postApi<{ result: StrategyBacktest | null; message?: string }>(`/strategy/run-template?template_name=${encodeURIComponent(name)}&years=3`)
        if (data.result) next[name] = data.result
        else nextErrors[name] = data.message || '真实历史行情不可用'
      }
      setResults(next)
      setErrors(nextErrors)
      if (Object.keys(next).length) message.success(`已完成 ${Object.keys(next).length} 个策略模板回测`)
      if (Object.keys(nextErrors).length) message.warning(`${Object.keys(nextErrors).length} 个策略缺少真实历史行情`)
    } catch (e) {
      message.error((e as Error)?.message || '批量回测失败')
    } finally {
      setLoading(false)
    }
  }

  if (!names.length) return <Card size="small"><Spin /> 正在加载策略模板...</Card>

  const rows = names.map((name) => {
    const result = results[name]
    const error = errors[name]
    const note = STRATEGY_NOTES[name] || { desc: templates[name]?.description || '策略模板', suit: '按回测结果判断', risk: '需结合市场环境验证' }
    return { key: name, name, note, result, error }
  })

  return (
    <div>
      <Card
        size="small"
        title="策略胜率实测"
        extra={<Button size="small" type="primary" icon={<ExperimentOutlined />} loading={loading} onClick={runAll}>批量回测</Button>}
      >
        <Table
          rowKey="name"
          size="small"
          dataSource={rows}
          pagination={false}
          locale={{ emptyText: <Empty description="暂无策略模板" /> }}
          columns={[
            {
              title: '策略',
              dataIndex: 'name',
              width: 150,
              render: (name: string, row: AnyData) => (
                <div>
                  <b>{name}</b>
                  <div style={{ fontSize: 12, color: '#999', marginTop: 4 }}>{row.note.desc}</div>
                </div>
              ),
            },
            { title: '适用环境', width: 130, render: (_: AnyData, row: AnyData) => <Tag color="blue">{row.note.suit}</Tag> },
            {
              title: '胜率',
              width: 90,
              render: (_: AnyData, row: AnyData) => row.result ? `${safeNum(row.result.win_rate).toFixed(1)}%` : row.error ? <Tag color="orange">不可用</Tag> : '待回测',
              sorter: (a: AnyData, b: AnyData) => (a.result?.win_rate || 0) - (b.result?.win_rate || 0),
            },
            {
              title: '总收益',
              width: 90,
              render: (_: AnyData, row: AnyData) => row.result
                ? <span style={{ color: safeNum(row.result.total_return) >= 0 ? '#f5222d' : '#52c41a' }}>{safeNum(row.result.total_return).toFixed(2)}%</span>
                : '—',
              sorter: (a: AnyData, b: AnyData) => (a.result?.total_return || 0) - (b.result?.total_return || 0),
            },
            { title: '夏普', width: 80, render: (_: AnyData, row: AnyData) => row.result ? safeNum(row.result.sharpe_ratio).toFixed(2) : '—' },
            { title: '回撤', width: 80, render: (_: AnyData, row: AnyData) => row.result ? `${safeNum(row.result.max_drawdown).toFixed(2)}%` : '—' },
            { title: '交易数', width: 80, render: (_: AnyData, row: AnyData) => row.result?.total_trades ?? '—' },
            { title: '核心风险', render: (_: AnyData, row: AnyData) => <span style={{ color: row.error ? '#fa8c16' : '#666' }}>{row.error || row.note.risk}</span> },
            {
              title: '操作',
              width: 110,
              render: (_: AnyData, row: AnyData) => (
                <Button size="small" loading={running === row.name} onClick={() => runTemplate(row.name)}>
                  回测
                </Button>
              ),
            },
          ]}
        />
      </Card>
      <div style={{ marginTop: 12, color: '#fa8c16', fontSize: 12 }}>
        胜率、收益、回撤仅来自 /api/strategy/run-template 的真实历史行情回测；数据源不可用时显示不可用，不展示模拟胜率。
      </div>
    </div>
  )
}

export default function VerificationPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const rawTab = searchParams.get('tab') || 'overview'
  const tabAliases: Record<string, string> = {
    capital: 'longhu',
    history: 'similar',
    odds: 'strategy',
  }
  const tab = tabAliases[rawTab] || rawTab

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <h2 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
          <AimOutlined style={{ color: '#fa8c16' }} /> 验证中心
        </h2>
      </div>

      <RiskDashboard />

      <Tabs
        activeKey={tab}
        onChange={(k) => setSearchParams({ tab: k }, { replace: true })}
        type="card"
        items={[
          {
            key: 'overview',
            label: <span><WarningOutlined /> 炸板归因</span>,
            children: <Suspense fallback={fallback}><BrokenCasesPage /></Suspense>,
          },
          {
            key: 'broken',
            label: <span><WarningOutlined /> 炸板归因</span>,
            children: <Suspense fallback={fallback}><BrokenCasesPage /></Suspense>,
          },
          {
            key: 'longhu',
            label: <span><AuditOutlined /> 龙虎榜资金</span>,
            children: <Suspense fallback={fallback}><LonghuPage /></Suspense>,
          },
          {
            key: 'similar',
            label: <span><HistoryOutlined /> 历史相似日</span>,
            children: <Suspense fallback={fallback}><SentimentPageV2 /></Suspense>,
          },
          {
            key: 'strategy',
            label: <span><ExperimentOutlined /> 策略胜率</span>,
            children: <StrategyTemplatesTab />,
          },
          {
            key: 'cases',
            label: <span><WarningOutlined /> 案例库</span>,
            children: <Suspense fallback={fallback}><BrokenCasesPage /></Suspense>,
          },
        ].filter((item) => {
          if (item.key === 'overview' && tab !== 'overview') return false
          if (item.key === 'broken' && tab === 'overview') return false
          return true
        })}
      />
      <AIDisclaimer variant="inline" />
    </div>
  )
}
