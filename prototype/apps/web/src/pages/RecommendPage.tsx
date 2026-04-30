import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Card, Tag, Space, List, Button, Typography, Alert, Descriptions, Modal, Spin, Progress } from 'antd'
import { BulbOutlined, ExperimentOutlined, RobotOutlined, FireOutlined, SafetyOutlined } from '@ant-design/icons'
import Markdown from 'react-markdown'
import { fetchApi } from '../api/client'
import Disclaimer from '../components/Disclaimer'

const { Title } = Typography

const STYLE_LABEL: Record<string, string> = {
  short: '短线/打板',
  hot: '热点/轮动',
  growth: '成长/景气',
  value: '价值/基本面',
}

interface Rec {
  id: string
  name: string
  style: string
  tags: string[]
  score: number
  market_score: number
  affinity: number
  risk_level: '保守' | '平衡' | '进取'
  reasons: string[]
  dsl: Record<string, any>
}

interface RecommendResp {
  primary_style: string
  secondary_style?: string
  style_combo?: string[]
  risk_preference: '保守' | '平衡' | '进取'
  market_sentiment: string
  market_summary: { limit_up_count: number; max_board: number; broken_rate: number }
  behavior_votes: Record<string, number>
  recommendations: Rec[]
}

const SENTIMENT_COLOR: Record<string, string> = {
  '高潮': 'red', '回暖': 'orange', '中性': 'blue', '低迷': 'cyan', '冰点': 'default',
}

const RISK_COLOR: Record<string, string> = {
  '保守': 'green', '平衡': 'blue', '进取': 'red',
}

