import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import Badge from './Badge.jsx'

describe('<Badge>', () => {
  it('renders its children', () => {
    render(<Badge tone="success">Paid</Badge>)
    expect(screen.getByText('Paid')).toBeInTheDocument()
  })

  it('applies the tone class for a known tone', () => {
    render(<Badge tone="danger">Failed</Badge>)
    expect(screen.getByText('Failed').className).toContain('text-danger')
  })

  it('falls back to the neutral tone for an unknown tone', () => {
    render(<Badge tone="nope">Meh</Badge>)
    expect(screen.getByText('Meh').className).toContain('text-tx-2')
  })
})
