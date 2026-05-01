import { useState, useCallback } from 'react'
import { ApiError } from '../api/client'

export function useRequireVip() {
  const [paywallOpen, setPaywallOpen] = useState(false)

  const handleApiError = useCallback((error: unknown) => {
    if (error instanceof ApiError && error.status === 403 && error.message.includes('升级会员')) {
      setPaywallOpen(true)
      return true
    }
    return false
  }, [])

  return { paywallOpen, setPaywallOpen, handleApiError }
}
