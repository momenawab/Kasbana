// DateRange (spec §10) — {value:{from,to}, onChange}. Native date inputs.
export default function DateRange({ value = {}, onChange }) {
  const set = (key) => (e) => onChange({ ...value, [key]: e.target.value })
  return (
    <div className="inline-flex items-center gap-2">
      <input
        type="date"
        value={value.from || ''}
        onChange={set('from')}
        className="rounded-ctl border border-line px-2 py-1.5 text-sm"
        aria-label="from"
      />
      <span className="text-tx-3">—</span>
      <input
        type="date"
        value={value.to || ''}
        onChange={set('to')}
        className="rounded-ctl border border-line px-2 py-1.5 text-sm"
        aria-label="to"
      />
    </div>
  )
}
