// Badge (spec §10) — tone maps to Direction-C palette.
const TONES = {
  neutral: 'bg-paper text-tx-2 border border-line',
  amber: 'bg-amber-bg text-amber-d',
  teal: 'bg-teal-bg text-teal',
  clay: 'bg-clay-bg text-clay',
  success: 'bg-teal-bg text-success',
  danger: 'bg-clay-bg text-danger',
}

export default function Badge({ tone = 'neutral', children }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${TONES[tone] || TONES.neutral}`}
    >
      {children}
    </span>
  )
}
