/**
 * useApiMeta — 从契约 API 响应抽取 ApiMeta 元数据
 *
 * M001/S02 D004 契约：所有数据路由响应统一携带 {data, source, data_status, mock, message}。
 * 本模块把任意响应抽象为 ApiMeta，前端组件（DataStatusBadge）按 SSOT 一致消费。
 *
 * 后端响应缺字段时 fallback 默认 {data_status:'empty', source:'unknown', mock:false}，
 * DataStatusBadge 显示 default 灰色 "暂无数据" —— 业主一眼看到契约掉链子。
 */

import type { ApiMeta, AnyData, DataStatus } from './types'

const VALID_STATUSES: ReadonlySet<string> = new Set([
  'real', 'mock', 'fallback', 'unavailable', 'empty', 'error',
])

function coerceStatus(status: unknown): DataStatus {
  return typeof status === 'string' && VALID_STATUSES.has(status)
    ? (status as DataStatus)
    : 'empty'
}

export function extractMeta(resp: AnyData | null | undefined, name?: string): ApiMeta {
  const meta: ApiMeta = {
    data_status: coerceStatus(resp?.data_status),
    source: typeof resp?.source === 'string' && resp.source ? resp.source : 'unknown',
    mock: Boolean(resp?.mock),
  }
  if (resp?.message) meta.message = String(resp.message)
  if (name !== undefined) meta.name = name
  return meta
}

export function extractMetaList(
  items: ReadonlyArray<{ name: string; resp: AnyData | null | undefined }>,
): ApiMeta[] {
  return items
    .filter(({ resp }) =>
      resp != null && (resp.source || resp.data_status || resp.mock !== undefined),
    )
    .map(({ name, resp }) => extractMeta(resp, name))
}
