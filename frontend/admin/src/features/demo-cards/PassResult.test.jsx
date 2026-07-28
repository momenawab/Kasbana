import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import PassResult from './PassResult.jsx'
import CardPreview from './CardPreview.jsx'

const RESULT = {
  merchant_name: 'Cafe Blooms',
  card_name: 'Coffee Club',
  apple_pass_url: 'https://example.test/pass.pkpass',
  google_save_url: 'https://pay.google.com/save/123',
}

describe('<PassResult>', () => {
  it('renders both wallet tiles with an add button per platform', () => {
    render(<PassResult result={RESULT} onClose={vi.fn()} />)
    expect(screen.getByText('Cafe Blooms', { exact: false })).toBeInTheDocument()
    expect(screen.getByText('Add to Apple Wallet')).toBeInTheDocument()
    expect(screen.getByText('Add to Google Wallet')).toBeInTheDocument()
  })

  it('links each button at its own pass URL', () => {
    render(<PassResult result={RESULT} onClose={vi.fn()} />)
    expect(screen.getByText('Add to Apple Wallet').closest('a')).toHaveAttribute(
      'href',
      RESULT.apple_pass_url,
    )
    expect(screen.getByText('Add to Google Wallet').closest('a')).toHaveAttribute(
      'href',
      RESULT.google_save_url,
    )
  })

  it('explains the gap instead of a dead button when a platform has no credentials', () => {
    render(
      <PassResult result={{ ...RESULT, google_save_url: null }} onClose={vi.fn()} />,
    )
    expect(screen.getByText('Add to Apple Wallet')).toBeInTheDocument()
    expect(screen.queryByText('Add to Google Wallet')).not.toBeInTheDocument()
    expect(screen.getByText(/Google Wallet credentials are not configured/)).toBeInTheDocument()
  })
})

describe('<CardPreview>', () => {
  const form = {
    type: 'STAMP',
    name: 'Coffee Club',
    reward_title: 'Free latte',
    stamps_required: 8,
    preview_stamps: 3,
    color_bg: '#0E1B2A',
    color_fg: '#FFFFFF',
  }

  it('shows the typed business name as the pass brand', () => {
    render(<CardPreview platform="APPLE" form={form} merchantName="Cafe Blooms" />)
    expect(screen.getByText('Cafe Blooms')).toBeInTheDocument()
    expect(screen.getByText('Coffee Club')).toBeInTheDocument()
    expect(screen.getByText('Free latte')).toBeInTheDocument()
  })

  it('falls back to placeholders before anything is typed', () => {
    render(<CardPreview platform="GOOGLE" form={{ type: 'STAMP' }} merchantName="" />)
    expect(screen.getByText('Business name')).toBeInTheDocument()
    expect(screen.getByText('Program name')).toBeInTheDocument()
  })
})
