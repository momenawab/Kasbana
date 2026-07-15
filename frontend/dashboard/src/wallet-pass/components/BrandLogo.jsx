// BrandLogo — the round logo chip in a pass header. Shows the merchant image
// when provided, otherwise a tinted monogram (first letter of the brand). Pure
// and presentational.

export default function BrandLogo({ src, name = '', size = 28, theme }) {
  const dim = { width: size, height: size }
  if (src) {
    return (
      <img
        src={src}
        alt=""
        style={dim}
        className="shrink-0 rounded-full bg-white/90 object-cover"
      />
    )
  }
  return (
    <span
      style={{ ...dim, background: 'rgba(255,255,255,0.22)', color: theme?.fg }}
      className="flex shrink-0 items-center justify-center rounded-full text-xs font-bold uppercase"
    >
      {name.trim().slice(0, 1) || '•'}
    </span>
  )
}
