// PassInfoRow — the "secondary information" band: a set of label/value columns.
// Matches the reference passes' paired columns (e.g. "Name / Member ID", or
// "Valid on / Valid at"). Items without a value are dropped, and the row hides
// entirely when nothing survives — the auto-hide-empty-sections rule.
//
// By default the first item aligns left and the last aligns right (the classic
// Apple two-up layout); pass an explicit `align` on an item to override.

function Cell({ label, value, align, theme }) {
  return (
    <div className={`flex min-w-0 flex-col gap-0.5 ${align === 'end' ? 'items-end text-right' : ''}`}>
      {label && (
        <span
          className="text-[10px] font-semibold uppercase tracking-wide"
          style={{ color: theme?.sub }}
        >
          {label}
        </span>
      )}
      <span className="truncate text-[13px] font-semibold" style={{ color: theme?.fg }}>
        {value}
      </span>
    </div>
  )
}

export default function PassInfoRow({ items = [], theme }) {
  const shown = items.filter((it) => it && (it.value ?? '') !== '')
  if (shown.length === 0) return null
  return (
    <div className="flex items-start justify-between gap-4">
      {shown.map((it, i) => (
        <Cell
          key={i}
          label={it.label}
          value={it.value}
          align={it.align || (i === shown.length - 1 && shown.length > 1 ? 'end' : 'start')}
          theme={theme}
        />
      ))}
    </div>
  )
}
