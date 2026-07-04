// PassHeader — the top row of every pass: brand logo + brand name on the left,
// an optional StatusBadge on the right. Mirrors Apple Wallet's logo row.
import BrandLogo from './BrandLogo'
import StatusBadge from './StatusBadge'

export default function PassHeader({ logo, brand, badge, badgeTone, theme }) {
  if (!brand && !logo && !badge) return null
  return (
    <div className="flex items-center justify-between gap-2">
      <div className="flex min-w-0 items-center gap-2">
        <BrandLogo src={logo} name={brand} theme={theme} />
        {brand && (
          <span className="truncate text-[13px] font-semibold" style={{ color: theme?.fg }}>
            {brand}
          </span>
        )}
      </div>
      <StatusBadge theme={theme} tone={badgeTone}>
        {badge}
      </StatusBadge>
    </div>
  )
}
