// PassTitle — the "small header" (tiny uppercase label) stacked above the large
// bold title, exactly the hierarchy in the reference passes ("4th Time's the
// Bite -" over "Free Burger!"). Either line is optional.

export default function PassTitle({ label, children, theme, size = 'lg' }) {
  if (!label && !children) return null
  const titleSize = size === 'xl' ? 'text-[26px]' : size === 'md' ? 'text-lg' : 'text-[22px]'
  return (
    <div className="flex flex-col gap-1">
      {label && (
        <span
          className="text-[11px] font-medium uppercase tracking-wide"
          style={{ color: theme?.sub }}
        >
          {label}
        </span>
      )}
      {children && (
        <span
          className={`font-head font-bold leading-tight ${titleSize}`}
          style={{ color: theme?.fg }}
        >
          {children}
        </span>
      )}
    </div>
  )
}
