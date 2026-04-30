import { useEffect, useState } from 'react'
import { Card, Button, Table, Select, InputNumber, Space, message, Tag, Typography } from 'antd'
import { CopyOutlined, PlusOutlined } from '@ant-design/icons'
import { fetchApi, postApi } from '../api/client'
import { getUser } from '../api/auth'

const { Title, Paragraph } = Typography

interface InviteCode {
  id: number
  code: string
  plan: string
  days: number
  max_uses: number
  used_count: number
  created_at: string
  expires_at: string | null
}

export default function AdminPage() {
  const [codes, setCodes] = useState<InviteCode[]>([])
  const [loading, setLoading] = useState(false)
  const [plan, setPlan] = useState<string>('standard')
  const [days, setDays] = useState(30)
  const [count, setCount] = useState(5)
  const [generating, setGenerating] = useState(false)

  const user = getUser()
  const isAdmin = user?.phone === 'admin' && user?.vip_level === 'pro'

  const loadCodes = async () => {
    setLoading(true)
    try {
      const r = await fetchApi<{ codes: InviteCode[] }>('/payment/admin/codes')
      setCodes(r.codes)
    } catch (e) {
      message.error((e as Error)?.message || '加载失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (isAdmin) void loadCodes()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const generate = async () => {
    setGenerating(true)
    try {
      const r = await postApi<{ codes: string[] }>('/payment/admin/generate-codes', {
        plan, days, count, max_uses: 1,
      })
      message.success(`已生成 ${r.codes.length} 个邀请码`)
      void loadCodes()
    } catch (e) {
      message.error((e as Error)?.message || '生成失败')
    } finally {
      setGenerating(false)
    }
  }

  const copyAll = () => {
    const unused = codes.filter(c => c.used_count < c.max_uses)
    if (!unused.length) { message.warning('没有可用的邀请码'); return }
    const text = unused.map(c => `${c.code}  (${c.plan} ${c.days}天)`).join('\n')
    void navigator.clipboard.writeText(text)
    message.success(`已复制 ${unused.length} 个未使用邀请码`)
  }

  if (!isAdmin) {
    return (
      <Card>
        <Title level={4}>无权限</Title>
        <Paragraph>此页面仅管理员可访问。请使用 admin 账户登录。</Paragraph>
      </Card>
    )
  }

  return (
    <div>
      <Title level={3}>邀请码管理</Title>

      <Card title="生成邀请码" size="small" style={{ marginBottom: 16 }}>
        <Space wrap>
          <Select value={plan} onChange={setPlan} style={{ width: 140 }}
            options={[
              { value: 'standard', label: '标准版' },
              { value: 'pro', label: '专业版' },
            ]}
          />
          <InputNumber value={days} onChange={v => setDays(v || 30)} min={1} max={365}
            addonAfter="天" style={{ width: 120 }} />
          <InputNumber value={count} onChange={v => setCount(v || 1)} min={1} max={100}
            addonAfter="个" style={{ width: 120 }} />
          <Button type="primary" icon={<PlusOutlined />} loading={generating} onClick={generate}>
            生成
          </Button>
          <Button icon={<CopyOutlined />} onClick={copyAll}>复制未使用</Button>
        </Space>
      </Card>

      <Card title={`邀请码列表 (${codes.length})`} size="small">
        <Table<InviteCode>
          dataSource={codes}
          rowKey="id"
          loading={loading}
          size="small"
          pagination={{ pageSize: 20 }}
          columns={[
            {
              title: '邀请码', dataIndex: 'code', width: 160,
              render: (v: string) => (
                <Space>
                  <code style={{ fontSize: 13 }}>{v}</code>
                  <CopyOutlined style={{ cursor: 'pointer', color: '#1677ff' }}
                    onClick={() => { void navigator.clipboard.writeText(v); message.success('已复制') }} />
                </Space>
              ),
            },
            {
              title: '套餐', dataIndex: 'plan', width: 100,
              render: (v: string) => <Tag color={v === 'pro' ? 'gold' : 'blue'}>{v.toUpperCase()}</Tag>,
            },
            { title: '天数', dataIndex: 'days', width: 70 },
            {
              title: '使用', width: 100,
              render: (_: unknown, r: InviteCode) => (
                <span style={{ color: r.used_count >= r.max_uses ? '#52c41a' : '#999' }}>
                  {r.used_count}/{r.max_uses}
                </span>
              ),
            },
            {
              title: '状态', width: 80,
              render: (_: unknown, r: InviteCode) =>
                r.used_count >= r.max_uses
                  ? <Tag color="green">已用</Tag>
                  : <Tag color="blue">可用</Tag>,
            },
            { title: '创建时间', dataIndex: 'created_at', width: 160 },
          ]}
        />
      </Card>
    </div>
  )
}
