import { useState } from 'react'
import { Search, SlidersHorizontal, X } from 'lucide-react'
import { useSalesUsers } from './api'
import { KIND, LEAD_TYPES, optionsFor } from './crm'

// The filter bar. Search and lead type sit out in the open because they are what
// people reach for constantly; the other nine live behind "Filters" so the
// default view is a table, not a control panel.
//
// Every dropdown's values come from `choices` (Settings → CRM Configuration) —
// nothing here is a hardcoded list.
export default function LeadFilters({ filters, onChange, choices }) {
  const [open, setOpen] = useState(false)
  const { data: salesUsers } = useSalesUsers()

  const set = (key, value) => onChange({ ...filters, [key]: value })

  // A multi-select as a plain <select multiple> is miserable to use; these send
  // one value at a time, which the backend ORs when repeated. The KPI drill-downs
  // are what set several at once.
  const setOne = (key) => (e) => set(key, e.target.value ? [e.target.value] : [])
  const one = (key) => filters[key]?.[0] ?? ''

  const active = countActive(filters)

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex min-w-[220px] flex-1 items-center gap-2 rounded-ctl border border-line bg-surface px-3 py-2">
          <Search size={16} className="text-tx-3" />
          <input
            value={filters.q ?? ''}
            onChange={(e) => set('q', e.target.value)}
            placeholder="Search business, owner, phone, email…"
            className="flex-1 bg-transparent text-sm text-tx outline-none placeholder:text-tx-3"
          />
          {filters.q && (
            <button onClick={() => set('q', '')} className="text-tx-3 hover:text-tx">
              <X size={14} />
            </button>
          )}
        </div>

        <Select value={one('lead_type')} onChange={setOne('lead_type')} label="All types">
          {LEAD_TYPES.map((t) => (
            <option key={t.slug} value={t.slug}>
              {t.label}
            </option>
          ))}
        </Select>

        <button
          onClick={() => setOpen((o) => !o)}
          className={`flex items-center gap-2 rounded-ctl border px-3 py-2 text-sm transition ${
            open || active
              ? 'border-brand text-brand'
              : 'border-line text-tx-2 hover:border-brand hover:text-brand'
          }`}
        >
          <SlidersHorizontal size={15} />
          Filters
          {active > 0 && (
            <span className="rounded-full bg-brand px-1.5 text-xs font-semibold text-white">
              {active}
            </span>
          )}
        </button>

        {active > 0 && (
          <button
            onClick={() => onChange({ q: filters.q ?? '' })}
            className="text-sm text-tx-3 underline-offset-2 hover:text-tx hover:underline"
          >
            Clear
          </button>
        )}
      </div>

      {open && (
        <div className="grid grid-cols-1 gap-3 rounded-card border border-line bg-surface p-4 sm:grid-cols-2 lg:grid-cols-4">
          <Labelled label="Status">
            <Select value={one('status')} onChange={setOne('status')} label="Any status" full>
              {optionsFor(choices, KIND.STATUS).map((c) => (
                <option key={c.slug} value={c.slug}>
                  {c.label}
                </option>
              ))}
            </Select>
          </Labelled>

          <Labelled label="Priority">
            <Select value={one('priority')} onChange={setOne('priority')} label="Any priority" full>
              {optionsFor(choices, KIND.PRIORITY).map((c) => (
                <option key={c.slug} value={c.slug}>
                  {c.label}
                </option>
              ))}
            </Select>
          </Labelled>

          <Labelled label="Temperature">
            <Select
              value={one('temperature')}
              onChange={setOne('temperature')}
              label="Any temperature"
              full
            >
              {optionsFor(choices, KIND.TEMPERATURE).map((c) => (
                <option key={c.slug} value={c.slug}>
                  {c.label}
                </option>
              ))}
            </Select>
          </Labelled>

          <Labelled label="Source">
            <Select value={one('source')} onChange={setOne('source')} label="Any source" full>
              {optionsFor(choices, KIND.SOURCE).map((c) => (
                <option key={c.slug} value={c.slug}>
                  {c.label}
                </option>
              ))}
            </Select>
          </Labelled>

          <Labelled label="Category">
            <Select value={one('category')} onChange={setOne('category')} label="Any category" full>
              {optionsFor(choices, KIND.CATEGORY).map((c) => (
                <option key={c.slug} value={c.slug}>
                  {c.label}
                </option>
              ))}
            </Select>
          </Labelled>

          <Labelled label="Assigned sales">
            {/* Unassigned is its own flag, not an id — "nobody" cannot be
                expressed as ?assigned_sales=<uuid>, and it is the single most
                useful thing to filter for. */}
            <select
              value={filters.unassigned ? '__none__' : one('assigned_sales')}
              onChange={(e) => {
                const v = e.target.value
                onChange({
                  ...filters,
                  unassigned: v === '__none__' ? '1' : '',
                  assigned_sales: v && v !== '__none__' ? [v] : [],
                })
              }}
              className={selectClass(true)}
            >
              <option value="">Anyone</option>
              <option value="__none__">Unassigned</option>
              {(salesUsers ?? []).map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name || a.email}
                </option>
              ))}
            </select>
          </Labelled>

          <Labelled label="Area">
            <input
              value={filters.area ?? ''}
              onChange={(e) => set('area', e.target.value)}
              placeholder="Any area"
              className={selectClass(true)}
            />
          </Labelled>

          <Labelled label="Follow-up">
            <select
              value={filters.overdue ? 'overdue' : (filters.follow_up ?? '')}
              onChange={(e) => {
                const v = e.target.value
                onChange({
                  ...filters,
                  overdue: v === 'overdue' ? '1' : '',
                  follow_up: v === 'today' ? 'today' : '',
                })
              }}
              className={selectClass(true)}
            >
              <option value="">Any time</option>
              <option value="today">Due today</option>
              <option value="overdue">Overdue</option>
            </select>
          </Labelled>

          <Labelled label="Created from">
            <input
              type="date"
              value={filters.created_from ?? ''}
              onChange={(e) => set('created_from', e.target.value)}
              className={selectClass(true)}
            />
          </Labelled>

          <Labelled label="Created to">
            <input
              type="date"
              value={filters.created_to ?? ''}
              onChange={(e) => set('created_to', e.target.value)}
              className={selectClass(true)}
            />
          </Labelled>
        </div>
      )}
    </div>
  )
}

// `q` is not counted: the search box shows its own state, so counting it would
// make the badge tick up for something already visible.
function countActive(filters) {
  return Object.entries(filters).filter(
    ([k, v]) => k !== 'q' && v != null && v !== '' && v.length !== 0,
  ).length
}

const selectClass = (full) =>
  `${full ? 'w-full' : ''} rounded-ctl border border-line bg-surface px-3 py-2 text-sm text-tx placeholder:text-tx-3 focus:border-brand focus:outline-none`

function Select({ value, onChange, label, full, children }) {
  return (
    <select value={value} onChange={onChange} className={selectClass(full)}>
      <option value="">{label}</option>
      {children}
    </select>
  )
}

function Labelled({ label, children }) {
  return (
    <label className="flex flex-col gap-1 text-xs text-tx-3">
      {label}
      {children}
    </label>
  )
}
