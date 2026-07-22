import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Loader2, Plus, Search } from 'lucide-react'
import { useAuth } from '../../hooks/useAuth'
import { useJobs } from './api'
import JobCard from './JobCard'
import NewSearchModal from './NewSearchModal'

// LEADGEN_RUN is held by Sales and super-admin (console/rbac.py). Everyone else
// can watch the pipeline; starting one spends money at Google.
const CAN_RUN = ['SUPER_ADMIN', 'SALES']

const STATUS_FILTERS = [
  { value: '', label: 'All' },
  { value: 'running', label: 'Running' },
  { value: 'queued', label: 'Queued' },
  { value: 'completed', label: 'Completed' },
  { value: 'failed', label: 'Failed' },
]

export default function LeadGenHome() {
  const { role } = useAuth()
  const canRun = CAN_RUN.includes(role)
  const [status, setStatus] = useState('')
  const [creating, setCreating] = useState(false)

  const { data, isLoading, fetchNextPage, hasNextPage, isFetchingNextPage } = useJobs({ status })
  const jobs = data?.pages.flatMap((page) => page.results ?? []) ?? []

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-tx">Lead Generation</h1>
          <p className="mt-1 text-sm text-tx-2">
            Discover businesses on Google Places, enrich and score them, then import the
            good ones into the CRM.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link
            to="/leadgen/queues"
            className="rounded-ctl bg-surface-2 px-3 py-2 text-sm text-tx-2 transition hover:bg-surface-3 hover:text-tx"
          >
            Queues
          </Link>
          <Link
            to="/leadgen/settings"
            className="rounded-ctl bg-surface-2 px-3 py-2 text-sm text-tx-2 transition hover:bg-surface-3 hover:text-tx"
          >
            Providers &amp; cost
          </Link>
          <Link
            to="/leadgen/leads"
            className="rounded-ctl bg-surface-2 px-3 py-2 text-sm text-tx-2 transition hover:bg-surface-3 hover:text-tx"
          >
            All generated leads
          </Link>
          {canRun && (
            <button
              onClick={() => setCreating(true)}
              className="inline-flex items-center gap-2 rounded-ctl bg-brand px-3 py-2 text-sm font-semibold text-white transition hover:bg-brand-d"
            >
              <Plus size={16} /> New search
            </button>
          )}
        </div>
      </header>

      <div className="flex flex-wrap gap-2">
        {STATUS_FILTERS.map((option) => (
          <button
            key={option.value}
            onClick={() => setStatus(option.value)}
            className={
              'rounded-full px-3 py-1 text-xs font-semibold transition ' +
              (status === option.value
                ? 'bg-brand text-white'
                : 'bg-surface-2 text-tx-2 hover:bg-surface-3 hover:text-tx')
            }
          >
            {option.label}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="flex justify-center py-16 text-tx-2">
          <Loader2 className="animate-spin" />
        </div>
      ) : jobs.length === 0 ? (
        <EmptyState canRun={canRun} onStart={() => setCreating(true)} />
      ) : (
        <div className="grid gap-3 lg:grid-cols-2">
          {jobs.map((job) => (
            <JobCard key={job.id} job={job} canManage={canRun} />
          ))}
        </div>
      )}

      {hasNextPage && (
        <div className="flex justify-center">
          <button
            onClick={() => fetchNextPage()}
            disabled={isFetchingNextPage}
            className="rounded-ctl bg-surface-2 px-4 py-2 text-sm text-tx-2 hover:bg-surface-3 hover:text-tx disabled:opacity-50"
          >
            {isFetchingNextPage ? 'Loading…' : 'Load more'}
          </button>
        </div>
      )}

      {creating && <NewSearchModal onClose={() => setCreating(false)} />}
    </div>
  )
}

function EmptyState({ canRun, onStart }) {
  return (
    <div className="rounded-card bg-surface p-12 text-center">
      <Search className="mx-auto text-tx-2" size={28} />
      <h2 className="mt-3 text-sm font-semibold text-tx">No searches yet</h2>
      <p className="mx-auto mt-1 max-w-md text-sm text-tx-2">
        Pick a city, an area and the kinds of business you sell to. Everything runs in the
        background — you can leave this page while it works.
      </p>
      {canRun && (
        <button
          onClick={onStart}
          className="mt-4 rounded-ctl bg-brand px-4 py-2 text-sm font-semibold text-white transition hover:bg-brand-d"
        >
          Start the first search
        </button>
      )}
    </div>
  )
}
