// Banner (spec §10) — inline notice with optional action.
const TONES = {
  ink: 'bg-ink text-white',
  amber: 'bg-amber-bg text-amber-d',
  teal: 'bg-teal-bg text-teal',
  danger: 'bg-clay-bg text-danger',
}

export default function Banner({ tone = 'amber', children, action }) {
  return (
    <div
      className={`flex items-center justify-between gap-3 rounded-ctl px-4 py-2 text-sm ${TONES[tone]}`}
    >
      <span>{children}</span>
      {action}
    </div>
  )
}
