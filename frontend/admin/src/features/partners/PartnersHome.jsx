import { useState } from 'react'
import { Loader2, Handshake, Plus, Power, Trash2, Settings2, UserPlus } from 'lucide-react'
import {
  usePartners,
  usePartnerReferrals,
  useProgramConfig,
  useSaveProgramConfig,
  useCreatePartner,
  useUpdatePartner,
  useDeletePartner,
  useAssignReferral,
} from './api'
import { useAuth } from '../../hooks/useAuth'
import Badge from '../../components/Badge'
import { normalizeError } from '../../lib/api'
import { num, shortDate } from '../../lib/format'

const FINANCE_ROLES = ['SUPER_ADMIN', 'FINANCE']

export default function PartnersHome() {
  const { role } = useAuth()
  const canManage = FINANCE_ROLES.includes(role)
  const { data, isLoading } = usePartners()
  const rows = data ?? []
  const [openId, setOpenId] = useState(null)

  return (
    <div className="flex flex-col gap-5">
      <h1 className="font-head text-2xl font-bold text-tx">Partners</h1>
      <p className="-mt-3 text-sm text-tx-3">
        Existing merchants who refer new merchants. On a referred merchant&apos;s first paid
        conversion, both sides receive the configured free months (one-time).
      </p>

      <ProgramConfig canManage={canManage} />
      {canManage && <CreatePartner />}

      {isLoading ? (
        <Loader2 className="mx-auto mt-6 animate-spin text-tx-3" />
      ) : rows.length === 0 ? (
        <div className="rounded-card border border-line bg-surface p-8 text-center text-tx-3">
          No partners yet.
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {rows.map((p) => (
            <PartnerRow
              key={p.id}
              p={p}
              canManage={canManage}
              open={openId === p.id}
              onToggle={() => setOpenId(openId === p.id ? null : p.id)}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function ProgramConfig({ canManage }) {
  const { data: config, isLoading } = useProgramConfig()
  const save = useSaveProgramConfig()
  const [msg, setMsg] = useState(null)

  if (isLoading || !config) return null

  async function patch(next) {
    setMsg(null)
    try {
      await save.mutateAsync(next)
      setMsg('Saved.')
    } catch (err) {
      setMsg(normalizeError(err).message)
    }
  }

  return (
    <div className="rounded-card border border-line bg-surface p-4">
      <div className="mb-3 flex items-center gap-2 text-tx">
        <Settings2 size={16} className="text-tx-3" />
        <h2 className="font-head text-sm font-semibold">Program default</h2>
        <Badge tone={config.enabled ? 'success' : 'neutral'}>
          {config.enabled ? 'on' : 'off'}
        </Badge>
      </div>
      <div className="flex flex-wrap items-end gap-4">
        <label className="flex items-center gap-2 text-sm text-tx-2">
          <input
            type="checkbox"
            checked={config.enabled}
            disabled={!canManage || save.isPending}
            onChange={(e) => patch({ enabled: e.target.checked })}
          />
          Enabled
        </label>
        <MonthsField
          label="Partner free months"
          value={config.partner_free_months}
          disabled={!canManage || save.isPending}
          onCommit={(v) => patch({ partner_free_months: v })}
        />
        <MonthsField
          label="New-merchant free months"
          value={config.merchant_free_months}
          disabled={!canManage || save.isPending}
          onCommit={(v) => patch({ merchant_free_months: v })}
        />
        {msg && <p className="text-sm text-tx-2">{msg}</p>}
      </div>
    </div>
  )
}

function MonthsField({ label, value, disabled, onCommit }) {
  const [v, setV] = useState(String(value ?? 0))
  return (
    <label className="text-xs text-tx-3">
      {label}
      <input
        type="number"
        min="0"
        value={v}
        disabled={disabled}
        onChange={(e) => setV(e.target.value)}
        onBlur={() => Number(v) !== value && onCommit(Number(v))}
        className="mt-1 block w-32 rounded-ctl border border-line bg-surface-2 px-3 py-2 text-sm text-tx outline-none focus:border-brand disabled:opacity-60"
      />
    </label>
  )
}

function CreatePartner() {
  const [form, setForm] = useState({ merchant_id: '', code: '' })
  const [msg, setMsg] = useState(null)
  const create = useCreatePartner()

  async function submit() {
    setMsg(null)
    if (!form.merchant_id.trim() || !form.code.trim()) {
      setMsg('Merchant ID and code are required.')
      return
    }
    try {
      await create.mutateAsync({ merchant_id: form.merchant_id.trim(), code: form.code.trim() })
      setForm({ merchant_id: '', code: '' })
      setMsg('Partner created.')
    } catch (err) {
      setMsg(normalizeError(err).message)
    }
  }

  return (
    <div className="rounded-card border border-line bg-surface p-4">
      <div className="mb-3 flex items-center gap-2 text-tx">
        <Handshake size={16} className="text-tx-3" />
        <h2 className="font-head text-sm font-semibold">Enrol a partner</h2>
      </div>
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-xs text-tx-3">
          Merchant ID
          <input
            value={form.merchant_id}
            onChange={(e) => setForm({ ...form, merchant_id: e.target.value })}
            placeholder="merchant uuid"
            className="mt-1 block w-72 rounded-ctl border border-line bg-surface-2 px-3 py-2 font-mono text-xs text-tx outline-none focus:border-brand"
          />
        </label>
        <label className="text-xs text-tx-3">
          Referral code
          <input
            value={form.code}
            onChange={(e) => setForm({ ...form, code: e.target.value.toUpperCase() })}
            placeholder="PARTNER25"
            className="mt-1 block w-40 rounded-ctl border border-line bg-surface-2 px-3 py-2 text-sm text-tx outline-none focus:border-brand"
          />
        </label>
        <button
          onClick={submit}
          disabled={create.isPending}
          className="flex items-center gap-1.5 rounded-ctl bg-brand px-4 py-2 text-sm font-semibold text-bg hover:bg-brand-d disabled:opacity-60"
        >
          <Plus size={14} /> Create
        </button>
        {msg && <p className="text-sm text-tx-2">{msg}</p>}
      </div>
    </div>
  )
}

function PartnerRow({ p, canManage, open, onToggle }) {
  const update = useUpdatePartner()
  const del = useDeletePartner()
  const r = p.resolved

  return (
    <div className="rounded-card border border-line bg-surface p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-tx">{p.code}</span>
            <Badge tone={p.active ? 'success' : 'neutral'}>{p.active ? 'active' : 'inactive'}</Badge>
            <span className="text-sm text-tx-2">{p.merchant.name}</span>
            <Badge tone={r.enabled ? 'info' : 'warn'}>{r.enabled ? 'rewarding' : 'paused'}</Badge>
          </div>
          <div className="mt-1 text-xs text-tx-3">
            {num(p.referral_count)} referred · {num(p.converted_count)} converted · partner{' '}
            {num(r.partner_free_months)}mo / new merchant {num(r.merchant_free_months)}mo
          </div>
        </div>
        <div className="flex gap-2">
          <button
            onClick={onToggle}
            className="rounded-ctl border border-line px-3 py-1.5 text-sm text-tx-2 hover:border-brand hover:text-brand"
          >
            {open ? 'Hide' : 'Referrals'}
          </button>
          {canManage && (
            <>
              <button
                onClick={() => update.mutate({ id: p.id, patch: { active: !p.active } })}
                className="flex items-center gap-1 rounded-ctl border border-line px-3 py-1.5 text-sm text-tx-2 hover:border-brand hover:text-brand"
              >
                <Power size={14} /> {p.active ? 'Deactivate' : 'Activate'}
              </button>
              <button
                onClick={() => {
                  if (window.confirm(`Delete partner "${p.code}"? Referral history is removed.`))
                    del.mutate(p.id)
                }}
                className="flex items-center gap-1 rounded-ctl border border-line px-3 py-1.5 text-sm text-tx-3 hover:border-danger hover:text-danger"
              >
                <Trash2 size={14} />
              </button>
            </>
          )}
        </div>
      </div>
      {open && <Referrals partnerId={p.id} canManage={canManage} />}
    </div>
  )
}

function Referrals({ partnerId, canManage }) {
  const { data, isLoading } = usePartnerReferrals(partnerId)
  const assign = useAssignReferral(partnerId)
  const [merchantId, setMerchantId] = useState('')
  const [msg, setMsg] = useState(null)
  const rows = data ?? []

  async function submit() {
    setMsg(null)
    if (!merchantId.trim()) return
    try {
      await assign.mutateAsync(merchantId.trim())
      setMerchantId('')
    } catch (err) {
      setMsg(normalizeError(err).message)
    }
  }

  return (
    <div className="mt-3">
      {canManage && (
        <div className="mb-3 flex items-end gap-2">
          <label className="text-xs text-tx-3">
            Attribute a merchant
            <input
              value={merchantId}
              onChange={(e) => setMerchantId(e.target.value)}
              placeholder="merchant uuid"
              className="mt-1 block w-72 rounded-ctl border border-line bg-surface-2 px-3 py-2 font-mono text-xs text-tx outline-none focus:border-brand"
            />
          </label>
          <button
            onClick={submit}
            disabled={assign.isPending}
            className="flex items-center gap-1.5 rounded-ctl border border-line px-3 py-2 text-sm text-tx-2 hover:border-brand hover:text-brand disabled:opacity-60"
          >
            <UserPlus size={14} /> Assign
          </button>
          {msg && <p className="text-sm text-tx-2">{msg}</p>}
        </div>
      )}
      {isLoading ? (
        <Loader2 className="animate-spin text-tx-3" size={16} />
      ) : rows.length === 0 ? (
        <p className="text-sm text-tx-3">No referrals yet.</p>
      ) : (
        <div className="overflow-hidden rounded-ctl border border-line">
          <table className="w-full text-sm">
            <thead className="border-b border-line text-tx-3">
              <tr className="text-left">
                <th className="px-3 py-2 font-medium">Merchant</th>
                <th className="px-3 py-2 font-medium">Via</th>
                <th className="px-3 py-2 font-medium">Converted</th>
                <th className="px-3 py-2 font-medium">Reward</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id} className="border-b border-line/60 last:border-0">
                  <td className="px-3 py-2 text-tx-2">{row.referred_merchant.name}</td>
                  <td className="px-3 py-2 text-tx-3">{row.attributed_via}</td>
                  <td className="px-3 py-2 text-tx-3">
                    {row.reward_granted ? shortDate(row.converted_at) : '—'}
                  </td>
                  <td className="px-3 py-2 text-tx-3">
                    {row.reward_granted
                      ? `partner ${num(row.partner_months_granted)}mo / merchant ${num(
                          row.merchant_months_granted,
                        )}mo`
                      : 'pending'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
