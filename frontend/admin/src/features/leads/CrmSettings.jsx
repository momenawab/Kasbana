import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, GripVertical, Loader2, Lock, Plus, Trash2, X } from 'lucide-react'
import {
  KIND,
  slugify,
  useAllCrmChoices,
  useCreateCrmChoice,
  useDeleteCrmChoice,
  useUpdateCrmChoice,
} from './crm'
import { useSalesUsers } from './api'
import { useAuth } from '../../hooks/useAuth'
import { normalizeError } from '../../lib/api'
import Badge from '../../components/Badge'

// Settings → CRM Configuration.
//
// Every dropdown in the CRM reads from here. Two kinds of row live side by side
// and the difference is the whole design:
//
//   • built-in — the value exists in console/crm.py and code reads it by name
//     (scoring, conversion, the KPI counts). Label, colour and order are yours;
//     the slug and the row's existence are not. Deleting one would strand every
//     lead sitting on it and break the maths silently, so the server refuses.
//   • custom — vocabulary you invented that no code reads. Entirely yours.
//
// The UI shows which is which rather than hiding the distinction, because a
// person who cannot see why "Converted" has no delete button will assume it is
// a bug and go looking.
const GROUPS = [
  { kind: KIND.STATUS, title: 'Statuses', hint: 'The pipeline a lead moves through.' },
  { kind: KIND.PRIORITY, title: 'Priorities', hint: 'Feeds the lead score.' },
  { kind: KIND.TEMPERATURE, title: 'Temperatures', hint: 'Feeds the lead score.' },
  { kind: KIND.SOURCE, title: 'Lead Sources', hint: 'Where the lead came from.' },
  { kind: KIND.CATEGORY, title: 'Business Categories', hint: 'Fully yours — no built-ins.' },
  { kind: KIND.EXPECTED_PLAN, title: 'Expected Plans', hint: 'A sales forecast, not the billed plan.' },
  { kind: KIND.CONTACT_METHOD, title: 'Contact Methods', hint: 'How you reached them.' },
  { kind: KIND.NEXT_ACTION, title: 'Next Actions', hint: 'What happens next.' },
]

export default function CrmSettings() {
  const { role } = useAuth()
  const canConfigure = role === 'SUPER_ADMIN'
  const { data: choices, isLoading } = useAllCrmChoices()
  const { data: salesUsers } = useSalesUsers()
  const [openKind, setOpenKind] = useState(KIND.STATUS)

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-start gap-3">
        <Link
          to="/leads"
          className="mt-1 rounded-ctl border border-line p-1.5 text-tx-3 hover:border-brand hover:text-brand"
        >
          <ArrowLeft size={15} />
        </Link>
        <div>
          <h1 className="font-head text-2xl font-bold text-tx">CRM Configuration</h1>
          <p className="mt-1 text-sm text-tx-3">
            Every dropdown in the lead CRM reads from here.
            {!canConfigure && ' Changes need super-admin.'}
          </p>
        </div>
      </div>

      {isLoading ? (
        <Loader2 className="mx-auto mt-10 animate-spin text-tx-3" />
      ) : (
        <div className="flex flex-col gap-3">
          {GROUPS.map((g) => (
            <Group
              key={g.kind}
              group={g}
              rows={choices?.[g.kind] ?? []}
              open={openKind === g.kind}
              onToggle={() => setOpenKind(openKind === g.kind ? null : g.kind)}
              canConfigure={canConfigure}
            />
          ))}

          <SalesUsersCard users={salesUsers ?? []} />
        </div>
      )}
    </div>
  )
}

function Group({ group, rows, open, onToggle, canConfigure }) {
  const active = rows.filter((r) => r.is_active).length

  return (
    <div className="rounded-card border border-line bg-surface">
      <button
        onClick={onToggle}
        className="flex w-full items-center justify-between px-4 py-3 text-left"
      >
        <div>
          <span className="font-head text-sm font-semibold text-tx">{group.title}</span>
          <span className="ml-2 text-xs text-tx-3">{group.hint}</span>
        </div>
        <span className="text-xs text-tx-3">
          {active} active{rows.length !== active && ` · ${rows.length - active} retired`}
        </span>
      </button>

      {open && (
        <div className="border-t border-line p-4">
          <div className="flex flex-col gap-1.5">
            {rows.map((row) => (
              <Row key={row.id} row={row} canConfigure={canConfigure} />
            ))}
          </div>
          {canConfigure && <AddRow kind={group.kind} />}
        </div>
      )}
    </div>
  )
}

