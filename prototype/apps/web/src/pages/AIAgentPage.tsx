import { useState } from 'react'
import { Card, Collapse, Descriptions, Tabs, Form, Select, Button, Spin, Empty, Typography, Space, Statistic, Tag } from 'antd'
import { RobotOutlined, ThunderboltOutlined, FundOutlined, DatabaseOutlined } from '@ant-design/icons'
import { fetchApi, postApi } from '../api/client'
import { extractMeta } from '../api/useApiMeta'
import DataStatusBadge from '../components/DataStatusBadge'
import AIDisclaimer from '../components/AIDisclaimer'
import AIBadge from '../components/AIBadge'
import type {
  BoardTradingInput,
  BoardTradingAdvice,
  EtfRotationInput,
  EtfRotationAdvice,
  ContractEnvelope,
  DataStatus,
  AnyData,
} from '../api/types'

const { Paragraph, Text } = Typography

const STYLE_OPTIONS = [
  { value: '均衡', label: '均衡' },
  { value: '激进', label: '激进' },
  { value: '保守', label: '保守' },
]

const RISK_OPTIONS = [
  { value: '低', label: '低' },
  { value: '中等', label: '中等' },
  { value: '高', label: '高' },
]

const HORIZON_OPTIONS = [
  { value: '短期', label: '短期' },
  { value: '中期', label: '中期' },
  { value: '长期', label: '长期' },
]

const SECTOR_OPTIONS = [
  { value: '科技', label: '科技' },
  { value: '消费', label: '消费' },
  { value: '医药', label: '医药' },
  { value: '新能源', label: '新能源' },
  { value: '金融', label: '金融' },
  { value: '军工', label: '军工' },
  { value: '半导体', label: '半导体' },
  { value: 'AI', label: 'AI' },
]

function AdviceDisplay({ advice, meta }: { advice: string; meta: ReturnType<typeof extractMeta> }) {
  if (!advice) {
    return <Empty description="暂无建议" />
  }
  return (
    <div>
      <Space style={{ marginBottom: 12 }}>
        <DataStatusBadge status={meta.data_status} source={meta.source} mock={meta.mock} />
        <AIBadge />
      </Space>
      {meta.message && (
        <div style={{ marginBottom: 12, padding: '6px 12px', background: '#fff7e6', borderRadius: 4, fontSize: 12, color: '#ad6800' }}>
          {meta.message}
        </div>
      )}
      <Card size="small" style={{ background: '#fafafa' }}>
        <Paragraph style={{ whiteSpace: 'pre-wrap', marginBottom: 0 }}>{advice}</Paragraph>
      </Card>
      <AIDisclaimer variant="compact" />
    </div>
  )
}

function BoardDataContext() {
  const [ctx, setCtx] = useState<AnyData>(null)
  const [loading, setLoading] = useState(false)
  const [fetched, setFetched] = useState(false)

  const handleExpand = (keys: string | string[]) => {
    if ((Array.isArray(keys) ? keys.length : keys) && !fetched) {
      setLoading(true)
      setFetched(true)
      fetchApi<AnyData>('/analysis/board-replay')
        .then(setCtx)
        .catch(() => setCtx(null))
        .finally(() => setLoading(false))
    }
  }

  const replay = ctx?.data
  const ctxMeta = extractMeta(ctx, '打板数据上下文')

  return (
    <Collapse
      size="small"
      style={{ marginBottom: 16 }}
      onChange={handleExpand}
      items={[{
        key: 'board-ctx',
        label: <Space><DatabaseOutlined />数据上下文 (展开加载)</Space>,
        children: loading ? <Spin size="small" /> : !replay ? (
          <Empty description="暂无数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        ) : (
          <div>
            <DataStatusBadge status={ctxMeta.data_status as DataStatus} source={ctxMeta.source} mock={ctxMeta.mock} size="small" />
            <Descriptions size="small" column={4} style={{ marginTop: 8 }}>
              <Descriptions.Item label="首板">{replay.first_board?.length ?? 0}</Descriptions.Item>
              <Descriptions.Item label="连板">{replay.consecutive?.length ?? 0}</Descriptions.Item>
              <Descriptions.Item label="炸板">{replay.broken?.length ?? 0}</Descriptions.Item>
              <Descriptions.Item label="日期">{ctx.trade_date ?? '-'}</Descriptions.Item>
            </Descriptions>
          </div>
        ),
      }]}
    />
  )
}

function BoardTradingPanel() {
  const [form] = Form.useForm<BoardTradingInput>()
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<ContractEnvelope<BoardTradingAdvice> | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async () => {
    const values = form.getFieldsValue()
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const resp = await postApi<ContractEnvelope<BoardTradingAdvice>>('/ai/agent/board-trading', values)
      setResult(resp)
    } catch (e: AnyData) {
      setError(e?.message || '请求失败，请稍后重试')
    } finally {
      setLoading(false)
    }
  }

  const meta = extractMeta(result)

  return (
    <div>
      <Card
        size="small"
        title={<Space><ThunderboltOutlined style={{ color: '#f5222d' }} /><Text strong>打板交易 AI Agent</Text></Space>}
        style={{ marginBottom: 16 }}
      >
        <Paragraph type="secondary" style={{ marginBottom: 16 }}>
          基于连板天梯、涨停复盘、龙虎榜及回测数据，为您生成个性化打板交易建议。
        </Paragraph>
        <Form form={form} layout="inline" style={{ flexWrap: 'wrap', gap: 8 }}
              initialValues={{ style: '均衡', risk_preference: '中等', focus_sectors: [] }}>
          <Form.Item name="style" label="交易风格">
            <Select options={STYLE_OPTIONS} style={{ width: 100 }} />
          </Form.Item>
          <Form.Item name="risk_preference" label="风险偏好">
            <Select options={RISK_OPTIONS} style={{ width: 100 }} />
          </Form.Item>
          <Form.Item name="focus_sectors" label="关注板块">
            <Select mode="multiple" options={SECTOR_OPTIONS} style={{ minWidth: 200 }} placeholder="可选" allowClear maxTagCount={3} />
          </Form.Item>
          <Form.Item>
            <Button type="primary" icon={<RobotOutlined />} onClick={handleSubmit} loading={loading}>
              生成建议
            </Button>
          </Form.Item>
        </Form>
      </Card>

      <BoardDataContext />

      {loading && <Spin size="large" style={{ display: 'block', margin: '40px auto' }} />}

      {error && (
        <Card size="small">
          <Empty description={error} image={Empty.PRESENTED_IMAGE_SIMPLE} />
        </Card>
      )}

      {!loading && result && (
        <Card size="small" title={<Space><Tag color="blue">打板建议</Tag>{result.trade_date && <Text type="secondary">{result.trade_date}</Text>}</Space>}>
          <AdviceDisplay advice={result.data?.advice || ''} meta={meta} />
        </Card>
      )}
    </div>
  )
}

