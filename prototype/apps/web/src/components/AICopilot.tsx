import { useEffect, useState } from 'react'
import { Drawer, Button, Input, Spin, Tabs, Card, Tag, message, Alert } from 'antd'
import { RobotOutlined, SendOutlined, SaveOutlined, BulbOutlined, ClearOutlined, CopyOutlined } from '@ant-design/icons'
import Markdown from 'react-markdown'
import { fetchApi, postApi } from '../api/client'
import Disclaimer from './Disclaimer'
import AIBadge from './AIBadge'
import type { AnyData } from '../api/types'

const { TextArea } = Input

const PAGE_HINTS: Record<string, { label: string; prompts: string[]; apis: string[]; scope: string }> = {
  '/replay': {
    label: '收盘复盘',
    prompts: ['今日市场主线是什么？', '龙头股有哪些？', '明天应该关注什么方向？'],
    apis: [
      'GET /api/market/summary',
      'GET /api/market/ladder',
      'GET /api/market/sectors',
      'GET /api/market/capital-flow',
      'GET /api/market/next-day-strategy',
    ],
    scope: '当前复盘页 + 全局短线核心数据，可回答跨题材、梯队、情绪、资金和次日计划问题。',
  },
  '/intraday': {
    label: '盘中盯盘',
    prompts: ['当前涨停板有什么特征？', '哪些板块最活跃？', '炸板率是否偏高？'],
    apis: ['GET /api/intraday/*', 'GET /api/market/sectors', 'GET /api/market/summary'],
    scope: '盘中页面上下文 + 全局短线核心数据。',
  },
  '/theme': {
    label: '题材板块',
    prompts: ['哪个题材最强？', '主线题材处于什么阶段？', '有没有新出现的题材？'],
    apis: ['GET /api/theme/*', 'GET /api/market/sectors', 'GET /api/ai/theme-analysis/{theme_name}'],
    scope: '题材页上下文 + 全局短线核心数据；可追问题材阶段、驱动和梯队。',
  },
  '/sentiment': {
    label: '情绪周期',
    prompts: ['当前市场情绪处于什么阶段？', '情绪指标有哪些变化？', '短线操作建议？'],
    apis: ['GET /api/market/summary', 'GET /api/market/sentiment-history', 'GET /api/market/sentiment-phase'],
    scope: '情绪页上下文 + 涨跌停/炸板/历史情绪数据。',
  },
  '/strategy': {
    label: '策略回测',
    prompts: ['帮我设计一个打板策略', '首阴低吸策略怎么设计？', '如何优化止盈止损参数？'],
    apis: ['POST /api/strategy/*', 'POST /api/backtest/*'],
    scope: '策略与回测上下文；跨市场问题会补充全局短线核心数据。',
  },
  '/stock': {
    label: '个股分析',
    prompts: ['这只股票涨停原因是什么？', '同题材还有哪些股？', '明天溢价预期如何？'],
    apis: ['GET /api/stock/*', 'GET /api/ai/stock-insight/{code}', 'GET /api/market/sectors'],
    scope: '个股页上下文；可联动题材、涨停池和全局市场。',
  },
  '/etf-rotation': {
    label: 'ETF轮动',
    prompts: ['当前哪个ETF处于启动阶段？', '资金在往哪个方向流？', '轮动信号怎么解读？'],
    apis: ['GET /api/etf/rotation/dashboard', 'POST /api/ai/agent/etf-rotation'],
    scope: 'ETF 轮动上下文；跨短线问题会补充全局市场数据。',
  },
  '/broken-cases': {
    label: '炸板案例库',
    prompts: ['今日炸板主要原因是什么？', '哪类炸板原因最多？', '炸板率高说明什么？'],
    apis: ['GET /api/analysis/broken-cases', 'GET /api/market/summary'],
    scope: '炸板案例上下文 + 市场风险数据。',
  },
  '/growth': {
    label: '景气度分析',
    prompts: ['哪些行业景气度在上升？', '宏观数据对市场有什么影响？', 'PMI数据怎么解读？'],
    apis: ['GET /api/growth/*'],
    scope: '成长景气页面上下文；跨板块问题会补充短线核心数据。',
  },
  '/value': {
    label: '价值/持仓',
    prompts: ['持仓股估值是否合理？', '哪些持仓股ROE最高？', '分红率最高的是哪只？'],
    apis: ['GET /api/value/*', 'GET /api/finance/*'],
    scope: '价值/持仓上下文；跨板块问题会补充短线核心数据。',
  },
  '/valuation': {
    label: '估值分析',
    prompts: ['这只股票PE处于什么分位？', 'DCF估值和市价差多少？', '机构预期是否一致？'],
    apis: ['GET /api/value/*', 'GET /api/finance/*'],
    scope: '估值页面上下文；跨板块问题会补充短线核心数据。',
  },
  '/chain': {
    label: '产业链图谱',
    prompts: ['这条产业链的传导逻辑是什么？', '上游涨价对下游有什么影响？', '哪个环节景气度最高？'],
    apis: ['GET /api/chain/*', 'GET /api/market/sectors'],
    scope: '产业链页面上下文；可联动 KPL 概念题材。',
  },
  '/advanced-strategy': {
    label: '高级策略',
    prompts: ['参数优化结果怎么看？', '最优止盈止损是多少？', '模拟交易怎么操作？'],
    apis: ['POST /api/advanced-strategy/*', 'POST /api/backtest/*'],
    scope: '高级策略上下文；跨市场问题会补充全局短线核心数据。',
  },
  '/report-archive': {
    label: '报告存档',
    prompts: ['最近的复盘报告说了什么？', '市场情绪趋势如何？', '历史报告有什么规律？'],
    apis: ['GET /api/analysis/reports', 'GET /api/market/archive'],
    scope: '报告存档上下文；可结合全局短线数据追问。',
  },
}

