import { test, expect } from '@playwright/test'

const BASE = 'http://localhost:5175'

test.describe('admin console', () => {
  test('boots the SPA and shows the admin title', async ({ page }) => {
    await page.goto(BASE, { waitUntil: 'domcontentloaded' })
    await expect(page).toHaveTitle(/Stampn Admin/i)
    await expect(page.locator('#root')).not.toBeEmpty()
  })
})
