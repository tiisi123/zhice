import { useEffect, useRef, useState } from 'react'
import {
  Card, Input, Button, Tag, Table, Empty, Spin, message, Row, Col,
  Select, Tabs, Statistic, Upload, Alert,
} from 'antd'
import { FileTextOutlined, RobotOutlined, UploadOutlined, SearchOutlined, RiseOutlined } from '@ant-design/icons'
import * as echarts from 'echarts'
import Markdown from 'react-markdown'
import { fetchApi, postApi } from '../api/client'
import AIDisclaimer from '../components/AIDisclaimer'

const { TextArea } = Input

interface FinSummary {
  code: string
  periods: string[]
  revenue: number[]
  net_profit: number[]
  roe: number[]
  eps: number[]
  gross_margin: number[]
  yoy_revenue: number[]
  yoy_profit: number[]
  source?: string
  data_status?: string
  mock?: boolean
  message?: string
}

interface Announcement {
  code: string
  title: string
  art_code: string
  notice_date: string
  url: string
}

interface ResearchReport {
  code: string
  title: string
  org: string
  rating: string
  target_price: number
  publish_date: string
  url: string
}

export default function FinanceReportPage() {
  const [code, setCode] = useState('600519')
  const [input, setInput] = useState('600519')
  const [summary, setSummary] = useState<FinSummary | null>(null)
  const [profile, setProfile] = useState<any>(null)
  const [anns, setAnns] = useState<Announcement[]>([])
  const [annKind, setAnnKind] = useState<string>('all')
  const [reports, setReports] = useState<ResearchReport[]>([])
  const [loading, setLoading] = useState(false)

  const [reportText, setReportText] = useState('')
  const [aiText, setAiText] = useState('')
  const [aiLoading, setAiLoading] = useState(false)

  const trendRef = useRef<HTMLDivElement>(null)

  const load = async () => {
    if (!/^\d{6}$/.test(code)) return
    setLoading(true)
    try {
      const [s, p, a, r] = await Promise.allSettled([
        fetchApi<FinSummary>(`/finance/summary/${code}?n=12`),
        fetchApi<any>(`/finance/profile/${code}`),
        fetchApi<{ items: Announcement[] }>(`/finance/announcements/${code}?days=180&kind=${annKind}`),
        fetchApi<{ items: ResearchReport[] }>(`/finance/research-reports/${code}?n=15`),
      ])
      if (s.status === 'rejected') throw s.reason
      setSummary(s.value)
      setProfile(p.status === 'fulfilled' ? p.value : null)
      setAnns(a.status === 'fulfilled' ? (a.value.items || []) : [])
      setReports(r.status === 'fulfilled' ? (r.value.items || []) : [])
      if (p.status === 'rejected') {
        message.warning('公司简介暂不可用，已继续展示财务摘要')
      }
    } catch (e: any) {
      message.error(e?.message || '加载失败')
    } finally {
      setLoading(false)
    }
  }
  useEffect(() => { load() }, [code]) // eslint-disable-line
  useEffect(() => {
    if (!code) return
    fetchApi<{ items: Announcement[] }>(`/finance/announcements/${code}?days=180&kind=${annKind}`)
      .then(r => setAnns(r.items || []))
      .catch(() => setAnns([]))
  }, [annKind, code])

  // 营收/净利双轴趋势
  useEffect(() => {
    if (!summary || !trendRef.current) return
    const chart = echarts.init(trendRef.current)
    // 倒序展示成正序
    const periods = [...summary.periods].reverse()
    const rev = [...summary.revenue].reverse().map(v => +(v / 1e8).toFixed(2))
    const np = [...summary.net_profit].reverse().map(v => +(v / 1e8).toFixed(2))
    const yoyR = [...summary.yoy_revenue].reverse()
    chart.setOption({
      tooltip: { trigger: 'axis' },
      legend: { data: ['营收', '净利', '营收同比%'], top: 0 },
      grid: { left: 50, right: 60, top: 40, bottom: 40 },
      xAxis: { type: 'category', data: periods, axisLabel: { rotate: 30, fontSize: 10 } },
      yAxis: [
        { type: 'value', name: '亿元', position: 'left' },
        { type: 'value', name: '同比%', position: 'right' },
      ],
      series: [
        { name: '营收', type: 'bar', data: rev, itemStyle: { color: '#1677ff' } },
        { name: '净利', type: 'bar', data: np, itemStyle: { color: '#f5222d' } },
        { name: '营收同比%', type: 'line', yAxisIndex: 1, data: yoyR, smooth: true, itemStyle: { color: '#fa8c16' } },
      ],
    })
    const onResize = () => chart.resize()
    window.addEventListener('resize', onResize)
    return () => { window.removeEventListener('resize', onResize); chart.dispose() }
  }, [summary])

  const explain = async () => {
    if (reportText.length < 20) { message.warning('请粘贴足够的财报正文（至少 20 字）'); return }
    setAiLoading(true)
    try {
      const r = await postApi<{ analysis: string }>('/finance/explain-report', {
        code, name: profile?.name || code,
        period: summary?.periods?.[0],
        text: reportText,
      })
      setAiText(r.analysis || '')
    } catch (e: any) {
      message.error(e?.message || 'AI 解读失败')
    } finally {
      setAiLoading(false)
    }
  }

  // 文本文件：直接读取
  const handleUploadText = (file: File) => {
    const reader = new FileReader()
    reader.onload = e => setReportText(String(e.target?.result || ''))
    reader.readAsText(file, 'utf-8')
    return false
  }

  // PDF：走后端抽取
  const handleUploadPdf = async (file: File) => {
    if (file.size > 30 * 1024 * 1024) { message.error('PDF 不能超过 30MB'); return false }
    setAiLoading(true)
    try {
      const fd = new FormData()
      fd.append('file', file)
      const base = '/api'
      const token = localStorage.getItem('zhice.token')
      const r = await fetch(`${base}/finance/extract-pdf`, {
        method: 'POST', body: fd,
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      if (!r.ok) throw new Error((await r.json()).detail || 'PDF 解析失败')
      const data = await r.json()
      if (data.warning) message.warning(data.warning)
      setReportText(data.text || '')
      message.success(`已抽取 ${data.char_count} 字${data.truncated ? '（已截断）' : ''}`)
    } catch (e: any) {
      message.error(e?.message || 'PDF 解析失败')
    } finally {
      setAiLoading(false)
    }
    return false
  }

  // PDF 一键解读：抽文本 + AI 解读一步到位
  const handleUploadPdfAndExplain = async (file: File) => {
    if (file.size > 30 * 1024 * 1024) { message.error('PDF 不能超过 30MB'); return false }
    setAiLoading(true)
    try {
      const fd = new FormData()
      fd.append('file', file)
      if (code) fd.append('code', code)
      if (profile?.name) fd.append('name', profile.name)
      if (summary?.periods?.[0]) fd.append('period', summary.periods[0])
      const base = '/api'
      const token = localStorage.getItem('zhice.token')
      const r = await fetch(`${base}/finance/explain-pdf`, {
        method: 'POST', body: fd,
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      if (!r.ok) throw new Error((await r.json()).detail || 'PDF 解读失败')
      const data = await r.json()
      setReportText(data.extracted_text_preview || '')
      setAiText(data.analysis || '')
      message.success(`已解读（PDF 全文 ${data.full_char_count} 字）`)
    } catch (e: any) {
      message.error(e?.message || 'PDF 解读失败')
    } finally {
      setAiLoading(false)
    }
    return false
  }

  const latest = summary?.periods?.[0]
  const latestIdx = 0

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
        <h2 style={{ margin: 0 }}><FileTextOutlined style={{ color: '#1677ff' }} /> 财报追踪 · AI 解读（M4D-02 / M4D-05）</h2>
        <Input
          placeholder="6 位股票代码" value={input}
          onChange={e => setInput(e.target.value)} onPressEnter={() => setCode(input)}
          style={{ width: 160 }} prefix={<SearchOutlined />} maxLength={6}
        />
        <Button type="primary" onClick={() => setCode(input)}>查询</Button>
      </div>

      {loading && <div style={{ textAlign: 'center', padding: 60 }}><Spin size="large" /></div>}

      {!loading && summary && (
        <>
          <Alert
            type={summary.mock ? 'warning' : summary.data_status === 'partial' || summary.data_status === 'stale' ? 'info' : 'success'}
            showIcon
            style={{ marginBottom: 12 }}
            message={`财务摘要数据状态：${summary.source || 'unknown'} / ${summary.data_status || 'unknown'}`}
            description={summary.message || '财务摘要用于趋势分析，AI 解读内容仅供研究参考。'}
          />

          <Card size="small" style={{ marginBottom: 16 }} title={<span>{profile?.name || code} <Tag color="blue">{profile?.industry || '—'}</Tag></span>}>
            <Row gutter={16}>
              <Col span={4}><Statistic title={`报告期 ${latest || '—'} 营收`} value={summary.revenue[latestIdx] / 1e8} suffix="亿" precision={2} /></Col>
              <Col span={4}><Statistic title="净利润" value={summary.net_profit[latestIdx] / 1e8} suffix="亿" precision={2} /></Col>
              <Col span={4}>
                <Statistic title="营收同比" value={summary.yoy_revenue[latestIdx]} suffix="%" precision={2}
                  valueStyle={{ color: summary.yoy_revenue[latestIdx] >= 0 ? '#cf1322' : '#3f8600' }} />
              </Col>
              <Col span={4}>
                <Statistic title="净利同比" value={summary.yoy_profit[latestIdx]} suffix="%" precision={2}
                  valueStyle={{ color: summary.yoy_profit[latestIdx] >= 0 ? '#cf1322' : '#3f8600' }} />
              </Col>
              <Col span={4}><Statistic title="ROE" value={summary.roe[latestIdx]} suffix="%" precision={2} /></Col>
              <Col span={4}><Statistic title="毛利率" value={summary.gross_margin[latestIdx]} suffix="%" precision={2} /></Col>
            </Row>
          </Card>

          <Card size="small" title={<span><RiseOutlined /> 营收 / 净利 趋势</span>} style={{ marginBottom: 16 }}>
            <div ref={trendRef} style={{ width: '100%', height: 320 }} />
          </Card>

          <Tabs
            defaultActiveKey="ann"
            items={[
              {
                key: 'ann', label: `公告（${anns.length}）`,
                children: (
                  <Card size="small" extra={
                    <Select value={annKind} onChange={setAnnKind} style={{ width: 130 }}
                      options={[
                        { value: 'all', label: '全部' },
                        { value: 'report', label: '定期报告' },
                        { value: 'earnings', label: '业绩预告' },
                      ]}
                    />
                  }>
                    <Table<Announcement>
                      dataSource={anns} rowKey="art_code" size="small" pagination={{ pageSize: 15 }}
                      locale={{ emptyText: <Empty description="近 180 天无相关公告" /> }}
                      columns={[
                        { title: '日期', dataIndex: 'notice_date', width: 100 },
                        { title: '标题', dataIndex: 'title', render: (t, r) => <a href={r.url} target="_blank" rel="noreferrer">{t}</a> },
                      ]}
                    />
                  </Card>
                ),
              },
              {
                key: 'reports', label: `券商研报（${reports.length}）`,
                children: (
                  <Card size="small">
                    <Table<ResearchReport>
                      dataSource={reports} rowKey="title" size="small" pagination={{ pageSize: 15 }}
                      locale={{ emptyText: <Empty description="近期暂无研报" /> }}
                      columns={[
                        { title: '日期', dataIndex: 'publish_date', width: 100 },
                        { title: '机构', dataIndex: 'org', width: 140 },
                        { title: '评级', dataIndex: 'rating', width: 100, render: r => <Tag color="blue">{r || '—'}</Tag> },
                        { title: '目标价', dataIndex: 'target_price', width: 80, render: (v: number) => v ? v.toFixed(2) : '—' },
                        { title: '标题', dataIndex: 'title', render: (t, r) => r.url ? <a href={r.url} target="_blank" rel="noreferrer">{t}</a> : t },
                      ]}
                    />
                  </Card>
                ),
              },
              {
                key: 'ai', label: <span><RobotOutlined /> AI 解读</span>,
                children: (
                  <Card size="small">
                    <Alert type="info" showIcon style={{ marginBottom: 12 }}
                      message="三种方式：① 直接上传 PDF 一键解读  ② 上传 PDF 仅抽文本（手动编辑后再解读）  ③ 直接粘贴文本"
                      description="PDF 仅支持文本层（非扫描件），≤30MB；扫描件请先 OCR 后再粘贴。" />
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                      <Upload beforeUpload={handleUploadPdfAndExplain} accept=".pdf" maxCount={1} showUploadList={false}>
                        <Button type="primary" icon={<RobotOutlined />} loading={aiLoading}>
                          上传 PDF · 一键解读
                        </Button>
                      </Upload>
                      <Upload beforeUpload={handleUploadPdf} accept=".pdf" maxCount={1} showUploadList={false}>
                        <Button icon={<UploadOutlined />}>仅抽 PDF 文本</Button>
                      </Upload>
                      <Upload beforeUpload={handleUploadText} accept=".txt,.md" maxCount={1} showUploadList={false}>
                        <Button icon={<UploadOutlined />}>上传 .txt</Button>
                      </Upload>
                    </div>
                    <TextArea
                      rows={8} value={reportText} onChange={e => setReportText(e.target.value)}
                      style={{ marginTop: 12 }}
                      placeholder="将财报正文 / 业绩预告原文粘贴到此处。例如：『公司预计 2025 年度归属于上市公司股东的净利润为 X 亿元，同比增长 X%。营业收入 X 亿元，同比增长 X%……』"
                    />
                    <div style={{ marginTop: 12 }}>
                      <Button type="primary" icon={<RobotOutlined />} loading={aiLoading} onClick={explain}>
                        AI 结构化解读
                      </Button>
                      <span style={{ marginLeft: 12, color: '#999', fontSize: 12 }}>已输入 {reportText.length} 字</span>
                    </div>
                    {aiText && (
                      <div style={{ marginTop: 16, padding: 16, background: '#fafafa', borderRadius: 4, fontSize: 13, lineHeight: 1.8 }}>
                        <Markdown>{aiText}</Markdown>
                      </div>
                    )}
                    <AIDisclaimer variant="inline" />
                  </Card>
                ),
              },
            ]}
          />
        </>
      )}

      {!loading && !summary && (
        <Card><Empty description="请输入股票代码后查询" /></Card>
      )}
    </div>
  )
}