interface CopilotProps {
  open: boolean
  onClose: () => void
  currentPage?: string
}

export default function AICopilot({ open, onClose, currentPage = '' }: CopilotProps) {
  const [activeTab, setActiveTab] = useState('report')
  const [report, setReport] = useState<string | null>(null)
  const [reportSummary, setReportSummary] = useState<AnyData>(null)
  const [chatInput, setChatInput] = useState('')
  const [chatMessages, setChatMessages] = useState<Array<{ role: string; content: string; sources?: string[]; evidence?: AnyData }>>([])
  const [loading, setLoading] = useState(false)

  const pageHint = PAGE_HINTS[currentPage] || PAGE_HINTS[Object.keys(PAGE_HINTS).find(k => currentPage.startsWith(k)) || ''] || null

  // 监听全局 askAI 事件：自动切到对话 Tab 并填充提示词
  useEffect(() => {
    const handler = (e: Event) => {
      const prompt = (e as CustomEvent).detail?.prompt
      if (typeof prompt === 'string' && prompt.trim()) {
        setActiveTab('chat')
        setChatInput(prompt)
      }
    }
    window.addEventListener('zhice:ai-ask', handler)
    return () => window.removeEventListener('zhice:ai-ask', handler)
  }, [])

  const generateReport = async () => {
    setLoading(true)
    try {
      const res = await fetchApi<{ report: string; summary: AnyData; trade_date: string }>('/ai/replay-report')
      setReport(res.report)
      setReportSummary(res.summary)
    } catch {
      setReport('报告生成失败，请检查后端服务。')
    }
    setLoading(false)
  }

  const saveReport = async () => {
    if (!report || !reportSummary) {
      message.warning('请先生成报告')
      return
    }
    try {
      await postApi('/analysis/save-report', {
        trade_date: reportSummary.trade_date || new Date().toISOString().slice(0, 10),
        report,
        sentiment: reportSummary.sentiment_level || '',
        limit_up: reportSummary.limit_up_count || 0,
        broken: reportSummary.broken_count || 0,
      })
      message.success('报告已保存到存档')
    } catch {
      message.error('保存报告失败')
    }
  }

  const sendChat = async (text?: string) => {
    const msg = (text || chatInput).trim()
    if (!msg) return
    setChatMessages(prev => [...prev, { role: 'user', content: msg }])
    setChatInput('')
    setLoading(true)
    try {
      const contextPrefix = pageHint ? `[当前页面: ${pageHint.label}] ` : ''
      const data = await postApi<{ response: string; context_sources?: string[]; evidence?: AnyData; data_status?: string; status_message?: string }>('/ai/chat', {
        message: contextPrefix + msg,
        history: chatMessages.slice(-6),
        current_page: currentPage,
        trade_date: reportSummary?.trade_date || new Date().toISOString().slice(0, 10),
      })
      const content = data.data_status === 'unavailable' && data.status_message
        ? data.status_message
        : data.response || '无回复'
      setChatMessages(prev => [...prev, { role: 'ai', content, sources: data.context_sources || [], evidence: data.evidence }])
    } catch {
      setChatMessages(prev => [...prev, { role: 'ai', content: '请求失败，请检查后端服务。' }])
    }
    setLoading(false)
  }

  const tabs = [
    {
      key: 'report',
      label: '复盘报告',
      children: (
        <div>
          <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
            <Button type="primary" onClick={generateReport} loading={loading} icon={<RobotOutlined />} style={{ flex: 1 }}>
              生成今日复盘报告
            </Button>
            {report && <Button onClick={saveReport} icon={<SaveOutlined />}>保存</Button>}
            {report && <Button onClick={() => { void navigator.clipboard.writeText(report); message.success('已复制到剪贴板') }} icon={<CopyOutlined />}>复制</Button>}
          </div>
          {report && (
            <Button
              block
              style={{ marginBottom: 12 }}
              onClick={() => {
                setActiveTab('chat')
                setChatInput('基于刚才这份复盘报告，继续分析主线题材的延续性和明日风险点。')
              }}
            >
              继续追问这份报告
            </Button>
          )}
          {report && (
            <Card size="small" style={{ maxHeight: 500, overflow: 'auto' }}>
              <div style={{ fontSize: 13, lineHeight: 1.8 }}><Markdown>{report}</Markdown></div>
            </Card>
          )}
        </div>
      ),
    },
    {
      key: 'chat',
      label: '智能问答',
      children: (
        <div>
          {pageHint && (
            <Alert
              type="info"
              showIcon
              style={{ marginBottom: 12 }}
              message={`上下文：${pageHint.label}`}
              description={
                <div style={{ fontSize: 12, lineHeight: 1.7 }}>
                  <div>{pageHint.scope}</div>
                  <div>本页接口：{pageHint.apis.join('、')}</div>
                  <div>每次回答会带最近 6 轮对话；跨板块问题会补全市场总览、涨停/炸板、主线题材等全局数据。</div>
                </div>
              }
            />
          )}
          {pageHint && chatMessages.length === 0 && (
            <Card size="small" style={{ marginBottom: 12, background: '#f6f8fa' }}>
              <div style={{ fontSize: 12, color: '#666', marginBottom: 8 }}>
                <BulbOutlined /> 当前在「{pageHint.label}」页面，你可以问：
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {pageHint.prompts.map((p, i) => (
                  <Tag
                    key={i}
                    color="blue"
                    style={{ cursor: 'pointer' }}
                    onClick={() => { setActiveTab('chat'); void sendChat(p) }}
                  >
                    {p}
                  </Tag>
                ))}
              </div>
            </Card>
          )}
          {chatMessages.length > 0 && (
            <div style={{ textAlign: 'right', marginBottom: 8 }}>
              <Button size="small" icon={<ClearOutlined />} onClick={() => setChatMessages([])}>清空对话</Button>
            </div>
          )}
          <div style={{ maxHeight: 400, overflow: 'auto', marginBottom: 12 }}>
            {chatMessages.map((m, i) => (
              <div key={i} style={{ marginBottom: 8, textAlign: m.role === 'user' ? 'right' : 'left' }}>
                <Tag color={m.role === 'user' ? 'blue' : 'green'}>{m.role === 'user' ? '你' : 'AI'}</Tag>
                <div style={{
                  display: 'inline-block', maxWidth: '80%', padding: '8px 12px',
                  background: m.role === 'user' ? '#e6f7ff' : '#f6ffed', borderRadius: 8,
                  fontSize: 13, textAlign: 'left',
                }}>
                  {m.role === 'user' ? m.content : <Markdown>{m.content}</Markdown>}
                </div>
                {m.role !== 'user' && m.sources && m.sources.length > 0 && (
                  <div style={{ marginTop: 4, fontSize: 11, color: '#999' }}>
                    数据上下文：{m.sources.join('、')}
                  </div>
                )}
                {m.role !== 'user' && m.evidence?.theme_stocks && (
                  <div style={{ marginTop: 4, fontSize: 11, color: '#999' }}>
                    题材明细：{m.evidence.theme_stocks.theme} · 涨停 {m.evidence.theme_stocks.limit_up_count} 只 · 炸板 {m.evidence.theme_stocks.broken_count} 只
                  </div>
                )}
              </div>
            ))}
            {loading && <Spin size="small" />}
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <TextArea
              value={chatInput}
              onChange={e => setChatInput(e.target.value)}
              onPressEnter={e => { if (!e.shiftKey) { e.preventDefault(); void sendChat() } }}
              placeholder="问我任何关于市场的问题..."
              autoSize={{ minRows: 1, maxRows: 3 }}
              style={{ flex: 1 }}
            />
            <Button type="primary" icon={<SendOutlined />} onClick={() => sendChat()} loading={loading} />
          </div>
          <div style={{ marginTop: 8, color: '#faad14', fontSize: 11 }}>
            以上分析仅供参考，不构成投资建议。
          </div>
        </div>
      ),
    },
  ]

  return (
    <Drawer
      title={<span><RobotOutlined /> 智策 AI Copilot</span>}
      placement="right"
      width={420}
      open={open}
      onClose={onClose}
    >
      <AIBadge style={{ marginBottom: 8 }} />
      <Disclaimer kind="ai" style={{ marginBottom: 8 }} />
      <Tabs activeKey={activeTab} onChange={setActiveTab} items={tabs} />
    </Drawer>
  )
}
