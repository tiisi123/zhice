import { useEffect, useRef, useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { Card, Tabs, Form, Input, Button, message, Typography, Spin } from 'antd'
import { UserOutlined, LockOutlined, PhoneOutlined, SafetyOutlined } from '@ant-design/icons'
import { postApi } from '../api/client'
import { setAuth, type User } from '../api/auth'

const { Title, Paragraph } = Typography
const TEST_LOGIN = { phone: 'admin', password: 'Zhice@2026test' }
const AUTO_TEST_LOGIN = import.meta.env.DEV && import.meta.env.VITE_DISABLE_AUTO_LOGIN !== '1'

export default function LoginPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const [loading, setLoading] = useState(false)
  const [tab, setTab] = useState<'login' | 'register'>('login')
  const autoLoginStarted = useRef(false)

  const nextUrl = new URLSearchParams(location.search).get('next') || '/replay'

  const handleLogin = async (values: { phone: string; password: string }) => {
    setLoading(true)
    try {
      const res = await postApi<{ user: User; token: string }>('/auth/login', values)
      setAuth(res.token, res.user)
      message.success(`欢迎回来，${res.user.nickname}`)
      void navigate(nextUrl, { replace: true })
    } catch (e) {
      message.error((e as Error)?.message || '登录失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!AUTO_TEST_LOGIN || autoLoginStarted.current) return
    autoLoginStarted.current = true
    void handleLogin(TEST_LOGIN)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleRegister = async (values: { phone: string; password: string; nickname: string; invite_code: string }) => {
    setLoading(true)
    try {
      const res = await postApi<{ user: User; token: string }>('/auth/register', values)
      setAuth(res.token, res.user)
      message.success('注册成功，开始体验')
      void navigate('/onboarding', { replace: true })
    } catch (e) {
      message.error((e as Error)?.message || '注册失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: 'linear-gradient(135deg,#1e3c72 0%,#2a5298 100%)', padding: 24,
    }}>
      <Card style={{ width: 420, boxShadow: '0 10px 40px rgba(0,0,0,0.2)' }}>
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <Title level={2} style={{ margin: 0 }}>智策</Title>
          <Paragraph type="secondary" style={{ marginTop: 4 }}>AI 投研与策略中枢</Paragraph>
        </div>
        {AUTO_TEST_LOGIN && (
          <div style={{ textAlign: 'center', padding: '24px 0 8px' }}>
            <Spin />
            <Paragraph type="secondary" style={{ marginTop: 12 }}>正在进入内测环境</Paragraph>
          </div>
        )}
        {!AUTO_TEST_LOGIN && (
        <Tabs
          activeKey={tab}
          onChange={(k) => setTab(k as 'login' | 'register')}
          centered
          items={[
            {
              key: 'login',
              label: '登录',
              children: (
                <Form layout="vertical" onFinish={handleLogin} autoComplete="on">
                  <Form.Item name="phone" rules={[
                    { required: true, message: '请输入手机号/账号' },
                    { min: 2, message: '至少 2 个字符' },
                  ]}>
                    <Input size="large" prefix={<PhoneOutlined />} placeholder="手机号" />
                  </Form.Item>
                  <Form.Item name="password" rules={[
                    { required: true, message: '请输入密码' },
                    { min: 6, message: '至少 6 位' },
                  ]}>
                    <Input.Password size="large" prefix={<LockOutlined />} placeholder="密码" />
                  </Form.Item>
                  <Button type="primary" size="large" block htmlType="submit" loading={loading}>
                    登录
                  </Button>
                </Form>
              ),
            },
            {
              key: 'register',
              label: '注册',
              children: (
                <Form layout="vertical" onFinish={handleRegister}>
                  <Form.Item name="phone" rules={[
                    { required: true, message: '请输入手机号/账号' },
                    { pattern: /^[\w\d]{2,20}$/, message: '2-20位字母、数字或下划线' },
                  ]}>
                    <Input size="large" prefix={<PhoneOutlined />} placeholder="手机号" maxLength={20} />
                  </Form.Item>
                  <Form.Item name="nickname">
                    <Input size="large" prefix={<UserOutlined />} placeholder="昵称（可选）" />
                  </Form.Item>
                  <Form.Item name="password" rules={[
                    { required: true, message: '请输入密码' },
                    { min: 6, message: '至少 6 位' },
                  ]}>
                    <Input.Password size="large" prefix={<LockOutlined />} placeholder="密码（≥6 位）" />
                  </Form.Item>
                  <Form.Item name="invite_code" rules={[
                    { required: true, message: '请输入邀请码' },
                    { len: 6, message: '邀请码为 6 位' },
                  ]}>
                    <Input size="large" prefix={<SafetyOutlined />} placeholder="邀请码（6位）" maxLength={6}
                      style={{ textTransform: 'uppercase' }}
                      onChange={(e) => { e.target.value = e.target.value.toUpperCase() }}
                    />
                  </Form.Item>
                  <Button type="primary" size="large" block htmlType="submit" loading={loading}>
                    注册
                  </Button>
                </Form>
              ),
            },
          ]}
        />
        )}
        <Paragraph type="secondary" style={{ fontSize: 11, marginTop: 16, textAlign: 'center' }}>
          投资有风险，入市需谨慎。平台内容仅供研究参考。
        </Paragraph>
      </Card>
    </div>
  )
}
