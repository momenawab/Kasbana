import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import i18n from '../../lib/i18n'
import api from '../../lib/api'
import Analytics from './Analytics'

// 3-day window: 2 + 0 + 10 → total 12, avg 4.0, peak 10 on 3 Jul, 2 of 3 days active.
const POINTS = [
  { date: '2026-07-01', value: 2 },
  { date: '2026-07-02', value: 0 },
  { date: '2026-07-03', value: 10 },
]

// The summary is range-scoped, so the fake varies with it: narrowing to July returns a
// different enrollment count, which is how we prove the KPI tiles follow the filter.
const JULY = 'from=2026-07-01'

vi.mock('../../lib/api', () => ({
  default: {
    get: vi.fn((url) => {
      if (url.startsWith('/analytics/summary')) {
        const enrollments = url.includes(JULY) ? 4 : 12
        return Promise.resolve({
          data: { enrollments, active_cards: 5, redemptions: 3, repeat_rate: 0.5, apple_count: 7, google_count: 3 },
        })
      }
      if (url.startsWith('/analytics/wallet_split')) {
        return Promise.resolve({ data: { apple_count: 7, google_count: 3 } })
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

// The page's DateRange renders before the expanded one, so [0] is the page filter
// and [1] — once a panel is open — is the modal's own copy.
const fromInputs = () => screen.getAllByLabelText('from')

const urlsHit = () => api.get.mock.calls.map(([url]) => url)
const hit = (re) => urlsHit().some((url) => re.test(url))

beforeAll(async () => {
  await i18n.changeLanguage('en')
})

beforeEach(() => {
  api.get.mockClear()
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

    // 7 Apple + 3 Google → 70% / 30% of 10. Each share shows twice: the stat tile
    // and the table row. The expanded donut fetches its own range, so wait for it.
    await waitFor(() => expect(screen.getAllByText('70%').length).toBeGreaterThan(0))
    expect(screen.getAllByText('30%').length).toBeGreaterThan(0)
  })

  it('fills the date picker in, rather than leaving the applied range implicit', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByLabelText('Expand — Joins')).toBeTruthy())

    // A blank picker used to hide the fact that a 30-day window was already applied.
    expect(fromInputs()[0].value).toMatch(/^\d{4}-\d{2}-\d{2}$/)
    // …and the KPI tiles ask for that same window, not for all-time totals.
    expect(hit(/^\/analytics\/summary\?from=\d{4}-\d{2}-\d{2}&to=\d{4}-\d{2}-\d{2}$/)).toBe(true)
  })

  it('re-dates the KPI tiles with the page filter', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('12')).toBeTruthy())

    fireEvent.change(fromInputs()[0], { target: { value: '2026-07-01' } })

    // The Enrollments tile moves to the July figure the range now selects.
    await waitFor(() => expect(screen.getByText('4')).toBeTruthy())
    expect(screen.queryByText('12')).toBeNull()
    expect(hit(/^\/analytics\/summary\?from=2026-07-01/)).toBe(true)
  })

  it('opens the expanded view on the range already chosen on the page', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByLabelText('Expand — Joins')).toBeTruthy())

    fireEvent.change(fromInputs()[0], { target: { value: '2026-07-01' } })
    fireEvent.click(screen.getByLabelText('Expand — Joins'))
    await waitFor(() => expect(screen.getByRole('dialog')).toBeTruthy())

    expect(fromInputs()).toHaveLength(2)
    expect(fromInputs()[1].value).toBe('2026-07-01')
  })

  it('re-dating inside the expanded view refetches it but leaves the page filter alone', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByLabelText('Expand — Joins')).toBeTruthy())

    fireEvent.change(fromInputs()[0], { target: { value: '2026-07-01' } })
    fireEvent.click(screen.getByLabelText('Expand — Joins'))
    await waitFor(() => expect(screen.getByRole('dialog')).toBeTruthy())

    fireEvent.change(fromInputs()[1], { target: { value: '2026-06-15' } })

    // The modal refetches on its own range …
    await waitFor(() =>
      expect(hit(/^\/analytics\/timeseries\?metric=joins&from=2026-06-15/)).toBe(true)
    )
    // … while the page's own filter is untouched.
    expect(fromInputs()[0].value).toBe('2026-07-01')
    expect(fromInputs()[1].value).toBe('2026-06-15')
  })
})
