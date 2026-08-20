import { useState, Fragment } from 'react'
import { Loader2, Users2, UserPlus, ShieldCheck } from 'lucide-react'
import { useAdmins, useInviteAdmin, useUpdateAdmin, useAdminActivity } from './api'
import { useAuth } from '../../hooks/useAuth'
import Badge from '../../components/Badge'
import { normalizeError } from '../../lib/api'
import { fromNow, shortDate } from '../../lib/format'

const ROLES = [
  'SUPER_ADMIN',
  'FINANCE',
  'SUPPORT',
  'MARKETING_ADMIN',
  'ENGINEERING',
  'READ_ONLY',
]

const inputClass =
  'rounded-ctl border border-line bg-surface-2 px-3 py-2 text-sm text-tx outline-none focus:border-brand'

export default function AdminsTab() {
  const { admin: me, role } = useAuth()
  const canManage = role === 'SUPER_ADMIN'
  const { data: admins = [], isLoading } = useAdmins()
  const invite = useInviteAdmin()
  const update = useUpdateAdmin()

  const [form, setForm] = useState({ email: '', name: '', role: 'READ_ONLY' })
  const [error, setError] = useState('')
  const [invited, setInvited] = useState(null) // { email, temporary_password }
  const [expanded, setExpanded] = useState(null)

  // Non-super admins can't reach these endpoints (403). Show a clear message
  // rather than a spinner-then-error.
  if (!canManage) {
    return (
      <div className="rounded-card border border-line bg-surface p-6 text-sm text-tx-3">
        <ShieldCheck size={20} className="mb-2 text-tx-3" />
        Only super-admins can manage the admin team. See the Permission matrix tab
        for what your role can do.
      </div>
    )
  }

  async function submitInvite(e) {
    e.preventDefault()
    setError('')
    setInvited(null)
    try {
      const res = await invite.mutateAsync(form)
      setInvited({ email: res.admin.email, temporary_password: res.temporary_password })
      setForm({ email: '', name: '', role: 'READ_ONLY' })
    } catch (err) {
      setError(normalizeError(err).message)
    }
  }

  async function changeRole(a, newRole) {
    const reason = window.prompt(`Reason for changing ${a.email} to ${newRole} (audited):`)
    if (!reason) return
    try {
      await update.mutateAsync({ id: a.id, patch: { role: newRole, reason } })
    } catch (err) {
      window.alert(normalizeError(err).message)
    }
  }

  async function toggleActive(a) {
    const reason = window.prompt(
      `Reason for ${a.is_active ? 'deactivating' : 'reactivating'} ${a.email} (audited):`
    )
    if (!reason) return
    try {
      await update.mutateAsync({ id: a.id, patch: { is_active: !a.is_active, reason } })
    } catch (err) {
      window.alert(normalizeError(err).message)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Invite */}
      <form
        onSubmit={submitInvite}
        className="flex flex-wrap items-end gap-3 rounded-card border border-line bg-surface p-4"
      >
        <label className="block">
          <span className="mb-1 block text-xs text-tx-3">Email</span>
          <input
            type="email"
            required
            dir="ltr"
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
            className={`${inputClass} w-56`}
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-xs text-tx-3">Name</span>
          <input
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            className={`${inputClass} w-40`}
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-xs text-tx-3">Role</span>
          <select
            value={form.role}
            onChange={(e) => setForm({ ...form, role: e.target.value })}
            className={inputClass}
          >
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
        </label>
        <button
          type="submit"
          disabled={invite.isPending || !form.email}
          className="inline-flex items-center gap-2 rounded-ctl bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-brand-d disabled:opacity-60"
        >
          <UserPlus size={16} /> Invite
        </button>
      </form>

      {error && <p className="text-sm text-danger">{error}</p>}

      {invited && (
        <div className="rounded-card border border-brand/40 bg-surface p-4 text-sm">
          <p className="text-tx-2">
            Invited <span className="font-semibold text-tx">{invited.email}</span>. Share this
            one-time password securely — it won&apos;t be shown again:
          </p>
          <code className="mt-2 block rounded-ctl bg-surface-2 px-3 py-2 font-num text-brand">
            {invited.temporary_password}
          </code>
        </div>
      )}

      {/* Table */}
      <div className="overflow-hidden rounded-card border border-line bg-surface">
        <table className="w-full text-sm">
          <thead className="border-b border-line text-tx-3">
            <tr className="text-left">
              <th className="px-4 py-3 font-medium">Admin</th>
              <th className="px-4 py-3 font-medium">Role</th>
              <th className="px-4 py-3 font-medium">MFA</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">Last login</th>
              <th className="px-4 py-3 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={6} className="px-4 py-10 text-center text-tx-3">
                  <Loader2 size={18} className="mx-auto animate-spin" />
                </td>
              </tr>
            ) : admins.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-10 text-center text-tx-3">
                  <Users2 size={22} className="mx-auto mb-2" />
                  No admins.
                </td>
              </tr>
            ) : (
              admins.map((a) => (
                <Fragment key={a.id}>
                  <tr className="border-b border-line/60 last:border-0">
                    <td className="px-4 py-3">
                      <button
                        onClick={() => setExpanded(expanded === a.id ? null : a.id)}
                        className="text-left"
                      >
                        <div className="font-medium text-tx hover:text-brand">
                          {a.name || a.email}
                        </div>
                        <div className="text-xs text-tx-3">{a.email}</div>
                      </button>
                    </td>
                    <td className="px-4 py-3">
                      <select
                        value={a.role}
                        disabled={a.id === me?.id}
                        onChange={(e) => changeRole(a, e.target.value)}
                        className={`${inputClass} py-1 disabled:opacity-60`}
                        title={a.id === me?.id ? "You can't change your own role" : ''}
                      >
                        {ROLES.map((r) => (
                          <option key={r} value={r}>
                            {r}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="px-4 py-3">
                      {a.mfa_required ? (
                        <Badge tone={a.mfa_enabled ? 'success' : 'warn'}>
                          {a.mfa_enabled ? 'On' : 'Required'}
                        </Badge>
                      ) : (
                        <span className="text-tx-3">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <Badge tone={a.is_active ? 'success' : 'danger'}>
                        {a.is_active ? 'Active' : 'Inactive'}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-tx-2">
                      {a.last_login_at ? shortDate(a.last_login_at) : '—'}
                    </td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => toggleActive(a)}
                        disabled={a.id === me?.id}
                        title={a.id === me?.id ? "You can't deactivate yourself" : ''}
                        className="text-xs font-semibold text-tx-2 hover:text-danger disabled:cursor-default disabled:text-tx-3 disabled:hover:text-tx-3"
                      >
                        {a.is_active ? 'Deactivate' : 'Reactivate'}
                      </button>
                    </td>
                  </tr>
                  {expanded === a.id && (
                    <tr>
                      <td colSpan={6} className="bg-surface-2 px-4 py-3">
                        <AdminActivity id={a.id} />
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function AdminActivity({ id }) {
  const { data: rows = [], isLoading } = useAdminActivity(id)
  if (isLoading) return <Loader2 size={16} className="animate-spin text-tx-3" />
  if (rows.length === 0) return <p className="text-xs text-tx-3">No recorded activity.</p>
  return (
    <ul className="flex flex-col gap-1 text-xs">
      {rows.slice(0, 12).map((r, i) => (
        <li key={i} className="flex justify-between text-tx-2">
          <span className="font-medium">{r.action}</span>
          <span className="text-tx-3">{fromNow(r.created_at)}</span>
        </li>
      ))}
    </ul>
  )
}
