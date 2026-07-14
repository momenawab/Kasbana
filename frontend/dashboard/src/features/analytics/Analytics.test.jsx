import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import i18n from '../../lib/i18n'
import Analytics from './Analytics'

// 3-day window: 2 + 0 + 10 → total 12, avg 4.0, peak 10 on 3 Jul, 2 of 3 days active.
const POINTS = [
  { date: '2026-07-01', value: 2 },
  { date: '2026-07-02', value: 0 },
  { date: '2026-07-03', value: 10 },
]

vi.mock('../../lib/api', () => ({
  default: {
    get: vi.fn((url) => {
      if (url.startsWith('/analytics/summary')) {
        return Promise.resolve({
          data: { enrollments: 12, active_cards: 5, redemptions: 3, repeat_rate: 0.5, apple_count: 7, google_count: 3 },
        })
      }
      return Promise.resolve({ data: { points: POINTS } })
    }),
  },
  normalizeError: (e) => ({ message: String(e) }),
}))

vi.mock('../../hooks/usePlan', () => ({
  usePlan: () => ({ entitlements: { plan: 'growth', features: { analytics: 'full' } } }),
}))

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <Analytics />
    </QueryClientProvider>
  )
}

beforeAll(async () => {
  await i18n.changeLanguage('en')
})

describe('<Analytics>', () => {
  it('gives every chart panel an expand control', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByLabelText('Expand — Joins')).toBeTruthy())
    for (const title of ['Joins', 'Stamps', 'Redemptions', 'Apple vs Google']) {
      expect(screen.getByLabelText(`Expand — ${title}`)).toBeTruthy()
    }
  })

  it('expanding a chart shows the stats derived from its points', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByLabelText('Expand — Joins')).toBeTruthy())

    // Closed: the detail stats are not on the page.
    expect(screen.queryByText('Daily average')).toBeNull()

    fireEvent.click(screen.getByLabelText('Expand — Joins'))

    await waitFor(() => expect(screen.getByRole('dialog')).toBeTruthy())
    const dialog = screen.getByRole('dialog')
    expect(dialog.getAttribute('aria-label')).toBe('Joins')

    // total 12, daily avg 4.0, peak 10 (on 3 Jul), 2 of 3 days active.
    expect(screen.getByText('Daily average')).toBeTruthy()
    expect(screen.getByText('4.0')).toBeTruthy()
    expect(screen.getByText('2 / 3')).toBeTruthy()
    expect(screen.getByText('3 Jul')).toBeTruthy()

    // Every day in the range is listed, zero-days included.
    expect(screen.getByText('Thu, 2 Jul 2026')).toBeTruthy()
    expect(screen.getByText('Fri, 3 Jul 2026')).toBeTruthy()
  })

  it('expanding the wallet split shows each wallet share', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByLabelText('Expand — Apple vs Google')).toBeTruthy())

    fireEvent.click(screen.getByLabelText('Expand — Apple vs Google'))

    await waitFor(() => expect(screen.getByRole('dialog')).toBeTruthy())
    // 7 Apple + 3 Google → 70% / 30% of 10. Each share shows twice: the stat tile
    // and the table row.
    expect(screen.getAllByText('70%').length).toBeGreaterThan(0)
    expect(screen.getAllByText('30%').length).toBeGreaterThan(0)
  })
})
