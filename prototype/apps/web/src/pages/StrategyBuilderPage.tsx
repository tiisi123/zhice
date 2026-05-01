import { useState } from 'react'
import {
  Card, Row, Col, Button, Space, Input, Select, InputNumber, Typography, Tag, Form, Divider, message, Tabs,
} from 'antd'
import { PlusOutlined, DeleteOutlined, ExperimentOutlined, CopyOutlined } from '@ant-design/icons'
import { postApi } from '../api/client'
import Disclaimer from '../components/Disclaimer'
import AIBadge from '../components/AIBadge'
import type { AnyData } from '../api/types'

const { Title, Paragraph } = Typography
const { TextArea } = Input

type Op = 'eq' | 'gte' | 'lte' | 'rank' | 'in'

interface Condition {
  id: number
  field: string
  op: Op
  value: string | number
}

const SELECT_FIELDS = [
  '连板次数', '题材热度', '龙头标签', '涨停原因', '板块', '换手率', '封单金额', '市值', '涨停类型', '昨炸板', '新题材',
]
const ENTRY_FIELDS = ['condition', '开盘涨幅', '成交额', '次日低开', '首次涨停', '分歧转一致', '二板确认']
const EXIT_FIELDS = ['止盈', '止损', '持有天数上限']
const POSITION_FIELDS = ['单票仓位', '总仓位上限']
const ENV_FIELDS = ['情绪评级', '大盘涨幅', '环境情绪']

const OP_LABEL: Record<Op, string> = {
  eq: '=', gte: '≥', lte: '≤', rank: '排名前', in: '∈',
}

let nextId = 1

function ConditionGroup({
  title, fields, conditions, setConditions,
}: {
  title: string
  fields: string[]
  conditions: Condition[]
  setConditions: (c: Condition[]) => void
}) {
  const add = () => setConditions([...conditions, { id: nextId++, field: fields[0], op: 'eq', value: '' }])
  const update = (id: number, patch: Partial<Condition>) =>
    setConditions(conditions.map((c) => (c.id === id ? { ...c, ...patch } : c)))
  const remove = (id: number) => setConditions(conditions.filter((c) => c.id !== id))

  return (
    <Card size="small" title={title} extra={<Button size="small" icon={<PlusOutlined />} onClick={add}>添加条件</Button>} style={{ marginBottom: 12 }}>
      {conditions.length === 0 && <div style={{ color: '#bbb' }}>暂无条件</div>}
      {conditions.map((c) => (
        <Space key={c.id} style={{ marginBottom: 8, width: '100%' }} size={8} wrap>
          <Select
            style={{ width: 140 }} value={c.field}
            onChange={(v) => update(c.id, { field: v })}
            options={fields.map((f) => ({ value: f, label: f }))}
          />
          <Select
            style={{ width: 90 }} value={c.op}
            onChange={(v) => update(c.id, { op: v })}
            options={(Object.keys(OP_LABEL) as Op[]).map((op) => ({ value: op, label: OP_LABEL[op] }))}
          />
          {typeof c.value === 'number' ? (
            <InputNumber style={{ width: 140 }} value={c.value} onChange={(v) => update(c.id, { value: v ?? 0 })} />
          ) : (
            <Input style={{ width: 180 }} value={String(c.value)} onChange={(e) => update(c.id, { value: e.target.value })} placeholder="值" />
          )}
          <Button type="text" icon={<DeleteOutlined />} onClick={() => remove(c.id)} />
        </Space>
      ))}
    </Card>
  )
}

function buildDSL(
  name: string,
  sel: Condition[], entry: Condition[], exit: Condition[], pos: Condition[], env: Condition[],
) {
  const toObj = (conds: Condition[]) => {
    const obj: Record<string, unknown> = {}
    for (const c of conds) {
      const val = c.value === '' ? '' : isNaN(Number(c.value)) ? c.value : Number(c.value)
      if (c.op === 'eq') {
        obj[c.field] = val
      } else {
        obj[c.field] = { [c.op]: val }
      }
    }
    return obj
  }
  return {
    name: name || '未命名策略',
    version: '1.0',
    select: toObj(sel),
    entry: toObj(entry),
    exit: toObj(exit),
    position: toObj(pos),
    environment: toObj(env),
  }
}

