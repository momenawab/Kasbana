import { test, expect } from '@playwright/test'

// Smoke test for the Locations page and its branch-coordinate MapPicker.
//
// The dashboard dev server runs with VITE_USE_MOCKS=1 and NO VITE_MAPTILER_KEY
// (see e2e/playwright.config.js). That gives us a deterministic run:
//   - /me is mocked, so the plan gate lets "Add" open the modal;
//   - /locations isn't mocked (onUnhandledRequest: 'bypass') → the table shows
//     its empty state, which is fine here;
//   - with no MapTiler key the MapPicker renders its "map unavailable" fallback
//     instead of a live MapLibre/WebGL map — so this test never depends on GPU
//     or network tiles in CI.
//
// We assert: the page loads behind auth, the add-location modal opens with the
// fields the picker fills, and the lazy-loaded MapPicker actually mounts.

const BASE = 'http://localhost:5174'

test.describe('merchant dashboard — locations', () => {
  test('opens the add-location modal with the map picker', async ({ page }) => {
    // Seed a session (refresh token) and pin the UI to English *before* the app
    // boots — i18n and RequireAuth both read localStorage on first render.
    await page.addInitScript(() => {
      localStorage.setItem('stampn_refresh', 'mock-refresh')
      localStorage.setItem('stampn_lang', 'en')
    })

    await page.goto(`${BASE}/locations`, { waitUntil: 'domcontentloaded' })

    // Authenticated: stayed on /locations (no bounce to /login) and rendered.
    await expect(page).toHaveURL(/\/locations/)
    await expect(page.getByRole('heading', { name: 'Locations' })).toBeVisible()

    // Open the add-location modal. Playwright waits for the button to be enabled
    // (it's gated on the /me plan entitlements loading). The empty state has an
    // "Add location" button too, so take the first (header) one.
    await page.getByRole('button', { name: 'Add location' }).first().click()

    // The modal exposes the manual fields the picker writes into. These name
    // attributes are stable regardless of translation.
    await expect(page.locator('input[name="name"]')).toBeVisible()
    await expect(page.locator('input[name="address"]')).toBeVisible()

    // The lazy-loaded MapPicker mounted (import() + Suspense resolved). Without a
    // MapTiler key it shows the fallback notice; with a key it shows the geocoding
    // search box. Accept either so the test doesn't hinge on WebGL tiles. Allow a
    // generous timeout: the first load lets Vite optimize the heavy @maptiler/sdk.
    const picker = page
      .getByText('Map unavailable', { exact: false })
      .or(page.getByPlaceholder('Search your business or address…'))
    await expect(picker).toBeVisible({ timeout: 30_000 })
  })
})
