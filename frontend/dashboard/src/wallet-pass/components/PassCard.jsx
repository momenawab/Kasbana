// PassCard — the shell every template composes into. Fixes the Apple-Wallet
// geometry (0.62 aspect ratio, 22px radius, 16px padding, overflow hidden) and
// the premium floating shadow + subtle hover scale. Applies the theme background
// (solid, gradient, or full-bleed image) and foreground colour, then stacks its
// children on an 8-pt rhythm. Children that render null (empty sections) simply
// collapse, so templates never need conditional wrappers.
//
// A template can drop `<div className="flex-1" />` between blocks to push a
// trailing FooterImage to the very bottom, exactly like the reference passes.
import '../passes.css'

const SHADOW = '0 22px 44px -16px rgba(14, 27, 42, 0.45), 0 6px 14px -8px rgba(14, 27, 42, 0.25)'

export default function PassCard({
  theme,
  backgroundImage,
  children,
  interactive = true,
  className = '',
  onClick,
}) {
  const surface = backgroundImage ? { color: theme?.fg } : { background: theme?.bg, color: theme?.fg }
  return (
    <article
      onClick={onClick}
      dir="ltr"
      style={{ ...surface, boxShadow: SHADOW }}
      className={`relative flex aspect-[0.62] w-full flex-col overflow-hidden rounded-[22px] p-4 transition-transform duration-300 will-change-transform ${
        interactive ? 'hover:scale-[1.02]' : ''
      } ${onClick ? 'cursor-pointer' : ''} ${className}`}
    >
      {backgroundImage && (
        <>
          <img src={backgroundImage} alt="" className="absolute inset-0 h-full w-full object-cover" />
          {/* Legibility scrim so header/title text stays readable over artwork. */}
          <div
            className="absolute inset-0"
            style={{ background: theme?.bg, opacity: 0.72, mixBlendMode: 'multiply' }}
          />
        </>
      )}
      <div className="relative flex h-full min-h-0 flex-col gap-3">{children}</div>
    </article>
  )
}
