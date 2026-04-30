import { useEffect, useState } from 'react'
import { Card, Row, Col, Button, Tag, Typography, Input, message, Descriptions, Space, Alert } from 'antd'
import { CrownOutlined, CheckOutlined, GiftOutlined } from '@ant-design/icons'
import { fetchApi, postApi } from '../api/client'
import { getUser, setUser, type User } from '../api/auth'

const { Title, Paragraph } = Typography

const FEATURES = {
  free: [
    '基础行情与盘中温度',
    '每日 1 次 AI 收盘复盘',
    '每日 3 次 AI 对话',
    '每日 2 次策略回测',
    '基础题材排行',
  ],
  standard: [
    '完整短线作战台（复盘+盯盘+题材+验证）',
    '情绪周期与仓位建议',
    '题材工坊（热力图+龙头梯队+事件时间线）',
    '连板天梯 + 接力分析',
    '每日 10 次 AI 复盘 + 50 次对话',
    '炸板风险雷达 + 归因分析',
    '次日观察池（可打板/可低吸/接力）',
    '龙虎榜资金验证',
    '研究池 + 价格异动提醒',
  ],
  pro: [
    '标准版全部功能',
    'AI 复盘 / 对话 / 回测 不限量',
    '历史相似日分析',
    '投委会 AI 备忘录生成',
    '策略参数优化 + 实验室',
    '成长景气 + 价值基本面工作台',
    '财报 AI 解读 + PDF 抽取',
    '自定义看板 + 报告归档',
    '盘中实时 WebSocket 推送',
    '专属客服',
  ],
}

export default function VipPage() {
  const [user, setLocalUser] = useState<User | null>(getUser())
  const [inviteCode, setInviteCode] = useState('')
  const [redeeming, setRedeeming] = useState(false)

  useEffect(() => {
    fetchApi<{ user: User }>('/auth/me')
      .then((r) => { setUser(r.user); setLocalUser(r.user) })
      .catch(() => {})
  }, [])

  const redeemCode = async () => {
    const code = inviteCode.trim()
    if (!code) { message.warning('请输入邀请码'); return }
    setRedeeming(true)
    try {
      const r = await postApi<{ message: string; user: User }>('/payment/redeem', { code })
      setUser(r.user)
      setLocalUser(r.user)
      message.success(r.message || '开通成功！')
      setInviteCode('')
    } catch (e: any) {
      message.error(e?.message || '兑换失败')
    } finally {
      setRedeeming(false)
    }
  }

  const tierCard = (tier: 'free' | 'standard' | 'pro', title: string, color: string) => (
    <Card
      title={<Space><CrownOutlined style={{ color }} />{title}</Space>}
      style={{ height: '100%' }}
      extra={user?.vip_level === tier && <Tag color="green">当前</Tag>}
    >
      {FEATURES[tier].map((f) => (
        <div key={f} style={{ margin: '6px 0' }}>
          <CheckOutlined style={{ color: '#52c41a', marginRight: 8 }} />
          {f}
        </div>
      ))}
    </Card>
  )

  return (
    <div>
      <Title level={3}>会员中心</Title>
      {user && (
        <Card style={{ marginBottom: 16 }}>
          <Descriptions column={4}>
            <Descriptions.Item label="昵称">{user.nickname}</Descriptions.Item>
            <Descriptions.Item label="手机">{user.phone}</Descriptions.Item>
            <Descriptions.Item label="当前等级">
              <Tag color={user.vip_level === 'pro' ? 'gold' : user.vip_level === 'standard' ? 'blue' : 'default'}>
                {user.vip_level.toUpperCase()}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="到期时间">{user.vip_expire_at || '—'}</Descriptions.Item>
          </Descriptions>
        </Card>
      )}

      <Card
        title={<span><GiftOutlined style={{ color: '#faad14' }} /> 邀请码兑换</span>}
        style={{ marginBottom: 16 }}
      >
        <Paragraph type="secondary">
          输入邀请码即可开通或续费 VIP。邀请码可从管理员或活动渠道获取。
        </Paragraph>
        <Space>
          <Input
            value={inviteCode}
            onChange={(e) => setInviteCode(e.target.value.toUpperCase())}
            onPressEnter={redeemCode}
            placeholder="请输入邀请码，如 ZC-A1B2C3D4"
            style={{ width: 280 }}
            maxLength={20}
          />
          <Button type="primary" loading={redeeming} onClick={redeemCode}>
            兑换
          </Button>
        </Space>
      </Card>

      <Row gutter={16}>
        <Col xs={24} md={8}>{tierCard('free', '免费版', '#999')}</Col>
        <Col xs={24} md={8}>{tierCard('standard', '标准版', '#1677ff')}</Col>
        <Col xs={24} md={8}>{tierCard('pro', '专业版', '#faad14')}</Col>
      </Row>

      <Alert
        type="info"
        showIcon
        style={{ marginTop: 16 }}
        message="邀请码内测"
        description="当前仅支持邀请码方式开通或续费 VIP。未开放真实微信/支付宝在线支付。"
      />
    </div>
  )
}
