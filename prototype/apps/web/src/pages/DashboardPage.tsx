import { useEffect, useState } from 'react'
import { Card, Row, Col, Button, Space, Input, Select, List, Tag, message, Empty, Modal, Alert } from 'antd'
import { PlusOutlined, DeleteOutlined, SaveOutlined, DragOutlined } from '@ant-design/icons'
import { fetchApi, postApi, deleteApi } from '../api/client'

interface Widget {
  key: string
  name: string
  tags: string[]
}

interface BoardListRow {
  id: number
  name: string
  is_default: number
  updated_at: string
}

interface BoardDetail {
  id: number
  name: string
  layout: string[]
  is_default: number
}

export default function DashboardPage() {
  const [widgets, setWidgets] = useState<Widget[]>([])
  const [boards, setBoards] = useState<BoardListRow[]>([])
  const [current, setCurrent] = useState<BoardDetail | null>(null)
  const [name, setName] = useState('我的看板')
  const [layout, setLayout] = useState<string[]>([])
  const [dragIndex, setDragIndex] = useState<number | null>(null)

  const refreshBoards = async () => {
    try {
      const r = await fetchApi<{ boards: BoardListRow[] }>('/dashboard/list')
      setBoards(r.boards)
    } catch (e: any) {
      message.error(e?.message || '加载看板列表失败')
    }
  }

  useEffect(() => {
    fetchApi<{ widgets: Widget[] }>('/dashboard/widgets')
      .then((r) => setWidgets(r.widgets))
      .catch((e: any) => message.error(e?.message || '加载组件库失败'))
    refreshBoards()
  }, [])

  const loadBoard = async (id: number) => {
    try {
      const r = await fetchApi<any>(`/dashboard/${id}`)
      const keys = (r.layout || []).map((i: any) => (typeof i === 'string' ? i : i.key)).filter(Boolean)
      setCurrent({ id: r.id, name: r.name, layout: keys, is_default: r.is_default })
      setName(r.name)
      setLayout(keys)
    } catch (e: any) {
      message.error(e?.message || '加载看板失败')
    }
  }

  const addWidget = (key: string) => {
    if (layout.includes(key)) { message.info('已添加'); return }
    if (layout.length >= 20) { message.warning('最多 20 个组件'); return }
    setLayout([...layout, key])
  }

  const removeWidget = (key: string) => setLayout(layout.filter((k) => k !== key))

  const save = async (isDefault = false) => {
    const payload = {
      id: current?.id,
      name: name.trim() || '未命名看板',
      layout: layout.map((k) => ({ key: k })),
      is_default: isDefault,
    }
    try {
      await postApi('/dashboard/save', payload)
      message.success('已保存')
      refreshBoards()
    } catch (e: any) {
      message.error(e?.message || '保存失败')
    }
  }

  const doDelete = async (id: number) => {
    Modal.confirm({
      title: '确认删除此看板？',
      onOk: async () => {
        await deleteApi(`/dashboard/${id}`)
        if (current?.id === id) { setCurrent(null); setLayout([]) }
        refreshBoards()
      },
    })
  }

  const widgetOf = (k: string) => widgets.find((w) => w.key === k)

  const onDragStart = (i: number) => () => setDragIndex(i)
  const onDragOver = (i: number) => (e: React.DragEvent) => { e.preventDefault() ; void i }
  const onDrop = (i: number) => (e: React.DragEvent) => {
    e.preventDefault()
    if (dragIndex === null || dragIndex === i) return
    const next = [...layout]
    const [m] = next.splice(dragIndex, 1)
    next.splice(i, 0, m)
    setLayout(next)
    setDragIndex(null)
  }

  return (
    <div>
      <Alert
        type="info"
        showIcon
        message="拖拽组件卡片即可调整顺序，最多 20 个，可保存为默认看板。"
        style={{ marginBottom: 16 }}
      />
      <Row gutter={16}>
        <Col xs={24} lg={6}>
          <Card title="我的看板" size="small" style={{ marginBottom: 12 }}>
            <List
              size="small"
              dataSource={boards}
              locale={{ emptyText: <Empty description="暂无看板" image={Empty.PRESENTED_IMAGE_SIMPLE} /> }}
              renderItem={(b) => (
                <List.Item
                  actions={[
                    <a key="load" onClick={() => loadBoard(b.id)}>加载</a>,
                    <a key="del" onClick={() => doDelete(b.id)}><DeleteOutlined /></a>,
                  ]}
                >
                  <Space>
                    {b.name}
                    {b.is_default ? <Tag color="gold">默认</Tag> : null}
                  </Space>
                </List.Item>
              )}
            />
            <Button block icon={<PlusOutlined />} style={{ marginTop: 12 }}
              onClick={() => { setCurrent(null); setLayout([]); setName('新看板') }}>
              新建
            </Button>
          </Card>
          <Card title="组件库" size="small">
            <Select
              showSearch
              style={{ width: '100%', marginBottom: 8 }}
              placeholder="搜索组件"
              options={widgets.map((w) => ({ value: w.key, label: `${w.name} · ${w.tags.join('/')}` }))}
              onChange={addWidget}
              optionFilterProp="label"
            />
            <List
              size="small"
              dataSource={widgets}
              renderItem={(w) => (
                <List.Item actions={[<a key="add" onClick={() => addWidget(w.key)}>加入</a>]}>
                  <Space>
                    <b>{w.name}</b>
                    {w.tags.map((t) => <Tag key={t}>{t}</Tag>)}
                  </Space>
                </List.Item>
              )}
            />
          </Card>
        </Col>

        <Col xs={24} lg={18}>
          <Card
            title={
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                style={{ width: 240 }}
                placeholder="看板名称"
              />
            }
            extra={
              <Space>
                <Button icon={<SaveOutlined />} onClick={() => save(false)}>保存</Button>
                <Button type="primary" icon={<SaveOutlined />} onClick={() => save(true)}>保存并设为默认</Button>
              </Space>
            }
          >
            {layout.length === 0 ? (
              <Empty description="从右侧组件库添加组件" />
            ) : (
              <Row gutter={[12, 12]}>
                {layout.map((k, i) => {
                  const w = widgetOf(k)
                  return (
                    <Col key={k} xs={24} md={12} xl={8}>
                      <div
                        draggable
                        onDragStart={onDragStart(i)}
                        onDragOver={onDragOver(i)}
                        onDrop={onDrop(i)}
                      >
                        <Card
                          size="small"
                          title={<Space><DragOutlined style={{ cursor: 'grab' }} />{w?.name || k}</Space>}
                          extra={<a onClick={() => removeWidget(k)}><DeleteOutlined /></a>}
                          style={{ height: 160 }}
                        >
                          <Space wrap>{w?.tags.map((t) => <Tag key={t}>{t}</Tag>)}</Space>
                          <div style={{ marginTop: 8, color: '#999', fontSize: 12 }}>
                            组件 Key: <code>{k}</code><br />
                            上线后自动渲染真实数据。
                          </div>
                        </Card>
                      </div>
                    </Col>
                  )
                })}
              </Row>
            )}
          </Card>
        </Col>
      </Row>
    </div>
  )
}
