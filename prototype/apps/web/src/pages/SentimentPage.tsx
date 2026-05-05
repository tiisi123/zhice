import { useEffect, useRef, useState } from 'react'
import { Card, Col, Row, Spin, Statistic, Empty, Select, Button, Space, Progress } from 'antd'
import { RobotOutlined, ArrowUpOutlined, WarningOutlined, ExperimentOutlined } from '@ant-design/icons'
import * as echarts from 'echarts'
import { fetchApi } from '../api/client'
import { askAI } from '../api/copilot'
import type { AnyData } from '../api/types'

interface SentimentRecord {
  date: string; limit_up: number; broken: number; broken_rate: number
  max_board: number; sentiment: string; score: number; up: number; down: number
}
interface PhaseResp { phase: string; confidence: number; slope: number; basis: string; recent: SentimentRecord[] }

const SENT_THEME: Record<string, { bg: string; text: string; emoji: string }> = {
  '冰点': { bg: 'linear-gradient(135deg,#1e3a8a,#3b82f6)', text: '#fff', emoji: '🧊' },
  '低迷': { bg: 'linear-gradient(135deg,#1e40af,#60a5fa)', text: '#fff', emoji: '🌧️' },
  '中性': { bg: 'linear-gradient(135deg,#525252,#a3a3a3)', text: '#fff', emoji: '⚖️' },
  '回暖': { bg: 'linear-gradient(135deg,#c2410c,#fb923c)', text: '#fff', emoji: '🔥' },
  '高潮': { bg: 'linear-gradient(135deg,#991b1b,#ef4444)', text: '#fff', emoji: '🚀' },
}

const POSITION_ADVICE: Record<string, { pos: string; desc: string; strategy: string; color: string }> = {
  '冰点': { pos: '空仓观望', desc: '市场极度低迷，等待企稳信号', strategy: '等待放量信号，不抄底', color: '#1e3a8a' },
  '低迷': { pos: '轻仓试探', desc: '可小仓位参与超跌反弹', strategy: '关注首板股质量，试探性参与', color: '#3b82f6' },
  '中性': { pos: '半仓运作', desc: '跟随主线，控制回撤', strategy: '跟随主线龙头，回避无量弱势品种', color: '#666' },
  '回暖': { pos: '重仓出击', desc: '情绪升温，积极参与龙头', strategy: '积极追板，关注2板确认品种', color: '#fa8c16' },
  '高潮': { pos: '止盈减仓', desc: '高位分歧加大，注意获利了结', strategy: '逢高减仓，不追高位股，警惕核按钮', color: '#f5222d' },
}

