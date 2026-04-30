import { useEffect, useMemo, useRef, useState } from 'react'
import { Card, Col, Row, Spin, Tag, Table, Empty, Button, Space, DatePicker, message } from 'antd'
import { FireOutlined, RobotOutlined, StarOutlined, CrownOutlined } from '@ant-design/icons'
import { Link } from 'react-router-dom'
import * as echarts from 'echarts'
import type { Dayjs } from 'dayjs'
import { fetchApi } from '../api/client'
import { askAI } from '../api/copilot'
import MockBanner from '../components/MockBanner'

interface SectorItem {
  PlateID?: string; plate_id?: string; PlateName?: string; plate_name?: string
  ChangePercent?: number; change_percent?: number; LimitUpNum?: number; limit_up_num?: number
  MainForce?: number; main_force?: number; Intensity?: number; intensity?: number
  is_new?: boolean; is_hot?: boolean; stage?: string
}
interface DetailStock { SecurityCode?: string; stock_code?: string; SecurityName?: string; stock_name?: string; ChangePercent?: number; change_percent?: number; board_count?: number }

function pick(s: SectorItem, ...keys: (keyof SectorItem)[]) { for (const k of keys) { const v = s[k]; if (v !== undefined && v !== null && v !== '') return v } return undefined }
function pickStr(s: SectorItem, ...keys: (keyof SectorItem)[]) { return String(pick(s, ...keys) || '—') }
function pickNum(s: SectorItem, ...keys: (keyof SectorItem)[]) { return Number(pick(s, ...keys) || 0) }

const STAGE_COLOR: Record<string, string> = { '高潮': 'red', '启动': 'orange', '发酵': 'gold', '中性': 'default', '退潮': 'blue' }

function Top3Cards({ sectors, onSelect }: { sectors: SectorItem[]; onSelect: (s: SectorItem) => void }) {
  const top3 = useMemo(() => sectors.slice(0, 3), [sectors])
  if (top3.length === 0) return <Empty description="暂无主线数据" />
  const medals = ['🥇', '🥈', '🥉']

  return (
    <Space direction="vertical" size={12} style={{ width: '100%' }}>
      {top3.map((s, i) => {
        const name = pickStr(s, 'PlateName', 'plate_name')
        const change = pickNum(s, 'ChangePercent', 'change_percent')
        const ztNum = pickNum(s, 'LimitUpNum', 'limit_up_num')
        const net = pickNum(s, 'MainForce', 'main_force')
        const intensity = pickNum(s, 'Intensity', 'intensity')
        const netStr = Math.abs(net) >= 1e8 ? `${(net / 1e8).toFixed(2)}亿` : `${(net / 1e4).toFixed(0)}万`

        return (
          <Card key={i} size="small" hoverable onClick={() => onSelect(s)} bodyStyle={{ padding: 14 }}>
            <Row gutter={12} align="middle">
              <Col flex="none">
                <div style={{ fontSize: 28, lineHeight: 1 }}>{medals[i]}</div>
              </Col>
              <Col flex="auto" style={{ minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
                  <span style={{ fontWeight: 700, fontSize: 16 }}>{name}</span>
                  {s.stage && <Tag color={STAGE_COLOR[s.stage] || 'default'}>{s.stage}</Tag>}
                  {s.is_new && <Tag color="magenta"><StarOutlined /> 新题材</Tag>}
                  <span style={{ color: change >= 0 ? '#f5222d' : '#52c41a', fontWeight: 600 }}>
                    {change >= 0 ? '+' : ''}{change.toFixed(2)}%
                  </span>
                </div>
                <div style={{ marginTop: 6, fontSize: 13, color: '#555' }}>
                  涨停 <b style={{ color: '#f5222d' }}>{ztNum}</b> 只
                  <span style={{ margin: '0 8px', color: '#ddd' }}>|</span>
                  强度 <b>{intensity}</b>
                  <span style={{ margin: '0 8px', color: '#ddd' }}>|</span>
                  主力 <span style={{ color: net >= 0 ? '#f5222d' : '#52c41a', fontWeight: 600 }}>{netStr}</span>
                </div>
              </Col>
              <Col flex="none">
                <Button type="link" icon={<RobotOutlined />} onClick={e => { e.stopPropagation(); askAI(`深度分析今日主线题材【${name}】：核心驱动、龙头股、产业链位置、题材阶段${s.stage ? `（当前${s.stage}）` : ''}，以及明日延续性判断。`) }}>
                  AI
                </Button>
              </Col>
            </Row>
          </Card>
        )
      })}
    </Space>
  )
}

function TreemapChart({ sectors, onSelect }: { sectors: SectorItem[]; onSelect: (s: SectorItem) => void }) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!ref.current || sectors.length === 0) return
    const chart = echarts.init(ref.current)
    const treeData = sectors.slice(0, 20).map(s => {
      const name = pickStr(s, 'PlateName', 'plate_name')
      const zt = pickNum(s, 'LimitUpNum', 'limit_up_num')
      const change = pickNum(s, 'ChangePercent', 'change_percent')
      return { name, value: Math.max(zt, 1), change, _raw: s }
    })
    chart.setOption({
      tooltip: { formatter: (p: any) => `${p.name}<br/>涨停 ${p.value} 只<br/>涨幅 ${p.data.change?.toFixed(2) || 0}%` },
      series: [{
        type: 'treemap', roam: false, nodeClick: false,
        breadcrumb: { show: false },
        label: { show: true, formatter: '{b}', fontSize: 12, color: '#fff' },
        itemStyle: { borderColor: '#fff', borderWidth: 2, gapWidth: 2 },
        levels: [{ colorMappingBy: 'value', itemStyle: { gapWidth: 3 } }],
        data: treeData.map(d => ({
          ...d,
          itemStyle: {
            color: d.change > 4 ? '#c0392b' : d.change > 2 ? '#e74c3c' : d.change > 0 ? '#fa8c16' : d.change > -1 ? '#95a5a6' : '#27ae60',
          },
        })),
      }],
    })
    chart.on('click', (p: any) => {
      const raw = treeData[p.dataIndex]?._raw
      if (raw) onSelect(raw)
    })
    const onResize = () => chart.resize()
    window.addEventListener('resize', onResize)
    return () => { window.removeEventListener('resize', onResize); chart.dispose() }
  }, [sectors, onSelect])

  return <div ref={ref} style={{ width: '100%', height: 300 }} />
}

