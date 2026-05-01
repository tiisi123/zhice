import { useEffect, useState } from 'react'
import { Card, Col, Row, Input, Button, Descriptions, Tag, Table, Statistic, Spin, Slider, message, Empty, Tabs, Timeline, Space, Alert } from 'antd'
import { RobotOutlined, RiseOutlined, FallOutlined, ThunderboltOutlined } from '@ant-design/icons'
import { fetchApi } from '../api/client'
import Disclaimer from '../components/Disclaimer'
import AIBadge from '../components/AIBadge'
import type { AnyData, ApiMeta, DataStatus } from '../api/types'
import { extractMetaList } from '../api/useApiMeta'
import DataStatusBadge from '../components/DataStatusBadge'

export default function ValuationPage() {
  const [code, setCode] = useState('600519')
  const [fin, setFin] = useState<AnyData>(null)
  const [exps, setExps] = useState<AnyData[]>([])
  const [dcf, setDcf] = useState<AnyData>(null)
  const [forecast, setForecast] = useState<AnyData>(null)
  const [screen, setScreen] = useState<AnyData[]>([])
  const [loading, setLoading] = useState(false)
  const [growth, setGrowth] = useState(10)
  const [aiReport, setAiReport] = useState<string | null>(null)
  const [aiLoading, setAiLoading] = useState(false)
  const [altData, setAltData] = useState<AnyData[]>([])
  const [expHistory, setExpHistory] = useState<AnyData[]>([])
  const [dataStatus, setDataStatus] = useState<ApiMeta[]>([])

  const load = async (c: string) => {
    setLoading(true)
    setFin(null)
    setExps([])
    setDcf(null)
    setForecast(null)
    setAiReport(null)
    try {
      const [f, e, d, fc, alt, eh] = await Promise.all([
        fetchApi<AnyData>(`/value/financial/${c}`).catch(() => null),
        fetchApi<AnyData>(`/value/expectations/${c}`).catch(() => null),
        fetchApi<AnyData>(`/value/dcf/${c}?growth=${growth / 100}`).catch(() => null),
        fetchApi<AnyData>(`/value/forecast/${c}`).catch(() => null),
        fetchApi<AnyData>(`/value/alternative/${c}`).catch(() => null),
        fetchApi<AnyData>(`/value/expectation-history/${c}`).catch(() => null),
      ])
      setFin(f?.data || null)
      setExps(e?.expectations || [])
      setDcf(d?.dcf || null)
      setForecast(fc?.scenarios || fc?.data?.scenarios || null)
      setAltData(alt?.data || [])
      setExpHistory(eh?.history || [])
      setDataStatus(extractMetaList([
        { name: '基本面', resp: f },
        { name: '卖方预期', resp: e },
        { name: 'DCF', resp: d },
        { name: '财务预测', resp: fc },
        { name: '另类数据', resp: alt },
        { name: '预期历史', resp: eh },
      ]))
    } catch (e) {
      message.error((e as Error)?.message || '获取估值数据失败')
    }
    setLoading(false)
  }

  const runAiAnalysis = async () => {
    setAiLoading(true)
    try {
      const r = await fetchApi<{ analysis: string }>(`/value/ai-analysis/${code}`)
      setAiReport(r.analysis)
    } catch (e) {
      message.error((e as Error)?.message || 'AI分析失败')
    }
    setAiLoading(false)
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { void load(code) }, [code])
  useEffect(() => {
    void fetchApi<AnyData>('/value/screen?max_pe=30&min_roe=15&min_div=1.0').then(r => setScreen(r.stocks || []))
  }, [])

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />

  return (
    <div>
      <h2>估值分析</h2>
      <AIBadge style={{ marginBottom: 8 }} />
      <Disclaimer kind="forecast" />
      <div style={{ marginBottom: 16, display: 'flex', gap: 8 }}>
        <Input value={code} onChange={e => setCode(e.target.value)} style={{ width: 120 }} placeholder="股票代码" />
        <Button type="primary" onClick={() => load(code)}>分析</Button>
        {fin && <Button icon={<RobotOutlined />} onClick={runAiAnalysis} loading={aiLoading}>AI 深度分析</Button>}
      </div>

      {!loading && !fin && (
        <Card style={{ marginBottom: 16 }}>
          <Empty description={`暂无 ${code} 的基本面数据（当前仅支持 600519、300750 示例数据）`} />
        </Card>
      )}

      {fin && (
        <>
          {dataStatus.some(s => s.mock || s.data_status === 'fallback' || s.data_status === 'unavailable') && (
            <Alert
              type="warning"
              showIcon
              style={{ marginBottom: 16 }}
              message="估值页包含样例或降级数据"
              description={
                <Space wrap size={6}>
                  {dataStatus.map((s) => (
                    <DataStatusBadge
                      key={s.name ?? s.source}
                      status={s.data_status as DataStatus}
                      source={s.source}
                      mock={s.mock}
                    />
                  ))}
                </Space>
              }
            />
          )}

          {aiReport && (
            <Alert
              type="info" showIcon icon={<RobotOutlined />}
              message="AI 基本面分析"
              description={<div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.8 }}>{aiReport}</div>}
              style={{ marginBottom: 16 }}
              closable
            />
          )}
          <Tabs type="card" items={[
            {
              key: 'fundamental', label: '基本面',
              children: (
                <Row gutter={16}>
                  <Col span={14}>
                    <Card title={`${fin.name} (${fin.code}) 基本面`} size="small" style={{ marginBottom: 16 }}>
                      <Row gutter={[8, 8]}>
                        <Col span={6}><Statistic title="PE" value={fin.pe} precision={1} /></Col>
                        <Col span={6}><Statistic title="PE分位" value={fin.pe_percentile} suffix="%" /></Col>
                        <Col span={6}><Statistic title="PB" value={fin.pb} precision={1} /></Col>
                        <Col span={6}><Statistic title="ROE" value={fin.roe} suffix="%" /></Col>
                        <Col span={6}><Statistic title="营收增长" value={fin.revenue_yoy} suffix="%" valueStyle={{ color: fin.revenue_yoy > 0 ? '#f5222d' : '#52c41a' }} /></Col>
                        <Col span={6}><Statistic title="净利增长" value={fin.net_profit_yoy} suffix="%" valueStyle={{ color: fin.net_profit_yoy > 0 ? '#f5222d' : '#52c41a' }} /></Col>
                        <Col span={6}><Statistic title="毛利率" value={fin.gross_margin} suffix="%" /></Col>
                        <Col span={6}><Statistic title="股息率" value={fin.div_yield} suffix="%" /></Col>
                      </Row>
                      <div style={{ marginTop: 12 }}>
                        <strong>亮点：</strong>{fin.highlights?.map((h: string, i: number) => <Tag key={i} color="blue">{h}</Tag>)}
                      </div>
                      <div style={{ marginTop: 6 }}>
                        <strong>风险：</strong>{fin.risks?.map((r: string, i: number) => <Tag key={i} color="red">{r}</Tag>)}
                      </div>
                    </Card>
                    {dcf && (
                      <Card title="DCF 估值" size="small">
                        <div style={{ marginBottom: 8 }}>
                          增长率：<Slider min={3} max={25} value={growth} onChange={setGrowth} style={{ width: 200, display: 'inline-block' }} /> {growth}%
                          <Button size="small" style={{ marginLeft: 8 }} onClick={() => load(code)}>重算</Button>
                        </div>
                        <Statistic title="企业价值" value={dcf.enterprise_value_billion} suffix="亿" />
                      </Card>
                    )}
                  </Col>
                  <Col span={10}>
                    <Card title="券商预期" size="small" style={{ marginBottom: 16 }}>
                      <Table dataSource={exps} rowKey="broker" size="small" pagination={false} columns={[
                        { title: '券商', dataIndex: 'broker', width: 80 },
                        { title: '评级', dataIndex: 'rating', width: 60, render: (v: string) => <Tag color={v === '买入' ? 'red' : 'blue'}>{v}</Tag> },
                        { title: '目标价', dataIndex: 'target', width: 70 },
                        { title: 'EPS预期', dataIndex: 'eps_2026e', width: 70 },
                      ]} />
                    </Card>
                    {forecast && (
                      <Card title="财务预测" size="small">
                        {Object.entries(forecast).map(([label, data]: [string, AnyData]) => (
                          <Descriptions key={label} title={label} column={2} size="small" style={{ marginBottom: 8 }}>
                            <Descriptions.Item label="营收">{data.revenue}亿</Descriptions.Item>
                            <Descriptions.Item label="净利">{data.net_profit}亿</Descriptions.Item>
                          </Descriptions>
                        ))}
                      </Card>
                    )}
                  </Col>
                </Row>
              ),
            },
            {
              key: 'timeline', label: '预期追踪',
              children: (
                <Row gutter={16}>
                  <Col span={14}>
                    <Card title="卖方预期时间线" size="small">
                      {expHistory.length === 0 ? <Empty description="暂无预期历史" /> : (
                        <Timeline
                          items={expHistory.map((h) => ({
                            color: h.rating === '买入' ? 'red' : h.rating === '增持' ? 'blue' : 'gray',
                            children: (
                              <div>
                                <span style={{ color: '#999', marginRight: 8 }}>{h.date}</span>
                                <Tag>{h.broker}</Tag>
                                <Tag color={h.rating === '买入' ? 'red' : 'blue'}>{h.rating}</Tag>
                                <span>目标价 ¥{h.target}</span>
                                <span style={{ marginLeft: 8, color: '#999' }}>EPS预期 {h.eps_e}</span>
                              </div>
                            ),
                          }))}
                        />
                      )}
                    </Card>
                  </Col>
                  <Col span={10}>
                    <Card title="目标价变化趋势" size="small">
                      {(() => {
                        const brokers = [...new Set(expHistory.map((h) => h.broker))]
                        return brokers.map((b) => {
                          const items = expHistory.filter((h) => h.broker === b)
                          if (items.length < 2) return null
                          const first = items[0]
                          const last = items[items.length - 1]
                          const diff = last.target - first.target
                          return (
                            <div key={b} style={{ marginBottom: 8 }}>
                              <Tag>{b}</Tag>
                              <span>¥{first.target} → ¥{last.target} </span>
                              <span style={{ color: diff > 0 ? '#f5222d' : diff < 0 ? '#52c41a' : '#999' }}>
                                {diff > 0 ? <RiseOutlined /> : diff < 0 ? <FallOutlined /> : null}
                                {diff > 0 ? '+' : ''}{diff}
                              </span>
                            </div>
                          )
                        })
                      })()}
                    </Card>
                  </Col>
                </Row>
              ),
            },
            {
              key: 'alt', label: '另类数据',
              children: (
                <Card title={<Space><ThunderboltOutlined />另类数据监控</Space>} size="small">
                  {altData.length === 0 ? <Empty description="暂无另类数据" /> : (
                    <Table
                      dataSource={altData}
                      rowKey={(r) => `${r.source}-${r.metric}`}
                      size="small" pagination={false}
                      columns={[
                        { title: '数据源', dataIndex: 'source', width: 70, render: (v: string) => <Tag color="purple">{v}</Tag> },
                        { title: '指标', dataIndex: 'metric', width: 220 },
                        { title: '当前', dataIndex: 'value', width: 100, align: 'right' as const },
                        { title: '前值', dataIndex: 'prev', width: 100, align: 'right' as const },
                        { title: '变化', dataIndex: 'change', width: 80, render: (v: string) => <span style={{ color: v.startsWith('+') ? '#f5222d' : '#52c41a' }}>{v}</span> },
                        { title: '信号', dataIndex: 'signal', width: 70, render: (v: string) => <Tag color={v === 'positive' ? 'green' : v === 'negative' ? 'red' : 'default'}>{v === 'positive' ? '正面' : v === 'negative' ? '负面' : '中性'}</Tag> },
                        { title: '日期', dataIndex: 'date', width: 80 },
                      ]}
                    />
                  )}
                </Card>
              ),
            },
          ]} />
        </>
      )}

      <Card title="价值股筛选 (PE≤30, ROE≥15%, 股息率≥1%)" size="small" style={{ marginTop: 16 }}>
        <Table dataSource={screen} rowKey="code" size="small" pagination={false} columns={[
          { title: '代码', dataIndex: 'code', width: 80 },
          { title: '名称', dataIndex: 'name', width: 80 },
          { title: 'PE', dataIndex: 'pe', width: 50 },
          { title: 'ROE', dataIndex: 'roe', width: 60, render: (v: number) => `${v}%` },
          { title: '股息率', dataIndex: 'div_yield', width: 60, render: (v: number) => `${v}%` },
          { title: 'PE分位', dataIndex: 'pe_percentile', width: 70,
            render: (v: number) => <Tag color={v < 30 ? 'green' : v > 70 ? 'red' : 'orange'}>{v}%</Tag> },
        ]} />
      </Card>

      <div style={{ marginTop: 12, color: '#999', fontSize: 12 }}>以上分析仅供参考，不构成投资建议。</div>
    </div>
  )
}