export default function StrategyBuilderPage() {
  const [name, setName] = useState('我的策略')
  const [sel, setSel] = useState<Condition[]>([
    { id: nextId++, field: '连板次数', op: 'gte', value: 3 },
    { id: nextId++, field: '龙头标签', op: 'eq', value: 'true' },
  ])
  const [entry, setEntry] = useState<Condition[]>([
    { id: nextId++, field: 'condition', op: 'eq', value: '分歧转一致' },
  ])
  const [exitC, setExitC] = useState<Condition[]>([
    { id: nextId++, field: '止盈', op: 'eq', value: 15 },
    { id: nextId++, field: '止损', op: 'eq', value: -5 },
    { id: nextId++, field: '持有天数上限', op: 'eq', value: 3 },
  ])
  const [pos, setPos] = useState<Condition[]>([
    { id: nextId++, field: '单票仓位', op: 'eq', value: 20 },
  ])
  const [env, setEnv] = useState<Condition[]>([])

  const [nlText, setNlText] = useState('')
  const [generating, setGenerating] = useState(false)

  const dsl = buildDSL(name, sel, entry, exitC, pos, env)

  const copy = async () => {
    await navigator.clipboard.writeText(JSON.stringify(dsl, null, 2))
    message.success('DSL 已复制')
  }

  const generateFromNL = async () => {
    if (!nlText.trim()) return
    setGenerating(true)
    try {
      const r = await postApi<{ dsl: string }>('/ai/strategy-dsl', { text: nlText })
      // AI 返回的 DSL 文本可以直接作为引用
      message.success('AI 生成完毕，已放入右侧预览')
      ;(navigator as AnyData).__zhice_ai_dsl = r.dsl
      try {
        const parsed = JSON.parse(r.dsl.trim().replace(/^```json|```$/g, '').trim())
        if (parsed.name) setName(parsed.name)
      } catch { /* ignore */ }
    } catch (e) {
      message.error((e as Error)?.message || '生成失败')
    } finally {
      setGenerating(false)
    }
  }

  return (
    <div>
      <Title level={3}>可视化策略构建器</Title>
      <Paragraph type="secondary">通过条件卡片拖拽式配置，实时生成标准化 DSL。也可结合 AI 自然语言生成。</Paragraph>
      <AIBadge style={{ marginBottom: 8 }} />
      <Disclaimer kind="ai" />

      <Row gutter={16}>
        <Col xs={24} md={14}>
          <Card size="small" style={{ marginBottom: 12 }}>
            <Form layout="inline">
              <Form.Item label="策略名">
                <Input value={name} onChange={(e) => setName(e.target.value)} style={{ width: 240 }} />
              </Form.Item>
            </Form>
          </Card>
          <ConditionGroup title="① 选股条件 (select)" fields={SELECT_FIELDS} conditions={sel} setConditions={setSel} />
          <ConditionGroup title="② 入场条件 (entry)" fields={ENTRY_FIELDS} conditions={entry} setConditions={setEntry} />
          <ConditionGroup title="③ 出场条件 (exit)" fields={EXIT_FIELDS} conditions={exitC} setConditions={setExitC} />
          <ConditionGroup title="④ 仓位 (position)" fields={POSITION_FIELDS} conditions={pos} setConditions={setPos} />
          <ConditionGroup title="⑤ 环境约束 (environment)" fields={ENV_FIELDS} conditions={env} setConditions={setEnv} />

          <Card size="small" title="AI 辅助：自然语言 → DSL" style={{ marginBottom: 12 }}>
            <TextArea rows={2} value={nlText} onChange={(e) => setNlText(e.target.value)} placeholder="例：3 连板龙头首次分歧低吸，止盈 15%，持 3 日" />
            <Button style={{ marginTop: 8 }} type="primary" loading={generating} onClick={generateFromNL}>生成 DSL</Button>
          </Card>
        </Col>

        <Col xs={24} md={10}>
          <Card
            size="small" title="实时 DSL 预览"
            extra={
              <Space>
                <Button size="small" icon={<CopyOutlined />} onClick={copy}>复制</Button>
                <Button size="small" type="primary" icon={<ExperimentOutlined />}
                  onClick={() => message.info('可将此 DSL 粘贴到回测页面调试运行')}>
                  去回测
                </Button>
              </Space>
            }
          >
            <Tabs
              size="small"
              items={[
                {
                  key: 'json',
                  label: 'JSON',
                  children: (
                    <pre style={{ fontSize: 12, background: '#f6f8fa', padding: 12, borderRadius: 4, maxHeight: 560, overflow: 'auto' }}>
                      {JSON.stringify(dsl, null, 2)}
                    </pre>
                  ),
                },
                {
                  key: 'summary',
                  label: '摘要',
                  children: (
                    <div style={{ lineHeight: 2 }}>
                      <div><Tag color="blue">选股</Tag>{sel.map((c) => `${c.field}${OP_LABEL[c.op]}${c.value}`).join('，') || '—'}</div>
                      <div><Tag color="cyan">入场</Tag>{entry.map((c) => `${c.field}${OP_LABEL[c.op]}${c.value}`).join('，') || '—'}</div>
                      <div><Tag color="green">出场</Tag>{exitC.map((c) => `${c.field}=${c.value}`).join('，') || '—'}</div>
                      <div><Tag color="purple">仓位</Tag>{pos.map((c) => `${c.field}=${c.value}%`).join('，') || '—'}</div>
                      <div><Tag color="orange">环境</Tag>{env.map((c) => `${c.field}${OP_LABEL[c.op]}${c.value}`).join('，') || '—'}</div>
                    </div>
                  ),
                },
              ]}
            />
            <Divider style={{ margin: '12px 0' }} />
            <Paragraph style={{ fontSize: 11, color: '#999', margin: 0 }}>
              生成的 DSL 遵循 packages/backtest/dsl_schema 规范，可直接提交策略回测引擎。
            </Paragraph>
          </Card>
        </Col>
      </Row>
    </div>
  )
}