function TemperatureCard({ latest, phase }: { latest: SentimentRecord | null; phase: PhaseResp | null }) {
  if (!latest) return <Card loading />
  const theme = SENT_THEME[latest.sentiment] || SENT_THEME['中性']
  const advice = POSITION_ADVICE[latest.sentiment] || POSITION_ADVICE['中性']

  return (
    <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
      <Col xs={24} md={8}>
        <div style={{ background: theme.bg, color: theme.text, borderRadius: 12, padding: 20, minHeight: 200 }}>
          <div style={{ fontSize: 13, opacity: 0.8 }}>当前市场情绪</div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginTop: 6 }}>
            <span style={{ fontSize: 52, fontWeight: 800, lineHeight: 1 }}>{theme.emoji}</span>
            <span style={{ fontSize: 34, fontWeight: 700 }}>{latest.sentiment}</span>
          </div>
          {phase && (
            <div style={{ marginTop: 10, fontSize: 13, opacity: 0.9 }}>
              周期相位：<b>{phase.phase}</b>
              <span style={{ marginLeft: 8 }}>趋势：{phase.slope > 0 ? '↑ 升温' : phase.slope < 0 ? '↓ 降温' : '→ 横盘'}</span>
            </div>
          )}
          <div style={{ marginTop: 12, fontSize: 13, opacity: 0.9, lineHeight: 1.7 }}>
            涨停 <b>{latest.limit_up}</b> · 炸板 <b>{latest.broken}</b> · 最高 <b>{latest.max_board}板</b>
          </div>
          <Button
            ghost block style={{ marginTop: 14, borderColor: 'rgba(255,255,255,0.4)' }}
            icon={<RobotOutlined />}
            onClick={() => askAI(`当前市场情绪【${latest.sentiment}】，周期相位【${phase?.phase || '未知'}】，涨停${latest.limit_up}家，最高${latest.max_board}板，炸板率${latest.broken_rate}%。分析后3个交易日情绪演化概率，并给出仓位建议。`)}
          >
            AI 预判后市
          </Button>
        </div>
      </Col>
      <Col xs={24} md={8}>
        <Row gutter={[12, 12]}>
          <Col span={12}>
            <Card size="small"><Statistic title="涨停" value={latest.limit_up} valueStyle={{ color: '#f5222d' }} prefix={<ArrowUpOutlined />} /></Card>
          </Col>
          <Col span={12}>
            <Card size="small"><Statistic title="炸板" value={latest.broken} valueStyle={{ color: '#fa8c16' }} prefix={<WarningOutlined />} /></Card>
          </Col>
          <Col span={12}>
            <Card size="small">
              <Statistic title="炸板率" value={latest.broken_rate} precision={1} suffix="%" valueStyle={{ color: latest.broken_rate > 30 ? '#f5222d' : '#52c41a' }} />
            </Card>
          </Col>
          <Col span={12}>
            <Card size="small">
              <Statistic title="最高板" value={latest.max_board} suffix="板" valueStyle={{ color: latest.max_board >= 5 ? '#f5222d' : '#262626' }} />
            </Card>
          </Col>
          {phase && (
            <Col span={24}>
              <Card size="small">
                <div style={{ fontSize: 12, color: '#666', marginBottom: 4 }}>置信度</div>
                <Progress percent={Math.round(phase.confidence * 100)} status={phase.confidence > 0.7 ? 'success' : 'normal'} size="small" />
              </Card>
            </Col>
          )}
        </Row>
      </Col>
      <Col xs={24} md={8}>
        <Card size="small" style={{ borderLeft: `4px solid ${advice.color}`, minHeight: 200 }}>
          <div style={{ fontSize: 15, fontWeight: 700, color: advice.color, marginBottom: 8 }}>
            <ExperimentOutlined /> 仓位建议：{advice.pos}
          </div>
          <div style={{ fontSize: 13, color: '#666', lineHeight: 1.8, marginBottom: 8 }}>{advice.desc}</div>
          <div style={{ fontSize: 12, color: '#999', lineHeight: 1.6 }}>策略：{advice.strategy}</div>
        </Card>
      </Col>
    </Row>
  )
}

