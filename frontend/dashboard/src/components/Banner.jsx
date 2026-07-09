// Banner (spec §10) — inline notice with optional action.
const TONES = {
  slate: 'bg-slate text-white',
  violet: 'bg-violet-bg text-violet-d',
  teal: 'bg-teal-bg text-teal',
  danger: 'bg-fuchsia-bg text-danger',
}

export default function Banner({ tone = 'violet', children, action }) {
  return (
    <div
      className={`flex items-center justify-between gap-3 rounded-ctl px-4 py-2 text-sm ${TONES[tone]}`}
    >
      <span>{children}</span>
      {action}
    </div>
  )
}
