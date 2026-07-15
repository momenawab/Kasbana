import { defineConfig, devices } from '@playwright/test'

// End-to-end smoke tests for the three Stampn frontends. Playwright starts each
// Vite dev server automatically (reusing one you already have running). The
// marketing site and the dashboard/admin *login* screens render without the
// backend, so these smoke tests need no Django server.
export default defineConfig({
  testDir: './tests',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  // Vite dev servers optimize dependencies on the first request, so the initial
  // navigation to a cold app can take a while — keep generous timeouts.
  timeout: 90_000,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    trace: 'on-first-retry',
    navigationTimeout: 60_000,
    actionTimeout: 15_000,
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      command: 'npm run dev',
      cwd: '../frontend',
      url: 'http://localhost:5173',
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
    {
      command: 'npm run dev',
      cwd: '../frontend/dashboard',
      url: 'http://localhost:5174',
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      env: { VITE_USE_MOCKS: '1' },
    },
    {
      command: 'npm run dev',
      cwd: '../frontend/admin',
      url: 'http://localhost:5175',
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
  ],
})
