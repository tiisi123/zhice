import { test, expect } from '@playwright/test'
import { injectAuth } from './fixtures/auth'

test.describe('M008 S07 data smoke', () => {
  test('unauthenticated user sees login form, not stale workspace state', async ({ page }) => {
    await page.addInitScript(() => localStorage.clear())
    await page.goto('/login')

    await expect(page.getByText('智策').first()).toBeVisible({ timeout: 10_000 })
    await expect(page.locator('#root')).not.toBeEmpty()
  })

  test('replay page renders with D004 metadata strip under authenticated state', async ({ page }) => {
    await injectAuth(page)
    await page.goto('/replay')

    await expect(page.getByText('收盘复盘').first()).toBeVisible({ timeout: 15_000 })
    await expect(page.getByText(/演示数据|实时数据|暂无数据|数据源不可用/).first()).toBeVisible({ timeout: 15_000 })
    await expect(page.locator('#root')).not.toBeEmpty()
  })

  test('intraday page renders limit-up members instead of a blank event pool', async ({ page }) => {
    await injectAuth(page)
    await page.goto('/intraday')

    await expect(page.getByText('盘中盯盘').first()).toBeVisible({ timeout: 15_000 })
    await expect(page.getByText(/涨停|活跃主线|实时异动流/).first()).toBeVisible({ timeout: 15_000 })
  })
})