export default function RecommendPage() {
  const navigate = useNavigate()
  const [data, setData] = useState<RecommendResp | null>(null)
  const [loading, setLoading] = useState(false)
  const [explainOpen, setExplainOpen] = useState(false)
  const [explainText, setExplainText] = useState('')
  const [explainLoading, setExplainLoading] = useState(false)
  const [explainName, setExplainName] = useState('')

  useEffect(() => {
    setLoading(true)
    fetchApi<RecommendResp>('/recommend/strategies').then(setData).finally(() => setLoading(false))
  }, [])

  const openExplain = async (r: Rec) => {
    setExplainOpen(true)
    setExplainName(r.name)
    setExplainText('')
    setExplainLoading(true)
    try {
      const resp = await fetchApi<{ explanation: string }>(`/recommend/explain/${r.id}`)
      setExplainText(resp.explanation || '')
    } catch (e: any) {
      setExplainText(`AI 解读失败：${e?.message || '未知错误'}`)
    } finally {
      setExplainLoading(false)
    }
  }

  if (!data) return <Card loading={loading} />

  const m = data.market_summary || { limit_up_count: 0, max_board: 0, broken_rate: 0 }
  const totalBehavior = (Object.values(data.behavior_votes || {}) as number[]).reduce((a, b) => a + (b || 0), 0)

  return (
    <div>
      <Title level={3}><BulbOutlined /> AI 策略推荐 · M3-04</Title>
      <Disclaimer kind="recommend" />

      {/* 用户画像 + 市场情绪 */}
      <Alert
        type="info"
        style={{ marginBottom: 12 }}
        message={
          <Space size="large" wrap>
            <span>主风格：<Tag color="blue">{STYLE_LABEL[data.primary_style] || data.primary_style}</Tag></span>
            {data.secondary_style && <span>副风格：<Tag>{STYLE_LABEL[data.secondary_style]}</Tag></span>}
            {data.style_combo && data.style_combo.length > 1 && (
              <span>组合：{data.style_combo.map(s => <Tag key={s}>{STYLE_LABEL[s] || s}</Tag>)}</span>
            )}
            <span>风险偏好：<Tag color={RISK_COLOR[data.risk_preference]} icon={<SafetyOutlined />}>{data.risk_preference}</Tag></span>
            <span>当下市场：<Tag color={SENTIMENT_COLOR[data.market_sentiment]} icon={<FireOutlined />}>{data.market_sentiment}</Tag></span>
            <span style={{ color: '#666', fontSize: 12 }}>
              涨停 {m.limit_up_count} · 最高 {m.max_board} 板 · 炸板率 {m.broken_rate?.toFixed?.(1)}%
            </span>
            <span style={{ color: '#999', fontSize: 12 }}>行为 {totalBehavior} 次</span>
          </Space>
        }
        description="综合分 = 主风格×1.0 + 副风格×0.4 + 市场情绪适配×0.6 + 风险偏好×0.3。点击「AI 解读」查看实时解读。"
      />

      <List
        dataSource={data.recommendations}
        renderItem={(r, idx) => (
          <Card
            key={r.id}
            style={{ marginBottom: 12 }}
            title={
              <Space wrap>
                <b style={{ fontSize: 16 }}>#{idx + 1}</b>
                <span style={{ fontWeight: 600 }}>{r.name}</span>
                <Tag color="purple">{STYLE_LABEL[r.style] || r.style}</Tag>
                <Tag color={RISK_COLOR[r.risk_level] || 'default'}>{r.risk_level}</Tag>
                {r.tags.map((t) => <Tag key={t}>{t}</Tag>)}
              </Space>
            }
            extra={
              <Space>
                <span style={{ fontSize: 12, color: '#999' }}>市场亲和</span>
                <Progress type="circle" size={36} percent={Math.round((r.affinity || 0) * 100)}
                  strokeColor={r.affinity >= 0.85 ? '#f5222d' : r.affinity >= 0.6 ? '#fa8c16' : '#bfbfbf'} />
                <Tag color={r.score >= 1.5 ? 'red' : r.score >= 1.0 ? 'orange' : 'default'} style={{ fontSize: 14, padding: '4px 10px' }}>
                  匹配 {r.score.toFixed(2)}
                </Tag>
              </Space>
            }
          >
            {/* 推荐理由列表 */}
            <div style={{ marginBottom: 12 }}>
              {r.reasons.map((reason, i) => (
                <div key={i} style={{ fontSize: 13, lineHeight: 1.8, color: reason.startsWith('⚠️') ? '#cf1322' : reason.startsWith('🔥') ? '#fa541c' : '#555' }}>
                  {reason}
                </div>
              ))}
            </div>
            <Descriptions size="small" column={1} bordered>
              {Object.entries(r.dsl).map(([k, v]) => (
                <Descriptions.Item label={k} key={k}>
                  <code style={{ fontSize: 12 }}>{JSON.stringify(v, null, 0)}</code>
                </Descriptions.Item>
              ))}
            </Descriptions>
            <Space style={{ marginTop: 12 }} wrap>
              <Button type="primary" icon={<ExperimentOutlined />}
                onClick={() => navigate('/strategy', { state: { dsl: r.dsl, name: r.name } })}>
                去回测
              </Button>
              <Button icon={<RobotOutlined />} onClick={() => openExplain(r)}>
                AI 解读：为什么现在适合？
              </Button>
            </Space>
          </Card>
        )}
      />

      {/* AI 解读 Modal */}
      <Modal
        title={<span><RobotOutlined style={{ color: '#1677ff' }} /> AI 推荐理由 · {explainName}</span>}
        open={explainOpen}
        onCancel={() => setExplainOpen(false)}
        footer={null}
        width={680}
      >
        {explainLoading ? (
          <div style={{ textAlign: 'center', padding: 40 }}><Spin tip="AI 正在生成..." /></div>
        ) : (
          <div style={{ fontSize: 13, lineHeight: 1.8, maxHeight: 480, overflow: 'auto' }}>
            <Markdown>{explainText || '*暂无解读*'}</Markdown>
          </div>
        )}
        <div style={{ marginTop: 12, fontSize: 11, color: '#999', textAlign: 'center' }}>
          AI 生成内容仅供参考，不构成投资建议。结果缓存 5 分钟。
        </div>
      </Modal>
    </div>
  )
}
