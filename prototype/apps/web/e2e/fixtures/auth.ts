import { type Page } from '@playwright/test'

export const MOCK_USER = {
  id: 1,
  phone: '13800000001',
  nickname: '测试用户',
  vip_level: 'pro' as const,
  vip_expire_at: '2099-12-31T23:59:59',
  style: 'short' as const,
  created_at: '2024-01-01T00:00:00',
}

export const MOCK_TOKEN = 'e2e-test-token-fixed'

export async function injectAuth(page: Page) {
  await page.addInitScript(
    ({ token, user }) => {
      localStorage.clear()
      localStorage.setItem('zhice.token', token)
      localStorage.setItem('zhice.user', JSON.stringify(user))
    },
    { token: MOCK_TOKEN, user: MOCK_USER },
  )
}

const unmatchedRequests: string[] = []

export async function setupApiFallback(page: Page) {
  unmatchedRequests.length = 0

  await page.route('**/api/**', (route) => {
    const url = route.request().url()
    unmatchedRequests.push(url)
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        data: null,
        data_status: 'empty',
        source: 'e2e_fallback',
        mock: false,
        message: 'E2E fallback — no specific mock registered',
        updated_at: new Date().toISOString(),
      }),
    })
  })

  await page.route('**/api/auth/me', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ user: MOCK_USER }),
    }),
  )
}

export function getUnmatchedRequests(): string[] {
  return [...unmatchedRequests]
}
