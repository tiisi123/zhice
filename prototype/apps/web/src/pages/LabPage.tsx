import { useEffect, useState } from 'react'
import {
  Card, Tabs, Table, Button, Select, Space, Typography, Tag, Form, InputNumber, Input, message, Switch, Popconfirm, Alert, Modal,
} from 'antd'
import { DeleteOutlined, EditOutlined, PlusOutlined, ExperimentOutlined, BellOutlined } from '@ant-design/icons'
import { fetchApi, postApi, deleteApi } from '../api/client'
import Disclaimer from '../components/Disclaimer'
import AIBadge from '../components/AIBadge'
import type { AnyData } from '../api/types'

const { Title, Paragraph } = Typography

// ========== M3-07 策略对比 ==========
function CompareTab() {
  const [templates, setTemplates] = useState<string[]>([])
  const [selected, setSelected] = useState<string[]>([])
  const [results, setResults] = useState<AnyData | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    void fetchApi<{ templates: Record<string, unknown> }>('/strategy/templates')
      .then((r) => setTemplates(Object.keys(r.templates)))
  }, [])

  const run = async () => {
    if (selected.length < 2) { message.warning('至少选 2 个策略'); return }
    setLoading(true)
    try {
      const r = await postApi<AnyData>('/lab/compare', { templates: selected, years: 3 })
      setResults(r)
    } catch (e) {
      message.error((e as Error)?.message || '对比失败')
    } finally { setLoading(false) }
  }

  const cols = [
    { title: '策略', dataIndex: 'strategy_name' },
    { title: '总收益%', dataIndex: 'total_return', align: 'right' as const, render: (v: number) => <span style={{ color: v >= 0 ? '#f5222d' : '#389e0d' }}>{v?.toFixed(2)}</span> },
    { title: '年化%', dataIndex: 'annualized_return', align: 'right' as const },
    { title: '最大回撤%', dataIndex: 'max_drawdown', align: 'right' as const },
    { title: '夏普', dataIndex: 'sharpe_ratio', align: 'right' as const },
    { title: '胜率%', dataIndex: 'win_rate', align: 'right' as const },
    { title: '盈亏比', dataIndex: 'profit_loss_ratio', align: 'right' as const },
    { title: '综合分', dataIndex: 'composite_score', align: 'right' as const, render: (v: number) => <Tag color="blue">{v?.toFixed(3)}</Tag> },
  ]

  return (
    <div>
      <Paragraph type="secondary">从模板库中选择 2-5 个策略进行回测对比，系统将给出综合评分排名。</Paragraph>
      <Space style={{ marginBottom: 12 }} wrap>
        <Select
          mode="multiple" style={{ minWidth: 360 }}
          placeholder="选择要对比的策略模板（2-5 个）"
          value={selected} onChange={setSelected} maxTagCount={3}
          options={templates.map((t) => ({ value: t, label: t }))}
          disabled={loading}
        />
        <Button type="primary" icon={<ExperimentOutlined />} loading={loading} onClick={run}>运行对比</Button>
      </Space>
      {results && (
        <>
          <Alert type="success" showIcon style={{ marginBottom: 12 }}
            message={<span>综合第一：<b>{results.winner}</b></span>}
            description={<span>排名：{(results.ranked || []).join(' → ')}</span>}
          />
          <Table rowKey="strategy_name" size="small" pagination={false} dataSource={results.results} columns={cols} />
        </>
      )}
    </div>
  )
}

// ========== M4A-10 自定义打板规则 ==========
interface Rule {
  id: number
  name: string
  kind: string
  enabled: number
  rules: {
    seal_amount_gte?: number | null
    turnover_ratio_lte?: number | null
    board_count_gte?: number | null
    market_cap_lte?: number | null
    theme_rank_top?: number | null
  }
}

