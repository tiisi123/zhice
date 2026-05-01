import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Card, Button, Input, Typography, Space, Tooltip, Divider, message } from 'antd'
import { CrownOutlined, LockOutlined, GiftOutlined } from '@ant-design/icons'
import { postApi, fetchApi } from '../api/client'
import { setUser, type User } from '../api/auth'

const { Title, Text, Paragraph } = Typography

const PLAN_MAP: Record<string, { name: string; price: string }> = {
  standard_month: { name: '标准版 · 月付', price: '¥99/月' },
  standard_year: { name: '标准版 · 年付', price: '¥888/年' },
  pro_month: { name: '专业版 · 月付', price: '¥199/月' },
  pro_year: { name: '专业版 · 年付', price: '¥1688/年' },
}

export default function CheckoutPage() {
  const [searchParams] = useSearchParams()
  const plan = searchParams.get('plan') || 'standard_month'
  const planInfo = PLAN_MAP[plan] || PLAN_MAP.standard_month

  const [redeemCode, setRedeemCode] = useState('')
  const [redeemLoading, setRedeemLoading] = useState(false)

  const handleRedeem = async () => {
    if (!redeemCode.trim()) {
      message.warning('请输入邀请码')
      return
    }
    setRedeemLoading(true)
    try {
      await postApi('/payment/redeem', { code: redeemCode.trim().toUpperCase() })
      message.success('开通成功')
      try {
        const me = await fetchApi<User>('/auth/me')
        setUser(me)
      } catch { /* user refresh best-effort */ }
    } catch (e) {
      message.error((e as Error)?.message || '兑换失败')
    } finally {
      setRedeemLoading(false)
    }
  }

  return (
    <div style={{ maxWidth: 520, margin: '0 auto' }}>
      <Title level={3} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <CrownOutlined style={{ color: '#faad14' }} /> 收银台
      </Title>

      <Card style={{ marginBottom: 24 }}>
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <div>
            <Text type="secondary">当前套餐</Text>
            <Title level={4} style={{ margin: '4px 0 0' }}>{planInfo.name}</Title>
            <Title level={2} style={{ margin: '8px 0 0', color: '#1677ff' }}>{planInfo.price}</Title>
          </div>

          <Divider style={{ margin: '8px 0' }} />

          <div>
            <Text type="secondary">支付方式</Text>
            <div style={{ marginTop: 8 }}>
              <Tooltip title="在线支付尚未接入真实通道，请使用邀请码兑换或联系客服">
                <Button type="primary" size="large" block disabled icon={<LockOutlined />}>
                  在线支付（内测中）
                </Button>
              </Tooltip>
            </div>
          </div>
        </Space>
      </Card>

      <Card title={<span><GiftOutlined /> 邀请码兑换</span>}>
        <Paragraph type="secondary">输入管理员提供的邀请码，可直接开通会员权益</Paragraph>
        <Space.Compact style={{ width: '100%' }}>
          <Input
            placeholder="请输入 6 位邀请码"
            maxLength={6}
            value={redeemCode}
            onChange={(e) => setRedeemCode(e.target.value.toUpperCase())}
            style={{ textTransform: 'uppercase' }}
            onPressEnter={handleRedeem}
          />
          <Button type="primary" loading={redeemLoading} onClick={handleRedeem}>
            兑换
          </Button>
        </Space.Compact>
      </Card>
    </div>
  )
}
