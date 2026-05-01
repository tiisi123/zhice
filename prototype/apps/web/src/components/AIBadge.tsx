import { Tag, Tooltip } from 'antd'
import type { CSSProperties } from 'react'

export default function AIBadge({ style }: { style?: CSSProperties }) {
  return (
    <Tooltip title="以上为 AI 辅助分析，请结合自身判断 · 仅供参考 · 非投资建议">
      <Tag color="blue" style={style}>AI 辅助生成</Tag>
    </Tooltip>
  )
}
