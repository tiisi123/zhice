export interface User {
  id: number
  phone: string
  nickname: string
  vip_level: 'free' | 'standard' | 'pro'
  vip_expire_at: string | null
  style: 'short' | 'hot' | 'growth' | 'value'
  created_at?: string
}

const TOKEN_KEY = 'zhice.token'
const USER_KEY = 'zhice.user'

type Listener = (user: User | null) => void
const listeners: Set<Listener> = new Set()

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function getUser(): User | null {
  const raw = localStorage.getItem(USER_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw) as User
  } catch {
    return null
  }
}

export function setAuth(token: string, user: User) {
  localStorage.setItem(TOKEN_KEY, token)
  localStorage.setItem(USER_KEY, JSON.stringify(user))
  listeners.forEach((l) => l(user))
}

export function setUser(user: User) {
  localStorage.setItem(USER_KEY, JSON.stringify(user))
  listeners.forEach((l) => l(user))
}

export function clearAuth() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
  listeners.forEach((l) => l(null))
}

export function onAuthChange(fn: Listener): () => void {
  listeners.add(fn)
  return () => listeners.delete(fn)
}
