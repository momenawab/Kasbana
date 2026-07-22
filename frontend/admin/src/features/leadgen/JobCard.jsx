import { Link } from 'react-router-dom'
import { Loader2, Pause, Play, RotateCcw, X } from 'lucide-react'
import Badge from '../../components/Badge'
import { JOB_TONES, STAGE_LABELS, TERMINAL_STATUSES, typeLabel } from './constants'
import { useJobAction } from './api'

// Which controls a job offers, derived from its status rather than always
// rendering four buttons and disabling three. A disabled Pause on a finished
// job is noise; the operator only ever has one or two real choices.
function actionsFor(status) {
  if (status === 'running') return ['pause', 'cancel']
  if (status === 'paused') return ['resume', 'cancel']
  if (status === 'queued') return ['cancel']
  if (TERMINAL_STATUSES.includes(status)) return ['retry']
  return []
}

const ACTION_META = {
  pause: { Icon: Pause, label: 'Pause' },
  resume: { Icon: Play, label: 'Resume' },
  cancel: { Icon: X, label: 'Cancel' },
  retry: { Icon: RotateCcw, label: 'Retry' },
}

export default function JobCard({ job, canManage }) {
  const action = useJobAction()
  const running = !TERMINAL_STATUSES.includes(job.status)
  const where = [job.street, job.city, job.province].filter(Boolean).join(', ')

  return (
    <div className="rounded-card bg-surface p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <Link
            to={`/leadgen/jobs/${job.id}`}
            className="text-sm font-semibold text-tx hover:text-brand"
          >
            {where || job.city}
          </Link>
          <p className="mt-1 truncate text-xs text-tx-2">
            {job.business_types.map(typeLabel).join(' · ')} · {job.radius_km} km · up to{' '}
            {job.max_results}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge tone={JOB_TONES[job.status]}>{job.status}</Badge>
          {canManage &&
            actionsFor(job.status).map((name) => {
              const { Icon, label } = ACTION_META[name]
              return (
                <button
                  key={name}
                  title={label}
                  disabled={action.isPending}
                  onClick={() => action.mutate({ jobId: job.id, action: name })}
                  className="rounded-ctl bg-surface-2 p-1.5 text-tx-2 transition hover:bg-surface-3 hover:text-tx disabled:opacity-50"
                >
                  <Icon size={14} />
                </button>
              )
            })}
        </div>
      </div>

      {running && (
        <div className="mt-3">
          <div className="h-1.5 overflow-hidden rounded-full bg-surface-2">
            <div
              className="h-full bg-brand transition-all duration-500"
              style={{ width: `${job.progress_percent}%` }}
            />
          </div>
          <p className="mt-1.5 flex items-center gap-1.5 text-xs text-tx-2">
            <Loader2 size={11} className="animate-spin" />
            {STAGE_LABELS[job.stage] || 'Starting'} — {job.discovered_count} found
          </p>
        </div>
      )}

      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-tx-2">
        <Stat label="found" value={job.discovered_count} />
        <Stat label="merged" value={job.duplicate_count} />
        <Stat label="ready" value={job.ready_count} tone="text-success" />
        <Stat label="imported" value={job.imported_count} />
        {job.failed_count > 0 && (
          <Stat label="failed" value={job.failed_count} tone="text-danger" />
        )}
      </div>

      {job.error && <p className="mt-2 text-xs text-danger">{job.error}</p>}
    </div>
  )
}

function Stat({ label, value, tone = 'text-tx' }) {
  return (
    <span>
      <span className={`font-semibold ${tone}`}>{value}</span> {label}
    </span>
  )
}
