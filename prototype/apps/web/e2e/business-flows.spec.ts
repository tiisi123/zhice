import { test, expect } from '@playwright/test'
import { injectAuth, setupApiFallback } from './fixtures/auth'
import {
  mockReplayPage,
  mockIntradayPage,
  mockEventChainPage,
  mockAIAgentPage,
  mockGrowthWorkshopPage,
  mockStrategyWorkshopPage,
} from './fixtures/api-mocks'

test.describe('Business flows with mocked API', () => {
  test.beforeEach(async ({ page }) => {
    await injectAuth(page)
    await setupApiFallback(page)
  })

  test('Replay page renders market summary from mock', async ({ page }) => {
    await mockReplayPage(page)
    await page.goto('/replay')

    await expect(page.getByRole('heading', { name: '收盘复盘' })).toBeVisible({ timeout: 15_000 })
    await expect(page.locator('#root')).not.toBeEmpty()
  })

  test('Replay page shows sentiment from mock', async ({ page }) => {
    await mockReplayPage(page)
    await page.goto('/replay')

    await expect(page.getByText('偏强').first()).toBeVisible({ timeout: 15_000 })
  })

  test('Replay page shows mock stock data', async ({ page }) => {
    await mockReplayPage(page)
    await page.goto('/replay')

    await expect(page.getByRole('heading', { name: '收盘复盘' })).toBeVisible({ timeout: 15_000 })
    await expect(page.getByText('首板测试').first()).toBeVisible({ timeout: 10_000 })
  })

  test('Intraday page renders limit-up stocks', async ({ page }) => {
    await mockIntradayPage(page)
    await page.goto('/intraday')

    await expect(page.getByText('盘中涨停A').first()).toBeVisible({ timeout: 15_000 })
  })

  test('Event chain page searches and renders chain nodes', async ({ page }) => {
    await mockEventChainPage(page)
    await page.goto('/event-chain')

    const searchInput = page.locator('.ant-input-search input').first()
    await expect(searchInput).toBeVisible({ timeout: 10_000 })

    await searchInput.fill('芯片')
    await page.locator('.ant-input-search .ant-btn').click()

    await expect(page.getByText('半导体产业链')).toBeVisible({ timeout: 15_000 })
    await expect(page.getByText('光刻胶').first()).toBeVisible({ timeout: 10_000 })
  })

  test('AI Agent page renders both panels', async ({ page }) => {
    await mockAIAgentPage(page)
    await page.goto('/ai-agent')

    await expect(page.getByText('打板交易 AI Agent')).toBeVisible({ timeout: 15_000 })
    await expect(page.getByText('ETF').first()).toBeVisible({ timeout: 10_000 })
  })

  test('Growth workshop page renders content', async ({ page }) => {
    await mockGrowthWorkshopPage(page)
    await page.goto('/growth-workshop')

    await expect(page.locator('#root')).toBeAttached({ timeout: 15_000 })
    await expect(page.locator('.ant-tabs, [role="tablist"]').first()).toBeVisible({ timeout: 15_000 })
  })

  test('Strategy workshop page renders tab interface', async ({ page }) => {
    await mockStrategyWorkshopPage(page)
    await page.goto('/strategy-workshop')

    await expect(
      page.locator('.ant-tabs, [role="tablist"]').first(),
    ).toBeVisible({ timeout: 15_000 })
  })
})
