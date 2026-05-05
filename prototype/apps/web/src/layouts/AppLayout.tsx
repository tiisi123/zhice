import { useEffect, useState, useMemo } from 'react'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { Layout, Menu, Button, Space, Grid } from 'antd'
import {
  DashboardOutlined, BarChartOutlined, StockOutlined,
  ExperimentOutlined, RobotOutlined, WarningOutlined,
  RiseOutlined, FundOutlined,
  CrownOutlined, AppstoreOutlined,
  BuildOutlined,
  EyeOutlined,
  FireOutlined,
  ApartmentOutlined,
} from '@ant-design/icons'
import AICopilot from '../components/AICopilot'
import UserMenu from '../components/UserMenu'
import { track } from '../api/tracking'
import { useHotkeys } from '../hooks/useHotkeys'
import { useAnomalyAlerts } from '../hooks/useAnomalyAlerts'

const { Sider, Header, Content } = Layout

const menuItems = [
  { key: 'short', label: '短线', type: 'group' as const, children: [
    { key: '/replay', icon: <DashboardOutlined />, label: '收盘复盘' },
    { key: '/intraday', icon: <BarChartOutlined />, label: '盘中盯盘' },
  ]},
  { key: 'hot', label: '热点', type: 'group' as const, children: [
    { key: '/theme-workshop', icon: <FireOutlined />, label: '题材工坊' },
    { key: '/event-chain', icon: <ApartmentOutlined />, label: '事件链' },
    { key: '/verification', icon: <WarningOutlined />, label: '验证中心' },
  ]},
  { key: 'growth', label: '成长', type: 'group' as const, children: [
    { key: '/gv-overview', icon: <DashboardOutlined />, label: '投研总览' },
    { key: '/growth-workshop', icon: <RiseOutlined />, label: '成长景气' },
  ]},
  { key: 'value', label: '价值', type: 'group' as const, children: [
    { key: '/value-workshop', icon: <FundOutlined />, label: '价值基本面' },
  ]},
  { key: 'tools', label: '工具', type: 'group' as const, children: [
    { key: '/tools-home', icon: <AppstoreOutlined />, label: '投研工具台' },
    { key: '/stock-research', icon: <StockOutlined />, label: '标的研究' },
    { key: '/research-pool', icon: <EyeOutlined />, label: '研究池' },
    { key: '/strategy-workshop', icon: <ExperimentOutlined />, label: '策略工坊' },
    { key: '/ai-agent', icon: <RobotOutlined />, label: 'AI 投研Agent' },
    { key: '/my-workspace', icon: <BuildOutlined />, label: '我的工作台' },
    { key: '/account/membership', icon: <CrownOutlined />, label: '会员' },
  ]},
  { key: 'ops', label: '运营管理', type: 'group' as const, children: [
    { key: '/feature-map', icon: <EyeOutlined />, label: '功能地图' },
    { key: '/admin', icon: <CrownOutlined />, label: '邀请码管理' },
  ]},
]

function getSelectedKey(pathname: string): string[] {
  if (pathname.startsWith('/stock-research') || pathname.startsWith('/stock') || pathname === '/chain') return ['/stock-research']
  if (pathname.startsWith('/research-pool') || pathname === '/watchlist') return ['/research-pool']
  if (pathname.startsWith('/strategy-workshop') || pathname === '/strategy' || pathname === '/strategy-builder'
      || pathname === '/advanced-strategy' || pathname === '/recommend' || pathname === '/lab') return ['/strategy-workshop']
  if (pathname.startsWith('/my-workspace') || pathname === '/dashboard' || pathname === '/report-archive') return ['/my-workspace']
  if (pathname === '/vip' || pathname.startsWith('/membership') || pathname.startsWith('/account/membership')) return ['/account/membership']
  // 短线作战工作台映射
  if (pathname === '/sentiment') return ['/replay']
  if (pathname.startsWith('/theme-workshop') || pathname.startsWith('/theme')
      || pathname === '/hot-events' || pathname === '/rotation') return ['/theme-workshop']
  if (pathname.startsWith('/verification') || pathname === '/broken-cases'
      || pathname === '/longhu') return ['/verification']
  // 成长/价值工作台映射
  if (pathname === '/growth' || pathname === '/prosperity' || pathname === '/etf-rotation'
      || pathname.startsWith('/growth-workshop')) return ['/growth-workshop']
  if (pathname === '/value' || pathname === '/valuation' || pathname === '/finance-compare'
      || pathname === '/finance-report' || pathname === '/research'
      || pathname.startsWith('/value-workshop')) return ['/value-workshop']
  return [pathname]
}

