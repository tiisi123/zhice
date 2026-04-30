import { getToken, clearAuth } from './auth'

const API_BASE = '/api'

function authHeaders(): Record<string, string> {
  const t = getToken()
  return t ? { Authorization: `Bearer ${t}` } : {}
}

async function handle<T>(res: Response): Promise<T> {
  if (res.status === 401) {
    // /auth/login、/auth/register、/auth/me 不强跳，避免循环
    const isAuthEndpoint = /\/auth\/(login|register|me)\b/.test(res.url)
    clearAuth()
    if (!isAuthEndpoint && location.pathname !== '/login') {
      location.href = `/login?next=${encodeURIComponent(location.pathname + location.search)}`
    }
    throw new ApiError('未登录或令牌失效', 401)
  }
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    let detail = text || `API error: ${res.status}`
    try {
      const j = JSON.parse(text)
      detail = j.detail || j.message || text
    } catch {
      // 非 JSON 直接使用 text
    }
    throw new ApiError(String(detail), res.status)
  }
  return res.json()
}

export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.status = status
    this.name = 'ApiError'
  }
}

export async function fetchApi<T = any>(path: string, params?: Record<string, string>): Promise<T> {
  let url = `${API_BASE}${path}`
  if (params) {
    const sp = new URLSearchParams(params)
    url += `?${sp.toString()}`
  }
  const res = await fetch(url, { headers: { ...authHeaders() } })
  return handle<T>(res)
}

export async function postApi<T = any>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  return handle<T>(res)
}

export async function deleteApi<T = any>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'DELETE',
    headers: { ...authHeaders() },
  })
  return handle<T>(res)
}

export async function patchApi<T = any>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  return handle<T>(res)
}
