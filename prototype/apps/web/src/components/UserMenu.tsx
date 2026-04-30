import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Dropdown, Avatar, Button, Tag, Space } from 'antd'
import { UserOutlined, CrownOutlined, LogoutOutlined, DashboardOutlined, SettingOutlined, BulbOutlined } from '@ant-design/icons'
import { clearAuth, getUser, onAuthChange, type User } from '../api/auth'

function vipTag(level: User['vip_level']) {
  if (level === 'pro') return <Tag color="gold">专业版</Tag>
  if (level === 'standard') return <Tag color="blue">标准版</Tag>
  return <Tag>免费</Tag>
}

export default function UserMenu() {
  const navigate = useNavigate()
  const [user, setUser] = useState<User | null>(getUser())

  useEffect(() => {
    const off = onAuthChange((u) => setUser(u))
    return () => { off() }
  }, [])

  if (!user) {
    return <Button type="primary" onClick={() => navigate('/login')}>登录 / 注册</Button>
  }

  return (
    <Dropdown
      menu={{
        items: [
          { key: 'nickname', label: (<span>{user.nickname} · {user.phone}</span>), disabled: true },
          { key: 'vip-status', label: (<Space>{vipTag(user.vip_level)} {user.vip_expire_at ? `至 ${user.vip_expire_at.slice(0,10)}` : ''}</Space>), disabled: true },
          { type: 'divider' },
          { key: 'vip', icon: <CrownOutlined />, label: '升级 VIP', onClick: () => navigate('/vip') },
          { key: 'dashboard', icon: <DashboardOutlined />, label: '我的看板', onClick: () => navigate('/dashboard') },
          { key: 'onboarding', icon: <BulbOutlined />, label: '风格测试', onClick: () => navigate('/onboarding') },
          { key: 'settings', icon: <SettingOutlined />, label: '我的埋点', onClick: () => navigate('/settings') },
          { type: 'divider' },
          { key: 'logout', icon: <LogoutOutlined />, label: '退出登录', onClick: () => { clearAuth(); navigate('/login') } },
        ],
      }}
    >
      <Space style={{ cursor: 'pointer' }}>
        <Avatar size="small" icon={<UserOutlined />} />
        <span>{user.nickname}</span>
        {vipTag(user.vip_level)}
      </Space>
    </Dropdown>
  )
}
