import { Progress, Tooltip } from 'antd'

interface Props {
  title: string
  value: number
  max?: number
  suffix?: string
  tooltip?: string
  thresholds?: { value: number; color: string }[]
}

const DEFAULT_THRESHOLDS = [
  { value: 30, color: '#52c41a' },
  { value: 60, color: '#faad14' },
  { value: 100, color: '#f5222d' },
]

export default function MetricGauge({ title, value, max = 100, suffix = '%', tooltip, thresholds = DEFAULT_THRESHOLDS }: Props) {
  const pct = Math.min((value / max) * 100, 100)
  const color = thresholds.reduce((c, t) => (pct <= t.value ? c || t.color : t.color), '' as string) || '#1677ff'

  const inner = (
    <div style={{ textAlign: 'center' }}>
      <div style={{ fontSize: 11, color: '#999', marginBottom: 4 }}>{title}</div>
      <Progress
        type="dashboard"
        percent={pct}
        size={80}
        strokeColor={color}
        format={() => <span style={{ fontSize: 16, fontWeight: 700, color }}>{value}{suffix}</span>}
      />
    </div>
  )
  return tooltip ? <Tooltip title={tooltip}>{inner}</Tooltip> : inner
}
