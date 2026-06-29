// Skeleton loading block (spec §10/§13).
export default function Skeleton({ w = '100%', h = 16, rounded = 'ctl', className = '' }) {
  const radius = rounded === 'full' ? '9999px' : rounded === 'card' ? '16px' : '10px'
  return (
    <span
      className={`block animate-pulse bg-line/70 ${className}`}
      style={{ width: w, height: h, borderRadius: radius }}
      aria-hidden="true"
    />
  )
}
