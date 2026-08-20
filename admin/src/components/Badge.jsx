const TONES = {
  neutral: 'bg-surface-2 text-tx-2',
  brand: 'bg-brand-bg text-brand',
  success: 'bg-surface-2 text-success',
  warn: 'bg-surface-2 text-warn',
  danger: 'bg-surface-2 text-danger',
  info: 'bg-surface-2 text-info',
}

export default function Badge({ tone = 'neutral', children }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${TONES[tone] || TONES.neutral}`}
    >
      {children}
    </span>
  )
}