function DetailPanel({ sector, detail, loading }: { sector: SectorItem; detail: DetailStock[]; loading: boolean }) {
  const name = pickStr(sector, 'PlateName', 'plate_name')
  const cols = [
    { title: '代码', key: 'c', width: 80, render: (_: any, r: DetailStock) => <Link to={`/stock/${(r.SecurityCode || r.stock_code || '').slice(0, 6)}`}>{r.SecurityCode || r.stock_code}</Link> },
    { title: '名称', key: 'n', width: 80, render: (_: any, r: DetailStock) => <span style={{ fontWeight: (r.board_count || 0) >= 2 ? 700 : 400 }}>{r.SecurityName || r.stock_name}</span> },
    { title: '涨幅', key: 'ch', width: 70, render: (_: any, r: DetailStock) => { const v = Number(r.ChangePercent || r.change_percent || 0); return <span style={{ color: v >= 0 ? '#f5222d' : '#52c41a', fontWeight: 600 }}>{v.toFixed(2)}%</span> } },
    { title: '连板', key: 'b', width: 55, render: (_: any, r: DetailStock) => (r.board_count || 0) >= 1 ? <Tag color="red">{r.board_count}板</Tag> : <span style={{ color: '#999' }}>—</span> },
  ]

  return (
    <Card
      title={<span><CrownOutlined style={{ color: '#fa8c16' }} /> {name} · 成分股</span>}
      size="small"
      extra={<Button type="link" icon={<RobotOutlined />} onClick={() => askAI(`分析题材【${name}】内个股的强弱排序、龙头识别标准，以及应该关注的核心品种。`)}>AI 选龙头</Button>}
    >
      {loading ? <Spin /> : (
        <Table
          dataSource={detail}
          columns={cols}
          rowKey={(r, i) => r.SecurityCode || r.stock_code || String(i)}
          size="small"
          pagination={{ pageSize: 15 }}
        />
      )}
    </Card>
  )
}

