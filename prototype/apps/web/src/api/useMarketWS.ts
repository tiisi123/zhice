import { useEffect, useRef, useState, useCallback } from 'react'
import type { LimitUpStock, AnyData } from './types'

interface MarketWSData {
  limitUp: LimitUpStock[]
  broken: LimitUpStock[]
  hot: AnyData[]
  anomaly: AnyData[]
  connected: boolean
}

function getWsUrl(): string {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${location.host}/api/ws/market`
}

const MAX_RECONNECT_DELAY = 10_000
const INITIAL_RECONNECT_DELAY = 1_000

function payloadData<T>(value: unknown): T[] {
  if (!value || typeof value !== 'object') return []
  const data = (value as { data?: unknown }).data
  return Array.isArray(data) ? data as T[] : []
}

function toNumber(value: unknown, fallback: unknown = 0): number {
  const n = Number(value)
  if (Number.isFinite(n)) return n
  const f = Number(fallback)
  return Number.isFinite(f) ? f : 0
}

function normalizeMarketItem<T>(item: T): T {
  const it = item as AnyData
  return {
    ...it,
    stock_code: it.stock_code ?? it.SecurityCode,
    stock_name: it.stock_name ?? it.SecurityName,
    first_plate_name: it.first_plate_name ?? it.PlateName ?? it.plate_name ?? it.concept_name,
    change_rate: toNumber(it.change_rate ?? it.ChangePercent, it.change_rate),
    board_count: toNumber(it.board_count, it.board_count),
  } as T
}

export function useMarketWS(enabled: boolean): MarketWSData {
  const [limitUp, setLimitUp] = useState<LimitUpStock[]>([])
  const [broken, setBroken] = useState<LimitUpStock[]>([])
  const [hot, setHot] = useState<AnyData[]>([])
  const [anomaly, setAnomaly] = useState<AnyData[]>([])
  const [connected, setConnected] = useState(false)

  const wsRef = useRef<WebSocket | null>(null)
  const reconnectDelay = useRef(INITIAL_RECONNECT_DELAY)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const enabledRef = useRef(enabled)
  enabledRef.current = enabled

  const cleanup = useCallback(() => {
    if (reconnectTimer.current) {
      clearTimeout(reconnectTimer.current)
      reconnectTimer.current = null
    }
    if (wsRef.current) {
      wsRef.current.onopen = null
      wsRef.current.onmessage = null
      wsRef.current.onclose = null
      wsRef.current.onerror = null
      wsRef.current.close()
      wsRef.current = null
    }
    setConnected(false)
  }, [])

  const connect = useCallback(() => {
    if (!enabledRef.current) return
    cleanup()

    const ws = new WebSocket(getWsUrl())
    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
      reconnectDelay.current = INITIAL_RECONNECT_DELAY
    }

    ws.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data)
        if (msg.type === 'market_update' && msg.data) {
          const d = msg.data
          if (d.limit_up) setLimitUp(payloadData<LimitUpStock>(d.limit_up).map(normalizeMarketItem))
          if (d.broken) setBroken(payloadData<LimitUpStock>(d.broken).map(normalizeMarketItem))
          if (d.hot) setHot(payloadData<AnyData>(d.hot).map(normalizeMarketItem))
          if (d.anomaly) setAnomaly(payloadData<AnyData>(d.anomaly).map(normalizeMarketItem))
        }
      } catch {
        // ignore malformed messages
      }
    }

    ws.onclose = () => {
      setConnected(false)
      if (enabledRef.current) {
        reconnectTimer.current = setTimeout(() => {
          reconnectDelay.current = Math.min(reconnectDelay.current * 2, MAX_RECONNECT_DELAY)
          connect()
        }, reconnectDelay.current)
      }
    }

    ws.onerror = () => {
      ws.close()
    }
  }, [cleanup])

  useEffect(() => {
    if (enabled) {
      connect()
    } else {
      cleanup()
    }
    return cleanup
  }, [enabled, connect, cleanup])

  return { limitUp, broken, hot, anomaly, connected }
}
