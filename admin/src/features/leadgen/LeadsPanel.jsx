import { useMemo, useState } from 'react'
import { Check, Download, Globe, Instagram, Loader2, Mail, Upload, User } from 'lucide-react'
import Badge from '../../components/Badge'
import { useAuth } from '../../hooks/useAuth'
import { useDebounced } from '../leads/useDebounced'
import { downloadExport, useBulkAction, useGeneratedLeads, useImportLeads } from './api'
import { BUSINESS_TYPES, SCORE_LABELS, SCORE_TONES, LEAD_STATES } from './constants'
import LeadDrawer from './LeadDrawer'

const CAN_IMPORT = ['SUPER_ADMIN', 'SALES']

// Shared by the job page and the all-leads page. One component rather than two
// near-identical ones: the only real difference is whether a job is pinned.
export default function LeadsPanel({ jobId }) {
  const { role } = useAuth()
  const canImport = CAN_IMPORT.includes(role)

  const [filters, setFilters] = useState({ q: '' })
  const [selected, setSelected] = useState(new Set())
  const [openLead, setOpenLead] = useState(null)
  const [result, setResult] = useState(null)

  const debouncedQ = useDebounced(filters.q ?? '', 350)
  const query = useMemo(
    () => ({ ...filters, q: debouncedQ, ...(jobId ? { job_id: jobId } : {}) }),
    [filters, debouncedQ, jobId],
  )

  const { data, isLoading, fetchNextPage, hasNextPage, isFetchingNextPage } =
    useGeneratedLeads(query)
  const leads = data?.pages.flatMap((page) => page.results ?? []) ?? []

  const importLeads = useImportLeads()
  const bulk = useBulkAction()
  const set = (key, value) => setFilters((current) => ({ ...current, [key]: value }))

  function toggle(id) {
    setSelected((current) => {
      const next = new Set(current)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  // Only leads that can actually be imported are selectable in bulk — an
  // already-imported row would just come back as a skip.
  const importable = leads.filter((lead) => !lead.imported_at)
  const allSelected = importable.length > 0 && importable.every((l) => selected.has(l.id))

  async function runImport(force) {
    const payload = { lead_ids: [...selected], force }
    const outcome = await importLeads.mutateAsync(payload)
    setResult(outcome)
    if (outcome.imported > 0) setSelected(new Set())
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        <input
          value={filters.q}
          onChange={(e) => set('q', e.target.value)}
          placeholder="Search name, address, phone or domain"
          className="min-w-[220px] flex-1 rounded-ctl bg-surface-2 px-3 py-2 text-sm text-tx outline-none placeholder:text-tx-2/60"
        />
        <Select value={filters.score_label} onChange={(v) => set('score_label', v)} label="Any score">
          {SCORE_LABELS.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </Select>
        <Select value={filters.state} onChange={(v) => set('state', v)} label="Any state">
          {LEAD_STATES.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </Select>
        <Select value={filters.category} onChange={(v) => set('category', v)} label="Any type">
          {BUSINESS_TYPES.map((t) => (
            <option key={t.value} value={t.value}>
              {t.label}
            </option>
          ))}
        </Select>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {[
          ['has_website', 'Has website'],
          ['has_email', 'Has email'],
          ['has_owner', 'Has owner name'],
          ['has_instagram', 'Instagram'],
          ['not_imported', 'Not imported'],
        ].map(([key, label]) => (
          <Chip key={key} on={filters[key] === 'true'} onClick={() => set(key, filters[key] === 'true' ? '' : 'true')}>
            {label}
          </Chip>
        ))}
        <span className="ml-auto flex items-center gap-1 text-xs text-tx-2">
          <Download size={12} /> Export
          {['csv', 'xlsx', 'json'].map((format) => (
            <button
              key={format}
              onClick={() => downloadExport(format, query)}
              className="rounded-ctl bg-surface-2 px-2 py-1 font-semibold uppercase text-tx-2 transition hover:bg-surface-3 hover:text-tx"
            >
              {format}
            </button>
          ))}
        </span>
      </div>

      {canImport && selected.size > 0 && (
        <div className="flex flex-wrap items-center gap-3 rounded-card bg-brand-bg px-4 py-3">
          <span className="text-sm font-semibold text-tx">{selected.size} selected</span>
          <button
            onClick={() => runImport(false)}
            disabled={importLeads.isPending}
            className="inline-flex items-center gap-2 rounded-ctl bg-brand px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-50"
          >
            {importLeads.isPending ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <Upload size={14} />
            )}
            Import to CRM
          </button>
          {[
            ['verify', 'Verify contacts'],
            ['rerun_ai', 'Run AI'],
            ['reject', 'Reject'],
          ].map(([action, label]) => (
            <button
              key={action}
              onClick={() =>
                bulk.mutate(
                  { lead_ids: [...selected], action },
                  { onSuccess: (d) => setResult({ imported: 0, skipped: [], bulk: d }) },
                )
              }
              disabled={bulk.isPending}
              className="rounded-ctl bg-surface-2 px-3 py-1.5 text-sm text-tx transition hover:bg-surface-3 disabled:opacity-50"
            >
              {label}
            </button>
          ))}
          <button onClick={() => setSelected(new Set())} className="text-sm text-tx-2 hover:text-tx">
            Clear
          </button>
        </div>
      )}

      {result && <ImportResult result={result} onForce={() => runImport(true)} onDismiss={() => setResult(null)} />}

      {isLoading ? (
        <div className="flex justify-center py-16 text-tx-2">
          <Loader2 className="animate-spin" />
        </div>
      ) : leads.length === 0 ? (
        <p className="rounded-card bg-surface p-10 text-center text-sm text-tx-2">
          No leads match these filters.
        </p>
      ) : (
        <div className="overflow-x-auto rounded-card bg-surface">
          <table className="w-full text-sm">
            <thead className="border-b border-surface-2 text-left text-xs uppercase tracking-wide text-tx-2">
              <tr>
                {canImport && (
                  <th className="w-10 p-3">
                    <input
                      type="checkbox"
                      checked={allSelected}
                      onChange={() =>
                        setSelected(allSelected ? new Set() : new Set(importable.map((l) => l.id)))
                      }
                    />
                  </th>
                )}
                <th className="p-3">Business</th>
                <th className="p-3">Score</th>
                <th className="p-3">Reviews</th>
                <th className="p-3">Signals</th>
                <th className="p-3">Owner</th>
                <th className="p-3">State</th>
              </tr>
            </thead>
            <tbody>
              {leads.map((lead) => (
                <tr
                  key={lead.id}
                  onClick={() => setOpenLead(lead.id)}
                  className="cursor-pointer border-b border-surface-2/50 transition last:border-0 hover:bg-surface-2/60"
                >
                  {canImport && (
                    <td className="p-3" onClick={(e) => e.stopPropagation()}>
                      <input
                        type="checkbox"
                        disabled={!!lead.imported_at}
                        checked={selected.has(lead.id)}
                        onChange={() => toggle(lead.id)}
                      />
                    </td>
                  )}
                  <td className="p-3">
                    <p className="font-medium text-tx">{lead.business_name}</p>
                    <p className="text-xs text-tx-2">{lead.address}</p>
                  </td>
                  <td className="p-3">
                    <Badge tone={SCORE_TONES[lead.score_label]}>
                      {lead.fit_score} {lead.score_label}
                    </Badge>
                  </td>
                  <td className="p-3 text-tx-2">
                    {lead.reviews_count}
                    {lead.rating ? <span className="text-xs"> · {lead.rating}★</span> : null}
                    {lead.branch_count > 1 && (
                      <span className="ml-1 text-xs text-brand">{lead.branch_count} br</span>
                    )}
                  </td>
                  <td className="p-3">
                    <div className="flex gap-1.5 text-tx-2">
                      {lead.has_website && <Globe size={14} title="Has website" />}
                      {lead.has_email && <Mail size={14} title="Has email" />}
                      {lead.social_platforms?.includes('instagram') && (
                        <Instagram size={14} title="Instagram" />
                      )}
                    </div>
                  </td>
                  <td className="p-3 text-xs text-tx-2">
                    {lead.owner_name ? (
                      <span className="flex items-center gap-1 text-tx">
                        <User size={12} /> {lead.owner_name}
                      </span>
                    ) : (
                      '—'
                    )}
                  </td>
                  <td className="p-3">
                    {lead.imported_at ? (
                      <Badge tone="success">
                        <Check size={11} /> Imported
                      </Badge>
                    ) : lead.crm_match ? (
                      <Badge tone="warn">In CRM</Badge>
                    ) : (
                      <Badge>{lead.state}</Badge>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
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

      {openLead && (
        <LeadDrawer leadId={openLead} onClose={() => setOpenLead(null)} canManage={canImport} />
      )}
    </div>
  )
}

// A partial import is the normal outcome, not an error: some leads match an
// existing CRM record and need a decision. Showing what happened per lead beats
// a toast that says "2 of 5 imported" and leaves the operator guessing which.
function ImportResult({ result, onForce, onDismiss }) {
  if (result.bulk) {
    return (
      <div className="flex items-center justify-between rounded-card bg-surface p-4">
        <p className="text-sm text-tx">
          <span className="font-semibold text-success">{result.bulk.affected}</span> leads:{' '}
          {result.bulk.action.replace('_', ' ')}
        </p>
        <button onClick={onDismiss} className="text-xs text-tx-2 hover:text-tx">
          Dismiss
        </button>
      </div>
    )
  }

  return (
    <div className="rounded-card bg-surface p-4">
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm text-tx">
          <span className="font-semibold text-success">{result.imported}</span> imported
          {result.skipped?.length > 0 && (
            <>
              , <span className="font-semibold text-warn">{result.skipped.length}</span> skipped
            </>
          )}
        </p>
        <button onClick={onDismiss} className="text-xs text-tx-2 hover:text-tx">
          Dismiss
        </button>
      </div>
      {result.skipped?.length > 0 && (
        <>
          <ul className="mt-2 space-y-1">
            {result.skipped.map((row) => (
              <li key={row.lead_id} className="text-xs text-tx-2">
                <span className="text-tx">{row.business_name}</span> — {row.reason}
              </li>
            ))}
          </ul>
          <button
            onClick={onForce}
            className="mt-3 rounded-ctl bg-surface-2 px-3 py-1.5 text-xs font-semibold text-tx hover:bg-surface-3"
          >
            Import them anyway
          </button>
        </>
      )}
    </div>
  )
}

function Select({ value = '', onChange, label, children }) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="rounded-ctl bg-surface-2 px-3 py-2 text-sm text-tx outline-none"
    >
      <option value="">{label}</option>
      {children}
    </select>
  )
}

function Chip({ on, onClick, children }) {
  return (
    <button
      onClick={onClick}
      className={
        'rounded-full px-3 py-1 text-xs font-semibold transition ' +
        (on ? 'bg-brand text-white' : 'bg-surface-2 text-tx-2 hover:bg-surface-3 hover:text-tx')
      }
    >
      {children}
    </button>
  )
}
