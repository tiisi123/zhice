/**
 * DataStatusBadge — 数据状态徽标
 *
 * D-DATA-CONTRACT 决议要求 28 路由响应统一 `{source, data_status, mock}` 三字段，
 * S02 将由所有数据卡片消费此组件作为统一渲染入口；本组件由 S01/T06 先行落地，
 * S02 路由批量改造时直接套用即可。请勿在 S02 重复实现等价组件。
 *
 * 状态语义：
 *   real        — 数据源直返成功（默认 green）
 *   fallback    — 主源失败但有降级数据（orange，提示用户结果可能滞后/不全）
 *   unavailable — 数据源完全不可用（red，业主需要排障）
 *   empty       — 数据源响应为空（default，区别于不可用）
 *   mock=true   — 演示数据（强制 yellow + 文案 "演示数据"），优先级高于 status
 */

import { Tag, Tooltip } from 'antd'

export type DataStatus = 'real' | 'fallback' | 'unavailable' | 'empty'

export interface DataStatusBadgeProps {
  status: DataStatus
  source?: string
  mock?: boolean
  size?: 'small' | 'default'
}

const STATUS_COLOR: Record<DataStatus, string> = {
  real: 'green',
  fallback: 'orange',
  unavailable: 'red',
  empty: 'default',
}

const STATUS_LABEL: Record<DataStatus, string> = {
  real: '实时数据',
  fallback: '降级数据',
  unavailable: '数据源不可用',
  empty: '暂无数据',
}

const MOCK_COLOR = 'gold'
const MOCK_LABEL = '演示数据'

export default function DataStatusBadge({
  status,
  source,
  mock = false,
  size = 'default',
}: DataStatusBadgeProps) {
  const color = mock ? MOCK_COLOR : STATUS_COLOR[status]
  const label = mock ? MOCK_LABEL : STATUS_LABEL[status]
  const fontSize = size === 'small' ? 11 : 12

  const tag = (
    <Tag color={color} style={{ fontSize, marginInlineEnd: 0 }}>
      {label}
    </Tag>
  )

  if (!source) return tag

  return <Tooltip title={`数据源: ${source}`}>{tag}</Tooltip>
}