function Row({ row, canConfigure }) {
  const update = useUpdateCrmChoice()
  const del = useDeleteCrmChoice()
  const [label, setLabel] = useState(row.label)
  const [err, setErr] = useState('')

  const save = async (patch) => {
    setErr('')
    try {
      await update.mutateAsync({ id: row.id, ...patch })
    } catch (e) {
      setErr(normalizeError(e).message)
      setLabel(row.label) // put the old label back rather than show a lie
    }
  }

  const remove = async () => {
    if (!window.confirm(`Delete "${row.label}"?`)) return
    setErr('')
    try {
      await del.mutateAsync(row.id)
    } catch (e) {
      // The server refuses a built-in, or a custom value leads still use, and
      // explains which — surface that rather than a generic failure.
      setErr(normalizeError(e).message)
    }
  }

  return (
    <div className={`rounded-ctl border border-line bg-bg p-2 ${row.is_active ? '' : 'opacity-60'}`}>
      <div className="flex flex-wrap items-center gap-2">
        <GripVertical size={13} className="shrink-0 text-tx-3" />

        <input
          type="color"
          value={row.color || '#6b7280'}
          disabled={!canConfigure}
          onChange={(e) => save({ color: e.target.value })}
          className="h-6 w-6 shrink-0 cursor-pointer rounded border border-line bg-transparent disabled:cursor-default"
          aria-label={`Colour for ${row.label}`}
        />

        <input
          value={label}
          disabled={!canConfigure}
          onChange={(e) => setLabel(e.target.value)}
          onBlur={() => label !== row.label && label.trim() && save({ label: label.trim() })}
          className="min-w-0 flex-1 rounded-ctl border border-transparent bg-transparent px-2 py-1 text-sm text-tx hover:border-line focus:border-brand focus:outline-none disabled:hover:border-transparent"
        />

        <code className="shrink-0 font-mono text-xs text-tx-3">{row.slug}</code>

        {row.is_system ? (
          <span
            className="flex shrink-0 items-center gap-1 text-xs text-tx-3"
            title="Built in — the CRM reads this value by name (scoring, conversion, the KPI cards). Rename and recolour it freely; it cannot be deleted. Untick Active to retire it."
          >
            <Lock size={11} /> Built-in
          </span>
        ) : (
          <Badge tone="brand">Custom</Badge>
        )}

        {canConfigure && (
          <>
            <label className="flex shrink-0 items-center gap-1 text-xs text-tx-3">
              <input
                type="checkbox"
                checked={row.is_active}
                onChange={(e) => save({ is_active: e.target.checked })}
                className="accent-brand"
              />
              Active
            </label>
            {/* No delete on a built-in: the server refuses it, so the button
                could only ever produce an error. The lock badge above says why,
                and unticking Active is the thing they actually want. */}
            {row.is_system ? (
              <span className="w-[21px] shrink-0" aria-hidden="true" />
            ) : (
              <button
                onClick={remove}
                disabled={del.isPending}
                className="shrink-0 rounded p-1 text-tx-3 hover:text-danger disabled:opacity-50"
                aria-label={`Delete ${row.label}`}
              >
                <Trash2 size={13} />
              </button>
            )}
          </>
        )}
      </div>

      {err && (
        <div className="mt-1.5 flex items-start gap-1.5 pl-6 text-xs text-danger">
          <span className="flex-1">{err}</span>
          <button onClick={() => setErr('')} className="text-tx-3 hover:text-tx">
            <X size={11} />
          </button>
        </div>
      )}
    </div>
  )
}

function AddRow({ kind }) {
  const create = useCreateCrmChoice()
  const [label, setLabel] = useState('')
  const [err, setErr] = useState('')

  async function submit(e) {
    e.preventDefault()
    const trimmed = label.trim()
    if (!trimmed) return
    setErr('')
    try {
      // The slug is derived, never typed: it is what the database and every
      // lead store, and letting someone hand-type it invites a typo that can
      // never be corrected afterwards (the server refuses re-slugging).
      await create.mutateAsync({ kind, slug: slugify(trimmed), label: trimmed })
      setLabel('')
    } catch (e2) {
      setErr(normalizeError(e2).message)
    }
  }

  return (
    <form onSubmit={submit} className="mt-3 flex flex-wrap items-center gap-2 border-t border-line pt-3">
      <input
        value={label}
        onChange={(e) => setLabel(e.target.value)}
        placeholder="Add a value…"
        className="min-w-0 flex-1 rounded-ctl border border-line bg-bg px-3 py-1.5 text-sm text-tx placeholder:text-tx-3 focus:border-brand focus:outline-none"
      />
      <button
        type="submit"
        disabled={create.isPending || !label.trim()}
        className="flex items-center gap-1.5 rounded-ctl border border-line px-3 py-1.5 text-sm text-tx-2 hover:border-brand hover:text-brand disabled:opacity-50"
      >
        {create.isPending ? <Loader2 size={13} className="animate-spin" /> : <Plus size={13} />}
        Add
      </button>
      {err && <div className="w-full text-xs text-danger">{err}</div>}
    </form>
  )
}

// Sales users are the one thing on this screen that isn't a CrmChoice — they
// are admin accounts, managed in Admin Team. Shown read-only so the settings
// page answers "who can leads be assigned to?" without pretending to own it.
function SalesUsersCard({ users }) {
  return (
    <div className="rounded-card border border-line bg-surface p-4">
      <div className="mb-1 flex items-center justify-between">
        <span className="font-head text-sm font-semibold text-tx">Sales Users</span>
        <Link to="/team" className="text-xs text-brand hover:underline">
          Manage in Admin Team →
        </Link>
      </div>
      <p className="mb-3 text-xs text-tx-3">
        Anyone with the Sales or Super Admin role can be assigned a lead.
      </p>
      <div className="flex flex-wrap gap-2">
        {users.length === 0 ? (
          <span className="text-sm text-tx-3">No sales users yet.</span>
        ) : (
          users.map((u) => (
            <span
              key={u.id}
              className="rounded-ctl border border-line bg-bg px-2.5 py-1 text-xs text-tx-2"
            >
              {u.name || u.email}
              <span className="ml-1.5 text-tx-3">{u.role === 'SUPER_ADMIN' ? 'Super' : 'Sales'}</span>
            </span>
          ))
        )}
      </div>
    </div>
  )
}
