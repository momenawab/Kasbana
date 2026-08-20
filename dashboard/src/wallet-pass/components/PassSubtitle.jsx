// PassSubtitle — a single muted supporting line (e.g. "Scan at entrance"). Hides
// itself when empty. `align` centres it for footer-style captions.

export default function PassSubtitle({ children, theme, align = 'start' }) {
  if (!children) return null
  return (
    <p
      className={`text-xs ${align === 'center' ? 'text-center' : ''}`}
      style={{ color: theme?.sub }}
    >
      {children}
    </p>
  )
}
