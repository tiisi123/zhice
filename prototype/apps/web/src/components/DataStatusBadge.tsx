/**
 * DataStatusBadge — 数据状态徽标
 *
 * M001/S02 D004 锁定 6 值 enum SSOT 来自 `src/api/types.ts::DataStatus`，
 * 与后端 `packages/shared/types.py::DataStatus` 一一对应。所有数据卡片消费此组件作为
 * 统一渲染入口，禁止 ad-hoc 实现等价组件。
 *
 * 状态语义（D004，参见 .gsd/DECISIONS.md::D004）：
 *   real        — 数据源直返成功（green）
 *   mock        — 演示/样例数据（gold，与 mock=true 互为充要条件）
 *   fallback    — 主源失败但有降级数据（orange，含 cache stale + Monte Carlo 降级）
 *   unavailable — 数据源完全不可用（red，业主需要排障）
 *   empty       — 数据源响应为空（default，区别于不可用）
 *   error       — 异常但已捕获（red，源可达但响应异常，区别于 unavailable=源不可达）
 *
 * boolean `mock` prop 与 status='mock' 等价；为兼容历史调用方，prop 仍优先（强制 gold/演示数据）。
 */

import { Tag, Tooltip } from 'antd'

import type { DataStatus } from '../api/types'

export type { DataStatus }

export interface DataStatusBadgeProps {
  status: DataStatus
  source?: string
  mock?: boolean
  size?: 'small' | 'default'
}

const STATUS_COLOR: Record<DataStatus, string> = {
  real: 'green',
  mock: 'gold',
  fallback: 'orange',
  unavailable: 'red',
  empty: 'default',
  error: 'red',
}

const STATUS_LABEL: Record<DataStatus, string> = {
  real: '实时数据',
  mock: '演示数据',
  fallback: '降级数据',
  unavailable: '数据源不可用',
  empty: '暂无数据',
  error: '数据异常',
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
