import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { TEMPLATES } from './registry'
import { RewardStampRow, PassBarcode, PassInfoRow, resolveTheme } from './components'

const theme = resolveTheme('red')

describe('wallet-pass templates', () => {
  it.each(TEMPLATES.map((t) => [t.name, t]))('%s renders from sample props', (_name, tpl) => {
    const Pass = tpl.component
    const { container } = render(<Pass {...tpl.sample} theme={tpl.theme} />)
    // The pass shell mounted.
    expect(container.querySelector('article')).toBeInTheDocument()
    // A distinctive sample string is visible (brand or title).
    const needle = tpl.sample.brand || tpl.sample.title || tpl.sample.passenger
    if (needle) expect(screen.getByText(needle)).toBeInTheDocument()
  })
})

describe('<RewardStampRow>', () => {
  it('renders one chip per target', () => {
    const { container } = render(<RewardStampRow progress={2} target={8} theme={theme} />)
    expect(container.querySelectorAll('span.rounded-full')).toHaveLength(8)
  })

  it('lights the reward chip only when complete', () => {
    const { container: partial } = render(<RewardStampRow progress={4} target={5} theme={theme} />)
    expect(partial.querySelector('.pass-reward-glow')).toBeNull()
    const { container: done } = render(<RewardStampRow progress={5} target={5} theme={theme} />)
    expect(done.querySelector('.pass-reward-glow')).not.toBeNull()
  })

  it('hides itself for a non-positive target', () => {
    const { container } = render(<RewardStampRow progress={0} target={0} theme={theme} />)
    expect(container.firstChild).toBeNull()
  })
})

describe('<PassBarcode>', () => {
  it('renders a real QR (svg) for the qr format', () => {
    const { container } = render(<PassBarcode format="qr" value="abc" theme={theme} />)
    expect(container.querySelector('svg')).toBeInTheDocument()
  })

  it.each(['code128', 'pdf417', 'aztec'])('renders a %s stand-in with its code label', (fmt) => {
    render(<PassBarcode format={fmt} value="X1" code="12345" theme={theme} />)
    expect(screen.getByText('12345')).toBeInTheDocument()
  })
})

describe('<PassInfoRow>', () => {
  it('drops empty-value items and hides when all are empty', () => {
    const { container } = render(
      <PassInfoRow theme={theme} items={[{ label: 'A', value: '' }, { label: 'B', value: '' }]} />
    )
    expect(container.firstChild).toBeNull()
  })
})
