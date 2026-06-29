import Skeleton from './Skeleton'

// Table (spec §10): columns [{key,label,render?}], rows, loading, emptyState,
// onRowClick, pagination. Skeleton rows on load; stacks to cards below md.
export default function Table({
  columns,
  rows = [],
  loading = false,
  emptyState = null,
  onRowClick,
  pagination = null,
}) {
  if (loading) {
    return (
      <div className="overflow-hidden rounded-card border border-line bg-white">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="flex gap-4 border-b border-line p-3 last:border-0">
            {columns.map((c) => (
              <div key={c.key} className="flex-1">
                <Skeleton h={14} />
              </div>
            ))}
          </div>
        ))}
      </div>
    )
  }

  if (!rows.length && emptyState) return emptyState

  return (
    <div>
      {/* Desktop table */}
      <div className="hidden overflow-x-auto rounded-card border border-line bg-white md:block">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-line text-start text-tx-2">
              {columns.map((c) => (
                <th key={c.key} className="px-4 py-3 text-start font-semibold">
                  {c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, ri) => (
              <tr
                key={row.id ?? ri}
                onClick={() => onRowClick?.(row)}
                className={`border-b border-line last:border-0 ${
                  onRowClick ? 'cursor-pointer hover:bg-paper' : ''
                }`}
              >
                {columns.map((c) => (
                  <td key={c.key} className="px-4 py-3 text-tx">
                    {c.render ? c.render(row) : row[c.key]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Mobile cards */}
      <div className="flex flex-col gap-2 md:hidden">
        {rows.map((row, ri) => (
          <div
            key={row.id ?? ri}
            onClick={() => onRowClick?.(row)}
            className={`rounded-card border border-line bg-white p-3 ${
              onRowClick ? 'cursor-pointer' : ''
            }`}
          >
            {columns.map((c) => (
              <div key={c.key} className="flex justify-between gap-3 py-1 text-sm">
                <span className="text-tx-2">{c.label}</span>
                <span className="text-tx">{c.render ? c.render(row) : row[c.key]}</span>
              </div>
            ))}
          </div>
        ))}
      </div>

      {pagination && <div className="mt-3 flex justify-center">{pagination}</div>}
    </div>
  )
}