export default function ThemePage() {
  const [sectors, setSectors] = useState<SectorItem[]>([])
  const [detail, setDetail] = useState<DetailStock[]>([])
  const [selectedSector, setSelectedSector] = useState<SectorItem | null>(null)
  const [loading, setLoading] = useState(true)
  const [detailLoading, setDetailLoading] = useState(false)
  const [isMock, setIsMock] = useState(false)
  const [selectedDate, setSelectedDate] = useState<string | undefined>(undefined)

  useEffect(() => {
    setLoading(true)
    const params = selectedDate ? `?date=${selectedDate}` : ''
    fetchApi<{ data: SectorItem[]; mock?: boolean }>(`/theme/sectors${params}`)
      .then(res => { setSectors(res.data || []); setIsMock(!!res.mock) })
      .catch(e => message.error(e.message || '获取板块失败'))
      .finally(() => setLoading(false))
  }, [selectedDate])

  const loadDetail = async (s: SectorItem) => {
    const plateId = s.PlateID || s.plate_id || ''
    if (!plateId) return
    setSelectedSector(s)
    setDetailLoading(true)
    try {
      const dateParam = selectedDate ? `?date=${selectedDate}` : ''
      const res = await fetchApi<{ data: DetailStock[] }>(`/theme/sectors/${plateId}${dateParam}`)
      setDetail(res.data || [])
    } catch { setDetail([]) }
    setDetailLoading(false)
  }

  const newThemes = useMemo(() => sectors.filter(s => s.is_new), [sectors])

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '120px auto' }} />

  return (
    <div>
      <MockBanner show={isMock} />
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <h2 style={{ margin: 0 }}>题材板块</h2>
        </div>
        <DatePicker onChange={(d: Dayjs | null) => setSelectedDate(d ? d.format('YYYY-MM-DD') : undefined)} placeholder="选择日期" allowClear size="small" />
      </div>

      {newThemes.length > 0 && (
        <Card size="small" style={{ marginBottom: 16, borderLeft: '4px solid #eb2f96' }}>
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 6 }}><StarOutlined style={{ color: '#eb2f96' }} /> 新题材发现</div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {newThemes.map(s => (
              <Tag key={s.PlateID || s.plate_id} color="magenta" style={{ cursor: 'pointer' }} onClick={() => loadDetail(s)}>
                {pickStr(s, 'PlateName', 'plate_name')} · 涨停{pickNum(s, 'LimitUpNum', 'limit_up_num')}只
              </Tag>
            ))}
          </div>
        </Card>
      )}

      <Row gutter={16}>
        <Col xs={24} lg={14}>
          <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 8 }}>
            <FireOutlined style={{ color: '#f5222d' }} /> 主线 Top 3
          </div>
          <Top3Cards sectors={sectors} onSelect={loadDetail} />

          <Card size="small" title="板块热力图" style={{ marginTop: 16 }} bodyStyle={{ padding: 8 }}>
            {sectors.length === 0 ? <Empty /> : <TreemapChart sectors={sectors} onSelect={loadDetail} />}
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          {selectedSector ? (
            <DetailPanel sector={selectedSector} detail={detail} loading={detailLoading} />
          ) : (
            <Card size="small" style={{ minHeight: 300, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Empty description="点击左侧板块查看成分股" />
            </Card>
          )}
        </Col>
      </Row>

      <Card size="small" title={<span><RobotOutlined style={{ color: '#1677ff' }} /> 向 AI 追问</span>} style={{ marginTop: 16 }}>
        <Space wrap>
          <Button type="primary" icon={<RobotOutlined />} onClick={() => {
            const top3 = sectors.slice(0, 3).map(s => pickStr(s, 'PlateName', 'plate_name')).join('、')
            askAI(`今日主线题材 Top3 是【${top3}】，分析各自所处阶段、核心逻辑、龙头梯队，判断明日哪条线最值得跟踪。`)
          }}>
            主线深度分析
          </Button>
          <Button onClick={() => askAI('今日有没有新出现的题材？新题材的特征和参与策略是什么？')}>新题材发现</Button>
          <Button onClick={() => askAI('哪些题材已经进入退潮期？退潮题材的风险信号有哪些？')}>退潮预警</Button>
        </Space>
      </Card>

      <div style={{ marginTop: 12, color: '#999', fontSize: 11, textAlign: 'center' }}>以上分析仅供参考，不构成投资建议。</div>
    </div>
  )
}
