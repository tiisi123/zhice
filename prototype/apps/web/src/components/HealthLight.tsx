/**
 * HealthLight — KPL 双健康灯
 *
 * M001/S03/T07 引入。三态硬色 hex 复用 D004 信号面板配色（绿 ok / 红 fail /
 * 灰 unknown / 橙 stale），仅在业主后台 /admin 健康监控 tab + KPL Cookie tab
 * 内使用。Tooltip 显示状态名 + lastOkAt（最近一次成功探测时间），故意不显示
 * cookie 字段以满足 ADR-013 redaction 约束。
 *
 * 状态语义：
 *   ok      — 最近探测 200（绿色 #52c41a）
 *   fail    — 探测失败（红色 #f5222d）
 *   unknown — APScheduler 还没探过，或 _HEALTH_CACHE 不可读（灰色 #bfbfbf）
 *   stale   — 探测时间已超过预期周期（橙色 #faad14；T05 _HEALTH_CACHE 暂不
 *             暴露 stale 字段，预留给 S08 业主 UAT 留证用）
 */
import { Tooltip } from 'antd'
import type { CSSProperties } from 'react'

export type HealthStatus = 'ok' | 'fail' | 'unknown' | 'stale'

export interface HealthLightProps {
  status: HealthStatus
  size?: 'sm' | 'md'
  label?: string
  lastOkAt?: string | null
}

const COLOR: Record<HealthStatus, string> = {
  ok: '#52c41a',
  fail: '#f5222d',
  unknown: '#bfbfbf',
  stale: '#faad14',
}

const STATUS_TEXT: Record<HealthStatus, string> = {
  ok: '正常',
  fail: '失败',
  unknown: '未知',
  stale: '过期',
}

export default function HealthLight({
  status,
  size = 'md',
  label,
  lastOkAt,
}: HealthLightProps) {
  const dimension = size === 'sm' ? 10 : 16
  const dotStyle: CSSProperties = {
    display: 'inline-block',
    width: dimension,
    height: dimension,
    borderRadius: '50%',
    backgroundColor: COLOR[status],
    boxShadow:
      status === 'ok'
        ? '0 0 6px rgba(82,196,26,0.6)'
        : status === 'fail'
          ? '0 0 6px rgba(245,34,45,0.6)'
          : 'none',
    verticalAlign: 'middle',
  }

  const tip = (
    <div>
      {label ? <div>{label}</div> : null}
      <div>状态: {STATUS_TEXT[status]}</div>
      {lastOkAt ? <div>最近成功: {lastOkAt}</div> : null}
    </div>
  )

  return (
    <Tooltip title={tip} placement="top">
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
        <span style={dotStyle} aria-label={`health-${status}`} role="status" />
        {label ? (
          <span style={{ fontSize: size === 'sm' ? 12 : 13 }}>{label}</span>
        ) : null}
      </span>
    </Tooltip>
  )
}
