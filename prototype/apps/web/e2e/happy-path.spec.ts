import { test, expect } from '@playwright/test';

// Happy-path E2E: 5 navigation + render checks.
// The app wraps most routes in AuthGuard, so unauthenticated navigation
// redirects to /login?next=... These tests verify the SPA loads, login
// page renders, auth-guarded routes redirect properly, and the React
// app mounts correctly in the built bundle.

test.describe('Happy-path 5 steps', () => {
  test('Step 1: /login renders login form', async ({ page }) => {
    await page.goto('/login');
    await expect(page.locator('input')).toHaveCount(2, { timeout: 10_000 });
    await expect(page.locator('button[type="submit"], button:has-text("登录")')).toBeVisible();
  });

  test('Step 2: /intraday redirects to login (AuthGuard)', async ({ page }) => {
    await page.goto('/intraday');
    await page.waitForURL(/\/login/, { timeout: 10_000 });
    await expect(page.locator('input')).toHaveCount(2);
  });

  test('Step 3: /theme-workshop redirects to login (AuthGuard)', async ({ page }) => {
    await page.goto('/theme-workshop');
    await page.waitForURL(/\/login/, { timeout: 10_000 });
    await expect(page.locator('input')).toHaveCount(2);
  });

  test('Step 4: /strategy-workshop redirects to login (AuthGuard)', async ({ page }) => {
    await page.goto('/strategy-workshop');
    await page.waitForURL(/\/login/, { timeout: 10_000 });
    await expect(page.locator('input')).toHaveCount(2);
  });

  test('Step 5: Built bundle contains React app mount', async ({ page }) => {
    await page.goto('/login');
    await expect(page.locator('#root')).toBeAttached();
    await expect(page.locator('#root')).not.toBeEmpty();
  });
});
