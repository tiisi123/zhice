import { useEffect, useState, useRef } from 'react'
import { Card, Select, Spin, Tag, Row, Col, Button, Space, Steps, Empty } from 'antd'
import { ApartmentOutlined, RobotOutlined, ClockCircleOutlined } from '@ant-design/icons'
import * as echarts from 'echarts'
import { fetchApi } from '../api/client'
import { askAI } from '../api/copilot'
import AIBadge from '../components/AIBadge'
import type { AnyData } from '../api/types'

const STREAM_COLORS: Record<string, string> = { '上游': '#1677ff', '中游': '#52c41a', '下游': '#fa8c16', '个股': '#d9d9d9' }

function ForceGraph({ graph }: { graph: AnyData }) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!ref.current || !graph) return
    const chart = echarts.init(ref.current)
    const categories = (graph.categories || []).map((c: AnyData) => ({ ...c, itemStyle: { color: STREAM_COLORS[c.name] || '#999' } }))
    chart.setOption({
      tooltip: { formatter: (p: AnyData) => p.dataType === 'node' ? p.data.name : `${p.data.source} → ${p.data.target}` },
      legend: { data: categories.map((c: AnyData) => c.name), bottom: 0 },
      series: [{
        type: 'graph', layout: 'force', roam: true, draggable: true,
        categories, nodes: graph.nodes || [], links: graph.links || [],
        force: { repulsion: 220, edgeLength: [60, 160], gravity: 0.08 },
        label: { show: true, fontSize: 11, color: '#333' },
        lineStyle: { color: '#aaa', curveness: 0.15 },
        emphasis: { focus: 'adjacency', lineStyle: { width: 3 } },
      }],
    })
    const onResize = () => chart.resize()
    window.addEventListener('resize', onResize)
    return () => { window.removeEventListener('resize', onResize); chart.dispose() }
  }, [graph])
  return <div ref={ref} style={{ width: '100%', height: 480 }} />
}

export default function ChainPage() {
  const [chains, setChains] = useState<string[]>([])
  const [selected, setSelected] = useState<string>('')
  const [detail, setDetail] = useState<AnyData>(null)
  const [graph, setGraph] = useState<AnyData>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    void fetchApi<{ chains: string[] }>('/chain/list')
      .then(r => { setChains(r.chains || []); if (r.chains?.length) setSelected(r.chains[0]) })
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (!selected) return
    void Promise.all([
      fetchApi<AnyData>(`/chain/${encodeURIComponent(selected)}`),
      fetchApi<AnyData>(`/chain/${encodeURIComponent(selected)}/graph`),
    ]).then(([d, g]) => { setDetail(d.data || d); setGraph(g.graph || g) })
  }, [selected])

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '120px auto' }} />

  const transmission = detail?.transmission_logic || ''
  const lag = detail?.transmission_lag || ''
  const streams = ['上游', '中游', '下游']
  const streamData = streams.map(s => {
    const items = (detail?.nodes || detail || []).filter?.((n: AnyData) => n.stream === s || n.category === s) || []
    return { name: s, count: items.length, items }
  })

  return (
    <div>
      <AIBadge style={{ marginBottom: 8 }} />
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
        <h2 style={{ margin: 0 }}><ApartmentOutlined style={{ color: '#722ed1' }} /> 产业链图谱</h2>
        <Select value={selected} onChange={setSelected} style={{ width: 180 }}
          options={chains.map(c => ({ label: c, value: c }))} />
      </div>

      <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
        {streamData.map(s => (
          <Col xs={8} key={s.name}>
            <Card size="small" style={{ borderTop: `3px solid ${STREAM_COLORS[s.name]}`, textAlign: 'center' }}>
              <Tag color={STREAM_COLORS[s.name]}>{s.name}</Tag>
              <div style={{ fontSize: 24, fontWeight: 700, marginTop: 4 }}>{s.count}</div>
              <div style={{ fontSize: 12, color: '#999' }}>节点</div>
            </Card>
          </Col>
        ))}
      </Row>

      <Row gutter={16}>
        <Col xs={24} lg={16}>
          <Card size="small" title="产业链关系图" bodyStyle={{ padding: 8 }}>
            {graph ? <ForceGraph graph={graph} /> : <Empty />}
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card size="small" title={<span><ClockCircleOutlined /> 传导逻辑</span>} style={{ marginBottom: 16 }}>
            {transmission ? (
              <Steps direction="vertical" size="small" current={-1} items={[
                { title: '上游涨价', description: transmission.split('→')[0] || '原材料供给变化' },
                { title: `时滞 ${lag || '—'}`, description: '价格信号传导' },
                { title: '中游传导', description: transmission.split('→')[1] || '制造成本变化' },
                { title: `时滞 ${lag || '—'}`, description: '订单/产能调整' },
                { title: '下游反映', description: transmission.split('→')[2] || '终端产品价格调整' },
              ]} />
            ) : (
              <div style={{ fontSize: 13, lineHeight: 1.8, color: '#555' }}>{transmission || '暂无传导逻辑数据'}</div>
            )}
            {lag && <div style={{ marginTop: 8, fontSize: 12, color: '#999' }}>传导时滞：{lag}</div>}
          </Card>

          <Card size="small" title={<span><RobotOutlined style={{ color: '#1677ff' }} /> 向 AI 追问</span>}>
            <Space direction="vertical" size={8} style={{ width: '100%' }}>
              <Button block icon={<RobotOutlined />}
                onClick={() => askAI(`分析【${selected}】产业链：1) 当前哪个环节景气度最高？2) 上游涨价是否已传导到下游？3) 最受益的个股有哪些？`)}
              >
                产业链景气分析
              </Button>
              <Button block onClick={() => askAI(`【${selected}】产业链的上游如果涨价10%，中游和下游分别会受到多大影响？传导时滞多久？`)}>
                涨价传导模拟
              </Button>
            </Space>
          </Card>
        </Col>
      </Row>

      <div style={{ fontSize: 11, color: '#999', textAlign: 'center', marginTop: 16, borderTop: '1px solid #f0f0f0', paddingTop: 8 }}>
        本内容仅为产业链信息分析汇总，非荐股建议。
      </div>
    </div>
  )
}