const { useBreakpoint } = Grid

export default function AppLayout() {
  const navigate = useNavigate()
  const location = useLocation()
  const [copilotOpen, setCopilotOpen] = useState(false)
  const screens = useBreakpoint()
  const isMobile = !screens.md
  const [collapsed, setCollapsed] = useState(false)
  // ?embed=1 嵌入模式（功能地图等场景）：隐藏 Sider / Header / 底部，仅渲染内容主体
  const isEmbed = useMemo(() => new URLSearchParams(location.search).get('embed') === '1', [location.search])

  // 全局快捷键 1-9 / ?
  useHotkeys()
  // 价格异动提醒（PRD US-004）：30s 轮询研究池
  useAnomalyAlerts(30_000)

  // 移动端默认折叠
  useEffect(() => {
    setCollapsed(isMobile)
  }, [isMobile])

  // 监听全局 askAI 事件：自动打开 Copilot 抽屉
  useEffect(() => {
    const handler = () => setCopilotOpen(true)
    window.addEventListener('zhice:ai-ask', handler)
    return () => window.removeEventListener('zhice:ai-ask', handler)
  }, [])

  const selectedKeys = useMemo(() => getSelectedKey(location.pathname), [location.pathname])

  useEffect(() => {
    track('page_view', location.pathname)
  }, [location.pathname])

  // 嵌入模式：去掉所有外壳，仅渲染内容（功能地图 iframe 用）
  if (isEmbed) {
    return (
      <div style={{ padding: 16, background: '#fff', minHeight: '100vh' }}>
        <Outlet />
      </div>
    )
  }

  return (
    <Layout style={{ minHeight: '100vh', background: '#f5f6f8' }}>
      <Sider
        width={200}
        collapsedWidth={isMobile ? 0 : 64}
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        breakpoint="md"
        theme="light"
        style={{
          overflow: 'auto',
          position: isMobile ? 'fixed' : 'sticky',
          top: 0, left: 0, height: '100vh', zIndex: 100,
          background: '#fff',
          borderRight: '1px solid #f0f0f0',
        }}
      >
        <div style={{
          height: 48, margin: '16px 16px 8px', color: '#1677ff', fontSize: 18, fontWeight: 700,
          whiteSpace: 'nowrap', overflow: 'hidden', letterSpacing: 2,
        }}>
          {collapsed ? '智' : '智策'}
        </div>
        <Menu
          theme="light"
          mode="inline"
          selectedKeys={selectedKeys}
          items={menuItems}
          onClick={({ key }) => { void navigate(key); if (isMobile) setCollapsed(true) }}
          style={{ borderRight: 'none' }}
        />
      </Sider>
      <Layout style={{ background: '#f5f6f8' }}>
        <Header style={{
          background: '#fff', padding: '0 16px', borderBottom: '1px solid #f0f0f0',
          display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 8,
        }}>
          <Space size={8}>
            <Button type="primary" icon={<RobotOutlined />} onClick={() => { track('open_copilot', location.pathname); setCopilotOpen(true) }}>
              {isMobile ? '' : 'AI Copilot'}
            </Button>
            <UserMenu />
          </Space>
        </Header>
        <Content style={{ margin: isMobile ? 8 : 16, padding: isMobile ? 12 : 20, background: '#fff', borderRadius: 8, overflow: 'auto' }}>
          <Outlet />
        </Content>
        <div style={{ textAlign: 'center', padding: '8px 16px', color: '#999', fontSize: 11, borderTop: '1px solid #f0f0f0' }}>
          免责声明：本平台所有数据、分析及AI生成内容仅供研究参考，不构成任何投资建议。投资有风险，入市需谨慎。
        </div>
      </Layout>
      <AICopilot open={copilotOpen} onClose={() => setCopilotOpen(false)} currentPage={location.pathname} />
    </Layout>
  )
}
