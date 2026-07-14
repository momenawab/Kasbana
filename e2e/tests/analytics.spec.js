import { test, expect } from '@playwright/test'

// Analytics: the expanded ("maximize") view of each chart panel.
//
// The dashboard dev server runs with VITE_USE_MOCKS=1 (see e2e/playwright.config.js),
// and src/mocks/handlers.js mocks /analytics/{summary,timeseries,wallet_split}, so the
// charts render real, deterministic data with no Django server.
//
// Two regressions this guards:
//   1. The expanded panel used to overflow the modal — you had to scroll inside it to
//      see the whole chart. Its body must now fit the 90vh dialog outright.
//   2. The date range picked on the page must carry into the expanded view, and the
//      copy inside the expanded view must NOT write back to the page's filter.

const BASE = 'http://localhost:5174'
const PANELS = ['Joins', 'Stamps', 'Redemptions', 'Apple vs Google']

async function openAnalytics(page) {
  await page.addInitScript(() => {
    localStorage.setItem('stampn_refresh', 'mock-refresh')
    localStorage.setItem('stampn_lang', 'en')
  })
  await page.goto(`${BASE}/analytics`, { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { name: 'Analytics' })).toBeVisible({ timeout: 30_000 })
}

// The Modal's scroll container: the flex child between the header and the footer.
const body = (page) => page.locator('[role="dialog"] > div.overflow-y-auto')

test.describe('merchant dashboard — analytics', () => {
  for (const panel of PANELS) {
    test(`the expanded "${panel}" panel fits the viewport without scrolling`, async ({ page }) => {
      await openAnalytics(page)

      await page.getByLabel(`Expand — ${panel}`).click()
      const dialog = page.getByRole('dialog')
      await expect(dialog).toBeVisible()
      await expect(dialog).toHaveAttribute('aria-label', panel)

      // Let recharts settle: it measures its container, so assert after a frame.
      await expect(dialog.locator('.recharts-surface').first()).toBeVisible()
      await page.waitForTimeout(300)

      // Nothing is clipped off the bottom: the modal body has no scrollable overflow…
      const overflow = await body(page).evaluate((el) => el.scrollHeight - el.clientHeight)
      expect(overflow).toBeLessThanOrEqual(1)

      // …and the dialog itself sits inside the viewport.
      const box = await dialog.boundingBox()
      const viewport = page.viewportSize()
      expect(box.y).toBeGreaterThanOrEqual(0)
      expect(box.y + box.height).toBeLessThanOrEqual(viewport.height + 1)

      // The chart got real height rather than being squeezed to nothing.
      const chart = await dialog.locator('.recharts-surface').first().boundingBox()
      expect(chart.height).toBeGreaterThan(150)
    })
  }

  test('carries the page date range in, and keeps the expanded copy independent', async ({
    page,
  }) => {
    await openAnalytics(page)

    // The page filter renders first; once a panel is open the second one is the
    // expanded view's own copy.
    const fromInputs = page.getByLabel('from')

    await fromInputs.first().fill('2026-07-01')
    await page.getByLabel('Expand — Joins').click()
    await expect(page.getByRole('dialog')).toBeVisible()

    // 1. The expanded view opened on the range already chosen on the page.
    await expect(fromInputs).toHaveCount(2)
    await expect(fromInputs.nth(1)).toHaveValue('2026-07-01')

    // 2. Re-dating inside the expanded view leaves the page's filter alone.
    await fromInputs.nth(1).fill('2026-06-15')
    await expect(fromInputs.nth(1)).toHaveValue('2026-06-15')
    await expect(fromInputs.first()).toHaveValue('2026-07-01')

    // 3. Closing it, the page is still on its own range.
    await page.getByRole('button', { name: 'Close' }).click()
    await expect(page.getByRole('dialog')).toBeHidden()
    await expect(fromInputs.first()).toHaveValue('2026-07-01')
  })
})
