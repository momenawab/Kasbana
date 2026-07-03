import { test, expect } from '@playwright/test'

const BASE = 'http://localhost:5173'

test.describe('marketing site', () => {
  test('home page renders the brand', async ({ page }) => {
    await page.goto(BASE, { waitUntil: 'domcontentloaded' })
    await expect(page.locator('#root')).not.toBeEmpty()
    await expect(page.getByText('Stampn').first()).toBeVisible()
  })

  test('exposes a link to the dashboard login', async ({ page }) => {
    await page.goto(BASE)
    const loginLink = page.locator('a[href*="/login"]').first()
    await expect(loginLink).toBeVisible()
  })
})