function SentimentChart({ data }: { data: SentimentRecord[] }) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!ref.current || data.length === 0) return
    const chart = echarts.init(ref.current)
    const dates = data.map(d => d.date.slice(5))

    chart.setOption({
      tooltip: {
        trigger: 'axis',
        formatter: (ps: AnyData) => {
          const i = ps[0]?.dataIndex; const d = data[i]
          if (!d) return ''
          return `<b>${d.date}</b><br/>情绪：${d.sentiment}<br/>涨停：${d.limit_up}<br/>炸板：${d.broken}（${d.broken_rate}%）<br/>最高板：${d.max_board}`
        },
      },
      legend: { data: ['涨停', '炸板', '炸板率', '最高板'], bottom: 0, textStyle: { fontSize: 11 } },
      grid: { left: 45, right: 45, top: 20, bottom: 40 },
      xAxis: { type: 'category', data: dates, axisLabel: { fontSize: 10 } },
      yAxis: [
        { type: 'value', name: '家数', axisLabel: { fontSize: 10 }, splitLine: { lineStyle: { type: 'dashed' } } },
        { type: 'value', name: '比率%', max: 60, axisLabel: { fontSize: 10 }, splitLine: { show: false } },
      ],
      series: [
        { name: '涨停', type: 'bar', data: data.map(d => d.limit_up), itemStyle: { color: 'rgba(245,34,45,0.6)' }, barWidth: '35%' },
        { name: '炸板', type: 'bar', data: data.map(d => d.broken), itemStyle: { color: 'rgba(250,173,20,0.6)' }, barWidth: '35%' },
        { name: '炸板率', type: 'line', yAxisIndex: 1, smooth: true, showSymbol: false, data: data.map(d => d.broken_rate), lineStyle: { color: '#722ed1', width: 2 }, itemStyle: { color: '#722ed1' } },
        { name: '最高板', type: 'line', smooth: true, showSymbol: false, data: data.map(d => d.max_board), lineStyle: { color: '#13c2c2', width: 2 }, itemStyle: { color: '#13c2c2' } },
      ],
    })
    const onResize = () => chart.resize()
    window.addEventListener('resize', onResize)
    return () => { window.removeEventListener('resize', onResize); chart.dispose() }
  }, [data])

  if (data.length === 0) return <Empty description="暂无情绪数据" />
  return <div ref={ref} style={{ width: '100%', height: 380 }} />
}

export default function SentimentPage() {
  const [data, setData] = useState<SentimentRecord[]>([])
  const [phase, setPhase] = useState<PhaseResp | null>(null)
  const [loading, setLoading] = useState(true)
  const [days, setDays] = useState(30)

  useEffect(() => {
    void (async () => {
      setLoading(true)
      Promise.all([
        fetchApi<{ data: SentimentRecord[] }>(`/market/sentiment-history?days=${days}`),
        fetchApi<PhaseResp>('/market/sentiment-phase').catch(() => null),
      ])
        .then(([hist, ph]) => { setData(hist.data || []); setPhase(ph) })
        .catch(() => setData([]))
        .finally(() => setLoading(false))
    })()
  }, [days])

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '120px auto' }} />

  const latest = data.length > 0 ? data[data.length - 1] : null

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
        <h2 style={{ margin: 0 }}>情绪周期</h2>
        <Select value={days} onChange={setDays} size="small" style={{ width: 100 }}
          options={[{ value: 10, label: '近10天' }, { value: 30, label: '近30天' }, { value: 60, label: '近60天' }, { value: 120, label: '近120天' }]}
        />
      </div>

      <TemperatureCard latest={latest} phase={phase} />

      <Card size="small" title="情绪走势" style={{ marginBottom: 16 }} bodyStyle={{ padding: 12 }}>
        <SentimentChart data={data} />
      </Card>

      <Card size="small" title={<span><RobotOutlined style={{ color: '#1677ff' }} /> 向 AI 追问</span>}>
        <Space wrap>
          <Button type="primary" icon={<RobotOutlined />}
            onClick={() => askAI(`基于近${days}天的情绪数据（当前${latest?.sentiment}，涨停趋势${phase?.slope && phase.slope > 0 ? '上升' : '下降'}），分析情绪周期所处阶段，预判未来3个交易日走势。`)}
          >
            周期阶段分析
          </Button>
          <Button onClick={() => askAI(`当前炸板率${latest?.broken_rate}%，这个水平在历史上意味着什么？是否有系统性风险信号？`)}>
            炸板率解读
          </Button>
          <Button onClick={() => askAI(`历史上情绪从【${latest?.sentiment}】阶段转换到下一个阶段，通常需要几天？有什么前兆信号？`)}>
            阶段转换信号
          </Button>
        </Space>
      </Card>

      <div style={{ marginTop: 12, color: '#999', fontSize: 11, textAlign: 'center' }}>
        以上分析仅供参考，不构成投资建议。
      </div>
    </div>
  )
}
