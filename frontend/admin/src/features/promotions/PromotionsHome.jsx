import { useState } from 'react'
import { Loader2, Ticket, Plus, Power } from 'lucide-react'
import { useCoupons, useCreateCoupon, useUpdateCoupon, useCouponRedemptions } from './api'
import { useAuth } from '../../hooks/useAuth'
import Badge from '../../components/Badge'
import { normalizeError } from '../../lib/api'
import { num, shortDate } from '../../lib/format'

const FINANCE_ROLES = ['SUPER_ADMIN', 'FINANCE']

const TYPES = [
  { key: 'percent', label: 'Percent off (%)' },
  { key: 'fixed', label: 'Fixed EGP off' },
  { key: 'free_months', label: 'Free months (comp)' },
  { key: 'trial_extension', label: 'Trial extension (days)' },
]

function typeLabel(t, value) {
  if (t === 'percent') return `${value}% off`
  if (t === 'fixed') return `${value} EGP off`
  if (t === 'free_months') return `${value} free month(s)`
  return `+${value} trial day(s)`
}

export default function PromotionsHome() {
  const { role } = useAuth()
  const canManage = FINANCE_ROLES.includes(role)
  const { data, isLoading } = useCoupons()
  const rows = data ?? []
  const [openCode, setOpenCode] = useState(null)

  return (
    <div className="flex flex-col gap-5">
      <h1 className="font-head text-2xl font-bold text-tx">Promotions</h1>
      {canManage && <Builder />}
      {isLoading ? (
        <Loader2 className="mx-auto mt-6 animate-spin text-tx-3" />
      ) : rows.length === 0 ? (
        <div className="rounded-card border border-line bg-surface p-8 text-center text-tx-3">
          No coupons yet.
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {rows.map((c) => (
            <CouponRow
              key={c.id}
              c={c}
              canManage={canManage}
              open={openCode === c.code}
              onToggle={() => setOpenCode(openCode === c.code ? null : c.code)}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function Builder() {
  const [form, setForm] = useState({ code: '', type: 'percent', value: '', max_redemptions: '' })
  const [msg, setMsg] = useState(null)
  const create = useCreateCoupon()

  function set(k, v) {
    setForm({ ...form, [k]: v })
  }

  async function submit() {
    setMsg(null)
    if (!form.code.trim() || !form.value) {
      setMsg('Code and value are required.')
      return
    }
    try {
      await create.mutateAsync({
        code: form.code,
        type: form.type,
        value: form.value,
        max_redemptions: form.max_redemptions ? Number(form.max_redemptions) : null,
      })
      setForm({ code: '', type: 'percent', value: '', max_redemptions: '' })
      setMsg('Coupon created.')
    } catch (err) {
      setMsg(normalizeError(err).message)
    }
  }

  return (
    <div className="rounded-card border border-line bg-surface p-4">
      <div className="mb-3 flex items-center gap-2 text-tx">
        <Ticket size={16} className="text-tx-3" />
        <h2 className="font-head text-sm font-semibold">New coupon</h2>
      </div>
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-xs text-tx-3">
          Code
          <input
            value={form.code}
            onChange={(e) => set('code', e.target.value.toUpperCase())}
            placeholder="SPRING25"
            className="mt-1 block w-36 rounded-ctl border border-line bg-surface-2 px-3 py-2 text-sm text-tx outline-none focus:border-brand"
          />
        </label>
        <label className="text-xs text-tx-3">
          Type
          <select
            value={form.type}
            onChange={(e) => set('type', e.target.value)}
            className="mt-1 block rounded-ctl border border-line bg-surface-2 px-3 py-2 text-sm text-tx"
          >
            {TYPES.map((t) => (
              <option key={t.key} value={t.key}>
                {t.label}
              </option>
            ))}
          </select>
        </label>
        <label className="text-xs text-tx-3">
          Value
          <input
            type="number"
            min="0"
            value={form.value}
            onChange={(e) => set('value', e.target.value)}
            className="mt-1 block w-24 rounded-ctl border border-line bg-surface-2 px-3 py-2 text-sm text-tx outline-none focus:border-brand"
          />
        </label>
        <label className="text-xs text-tx-3">
          Max redemptions
          <input
            type="number"
            min="0"
            value={form.max_redemptions}
            onChange={(e) => set('max_redemptions', e.target.value)}
            placeholder="∞"
            className="mt-1 block w-28 rounded-ctl border border-line bg-surface-2 px-3 py-2 text-sm text-tx outline-none focus:border-brand"
          />
        </label>
        <button
          onClick={submit}
          disabled={create.isPending}
          className="flex items-center gap-1.5 rounded-ctl bg-brand px-4 py-2 text-sm font-semibold text-bg hover:bg-brand-d disabled:opacity-60"
        >
          <Plus size={14} /> Create
        </button>
      </div>
      {msg && <p className="mt-2 text-sm text-tx-2">{msg}</p>}
    </div>
  )
}

function CouponRow({ c, canManage, open, onToggle }) {
  const update = useUpdateCoupon()
  const capped = c.max_redemptions != null
  const remaining = capped ? c.max_redemptions - c.redemption_count : null

  return (
    <div className="rounded-card border border-line bg-surface p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-tx">{c.code}</span>
            <Badge tone={c.active ? 'success' : 'neutral'}>{c.active ? 'active' : 'inactive'}</Badge>
            <span className="text-sm text-tx-2">{typeLabel(c.type, c.value)}</span>
          </div>
          <div className="mt-1 text-xs text-tx-3">
            {num(c.redemption_count)} redeemed
            {capped ? ` · ${num(remaining)} left of ${num(c.max_redemptions)}` : ' · unlimited'}
            {c.expires_at ? ` · expires ${shortDate(c.expires_at)}` : ''}
          </div>
        </div>
        <div className="flex gap-2">
          <button onClick={onToggle} className="rounded-ctl border border-line px-3 py-1.5 text-sm text-tx-2 hover:border-brand hover:text-brand">
            {open ? 'Hide' : 'Redemptions'}
          </button>
          {canManage && (
            <button
              onClick={() => update.mutate({ code: c.code, patch: { active: !c.active } })}
              className="flex items-center gap-1 rounded-ctl border border-line px-3 py-1.5 text-sm text-tx-2 hover:border-brand hover:text-brand"
            >
              <Power size={14} /> {c.active ? 'Deactivate' : 'Activate'}
            </button>
          )}
        </div>
      </div>
      {open && <Redemptions code={c.code} />}
    </div>
  )
}

function Redemptions({ code }) {
  const { data, isLoading } = useCouponRedemptions(code)
  if (isLoading) return <Loader2 className="mt-3 animate-spin text-tx-3" size={16} />
  const rows = data ?? []
  if (rows.length === 0) return <p className="mt-3 text-sm text-tx-3">No redemptions yet.</p>
  return (
    <div className="mt-3 overflow-hidden rounded-ctl border border-line">
      <table className="w-full text-sm">
        <thead className="border-b border-line text-tx-3">
          <tr className="text-left">
            <th className="px-3 py-2 font-medium">Merchant</th>
            <th className="px-3 py-2 font-medium">Detail</th>
            <th className="px-3 py-2 font-medium text-right">Discount</th>
            <th className="px-3 py-2 font-medium">When</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id} className="border-b border-line/60 last:border-0">
              <td className="px-3 py-2 text-tx-2">{r.merchant.name}</td>
              <td className="px-3 py-2 text-tx-3">{r.detail || '—'}</td>
              <td className="px-3 py-2 text-right font-num text-tx">{num(r.discount_egp)} EGP</td>
              <td className="px-3 py-2 text-tx-3">{shortDate(r.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
