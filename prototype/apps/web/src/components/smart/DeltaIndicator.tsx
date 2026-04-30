import { RiseOutlined, FallOutlined, MinusOutlined } from '@ant-design/icons'

interface Props {
  current: number
  prev?: number
  invert?: boolean
  suffix?: string
  precision?: number
}

export default function DeltaIndicator({ current, prev, invert, suffix = '', precision = 0 }: Props) {
  if (prev === undefined || prev === null || isNaN(prev)) return null
  const d = current - prev
  if (Math.abs(d) < 0.001) return <span style={{ color: '#999', fontSize: 12 }}><MinusOutlined /> 持平</span>
  const positive = d > 0
  const good = invert ? !positive : positive
  const color = good ? '#f5222d' : '#52c41a'
  const Icon = positive ? RiseOutlined : FallOutlined
  return (
    <span style={{ color, fontSize: 12 }}>
      <Icon /> {positive ? '+' : ''}{d.toFixed(precision)}{suffix}
    </span>
  )
}
