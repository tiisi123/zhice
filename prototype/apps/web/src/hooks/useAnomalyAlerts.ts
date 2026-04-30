import { useEffect, useRef } from 'react'
import { notification } from 'antd'
import { watchlistApi } from '../api/watchlist'

const KIND_TYPE: Record<string, 'success' | 'warning' | 'error' | 'info'> = {
  limit_up: 'success',
  broken: 'warning',
  up: 'info',
  down: 'error',
  report: 'info',
  earnings: 'success',
  contract: 'success',
  ann: 'info',
}

const KIND_LABEL: Record<string, string> = {
  limit_up: '🔥 涨停',
  broken: '⚠️ 炸板',
  up: '📈 涨幅触发',
  down: '📉 跌幅触发',
  report: '📄 定期报告',
  earnings: '💰 业绩公告',
  contract: '📑 合同/中标',
  ann: '📢 公告',
}

/**
 * PRD US-004：价格异动提醒
 * 轮询 /watchlist/check-alerts，发现新增触发即通过 antd notification 弹出。
 *
 * 去重策略：按 (watch_id + kind) 在 sessionStorage 中记录已提醒的项目，
 * 避免同一会话内反复弹同一条；新交易日自然失效（key 中带 trade_date）。
 *
 * 关闭逻辑：未登录 / 研究池为空 / 用户在 settings 关闭时不会发起请求。
 */
export function useAnomalyAlerts(intervalMs = 30_000) {
  const stopRef = useRef(false)

  useEffect(() => {
    stopRef.current = false
    let timer: number | null = null
    const isLoggedIn = () => !!localStorage.getItem('zhice.token')
    const enabled = () => localStorage.getItem('zhice_alert_enabled') !== '0'

    const tick = async () => {
      if (stopRef.current || !isLoggedIn() || !enabled()) return
      try {
        const r = await watchlistApi.checkAlerts()
        if (!r.alerts?.length) return
        const seenKey = `zhice_alert_seen_${r.trade_date}`
        const seen: Record<string, 1> = JSON.parse(sessionStorage.getItem(seenKey) || '{}')
        let dirty = false
        for (const a of r.alerts) {
          const k = `${a.watch_id}:${a.kind}`
          if (seen[k]) continue
          seen[k] = 1
          dirty = true
          notification[KIND_TYPE[a.kind]]({
            message: `${KIND_LABEL[a.kind]} · ${a.name}`,
            description: a.message,
            placement: 'topRight',
            duration: 6,
            btn: undefined,
            onClick: () => { window.location.href = `/stock/${a.code}` },
          })
        }
        if (dirty) sessionStorage.setItem(seenKey, JSON.stringify(seen))
      } catch {
        // 静默：未登录或后端不可用都不打扰用户
      }
    }

    // 启动延迟 5s，避免与登录/初始化抢资源
    const startup = window.setTimeout(() => {
      tick()
      timer = window.setInterval(tick, intervalMs)
    }, 5_000)

    return () => {
      stopRef.current = true
      window.clearTimeout(startup)
      if (timer) window.clearInterval(timer)
    }
  }, [intervalMs])
}
