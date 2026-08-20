import { ArrowDown, ArrowUp, ChevronsUpDown, Inbox, Globe, UserPlus } from 'lucide-react'
import Badge from '../../components/Badge'
import { fromNow, shortDate } from '../../lib/format'
import {
  KIND,
  PRIORITY_TONE,
  TEMPERATURE_TONE,
  colorFor,
  labelFor,
  scoreTone,
  titleCase,
} from './crm'

import { COLUMNS } from './columns'

export default function LeadsTable({
  rows,
  choices,
  isLoading,
  visible,
  sort,
  onSort,
  selected,
  onSelect,
  onOpen,
  hasFilters,
}) {
  const cols = COLUMNS.filter((c) => visible.includes(c.key))
  const allSelected = rows.length > 0 && rows.every((r) => selected.has(r.id))

  const toggleAll = () => onSelect(allSelected ? new Set() : new Set(rows.map((r) => r.id)))
  const toggleOne = (id) => {
    const next = new Set(selected)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    onSelect(next)
  }

  return (
    <div className="overflow-x-auto rounded-card border border-line bg-surface">
      <table className="w-full min-w-[900px] text-sm">
        {/* Sticky header: these tables get long, and a scrolled-away header
            turns a dense grid into unlabelled noise. */}
        <thead className="sticky top-0 z-10 bg-surface-2/95 backdrop-blur">
          <tr className="border-b border-line text-left text-tx-3">
            <th className="w-10 px-3 py-3">
              <input
                type="checkbox"
                checked={allSelected}
                onChange={toggleAll}
                aria-label="Select all leads on this page"
                className="accent-brand"
              />
            </th>
            {cols.map((c) => (
              <SortableHeader key={c.key} col={c} sort={sort} onSort={onSort} />
            ))}
          </tr>
        </thead>
        <tbody>
          {isLoading ? (
            <SkeletonRows cols={cols.length + 1} />
          ) : rows.length === 0 ? (
            <tr>
              <td colSpan={cols.length + 1} className="px-4 py-16 text-center">
                <Inbox size={26} className="mx-auto mb-3 text-tx-3" />
                <div className="text-tx-2">
                  {hasFilters ? 'No leads match these filters.' : 'No leads yet.'}
                </div>
                <div className="mt-1 text-xs text-tx-3">
                  {hasFilters
                    ? 'Try clearing a filter or widening the date range.'
                    : 'Website leads arrive here automatically. Use Add Lead for the rest.'}
                </div>
              </td>
            </tr>
          ) : (
            rows.map((lead) => (
              <tr
                key={lead.id}
                onClick={() => onOpen(lead)}
                className="cursor-pointer border-b border-line/60 transition last:border-0 hover:bg-surface-2"
              >
                <td className="px-3 py-3" onClick={(e) => e.stopPropagation()}>
                  <input
                    type="checkbox"
                    checked={selected.has(lead.id)}
                    onChange={() => toggleOne(lead.id)}
                    aria-label={`Select ${lead.business_name}`}
                    className="accent-brand"
                  />
                </td>
                {cols.map((c) => (
                  <td key={c.key} className="px-4 py-3">
                    <Cell col={c.key} lead={lead} choices={choices} />
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  )
}

function SortableHeader({ col, sort, onSort }) {
  if (!col.sort) {
    return <th className="whitespace-nowrap px-4 py-3 text-xs font-medium">{col.label}</th>
  }

  const active = sort === col.sort || sort === `-${col.sort}`
  const desc = sort === `-${col.sort}`
  const Icon = !active ? ChevronsUpDown : desc ? ArrowDown : ArrowUp

  return (
    <th className="whitespace-nowrap px-4 py-3 text-xs font-medium">
      <button
        onClick={() => onSort(active && desc ? col.sort : `-${col.sort}`)}
        className={`flex items-center gap-1 transition hover:text-tx ${active ? 'text-brand' : ''}`}
      >
        {col.label}
        <Icon size={12} className={active ? '' : 'opacity-40'} />
      </button>
    </th>
  )
}

function Cell({ col, lead, choices }) {
  switch (col) {
    case 'business':
      return (
        <div className="flex items-center gap-2">
          {/* The one place lead type earns space in the default view: a small
              mark, not a column, since it is context rather than a value. */}
          {lead.lead_type === 'website' ? (
            <Globe size={13} className="shrink-0 text-info" aria-label="Website lead" />
          ) : (
            <UserPlus size={13} className="shrink-0 text-tx-3" aria-label="Manual lead" />
          )}
          <span className="font-medium text-tx">{lead.business_name}</span>
        </div>
      )
    case 'owner':
      return <span className="whitespace-nowrap text-tx-2">{lead.name || '—'}</span>
    case 'phone':
      return (
        <a
          href={`tel:${lead.phone}`}
          onClick={(e) => e.stopPropagation()}
          className="font-num text-tx-2 hover:text-brand"
        >
          {lead.phone || '—'}
        </a>
      )
    case 'area':
      return <span className="text-tx-2">{lead.area || '—'}</span>
    case 'category':
      return <span className="text-tx-2">{labelFor(choices, KIND.CATEGORY, lead.category)}</span>
    case 'assigned_sales':
      return lead.assigned_sales ? (
        <span className="whitespace-nowrap text-tx-2">
          {lead.assigned_sales.name || lead.assigned_sales.email}
        </span>
      ) : (
        <span className="whitespace-nowrap text-xs text-tx-3">Unassigned</span>
      )
    case 'priority':
      return (
        <span className="whitespace-nowrap">
          <Badge tone={PRIORITY_TONE[lead.priority] ?? 'neutral'}>
            {labelFor(choices, KIND.PRIORITY, lead.priority)}
          </Badge>
        </span>
      )
    case 'status':
      return <StatusBadge lead={lead} choices={choices} />
    case 'temperature':
      return (
        <span className="whitespace-nowrap">
          <Badge tone={TEMPERATURE_TONE[lead.temperature] ?? 'neutral'}>
            {labelFor(choices, KIND.TEMPERATURE, lead.temperature)}
          </Badge>
        </span>
      )
    case 'lead_score':
      return <ScoreBar score={lead.lead_score} />
    case 'lead_type':
      return <span className="text-tx-2">{titleCase(lead.lead_type)}</span>
    case 'source':
      return <span className="text-tx-2">{labelFor(choices, KIND.SOURCE, lead.source)}</span>
    case 'next_follow_up_at':
      return <FollowUp lead={lead} />
    case 'last_activity':
      return (
        <span className="block max-w-[220px] truncate text-tx-3" title={lead.last_activity}>
          {lead.last_activity || '—'}
        </span>
      )
    case 'created_at':
      return <span className="whitespace-nowrap text-tx-3">{shortDate(lead.created_at)}</span>
    default:
      return null
  }
}

// The status badge takes its colour from the admin's own CRM configuration, so
// a re-coloured status re-colours here without a deploy. Falls back to the
// neutral Badge when no colour is set — most statuses have none, deliberately.
function StatusBadge({ lead, choices }) {
  const color = colorFor(choices, KIND.STATUS, lead.status)
  const label = labelFor(choices, KIND.STATUS, lead.status)

  // whitespace-nowrap on both branches: a two-word status wrapping mid-badge
  // makes that one row taller than its neighbours and the table looks broken.
  if (!color)
    return (
      <span className="whitespace-nowrap">
        <Badge>{label}</Badge>
      </span>
    )
  return (
    <span
      className="inline-flex items-center whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-semibold"
      style={{ backgroundColor: `${color}22`, color }}
    >
      {label}
    </span>
  )
}

function ScoreBar({ score = 0 }) {
  const tone = scoreTone(score)
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-14 overflow-hidden rounded-full bg-surface-3">
        <div className={`h-full rounded-full ${tone.bar}`} style={{ width: `${score}%` }} />
      </div>
      <span className={`font-num text-xs ${tone.text}`}>{score}</span>
    </div>
  )
}

// A follow-up in the past is the table's one piece of urgency, so it is the one
// thing allowed to shout.
function FollowUp({ lead }) {
  if (!lead.next_follow_up_at) return <span className="text-tx-3">—</span>

  const overdue = new Date(lead.next_follow_up_at) < new Date()
  return (
    <span className={`whitespace-nowrap text-xs ${overdue ? 'text-danger' : 'text-tx-2'}`}>
      {fromNow(lead.next_follow_up_at)}
    </span>
  )
}

function SkeletonRows({ cols }) {
  return Array.from({ length: 8 }).map((_, r) => (
    <tr key={r} className="border-b border-line/60 last:border-0">
      {Array.from({ length: cols }).map((__, c) => (
        <td key={c} className="px-4 py-3">
          <div className="h-3 animate-pulse rounded bg-surface-2" style={{ width: `${40 + ((c * 17) % 50)}%` }} />
        </td>
      ))}
    </tr>
  ))
}
