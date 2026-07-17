const tones = { healthy: 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400', ok: 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400', warning: 'bg-amber-500/15 text-amber-700 dark:text-amber-400', critical: 'bg-red-500/15 text-red-600 dark:text-red-400', open: 'bg-red-500/15 text-red-600 dark:text-red-400', resolved: 'bg-slate-500/15 text-tx-2' }
export default function StatusBadge({ value }) {
  const label = String(value || 'unknown').replace(/_/g, ' ')
  return <span className={`rounded-full px-2.5 py-1 text-xs font-semibold capitalize ${tones[value] || 'bg-surface-2 text-tx-2'}`}>{label}</span>
}
