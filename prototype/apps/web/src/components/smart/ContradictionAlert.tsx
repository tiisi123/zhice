import { Alert, Space } from 'antd'
import { WarningOutlined } from '@ant-design/icons'

export interface ContradictionRule {
  condition: boolean
  message: string
  severity: 'warning' | 'danger'
}

interface Props {
  rules: ContradictionRule[]
}

export default function ContradictionAlert({ rules }: Props) {
  const fired = rules.filter(r => r.condition)
  if (fired.length === 0) return null
  return (
    <Space direction="vertical" size={6} style={{ width: '100%', marginBottom: 12 }}>
      {fired.map((r, i) => (
        <Alert
          key={i}
          type={r.severity === 'danger' ? 'error' : 'warning'}
          showIcon
          icon={<WarningOutlined />}
          message={r.message}
          banner
          style={{ borderRadius: 6 }}
        />
      ))}
    </Space>
  )
}
