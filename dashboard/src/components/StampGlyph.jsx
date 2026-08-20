// A single stamp glyph, tinted with `color`. `filled` picks the solid vs outline
// design; `faded` dims the outline for a not-yet-collected slot (mirrors the
// backend _EMPTY_ALPHA so the preview matches the real pass). Path data + the
// icon registry live in stampIcons.js.
import { forwardRef } from 'react'
import { STAMP_ICON_PATHS } from './stampIcons'

const StampGlyph = forwardRef(function StampGlyph(
  { icon, filled = false, color = 'currentColor', faded = false, size = 20, ...rest },
  ref
) {
  const paths = STAMP_ICON_PATHS[icon]
  if (!paths) return null
  return (
    <svg
      ref={ref}
      width={size}
      height={size}
      viewBox="0 0 256 256"
      fill={color}
      style={{ opacity: faded ? 0.45 : 1 }}
      aria-hidden="true"
      {...rest}
    >
      <path d={filled ? paths.filled : paths.outline} />
    </svg>
  )
})

export default StampGlyph
