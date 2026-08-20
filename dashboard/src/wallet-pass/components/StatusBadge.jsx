// StatusBadge — a small rounded pill (e.g. "VIP", "Boarding", "Gold"). Sits in
// the header's top-right. Renders nothing when there is no label.

export default function StatusBadge({ children, theme, tone = 'solid' }) {
  if (!children) return null
  const solid = tone === 'solid'
  return (
    <span
      style={
        solid
          ? { background: theme?.accent, color: theme?.accentFg }
          : { border: `1px solid ${theme?.hairline}`, color: theme?.fg }
      }
      className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide"
    >
      {children}
    </span>
  )
}
