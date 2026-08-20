import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Loader2, Plus, Settings2, Upload } from 'lucide-react'
import { useLeadKpis, useLeads } from './api'
import { useCrmChoices } from './crm'
import { useDebounced } from './useDebounced'
import LeadKpis from './LeadKpis'
import LeadFilters from './LeadFilters'
import LeadsTable from './LeadsTable'
import { DEFAULT_VISIBLE } from './columns'
import ColumnPicker from './ColumnPicker'
import BulkBar from './BulkBar'
import AddLeadModal from './AddLeadModal'
import ImportModal from './ImportModal'
import { useAuth } from '../../hooks/useAuth'

const CAN_MANAGE = ['SUPER_ADMIN', 'SALES']
const COLUMNS_KEY = 'stampn.leads.columns'

// The sort the pipeline should open on. Not newest-first: a sales user opening
// this screen is asking "who do I call next", and the answer is the hottest
// lead, not the most recent form submission.
const DEFAULT_SORT = '-lead_score'

export default function LeadsHome() {
  const navigate = useNavigate()
  const { role } = useAuth()
  const canManage = CAN_MANAGE.includes(role)
  // CRM_CONFIGURE is super-admin-only (console/rbac.py) — reshaping everyone's
  // dropdowns is platform config, not a day-to-day sales action.
  const isSuper = role === 'SUPER_ADMIN'

  const [filters, setFilters] = useState({ q: '' })
  const [sort, setSort] = useState(DEFAULT_SORT)
  const [selected, setSelected] = useState(new Set())
  const [adding, setAdding] = useState(false)
  const [importing, setImporting] = useState(false)
  const [visible, setVisible] = useState(loadColumns)

  // Only the search box needs debouncing — the dropdowns fire once per choice.
  const debouncedQ = useDebounced(filters.q ?? '', 350)
  const query = useMemo(
    () => ({ ...filters, q: debouncedQ, sort }),
    [filters, debouncedQ, sort],
  )

  const { data, isLoading, isFetching, fetchNextPage, hasNextPage, isFetchingNextPage } =
    useLeads(query)
  const { data: kpis, isLoading: kpisLoading } = useLeadKpis(query)
  const { data: choices } = useCrmChoices()

  const rows = data?.pages.flatMap((p) => p.results) ?? []
  const hasFilters = Object.entries(filters).some(([k, v]) => k !== 'q' && v && v.length !== 0)

  const setColumns = (next) => {
    setVisible(next)
    saveColumns(next)
  }

  // A KPI card hands back either a filter object or one of the two named
  // follow-up views. Both replace the current filters rather than merging:
  // clicking "Overdue" while a status filter is on should show the overdue
  // leads, not the empty intersection of the two.
  const drill = (filter) => {
    setSelected(new Set())
    if (filter === 'overdue') return setFilters({ q: '', overdue: '1' })
    if (filter === 'today') return setFilters({ q: '', follow_up: 'today' })
    setFilters({ q: '', ...filter })
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h1 className="font-head text-2xl font-bold text-tx">Leads</h1>
          {isFetching && !isLoading && <Loader2 size={15} className="animate-spin text-tx-3" />}
        </div>
        <div className="flex items-center gap-2">
          {/* CRM config lives beside the CRM rather than in Operations →
              Settings: that screen is platform/Engineering config, this is the
              sales vocabulary, and this is where someone goes looking for it. */}
          {isSuper && (
            <Link
              to="/leads/settings"
              className="flex items-center gap-2 rounded-ctl border border-line px-3 py-2 text-sm text-tx-2 transition hover:border-brand hover:text-brand"
              title="CRM Configuration"
            >
              <Settings2 size={15} />
              <span className="hidden sm:inline">Settings</span>
            </Link>
          )}
          <ColumnPicker visible={visible} onChange={setColumns} />
          {canManage && (
            <button
              onClick={() => setImporting(true)}
              className="flex items-center gap-2 rounded-ctl border border-line px-3 py-2 text-sm text-tx-2 transition hover:border-brand hover:text-brand"
              title="Import from CSV or Excel"
            >
              <Upload size={15} />
              <span className="hidden sm:inline">Import</span>
            </button>
          )}
          {canManage && (
            <button
              onClick={() => setAdding(true)}
              className="flex items-center gap-2 rounded-ctl bg-brand px-4 py-2 text-sm font-semibold text-white transition hover:bg-brand-d"
            >
              <Plus size={15} /> Add Lead
            </button>
          )}
        </div>
      </div>

      <LeadKpis data={kpis} isLoading={kpisLoading} onDrill={drill} />

      <LeadFilters
        filters={filters}
        onChange={(f) => {
          setFilters(f)
          setSelected(new Set())
        }}
        choices={choices}
      />

      {selected.size > 0 && canManage && (
        <BulkBar selected={selected} onClear={() => setSelected(new Set())} choices={choices} />
      )}

      <LeadsTable
        rows={rows}
        choices={choices}
        isLoading={isLoading}
        visible={visible}
        sort={sort}
        onSort={setSort}
        selected={selected}
        onSelect={setSelected}
        onOpen={(lead) => navigate(`/leads/${lead.id}`)}
        hasFilters={hasFilters}
      />

      {hasNextPage && (
        <button
          onClick={() => fetchNextPage()}
          disabled={isFetchingNextPage}
          className="mx-auto rounded-ctl border border-line px-4 py-2 text-sm text-tx-2 hover:border-brand hover:text-brand disabled:opacity-60"
        >
          {isFetchingNextPage ? 'Loading…' : 'Load more'}
        </button>
      )}

      {adding && (
        <AddLeadModal
          choices={choices}
          onClose={() => setAdding(false)}
          onCreated={(lead) => navigate(`/leads/${lead.id}`)}
        />
      )}

      {importing && <ImportModal choices={choices} onClose={() => setImporting(false)} />}
    </div>
  )
}

// A stored column set is merged against the current COLUMNS, not trusted
// wholesale: a release that adds a column would otherwise leave it invisible
// forever for everyone who had already picked their columns.
function loadColumns() {
  try {
    const saved = JSON.parse(localStorage.getItem(COLUMNS_KEY))
    if (!Array.isArray(saved)) return DEFAULT_VISIBLE
    return saved.length ? saved : DEFAULT_VISIBLE
  } catch {
    return DEFAULT_VISIBLE
  }
}

function saveColumns(cols) {
  try {
    localStorage.setItem(COLUMNS_KEY, JSON.stringify(cols))
  } catch {
    // A private-mode browser refusing localStorage must not break the table.
  }
}
