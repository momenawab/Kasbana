import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import i18n from '../../lib/i18n'
import TemplatePicker from './TemplatePicker'

beforeAll(async () => {
  await i18n.changeLanguage('en')
})

describe('<TemplatePicker>', () => {
  it('renders all eight templates', () => {
    render(<TemplatePicker onChoose={() => {}} onSkip={() => {}} />)
    // Some category names also appear as a pass badge (e.g. "Boarding"), so
    // assert each name is present at least once rather than uniquely.
    for (const name of [
      'Loyalty',
      'Event',
      'Boarding',
      'Membership',
      'Coupon',
      'Gift card',
      'Invitation',
      'Special occasion',
    ]) {
      expect(screen.getAllByText(name).length).toBeGreaterThan(0)
    }
  })

  it('offers loyalty as publishable and marks the other seven preview-only', () => {
    render(<TemplatePicker onChoose={() => {}} onSkip={() => {}} />)
    expect(screen.getAllByText('Use this template')).toHaveLength(1)
    expect(screen.getAllByText('Coming soon')).toHaveLength(7)
  })

  it('calls onChoose with the loyalty id when its button is clicked', () => {
    const onChoose = vi.fn()
    render(<TemplatePicker onChoose={onChoose} onSkip={() => {}} />)
    fireEvent.click(screen.getByText('Use this template'))
    expect(onChoose).toHaveBeenCalledWith('loyalty')
  })

  it('calls onSkip from the start-from-scratch action', () => {
    const onSkip = vi.fn()
    render(<TemplatePicker onChoose={() => {}} onSkip={onSkip} />)
    fireEvent.click(screen.getByText('Start from scratch'))
    expect(onSkip).toHaveBeenCalled()
  })
})
