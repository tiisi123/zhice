import { useEffect, useRef, useState } from 'react'
import {
  Card, Tag, Space, Button, Empty, Spin, Switch, message,
  Input, Modal, Row, Col, Divider,
} from 'antd'
import { ThunderboltOutlined, RobotOutlined, ReloadOutlined, FireOutlined } from '@ant-design/icons'
import { Link } from 'react-router-dom'
import Markdown from 'react-markdown'
import { fetchApi, postApi } from '../api/client'
import { askAI } from '../api/copilot'
import AIDisclaimer from '../components/AIDisclaimer'

const { TextArea } = Input

interface NewsItem {
  id: string
  title: string
  summary: string
  publish_time: string
  source: string
  url: string
  is_red: boolean
  matched_themes: string[]
  matched_stocks?: { code: string; name: string }[]
  stocks: { code: string; name: string }[]
}

const REFRESH_MS = 60_000

export default function HotEventsPage() {
  const [items, setItems] = useState<NewsItem[]>([])
  const [loading, setLoading] = useState(false)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [importantOnly, setImportantOnly] = useState(false)
  const [aiText, setAiText] = useState('')
  const [aiLoading, setAiLoading] = useState(false)
  const [aiNews, setAiNews] = useState<NewsItem | null>(null)
  const [showAi, setShowAi] = useState(false)
  const [customText, setCustomText] = useState('')
  const timer = useRef<number | null>(null)

  const load = (silent = false) => {
    if (!silent) setLoading(true)
    fetchApi<{ items: NewsItem[] }>(
      `/news/timeline?n=80&important_only=${importantOnly}`,
    )
      .then(r => setItems(r.items || []))
      .catch(() => !silent && message.error('加载快讯失败'))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [importantOnly]) // eslint-disable-line

  useEffect(() => {
    if (timer.current) window.clearInterval(timer.current)
    if (autoRefresh) {
      timer.current = window.setInterval(() => load(true), REFRESH_MS)
    }
    return () => { if (timer.current) window.clearInterval(timer.current) }
  }, [autoRefresh, importantOnly]) // eslint-disable-line

  const linkThemes = async (text: string, news?: NewsItem) => {
    if (text.length < 10) { message.warning('文本太短'); return }
    setAiNews(news || null)
    setAiText('')
    setShowAi(true)
    setAiLoading(true)
    try {
      const r = await postApi<{ analysis: string }>('/news/link-themes', { text })
      setAiText(r.analysis || '')
    } catch (e) {
      message.error((e as Error)?.message || 'AI 分析失败')
    } finally {
      setAiLoading(false)
    }
  }

  const groupByDate = (arr: NewsItem[]) => {
    const map: Record<string, NewsItem[]> = {}
    for (const n of arr) {
      const d = (n.publish_time || '').slice(0, 10) || '其他'
      if (!map[d]) map[d] = []
      map[d].push(n)
    }
    return Object.entries(map).sort(([a], [b]) => b.localeCompare(a))
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
        <h2 style={{ margin: 0 }}>
          <ThunderboltOutlined style={{ color: '#fa541c' }} /> 热点事件时间线（M2-04）
        </h2>
        <Tag color="blue">{items.length} 条</Tag>
        <Space>
          <span>自动刷新</span>
          <Switch checked={autoRefresh} onChange={setAutoRefresh} size="small" />
          <span>仅重要</span>
          <Switch checked={importantOnly} onChange={setImportantOnly} size="small" />
          <Button icon={<ReloadOutlined />} onClick={() => load()}>刷新</Button>
        </Space>
      </div>

      <Row gutter={16}>
        <Col xs={24} lg={16}>
          {loading && items.length === 0 ? (
            <div style={{ textAlign: 'center', padding: 60 }}><Spin size="large" /></div>
          ) : items.length === 0 ? (
            <Card><Empty description="暂无快讯" /></Card>
          ) : (
            groupByDate(items).map(([date, list]) => (
              <Card key={date} size="small" title={<span style={{ fontSize: 13 }}>📅 {date}</span>} style={{ marginBottom: 12 }}>
                {list.map(n => (
                  <div key={n.id} style={{
                    padding: '10px 0', borderBottom: '1px dashed #f0f0f0',
                    display: 'flex', gap: 12, alignItems: 'flex-start',
                  }}>
                    <div style={{ width: 60, color: '#999', fontSize: 12, flexShrink: 0 }}>
                      {(n.publish_time || '').slice(11, 16)}
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 14, lineHeight: 1.6, fontWeight: n.is_red ? 600 : 400 }}>
                        {n.is_red && <Tag color="red" style={{ marginRight: 6 }}>重要</Tag>}
                        {n.url ? (
                          <a href={n.url} target="_blank" rel="noreferrer" style={{ color: n.is_red ? '#cf1322' : 'inherit' }}>
                            {n.title}
                          </a>
                        ) : n.title}
                      </div>
                      {n.summary && n.summary !== n.title && (
                        <div style={{ fontSize: 12, color: '#666', marginTop: 4, lineHeight: 1.6 }}>{n.summary}</div>
                      )}
                      <div style={{ marginTop: 6, display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
                        {n.matched_themes?.map(t => (
                          <Link key={t} to={`/theme?name=${encodeURIComponent(t)}`}>
                            <Tag color="orange" style={{ cursor: 'pointer' }}>
                              <FireOutlined /> {t}
                            </Tag>
                          </Link>
                        ))}
                        {(n.stocks || n.matched_stocks || []).slice(0, 5).map(s => s.code && (
                          <Link key={s.code} to={`/stock/${s.code}`}>
                            <Tag color="blue" style={{ cursor: 'pointer' }}>{s.name || s.code}</Tag>
                          </Link>
                        ))}
                        {n.source && <span style={{ fontSize: 11, color: '#bbb' }}>· {n.source}</span>}
                        <Button size="small" type="link" icon={<RobotOutlined />}
                          onClick={() => linkThemes(`${n.title}\n${n.summary}`, n)}
                        >AI 找关联</Button>
                      </div>
                    </div>
                  </div>
                ))}
              </Card>
            ))
          )}
        </Col>

        <Col xs={24} lg={8}>
          <Card size="small" title={<span><RobotOutlined /> 自由分析</span>} style={{ marginBottom: 12 }}>
            <p style={{ fontSize: 12, color: '#666', marginTop: 0 }}>
              粘贴一段新闻/政策原文，AI 自动找受益题材和个股
            </p>
            <TextArea
              rows={5} value={customText} onChange={e => setCustomText(e.target.value)}
              placeholder="例：国务院常务会议研究部署进一步扩大有效投资工作，加快推进重大项目建设..."
            />
            <Button
              type="primary" block icon={<RobotOutlined />} style={{ marginTop: 8 }}
              loading={aiLoading} onClick={() => linkThemes(customText)}
            >AI 找受益题材/个股</Button>
          </Card>

          <Card size="small" title="使用说明">
            <ul style={{ fontSize: 12, color: '#666', paddingLeft: 20, margin: 0, lineHeight: 1.8 }}>
              <li>橙色 Tag = 命中当日盘面活跃题材，可点击直达题材页</li>
              <li>蓝色 Tag = 该快讯关联的个股，可点击直达个股页</li>
              <li>"AI 找关联" 让大模型从该条新闻反查受益标的</li>
              <li>右侧支持自由粘贴文本（如政策原文/研报摘要）</li>
              <li>每 60 秒自动刷新，可手动关闭</li>
            </ul>
          </Card>

          <Button type="primary" block icon={<RobotOutlined />} style={{ marginTop: 12 }}
            onClick={() => askAI(`基于今日 ${items.length} 条快讯，总结 3 条最值得关注的市场主线。重点关注命中题材较多或带"重要"标签的新闻。`)}>
            AI 总结今日主线
          </Button>
        </Col>
      </Row>

      <Modal
        title={aiNews ? `AI 分析：${aiNews.title}` : 'AI 分析'}
        open={showAi}
        onCancel={() => setShowAi(false)}
        footer={null}
        width={720}
      >
        {aiLoading ? (
          <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>
        ) : (
          <div style={{ maxHeight: 500, overflow: 'auto', fontSize: 13, lineHeight: 1.8 }}>
            {aiNews && <Card size="small" style={{ marginBottom: 12, background: '#fafafa' }}>
              <div style={{ fontSize: 13, fontWeight: 600 }}>{aiNews.title}</div>
              {aiNews.summary && <div style={{ fontSize: 12, color: '#666', marginTop: 4 }}>{aiNews.summary}</div>}
            </Card>}
            <Divider style={{ margin: '8px 0' }} />
            <Markdown>{aiText || '*暂无分析结果*'}</Markdown>
          </div>
        )}
        <AIDisclaimer variant="inline" />
      </Modal>
    </div>
  )
}
