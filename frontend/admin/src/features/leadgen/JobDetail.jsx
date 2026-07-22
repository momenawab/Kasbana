import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, Loader2 } from 'lucide-react'
import Badge from '../../components/Badge'
import { useAuth } from '../../hooks/useAuth'
import { useJob, useJobLogs, useRunStage } from './api'
import { JOB_TONES, STAGE_LABELS, TERMINAL_STATUSES, typeLabel } from './constants'
import LeadsPanel from './LeadsPanel'

const CAN_RUN = ['SUPER_ADMIN', 'SALES']

export default function JobDetail() {
  const { id } = useParams()
  const { role } = useAuth()
  const [showLogs, setShowLogs] = useState(false)
  const { data: job, isLoading } = useJob(id)

  if (isLoading || !job) {
    return (
      <div className="flex justify-center py-20 text-tx-2">
        <Loader2 className="animate-spin" />
      </div>
    )
  }

  const running = !TERMINAL_STATUSES.includes(job.status)
  const where = [job.street, job.city, job.province].filter(Boolean).join(', ')

  return (
    <div className="space-y-5">
      <Link
        to="/leadgen"
        className="inline-flex items-center gap-1.5 text-sm text-tx-2 hover:text-tx"
      >
        <ArrowLeft size={14} /> All searches
      </Link>

      <header className="rounded-card bg-surface p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-lg font-semibold text-tx">{where || job.city}</h1>
            <p className="mt-1 text-sm text-tx-2">
              {job.business_types.map(typeLabel).join(' · ')} · {job.radius_km} km · up to{' '}
              {job.max_results} · {job.priority} priority
            </p>
            <p className="mt-1 text-xs text-tx-2">
              Started by {job.created_by_name}
              {job.started_at && ` · ${new Date(job.started_at).toLocaleString()}`}
            </p>
          </div>
          <Badge tone={JOB_TONES[job.status]}>{job.status}</Badge>
        </div>

        {running && (
          <div className="mt-4">
            <div className="h-2 overflow-hidden rounded-full bg-surface-2">
              <div
                className="h-full bg-brand transition-all duration-500"
                style={{ width: `${job.progress_percent}%` }}
              />
            </div>
            <p className="mt-2 flex items-center gap-1.5 text-sm text-tx-2">
              <Loader2 size={12} className="animate-spin" />
              {STAGE_LABELS[job.stage] || 'Starting'}
            </p>
          </div>
        )}

        {job.error && (
          <p className="mt-3 rounded-ctl bg-surface-2 px-3 py-2 text-sm text-danger">
            {job.error}
          </p>
        )}

        <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <Stat label="Found" value={job.discovered_count} />
          <Stat label="Merged" value={job.duplicate_count} />
          <Stat label="Crawled" value={job.crawled_count} />
          <Stat label="Ready" value={job.ready_count} tone="text-success" />
          <Stat label="Imported" value={job.imported_count} tone="text-brand" />
          <Stat label="Failed" value={job.failed_count} tone={job.failed_count ? 'text-danger' : 'text-tx'} />
        </div>
      </header>

      <div>
        <button
          onClick={() => setShowLogs((v) => !v)}
          className="text-sm text-tx-2 hover:text-tx"
        >
          {showLogs ? 'Hide' : 'Show'} pipeline log
        </button>
        {showLogs && <JobLogs jobId={id} />}
      </div>

      {CAN_RUN.includes(role) && <StageActions jobId={id} />}

      <LeadsPanel jobId={id} />
    </div>
  )
}

// The two paid stages are run on demand rather than automatically after
// discovery: they cost money per lead, and an operator should decide whether a
// given batch is worth enriching before it is charged for.
function StageActions({ jobId }) {
  const run = useRunStage()
  const [done, setDone] = useState('')

  return (
    <div className="flex flex-wrap items-center gap-3 rounded-card bg-surface p-4">
      <div className="mr-auto">
        <p className="text-sm font-semibold text-tx">Enrich further</p>
        <p className="text-xs text-tx-2">
          Both cost money per lead and run in the background.
        </p>
      </div>
      {[
        ['verify', 'Verify contacts'],
        ['ai', 'Run AI analysis'],
      ].map(([stage, label]) => (
        <button
          key={stage}
          onClick={() =>
            run.mutate({ jobId, stage }, { onSuccess: (d) => setDone(`${label}: ${d.dispatch}`) })
          }
          disabled={run.isPending}
          className="rounded-ctl bg-surface-2 px-3 py-2 text-sm font-semibold text-tx transition hover:bg-surface-3 disabled:opacity-50"
        >
          {label}
        </button>
      ))}
      {done && <span className="text-xs text-tx-2">{done}</span>}
    </div>
  )
}

function JobLogs({ jobId }) {
  const { data, isLoading } = useJobLogs(jobId)
  const logs = data?.results ?? []

  if (isLoading) return <p className="mt-2 text-sm text-tx-2">Loading…</p>
  if (!logs.length) return <p className="mt-2 text-sm text-tx-2">No entries yet.</p>

  return (
    <ul className="mt-2 max-h-72 space-y-1 overflow-y-auto rounded-card bg-surface p-3">
      {logs.map((entry) => (
        <li key={entry.id} className="flex gap-2 text-xs">
          <span className="shrink-0 text-tx-2">
            {new Date(entry.created_at).toLocaleTimeString()}
          </span>
          <span
            className={
              entry.level === 'error'
                ? 'text-danger'
                : entry.level === 'warning'
                  ? 'text-warn'
                  : 'text-tx-2'
            }
          >
            {entry.message}
          </span>
        </li>
      ))}
    </ul>
  )
}

function Stat({ label, value, tone = 'text-tx' }) {
  return (
    <div className="rounded-ctl bg-surface-2 px-3 py-2">
      <p className={`text-lg font-semibold ${tone}`}>{value}</p>
      <p className="text-xs text-tx-2">{label}</p>
    </div>
  )
}
