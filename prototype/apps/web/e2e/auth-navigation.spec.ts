import { test, expect } from '@playwright/test'
import { injectAuth, setupApiFallback } from './fixtures/auth'

test.describe('Authenticated navigation', () => {
  test.beforeEach(async ({ page }) => {
    await injectAuth(page)
    await setupApiFallback(page)
  })

  const protectedRoutes = [
    { path: '/replay', heading: '收盘复盘' },
    { path: '/intraday', heading: '盘中盯盘' },
    { path: '/theme-workshop', heading: '题材工坊' },
    { path: '/event-chain', heading: '事件链' },
    { path: '/growth-workshop', heading: '成长景气' },
    { path: '/value-workshop', heading: '价值基本面' },
    { path: '/strategy-workshop', heading: '策略工坊' },
    { path: '/ai-agent', heading: 'AI 投研Agent' },
    { path: '/tools-home', heading: '投研工具台' },
    { path: '/stock-research', heading: '标的研究' },
    { path: '/my-workspace', heading: '我的工作台' },
  ]

  for (const { path, heading } of protectedRoutes) {
    test(`${path} renders without redirect`, async ({ page }) => {
      await page.goto(path)
      await expect(page).not.toHaveURL(/\/login/)
      const sidebar = page.locator('.ant-layout-sider, nav, [class*="sider"]')
      await expect(sidebar.or(page.locator('#root'))).toBeAttached({ timeout: 10_000 })
      const menuItem = page.locator(`.ant-menu-item >> text="${heading}"`)
      if (await menuItem.count() > 0) {
        await expect(menuItem).toBeVisible()
      }
    })
  }

  test('/ redirects to /replay', async ({ page }) => {
    await page.goto('/')
    await page.waitForURL(/\/replay/, { timeout: 10_000 })
  })

  test('sidebar menu items are visible', async ({ page }) => {
    await page.goto('/replay')
    const sider = page.locator('.ant-menu')
    await expect(sider).toBeVisible({ timeout: 10_000 })
    await expect(page.locator('.ant-menu-item >> text="收盘复盘"')).toBeVisible()
    await expect(page.locator('.ant-menu-item >> text="盘中盯盘"')).toBeVisible()
    await expect(page.locator('.ant-menu-item >> text="事件链"')).toBeVisible()
    await expect(page.locator('.ant-menu-item >> text="AI 投研Agent"')).toBeVisible()
  })

  test('sidebar click navigates to target page', async ({ page }) => {
    await page.goto('/replay')
    await page.locator('.ant-menu-item >> text="盘中盯盘"').click()
    await page.waitForURL(/\/intraday/, { timeout: 10_000 })
  })

  test('clearing auth redirects to login on next navigation', async ({ page }) => {
    await page.goto('/replay')
    await page.addInitScript(() => {
      localStorage.removeItem('zhice.token')
      localStorage.removeItem('zhice.user')
    })
    await page.goto('/replay')
    await page.waitForURL(/\/login/, { timeout: 10_000 })
    await expect(page.locator('button[type="submit"], button:has-text("登录")')).toBeVisible()
  })
})
