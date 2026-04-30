import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { message } from 'antd'

/**
 * PRD 操作员快捷键（覆盖打板/短线 5 大高频场景）
 *  1 → 收盘复盘   2 → 盘中盯盘   3 → 情绪周期   4 → 题材板块
 *  5 → 个股分析   6 → 策略回测   7 → 龙虎榜     8 → 报告存档
 *  9 → 功能地图   /  → 全局搜索（聚焦顶部搜索框，若有）
 *  ?  → 显示快捷键帮助
 *
 * 仅在非输入控件聚焦时生效，避免干扰填写。
 */
export const HOTKEY_MAP: Record<string, { path: string; label: string }> = {
  '1': { path: '/replay', label: '收盘复盘' },
  '2': { path: '/intraday', label: '盘中盯盘' },
  '3': { path: '/sentiment', label: '情绪周期' },
  '4': { path: '/theme', label: '题材板块' },
  '5': { path: '/stock', label: '个股分析' },
  '6': { path: '/strategy', label: '策略回测' },
  '7': { path: '/longhu', label: '龙虎榜' },
  '8': { path: '/report-archive', label: '报告存档' },
  '9': { path: '/feature-map', label: '功能地图' },
  '0': { path: '/watchlist', label: '研究池' },
}

function isEditableTarget(t: EventTarget | null): boolean {
  if (!t) return false
  const el = t as HTMLElement
  if (!el.tagName) return false
  const tag = el.tagName.toUpperCase()
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true
  if (el.isContentEditable) return true
  return false
}

export function useHotkeys() {
  const navigate = useNavigate()

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // 在输入框/可编辑区域内不响应
      if (isEditableTarget(e.target)) return
      // 修饰键组合（Ctrl/Cmd/Alt/Meta）跳过，避免冲突
      if (e.ctrlKey || e.metaKey || e.altKey) return

      // 数字键 1-9：跳路由
      const route = HOTKEY_MAP[e.key]
      if (route) {
        e.preventDefault()
        navigate(route.path)
        message.success(`快捷键 ${e.key} → ${route.label}`, 1)
        return
      }

      // ? 键：弹出快捷键帮助
      if (e.key === '?') {
        e.preventDefault()
        const html = Object.entries(HOTKEY_MAP)
          .map(([k, v]) => `${k} → ${v.label}`)
          .join('  |  ')
        message.info(`快捷键：${html}  |  Esc 关闭弹层`, 6)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [navigate])
}
