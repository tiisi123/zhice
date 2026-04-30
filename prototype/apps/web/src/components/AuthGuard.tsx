import { useEffect, useState } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { clearAuth, getToken, getUser, onAuthChange, setUser, type User } from '../api/auth'
import { fetchApi } from '../api/client'

interface Props {
  children: React.ReactNode
}

export default function AuthGuard({ children }: Props) {
  const location = useLocation()
  const [user, setLocalUser] = useState<User | null>(getUser())
  const [checking, setChecking] = useState(false)

  useEffect(() => {
    const off = onAuthChange((u) => setLocalUser(u))
    return () => { off() }
  }, [])

  useEffect(() => {
    const t = getToken()
    if (t && !getUser()) {
      setChecking(true)
      fetchApi<{ user: User }>('/auth/me')
        .then((r) => {
          setUser(r.user)
          setLocalUser(r.user)
        })
        .catch(() => {
          clearAuth()
        })
        .finally(() => setChecking(false))
    }
  }, [])

  if (!getToken()) {
    return <Navigate to={`/login?next=${encodeURIComponent(location.pathname + location.search)}`} replace />
  }
  if (checking && !user) {
    return null
  }
  if (user && !user.style && location.pathname !== '/onboarding' && location.pathname !== '/settings') {
    return <Navigate to="/onboarding" replace />
  }
  return <>{children}</>
}
