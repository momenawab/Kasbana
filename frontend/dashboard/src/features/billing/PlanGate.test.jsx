import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import i18n from '../../lib/i18n'
import api from '../../lib/api'
import PlanGate from './PlanGate'

// Prices come from the server, not the client: they are admin-editable without
// a deploy, so these are deliberately not the seed values — a hardcoded copy in
// the component would make this test pass while lying to real merchants.
const PLANS = [
  { key: 'starter', name: 'Starter', price_egp: '599.00', price_egp_annual: '5990.00' },
  { key: 'growth', name: 'Growth', price_egp: '999.00', price_egp_annual: '9990.00' },
]

vi.mock('../../lib/api', () => ({
  default: { get: vi.fn(), post: vi.fn() },
  normalizeError: (e) => ({ message: String(e?.message ?? e) }),
}))

const toast = { error: vi.fn(), success: vi.fn() }
vi.mock('../../hooks/useToast', () => ({ useToast: () => toast }))
vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => ({ merchant: { name: 'Cafe Riche' } }),
}))

function renderGate() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <PlanGate />
    </QueryClientProvider>
  )
}

async function reachPlanStep() {
  renderGate()
  fireEvent.click(screen.getByRole('button', { name: /choose a plan/i }))
  await screen.findByText('Growth')
}

beforeAll(async () => {
  await i18n.changeLanguage('en')
})

beforeEach(() => {
  vi.clearAllMocks()
  api.get.mockResolvedValue({ data: PLANS })
  api.post.mockResolvedValue({ data: { checkout_url: 'https://pay.example/checkout' } })
  delete window.location
  window.location = { assign: vi.fn() }
})

describe('PlanGate', () => {
  it('opens on the intro, not the plan picker', () => {
    renderGate()
    // A merchant who just signed up has no idea what this product does; asking
    // for a card first is how you lose them.
    expect(screen.getByText(/Welcome, Cafe Riche/)).toBeInTheDocument()
    expect(screen.queryByText('Growth')).not.toBeInTheDocument()
  })

  it('renders server prices for the chosen interval', async () => {
    await reachPlanStep()
    expect(screen.getByText('EGP 999')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /annual/i }))

    expect(await screen.findByText('EGP 9,990')).toBeInTheDocument()
    expect(screen.queryByText('EGP 999')).not.toBeInTheDocument()
  })

  it('cannot start a trial before a plan is picked', async () => {
    await reachPlanStep()
    expect(screen.getByRole('button', { name: /add card and start trial/i })).toBeDisabled()
  })

  it('subscribes with the picked plan and interval', async () => {
    await reachPlanStep()
    fireEvent.click(screen.getByRole('button', { name: /annual/i }))
    fireEvent.click(screen.getByRole('button', { name: /Growth/ }))
    fireEvent.click(screen.getByRole('button', { name: /add card and start trial/i }))

    await waitFor(() =>
      expect(api.post).toHaveBeenCalledWith('/billing/subscribe', {
        plan: 'growth',
        interval: 'annual',
      })
    )
  })

  it('defaults to monthly so nobody buys a year by accident', async () => {
    await reachPlanStep()
    fireEvent.click(screen.getByRole('button', { name: /Starter/ }))
    fireEvent.click(screen.getByRole('button', { name: /add card and start trial/i }))

    await waitFor(() =>
      expect(api.post).toHaveBeenCalledWith('/billing/subscribe', {
        plan: 'starter',
        interval: 'monthly',
      })
    )
  })

  it('hands off to the gateway checkout', async () => {
    await reachPlanStep()
    fireEvent.click(screen.getByRole('button', { name: /Growth/ }))
    fireEvent.click(screen.getByRole('button', { name: /add card and start trial/i }))

    await waitFor(() =>
      expect(window.location.assign).toHaveBeenCalledWith('https://pay.example/checkout')
    )
  })

  it('surfaces a failed checkout instead of stranding the merchant', async () => {
    api.post.mockRejectedValue(new Error('gateway down'))
    await reachPlanStep()
    fireEvent.click(screen.getByRole('button', { name: /Growth/ }))
    fireEvent.click(screen.getByRole('button', { name: /add card and start trial/i }))

    await waitFor(() => expect(toast.error).toHaveBeenCalled())
    expect(window.location.assign).not.toHaveBeenCalled()
  })

  it('says the trial needs a card and what it costs today', async () => {
    await reachPlanStep()
    // The 1 EGP charge is real money on their statement — burying it is how you
    // earn a chargeback.
    expect(screen.getByText(/1 EGP now/)).toBeInTheDocument()
  })
})
