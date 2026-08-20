import { pct } from './format'

export default function MetricCard({ label, value, subtext, tone = 'brand', progress }) {
  const colors = { brand: 'bg-brand', healthy: 'bg-emerald-500', warning: 'bg-amber-500', critical: 'bg-red-500' }
  return <article className="rounded-ctl border border-line bg-surface p-4 shadow-sm">
    <p className="text-xs font-medium uppercase tracking-wide text-tx-3">{label}</p>
    <div className="mt-2 flex items-end justify-between gap-3"><strong className="text-2xl text-tx">{value}</strong><span className="text-xs text-tx-3">{subtext}</span></div>
    {progress != null && <div className="mt-3 h-1.5 overflow-hidden rounded bg-surface-2"><div className={`h-full ${colors[tone] || colors.brand}`} style={{ width: pct(progress) }} /></div>}
  </article>
}
