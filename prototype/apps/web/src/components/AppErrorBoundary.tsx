import React from 'react'
import { Alert, Button, Card } from 'antd'

interface State {
  hasError: boolean
  message: string
}

class AppErrorBoundary extends React.Component<React.PropsWithChildren, State> {
  state: State = { hasError: false, message: '' }

  static getDerivedStateFromError(error: Error): State {
    return {
      hasError: true,
      message: (error as Error)?.message || '未知错误',
    }
  }

  componentDidCatch(error: Error) {
    // Keep full stack in console for quick diagnosis.
    console.error('AppErrorBoundary:', error)
  }

  handleReload = () => {
    window.location.reload()
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24 }}>
          <Card style={{ maxWidth: 760, width: '100%' }}>
            <Alert
              type="error"
              showIcon
              message="页面渲染失败"
              description={this.state.message}
              style={{ marginBottom: 12 }}
            />
            <div style={{ display: 'flex', gap: 8 }}>
              <Button type="primary" onClick={this.handleReload}>刷新页面</Button>
              <Button onClick={() => window.location.assign('/')}>返回首页</Button>
            </div>
          </Card>
        </div>
      )
    }
    return this.props.children
  }
}

export default AppErrorBoundary
