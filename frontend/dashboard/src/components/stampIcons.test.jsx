import { describe, it, expect, beforeAll } from 'vitest'
import { render } from '@testing-library/react'
import i18n from '../lib/i18n'
import { STAMP_ICONS, STAMP_ICON_PATHS, isStampIcon } from './stampIcons'
import StampGlyph from './StampGlyph'
import WalletPreview from './WalletPreview'

beforeAll(async () => {
  await i18n.changeLanguage('en')
})

describe('stampIcons module', () => {
  it('exposes ten icons, each with an outline + filled path', () => {
    expect(STAMP_ICONS).toHaveLength(10)
    for (const [key, label, , paths] of STAMP_ICONS) {
      expect(typeof label).toBe('string')
      expect(paths.outline).toMatch(/^M/)
      expect(paths.filled).toMatch(/^M/)
      expect(STAMP_ICON_PATHS[key]).toBe(paths)
    }
  })

  it('validates known vs unknown keys', () => {
    expect(isStampIcon('coffee')).toBe(true)
    expect(isStampIcon('bogus')).toBe(false)
    expect(isStampIcon('')).toBe(false)
    expect(isStampIcon(undefined)).toBe(false)
  })

  it('renders the filled path when filled, outline otherwise', () => {
    const { container, rerender } = render(<StampGlyph icon="coffee" filled color="#ff0000" />)
    let path = container.querySelector('path')
    expect(path.getAttribute('d')).toBe(STAMP_ICON_PATHS.coffee.filled)
    expect(container.querySelector('svg').getAttribute('fill')).toBe('#ff0000')

    rerender(<StampGlyph icon="coffee" faded />)
    path = container.querySelector('path')
    expect(path.getAttribute('d')).toBe(STAMP_ICON_PATHS.coffee.outline)
    expect(container.querySelector('svg').style.opacity).toBe('0.45')
  })

  it('renders nothing for an unknown icon', () => {
    const { container } = render(<StampGlyph icon="bogus" />)
    expect(container.querySelector('svg')).toBeNull()
  })
})

describe('<WalletPreview> stamp strip', () => {
  const base = {
    platform: 'APPLE',
    cardType: 'STAMP',
    stampsRequired: 4,
    stampCount: 2,
  }

  it('tints the built-in icon and draws one glyph per stamp', () => {
    const { container } = render(
      <WalletPreview {...base} design={{ apple_strip_enabled: true, stamp_icon: 'star', stamp_color: '#00ff00' }} />
    )
    const paths = [...container.querySelectorAll('svg path')].map((p) => p.getAttribute('d'))
    // 2 earned (filled) + 2 remaining (outline) star glyphs somewhere in the pass.
    expect(paths.filter((d) => d === STAMP_ICON_PATHS.star.filled)).toHaveLength(2)
    expect(paths.filter((d) => d === STAMP_ICON_PATHS.star.outline)).toHaveLength(2)
    const tinted = [...container.querySelectorAll('svg')].filter(
      (s) => s.getAttribute('fill') === '#00ff00'
    )
    expect(tinted.length).toBeGreaterThanOrEqual(4)
  })

  it('recolors the drawn circles with stamp_color when no icon is picked', () => {
    const { container } = render(
      <WalletPreview {...base} design={{ apple_strip_enabled: true, stamp_color: '#123456' }} />
    )
    // No glyph paths — falls back to drawn circles, tinted with stamp_color.
    expect(container.querySelector('svg path')).toBeNull()
    const tintedCircles = [...container.querySelectorAll('span')].filter(
      (el) => el.style.borderColor.replace(/\s/g, '') === 'rgb(18,52,86)'
    )
    expect(tintedCircles).toHaveLength(4)
  })
})
