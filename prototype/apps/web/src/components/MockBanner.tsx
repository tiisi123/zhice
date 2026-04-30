import { Alert } from 'antd'

interface Props {
  show: boolean
  style?: React.CSSProperties
}

export default function MockBanner({ show, style }: Props) {
  if (!show) return null
  return (
    <Alert
      type="warning"
      showIcon
      banner
      message="当前展示为示例数据（数据源暂不可用），仅供界面预览，不反映真实市场行情。"
      style={{ marginBottom: 12, ...style }}
    />
  )
}
