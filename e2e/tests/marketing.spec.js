import { test, expect } from '@playwright/test'

const BASE = 'http://localhost:5173'

test.describe('marketing site', () => {
  test('home page renders the brand', async ({ page }) => {
    await page.goto(BASE, { waitUntil: 'domcontentloaded' })
    await expect(page.locator('#root')).not.toBeEmpty()
    await expect(page.getByText('Stampn').first()).toBeVisible()
  })

  test('exposes a Get started link to the waitlist', async ({ page }) => {
    // The dashboard isn't enabled yet, so the header Log in link was removed;
    // the primary CTA now points at the waitlist form (/get-started).
    await page.goto(BASE)
    const cta = page.locator('a[href*="/get-started"]').first()
    await expect(cta).toBeVisible()
  })

  test('submitting the waitlist form shows a confirmation', async ({ page }) => {
    // Intercept the lead POST so the test never hits the real backend.
    await page.route('**/api/v1/leads', (route) =>
      route.fulfill({ status: 201, contentType: 'application/json', body: '{}' })
    )
    await page.goto(`${BASE}/get-started`)
    await page.fill('#name', 'Test Owner')
    await page.fill('#email', 'owner@example.com')
    await page.fill('#phone', '01000000000')
    await page.fill('#business_name', 'Test Café')
    await page.getByRole('button', { name: /join the waitlist/i }).click()
    await expect(page.getByRole('heading', { name: /on the list/i })).toBeVisible()
  })
})
