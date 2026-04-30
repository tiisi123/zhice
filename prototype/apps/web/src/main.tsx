import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { ConfigProvider, App as AntdApp, theme } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import 'dayjs/locale/zh-cn'
import dayjs from 'dayjs'
import './index.css'
import App from './App.tsx'
import AppErrorBoundary from './components/AppErrorBoundary'

dayjs.locale('zh-cn')

const themeConfig = {
  algorithm: theme.defaultAlgorithm,
  token: {
    colorPrimary: '#1677ff',
    colorSuccess: '#52c41a',
    colorWarning: '#faad14',
    colorError: '#f5222d',
    borderRadius: 6,
    fontFamily:
      "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'PingFang SC', 'Microsoft YaHei', sans-serif",
  },
  components: {
    Layout: { headerHeight: 56, headerPadding: '0 16px' },
    Table: { cellPaddingBlockSM: 6, cellPaddingInlineSM: 8 },
  },
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ConfigProvider locale={zhCN} theme={themeConfig}>
      <AntdApp>
        <AppErrorBoundary>
          <App />
        </AppErrorBoundary>
      </AntdApp>
    </ConfigProvider>
  </StrictMode>,
)