function AlertRulesTab() {
  const [rules, setRules] = useState<Rule[]>([])
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<Rule | null>(null)
  const [form] = Form.useForm()
  const [evalResult, setEvalResult] = useState<AnyData | null>(null)

  const load = async () => {
    const r = await fetchApi<{ items: Rule[] }>('/lab/alert-rules')
    setRules(r.items)
  }
  useEffect(() => {
    const run = async () => { await load() }
    void run()
  }, [])

  const save = async () => {
    const v = await form.validateFields()
    const body = {
      id: editing?.id,
      name: v.name,
      kind: 'limit_up',
      enabled: v.enabled !== false,
      seal_amount_gte: v.seal_amount_gte,
      turnover_ratio_lte: v.turnover_ratio_lte,
      board_count_gte: v.board_count_gte,
      market_cap_lte: v.market_cap_lte,
      theme_rank_top: v.theme_rank_top,
    }
    await postApi('/lab/alert-rules', body)
    message.success('已保存')
    setOpen(false)
    setEditing(null)
    form.resetFields()
    void load()
  }

  const remove = async (id: number) => {
    await deleteApi(`/lab/alert-rules/${id}`)
    void load()
  }

  const evaluate = async (id: number) => {
    const r = await postApi<AnyData>(`/lab/alert-rules/${id}/evaluate`)
    setEvalResult(r)
  }

  const openEdit = (r: Rule | null) => {
    setEditing(r)
    form.setFieldsValue(r ? { name: r.name, enabled: !!r.enabled, ...(r.rules || {}) } : { name: '', enabled: true })
    setOpen(true)
  }

  return (
    <div>
      <Paragraph type="secondary">自定义涨停股筛选条件，一键扫描当日涨停池。</Paragraph>
      <Space style={{ marginBottom: 12 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => openEdit(null)}>新建规则</Button>
      </Space>
      <Table
        rowKey="id" size="small" pagination={false} dataSource={rules}
        columns={[
          { title: '名称', dataIndex: 'name' },
          {
            title: '条件摘要',
            render: (_, r) => (
              <Space wrap>
                {r.rules?.board_count_gte != null && <Tag>连板≥{r.rules.board_count_gte}</Tag>}
                {r.rules?.seal_amount_gte != null && <Tag>封单≥{(r.rules.seal_amount_gte / 1e4).toFixed(0)}万</Tag>}
                {r.rules?.turnover_ratio_lte != null && <Tag>换手≤{r.rules.turnover_ratio_lte}%</Tag>}
                {r.rules?.market_cap_lte != null && <Tag>流通市值≤{r.rules.market_cap_lte}亿</Tag>}
                {r.rules?.theme_rank_top != null && <Tag>题材Top{r.rules.theme_rank_top}</Tag>}
              </Space>
            ),
          },
          { title: '状态', dataIndex: 'enabled', width: 80, render: (v: number) => <Tag color={v ? 'green' : 'default'}>{v ? '启用' : '停用'}</Tag> },
          {
            title: '操作', width: 220,
            render: (_, r) => (
              <Space>
                <Button size="small" icon={<BellOutlined />} onClick={() => evaluate(r.id)}>评估</Button>
                <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(r)} />
                <Popconfirm title="删除此规则？" onConfirm={() => remove(r.id)}>
                  <Button size="small" danger icon={<DeleteOutlined />} />
                </Popconfirm>
              </Space>
            ),
          },
        ]}
      />

      {evalResult && (
        <Card title={`命中结果（${evalResult.match_count}/${evalResult.total}）`} size="small" style={{ marginTop: 12 }}
          extra={<Button size="small" onClick={() => setEvalResult(null)}>关闭</Button>}>
          <Table
            rowKey={(r: AnyData) => r.stock_code || r.code} size="small" pagination={{ pageSize: 10 }}
            dataSource={evalResult.matches}
            columns={[
              { title: '代码', dataIndex: 'stock_code', width: 100 },
              { title: '名称', dataIndex: 'stock_name', width: 120 },
              { title: '连板', dataIndex: 'board_count', width: 70 },
              { title: '封单(元)', dataIndex: 'seal_amount', width: 120, render: (v: number) => (v / 1e4).toFixed(0) + '万' },
              { title: '换手%', dataIndex: 'turnover_ratio', width: 80 },
              { title: '涨停原因', dataIndex: 'reason', ellipsis: true },
            ]}
          />
        </Card>
      )}

      <Modal
        open={open}
        title={editing ? '编辑规则' : '新建规则'}
        onCancel={() => { setOpen(false); setEditing(null) }}
        onOk={save}
        destroyOnHidden
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="规则名称" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="enabled" label="启用" valuePropName="checked">
            <Switch defaultChecked />
          </Form.Item>
          <Form.Item name="board_count_gte" label="最小连板数">
            <InputNumber min={1} max={10} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="seal_amount_gte" label="封单金额 ≥（元）">
            <InputNumber min={0} step={10000000} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="turnover_ratio_lte" label="换手率 ≤（%）">
            <InputNumber min={0} max={100} step={0.5} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="market_cap_lte" label="流通市值 ≤（亿）">
            <InputNumber min={0} step={10} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="theme_rank_top" label="所属题材排名 ≤ TopN">
            <InputNumber min={1} max={20} style={{ width: '100%' }} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

// ========== M4E-04 多风格组合 ==========
const STYLE_LABEL: Record<string, string> = {
  short: '短线/打板', hot: '热点/轮动', growth: '成长/景气', value: '价值/基本面',
}

function StyleComboTab() {
  const [styles, setStyles] = useState<string[]>([])
  const [detected, setDetected] = useState<string | null>(null)
  const [votes, setVotes] = useState<Record<string, number>>({})

  const load = async () => {
    const r = await fetchApi<{ styles: string[] }>('/lab/style-combo')
    setStyles(r.styles)
  }
  useEffect(() => {
    const run = async () => { await load() }
    void run()
  }, [])

  const save = async () => {
    if (styles.length === 0) { message.warning('至少选择一个风格'); return }
    const r = await postApi<AnyData>('/lab/style-combo', { styles })
    message.success(`已保存，主风格：${STYLE_LABEL[r.primary]}`)
  }

  const detect = async () => {
    const r = await fetchApi<{ detected: string; votes: Record<string, number> }>('/style/detect')
    setDetected(r.detected)
    setVotes(r.votes)
  }

  const applyDetected = async () => {
    const r = await postApi<AnyData>('/lab/style-learn/apply')
    if (!r.applied) { message.info(r.reason || '无法识别'); return }
    message.success(`已应用识别结果：${STYLE_LABEL[r.style]}`)
  }

  return (
    <div>
      <Paragraph type="secondary">M4E-04：可同时开启多个风格视图；第一个为主风格，次风格用于加权推荐。</Paragraph>
      <Select
        mode="multiple" style={{ minWidth: 420 }} value={styles} onChange={setStyles}
        options={Object.entries(STYLE_LABEL).map(([v, l]) => ({ value: v, label: l }))}
      />
      <Button type="primary" style={{ marginLeft: 12 }} onClick={save}>保存组合</Button>

      <Card style={{ marginTop: 16 }} title="M4E-05 风格学习（基于最近 300 条行为埋点）" size="small">
        <Space>
          <Button onClick={detect}>识别</Button>
          <Button type="primary" onClick={applyDetected}>应用识别结果</Button>
        </Space>
        {detected && (
          <Alert
            style={{ marginTop: 12 }}
            type="info" showIcon
            message={<span>识别风格：<b>{STYLE_LABEL[detected] || detected}</b></span>}
            description={
              <Space>
                {Object.entries(votes).map(([k, v]) => (
                  <Tag key={k}>{STYLE_LABEL[k] || k}: {v}</Tag>
                ))}
              </Space>
            }
          />
        )}
      </Card>
    </div>
  )
}

export default function LabPage() {
  return (
    <div>
      <Title level={3}>策略实验室</Title>
      <AIBadge style={{ marginBottom: 8 }} />
      <Alert
        type="warning"
        showIcon
        style={{ marginBottom: 12 }}
        message="蒙特卡洛模拟提示"
        description="当前为蒙特卡洛模拟数据（非真实回测），结果仅供策略思路参考"
      />
      <Disclaimer kind="backtest" />
      <Tabs
        items={[
          { key: 'compare', label: 'M3-07 策略对比', children: <CompareTab /> },
          { key: 'alerts', label: 'M4A-10 自定义打板规则', children: <AlertRulesTab /> },
          { key: 'style', label: 'M4E 多风格组合 / 学习', children: <StyleComboTab /> },
        ]}
      />
    </div>
  )
}
