// EmptyState (spec §10/§13) — icon + title + body + optional CTA.
export default function EmptyState({ icon: Icon, title, body, action }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-card border border-dashed border-line bg-white p-10 text-center">
      {Icon && <Icon size={32} className="text-tx-3" />}
      <h3 className="font-head text-lg font-semibold text-ink">{title}</h3>
      {body && <p className="max-w-sm text-sm text-tx-2">{body}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  )
}
