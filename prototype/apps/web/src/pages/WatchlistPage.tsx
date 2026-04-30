import { useEffect, useState } from 'react'
import {
  Card, Table, Button, Modal, Form, Input, InputNumber, Switch, Select,
  Tag, Space, Popconfirm, message, Empty, Alert,
} from 'antd'
import { PlusOutlined, ReloadOutlined, EyeOutlined, BellOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons'
import { Link } from 'react-router-dom'
import { watchlistApi, type WatchItem, type AlertHit } from '../api/watchlist'
import AIDisclaimer from '../components/AIDisclaimer'

const KIND_TAG: Record<string, { color: string; label: string }> = {
  limit_up: { color: 'red', label: '涨停' },
  broken: { color: 'orange', label: '炸板' },
  up: { color: 'magenta', label: '涨幅' },
  down: { color: 'green', label: '跌幅' },
  report: { color: 'blue', label: '定期报告' },
  earnings: { color: 'gold', label: '业绩' },
  contract: { color: 'cyan', label: '合同' },
  ann: { color: 'default', label: '公告' },
}

export default function WatchlistPage() {
  const [items, setItems] = useState<WatchItem[]>([])
  const [groups, setGroups] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [filterGroup, setFilterGroup] = useState<string>('')
  const [editing, setEditing] = useState<WatchItem | null>(null)
  const [showModal, setShowModal] = useState(false)
  const [alerts, setAlerts] = useState<AlertHit[]>([])
  const [history, setHistory] = useState<AlertHit[]>([])
  const [form] = Form.useForm()

  const load = () => {
    setLoading(true)
    watchlistApi.list(filterGroup || undefined)
      .then(r => { setItems(r.items); setGroups(r.groups) })
      .catch(() => message.error('加载研究池失败，请确认已登录'))
      .finally(() => setLoading(false))
  }
  const checkAlerts = () => {
    watchlistApi.checkAlerts()
      .then(r => setAlerts(r.alerts))
      .catch(() => setAlerts([]))
  }
  const loadHistory = () => {
    watchlistApi.alertHistory(7)
      .then(r => setHistory(r.items || []))
      .catch(() => setHistory([]))
  }
  useEffect(() => { load() }, [filterGroup])  // eslint-disable-line
  useEffect(() => { checkAlerts(); loadHistory() }, [items.length])  // eslint-disable-line

  const openAdd = () => { setEditing(null); form.resetFields(); setShowModal(true) }
  const openEdit = (it: WatchItem) => {
    setEditing(it)
    form.setFieldsValue({
      ...it,
      alert_change_up: it.alert_change_up ?? undefined,
      alert_change_down: it.alert_change_down ?? undefined,
    })
    setShowModal(true)
  }
  const submit = async () => {
    const v = await form.validateFields()
    try {
      if (editing) {
        await watchlistApi.patch(editing.id, v)
        message.success('已更新')
      } else {
        await watchlistApi.add(v)
        message.success('已加入研究池')
      }
      setShowModal(false)
      load()
    } catch (e: any) {
      message.error(e?.message || '保存失败')
    }
  }
  const remove = async (id: number) => {
    await watchlistApi.remove(id)
    message.success('已移除')
    load()
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h2 style={{ margin: 0 }}><EyeOutlined style={{ color: '#1677ff' }} /> 研究池（RE-004）</h2>
        <Space>
          <Select
            placeholder="全部分组"
            allowClear
            style={{ width: 140 }}
            value={filterGroup || undefined}
            onChange={v => setFilterGroup(v || '')}
            options={groups.map(g => ({ value: g, label: g }))}
          />
          <Button icon={<ReloadOutlined />} onClick={load}>刷新</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={openAdd}>加入研究池</Button>
        </Space>
      </div>

      {/* 当前生效的异动提醒 */}
      <Card
        size="small"
        style={{ marginBottom: 16 }}
        title={<span><BellOutlined style={{ color: '#fa541c' }} /> 当前异动（US-004）· {alerts.length} 条</span>}
        extra={<Button size="small" onClick={checkAlerts}>立即扫描</Button>}
      >
        {alerts.length === 0 ? (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="当前研究池无异动触发" />
        ) : (
          <Space wrap>
            {alerts.map((a, i) => (
              <Link key={i} to={`/stock/${a.code}`}>
                <Tag color={KIND_TAG[a.kind].color}>
                  {KIND_TAG[a.kind].label} · {a.name} · {a.message}
                </Tag>
              </Link>
            ))}
          </Space>
        )}
      </Card>

      {/* 近 7 日命中历史（来自调度器持久化） */}
      <Card
        size="small" style={{ marginBottom: 16 }}
        title={<span><BellOutlined style={{ color: '#1677ff' }} /> 近 7 日命中历史 · {history.length} 条</span>}
        extra={<Button size="small" onClick={loadHistory}>刷新</Button>}
      >
        {history.length === 0 ? (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="近 7 日无持久化命中（调度器交易时段每分钟扫一次）" />
        ) : (
          <Table<AlertHit>
            dataSource={history.slice(0, 30)}
            rowKey={(r: AlertHit) => `${r.code}-${r.kind}-${r.trade_date}-${r.ts}`}
            size="small" pagination={false}
            columns={[
              { title: '日期', dataIndex: 'trade_date', width: 100 },
              { title: '时间', dataIndex: 'ts', width: 80 },
              {
                title: '类型', dataIndex: 'kind', width: 100,
                render: (k: string) => <Tag color={KIND_TAG[k]?.color || 'default'}>{KIND_TAG[k]?.label || k}</Tag>,
              },
              {
                title: '股票', dataIndex: 'code', width: 140,
                render: (c, r) => <Link to={`/stock/${c}`}>{r.name || c}</Link>,
              },
              { title: '消息', dataIndex: 'message', ellipsis: true },
            ]}
          />
        )}
      </Card>

      <Card size="small">
        <Table<WatchItem>
          loading={loading}
          rowKey="id"
          dataSource={items}
          size="small"
          pagination={{ pageSize: 20 }}
          locale={{ emptyText: <Empty description="研究池为空，点击右上「加入研究池」开始" /> }}
          columns={[
            {
              title: '股票', dataIndex: 'code', width: 160,
              render: (_, r) => (
                <Link to={`/stock/${r.code}`}><b>{r.name || r.code}</b> <span style={{ color: '#999', fontSize: 12 }}>{r.code}</span></Link>
              ),
            },
            { title: '分组', dataIndex: 'group_name', width: 100, render: g => <Tag>{g}</Tag> },
            { title: '备注', dataIndex: 'note', ellipsis: true },
            {
              title: '涨幅触发', dataIndex: 'alert_change_up', width: 100,
              render: v => v == null ? <span style={{ color: '#bbb' }}>—</span> : <Tag color="red">≥ {v}%</Tag>,
            },
            {
              title: '跌幅触发', dataIndex: 'alert_change_down', width: 100,
              render: v => v == null ? <span style={{ color: '#bbb' }}>—</span> : <Tag color="green">≤ -{Math.abs(v)}%</Tag>,
            },
            {
              title: '涨停', dataIndex: 'alert_limit_up', width: 60,
              render: v => v ? <Tag color="red">开</Tag> : <Tag>关</Tag>,
            },
            {
              title: '炸板', dataIndex: 'alert_broken', width: 60,
              render: v => v ? <Tag color="orange">开</Tag> : <Tag>关</Tag>,
            },
            {
              title: '操作', width: 130,
              render: (_, r) => (
                <Space>
                  <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(r)}>编辑</Button>
                  <Popconfirm title="确认移除？" onConfirm={() => remove(r.id)}>
                    <Button size="small" danger icon={<DeleteOutlined />} />
                  </Popconfirm>
                </Space>
              ),
            },
          ]}
        />
      </Card>

      <Alert
        type="info" showIcon style={{ marginTop: 12 }}
        message="提醒会以右上角通知方式弹出"
        description="未登录或将本地 zhice_alert_enabled 设为 0 可关闭。轮询周期 30 秒，命中后同会话同事件不重复。"
      />
      <AIDisclaimer variant="inline" />

      <Modal
        title={editing ? '编辑研究池条目' : '加入研究池'}
        open={showModal}
        onCancel={() => setShowModal(false)}
        onOk={submit}
        okText="保存"
        destroyOnClose
      >
        <Form form={form} layout="vertical" initialValues={{
          group_name: '默认', alert_limit_up: true, alert_broken: true,
        }}>
          <Form.Item label="股票代码" name="code" rules={[{ required: true, len: 6, message: '6 位代码' }]}>
            <Input placeholder="如 600519" disabled={!!editing} />
          </Form.Item>
          <Form.Item label="股票名称" name="name">
            <Input placeholder="如 贵州茅台" />
          </Form.Item>
          <Form.Item label="分组" name="group_name">
            <Input placeholder="如 龙头池/储备池/观察池" />
          </Form.Item>
          <Form.Item label="备注" name="note">
            <Input.TextArea rows={2} placeholder="逻辑/位置/止损位等" />
          </Form.Item>
          <Form.Item label="涨幅触发阈值（%）" name="alert_change_up" tooltip="涨幅达到该百分比即提醒，留空表示不监控">
            <InputNumber style={{ width: '100%' }} placeholder="如 5" min={0} max={20} step={0.5} />
          </Form.Item>
          <Form.Item label="跌幅触发阈值（%）" name="alert_change_down" tooltip="跌幅达到该绝对值即提醒，输入正数即可">
            <InputNumber style={{ width: '100%' }} placeholder="如 5" min={0} max={20} step={0.5} />
          </Form.Item>
          <Space>
            <Form.Item label="涨停提醒" name="alert_limit_up" valuePropName="checked">
              <Switch />
            </Form.Item>
            <Form.Item label="炸板提醒" name="alert_broken" valuePropName="checked">
              <Switch />
            </Form.Item>
          </Space>
        </Form>
      </Modal>
    </div>
  )
}
