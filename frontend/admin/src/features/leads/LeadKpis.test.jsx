import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import LeadKpis from './LeadKpis'

const KPIS = {
  total: 12,
  website: 5,
  manual: 7,
  interested: 3,
  demo_scheduled: 1,
  customers: 2,
  calls_today: 4,
  follow_ups_today: 2,
  overdue_follow_ups: 0,
  conversion_rate: 16.7,
}

const card = (label) => screen.getByText(label).closest('button')

describe('<LeadKpis>', () => {
  it('shows the pipeline counts', () => {
    render(<LeadKpis data={KPIS} onDrill={() => {}} />)
    expect(screen.getByText('12')).toBeInTheDocument()
    expect(screen.getByText('16.7')).toBeInTheDocument()
  })

  it('drills into the rows behind a card', async () => {
    const onDrill = vi.fn()
    render(<LeadKpis data={KPIS} onDrill={onDrill} />)

    await userEvent.click(card('Website'))
    expect(onDrill).toHaveBeenCalledWith({ lead_type: ['website'] })
  })

  it('counts Customers as both won statuses, matching the backend KPI', () => {
    const onDrill = vi.fn()
    render(<LeadKpis data={KPIS} onDrill={onDrill} />)

    return userEvent.click(card('Customers')).then(() => {
      expect(onDrill).toHaveBeenCalledWith({ status: ['customer', 'converted'] })
    })
  })

  it('does not offer a drill-down for a card with no rows behind it', async () => {
    render(<LeadKpis data={KPIS} onDrill={() => {}} />)
    // Overdue is 0 here — clicking through to an empty table is a dead end.
    expect(card('Overdue')).toBeDisabled()
  })

  it('only reddens Overdue when there is something to chase', () => {
    const { rerender } = render(<LeadKpis data={KPIS} onDrill={() => {}} />)
    // A permanently red 0 trains people to ignore the colour.
    expect(card('Overdue').querySelector('.text-danger')).toBeNull()

    rerender(<LeadKpis data={{ ...KPIS, overdue_follow_ups: 3 }} onDrill={() => {}} />)
    expect(card('Overdue').querySelector('.text-danger')).not.toBeNull()
  })

  it('renders skeletons while loading, not zeroes', () => {
    // Showing "0 Total Leads" before the numbers land reads as an empty
    // pipeline rather than a loading one.
    const { container } = render(<LeadKpis isLoading onDrill={() => {}} />)
    expect(screen.queryByText('Total Leads')).toBeNull()
    expect(container.querySelectorAll('.animate-pulse').length).toBeGreaterThan(0)
  })

  it('keeps showing the old numbers while refiltering', () => {
    // isLoading with data present = a background refetch, not a first load.
    render(<LeadKpis data={KPIS} isLoading onDrill={() => {}} />)
    expect(screen.getByText('12')).toBeInTheDocument()
  })
})
