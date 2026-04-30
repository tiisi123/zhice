import { fetchApi, postApi, patchApi, deleteApi } from './client'

export interface WatchItem {
  id: number
  code: string
  name: string
  group_name: string
  note: string
  alert_change_up: number | null
  alert_change_down: number | null
  alert_limit_up: boolean
  alert_broken: boolean
  created_at: string
}

export interface AlertHit {
  watch_id?: number
  code: string
  name: string
  group?: string
  kind: 'limit_up' | 'broken' | 'up' | 'down' | 'report' | 'earnings' | 'contract' | 'ann'
  message: string
  change_rate: number
  trade_date?: string
  ts: string
}

export const watchlistApi = {
  list: (group?: string) =>
    fetchApi<{ items: WatchItem[]; total: number; groups: string[] }>(
      group ? `/watchlist?group=${encodeURIComponent(group)}` : '/watchlist',
    ),
  add: (item: Partial<WatchItem> & { code: string }) =>
    postApi<{ ok: boolean; id: number }>('/watchlist', item),
  patch: (id: number, patch: Partial<WatchItem>) =>
    patchApi<{ ok: boolean }>(`/watchlist/${id}`, patch),
  remove: (id: number) => deleteApi<{ ok: boolean }>(`/watchlist/${id}`),
  checkAlerts: () =>
    fetchApi<{ alerts: AlertHit[]; checked: number; trade_date: string }>('/watchlist/check-alerts'),
  alertHistory: (days = 7) =>
    fetchApi<{ items: AlertHit[]; total: number }>(`/watchlist/alerts/history?days=${days}`),
}