function EtfDataContext() {
  const [ctx, setCtx] = useState<AnyData>(null)
  const [loading, setLoading] = useState(false)
  const [fetched, setFetched] = useState(false)

  const handleExpand = (keys: string | string[]) => {
    if ((Array.isArray(keys) ? keys.length : keys) && !fetched) {
      setLoading(true)
      setFetched(true)
      fetchApi<AnyData>('/etf/rotation/dashboard')
        .then(setCtx)
        .catch(() => setCtx(null))
        .finally(() => setLoading(false))
    }
  }

  const dashboard = ctx?.data
  const ctxMeta = extractMeta(ctx, 'ETF轮动上下文')

  return (
    <Collapse
      size="small"
      style={{ marginBottom: 16 }}
      onChange={handleExpand}
      items={[{
        key: 'etf-ctx',
        label: <Space><DatabaseOutlined />数据上下文 (展开加载)</Space>,
        children: loading ? <Spin size="small" /> : !dashboard ? (
          <Empty description="暂无数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        ) : (
          <div>
            <DataStatusBadge status={ctxMeta.data_status as DataStatus} source={ctxMeta.source} mock={ctxMeta.mock} size="small" />
            <Space wrap style={{ marginTop: 8 }}>
              {dashboard.current_signal && (
                <Statistic title="当前信号" value={dashboard.current_signal} valueStyle={{ fontSize: 14 }} />
              )}
              {dashboard.etf_count != null && (
                <Statistic title="ETF数量" value={dashboard.etf_count} valueStyle={{ fontSize: 14 }} />
              )}
              {dashboard.data_mode && (
                <Tag color={dashboard.data_mode === 'live' ? 'green' : 'orange'}>{dashboard.data_mode}</Tag>
              )}
            </Space>
          </div>
        ),
      }]}
    />
  )
}

function EtfRotationPanel() {
  const [form] = Form.useForm<EtfRotationInput>()
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<ContractEnvelope<EtfRotationAdvice> | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async () => {
    const values = form.getFieldsValue()
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const resp = await postApi<ContractEnvelope<EtfRotationAdvice>>('/ai/agent/etf-rotation', values)
      setResult(resp)
    } catch (e: AnyData) {
      setError(e?.message || '请求失败，请稍后重试')
    } finally {
      setLoading(false)
    }
  }

  const meta = extractMeta(result)

  return (
    <div>
      <Card
        size="small"
        title={<Space><FundOutlined style={{ color: '#1677ff' }} /><Text strong>ETF轮动 AI Agent</Text></Space>}
        style={{ marginBottom: 16 }}
      >
        <Paragraph type="secondary" style={{ marginBottom: 16 }}>
          基于多因子轮动信号与回测数据，为您生成 ETF 配置与轮动建议。
        </Paragraph>
        <Form form={form} layout="inline" style={{ flexWrap: 'wrap', gap: 8 }}
              initialValues={{ style: '均衡', investment_horizon: '中期', risk_preference: '中等' }}>
          <Form.Item name="style" label="投资风格">
            <Select options={STYLE_OPTIONS} style={{ width: 100 }} />
          </Form.Item>
          <Form.Item name="investment_horizon" label="投资期限">
            <Select options={HORIZON_OPTIONS} style={{ width: 100 }} />
          </Form.Item>
          <Form.Item name="risk_preference" label="风险偏好">
            <Select options={RISK_OPTIONS} style={{ width: 100 }} />
          </Form.Item>
          <Form.Item>
            <Button type="primary" icon={<RobotOutlined />} onClick={handleSubmit} loading={loading}>
              生成建议
            </Button>
          </Form.Item>
        </Form>
      </Card>

      <EtfDataContext />

      {loading && <Spin size="large" style={{ display: 'block', margin: '40px auto' }} />}

      {error && (
        <Card size="small">
          <Empty description={error} image={Empty.PRESENTED_IMAGE_SIMPLE} />
        </Card>
      )}

      {!loading && result && (
        <Card size="small" title={<Tag color="blue">ETF轮动建议</Tag>}>
          <AdviceDisplay advice={result.data?.advice || ''} meta={meta} />
        </Card>
      )}
    </div>
  )
}

const TAB_ITEMS = [
  { key: 'board', label: <Space><ThunderboltOutlined />打板交易</Space>, children: <BoardTradingPanel /> },
  { key: 'etf', label: <Space><FundOutlined />ETF轮动</Space>, children: <EtfRotationPanel /> },
]

export default function AIAgentPage() {
  return (
    <div>
      <Tabs items={TAB_ITEMS} defaultActiveKey="board" />
    </div>
  )
}
