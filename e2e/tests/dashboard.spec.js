import { test, expect } from '@playwright/test'

const BASE = 'http://localhost:5174'

test.describe('merchant dashboard', () => {
  test('boots the SPA and shows the Stampn title', async ({ page }) => {
    await page.goto(BASE, { waitUntil: 'domcontentloaded' })
    await expect(page).toHaveTitle(/Stampn/i)
    await expect(page.locator('#root')).not.toBeEmpty()
  })
})
