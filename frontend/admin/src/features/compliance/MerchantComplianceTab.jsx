import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Loader2, Download, Trash2, AlertTriangle } from 'lucide-react'
import { useConsent, useEraseMerchant, downloadMerchantExport } from './api'
import { useAuth } from '../../hooks/useAuth'
import { normalizeError } from '../../lib/api'
import StepUpModal from '../security/StepUpModal'

function fmt(ts) {
  return ts ? new Date(ts).toLocaleDateString() : '—'
}

export default function MerchantComplianceTab({ merchantId, slug, name }) {
  const { role } = useAuth()
  const isSuper = role === 'SUPER_ADMIN'
  const { data: consent, isLoading } = useConsent(merchantId)

  if (!isSuper) {
    // Consent is a read (any admin); export/erase are super-only.
    return (
      <div className="flex flex-col gap-5">
        <ConsentTable consent={consent} isLoading={isLoading} />
        <p className="text-sm text-tx-3">Data export and erasure are restricted to super-admins.</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <ExportCard merchantId={merchantId} slug={slug} />
      <ConsentTable consent={consent} isLoading={isLoading} />
      <DangerZone merchantId={merchantId} slug={slug} name={name} />
    </div>
  )
}

function ExportCard({ merchantId, slug }) {
  const [busy, setBusy] = useState(false)
  async function run() {
    setBusy(true)
    try {
      await downloadMerchantExport(merchantId, slug)
    } catch (err) {
      window.alert(normalizeError(err).message)
    } finally {
      setBusy(false)
    }
  }
  return (
    <div className="flex items-center justify-between rounded-card border border-line bg-surface p-4">
      <div>
        <h2 className="font-head font-semibold text-tx">Data export</h2>
        <p className="text-sm text-tx-3">
          Download this merchant’s full data bundle (JSON). The export is audited — it contains PII.
        </p>
      </div>
      <button
        onClick={run}
        disabled={busy}
        className="flex items-center gap-1.5 rounded-ctl border border-line px-3 py-2 text-sm font-semibold text-tx-2 hover:border-brand hover:text-brand disabled:opacity-60"
      >
        <Download size={15} /> {busy ? 'Exporting…' : 'Export JSON'}
      </button>
    </div>
  )
}

function ConsentTable({ consent, isLoading }) {
  return (
    <div className="flex flex-col gap-2">
      <h2 className="font-head font-semibold text-tx">Consent records</h2>
      {isLoading ? (
        <Loader2 className="animate-spin text-tx-3" />
      ) : (
        <div className="overflow-x-auto rounded-card border border-line bg-surface">
          <table className="w-full text-sm">
            <thead className="border-b border-line text-tx-3">
              <tr className="text-left">
                <th className="px-4 py-3 font-medium">Customer</th>
                <th className="px-4 py-3 font-medium">Phone</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">PDPL consent</th>
              </tr>
            </thead>
            <tbody>
              {(consent ?? []).length === 0 && (
                <tr>
                  <td colSpan={4} className="px-4 py-6 text-center text-tx-3">
                    No customers.
                  </td>
                </tr>
              )}
              {(consent ?? []).map((c) => (
                <tr key={c.id} className="border-b border-line/60 last:border-0">
                  <td className="px-4 py-2.5 text-tx-2">{c.customer_name || '—'}</td>
                  <td className="px-4 py-2.5 font-num text-tx-3">{c.customer_phone}</td>
                  <td className="px-4 py-2.5 text-tx-3">{c.status}</td>
                  <td className="px-4 py-2.5 text-tx-3">
                    {c.consent_at ? fmt(c.consent_at) : 'Not recorded'}
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

function DangerZone({ merchantId, slug, name }) {
  const navigate = useNavigate()
  const erase = useEraseMerchant(merchantId)
  const [confirm, setConfirm] = useState('')
  const [reason, setReason] = useState('')
  const [stepUp, setStepUp] = useState(false)
  const ready = confirm === slug && reason.trim().length > 0

  async function doErase() {
    await erase.mutateAsync({ confirm, reason })
    navigate('/merchants')
  }

  async function run() {
    if (!ready) return
    if (!window.confirm(`Permanently erase "${name}" and ALL its data? This cannot be undone.`)) {
      return
    }
    try {
      await doErase()
    } catch (err) {
      // A stale session needs a fresh credential proof first (Phase 15) — open
      // the step-up modal, then it retries the erase on success.
      if (normalizeError(err).code === 'STEP_UP_REQUIRED') {
        setStepUp(true)
        return
      }
      window.alert(normalizeError(err).message)
    }
  }

  return (
    <div className="flex flex-col gap-3 rounded-card border border-danger/40 bg-surface p-4">
      <div className="flex items-center gap-2 text-danger">
        <AlertTriangle size={18} />
        <h2 className="font-head font-semibold">Right to be forgotten</h2>
      </div>
      <p className="text-sm text-tx-3">
        Irreversibly delete this merchant and everything that cascades from it — customers, cards,
        ledger, wallets, invoices. The action is audited. Type the merchant’s slug{' '}
        <span className="font-num text-tx-2">{slug}</span> to confirm.
      </p>
      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-xs text-tx-3">
          Type slug to confirm
          <input
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            placeholder={slug}
            className="w-48 rounded-ctl border border-line bg-bg px-3 py-2 text-sm text-tx focus:border-danger focus:outline-none"
          />
        </label>
        <label className="flex flex-1 flex-col gap-1 text-xs text-tx-3">
          Reason (audited)
          <input
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="PDPL erasure request"
            className="w-full rounded-ctl border border-line bg-bg px-3 py-2 text-sm text-tx focus:border-danger focus:outline-none"
          />
        </label>
        <button
          onClick={run}
          disabled={!ready || erase.isPending}
          className="flex items-center gap-1.5 rounded-ctl border border-danger/50 px-3 py-2 text-sm font-semibold text-danger hover:bg-danger hover:text-bg disabled:cursor-not-allowed disabled:opacity-40"
        >
          <Trash2 size={15} /> {erase.isPending ? 'Erasing…' : 'Erase merchant'}
        </button>
      </div>
      {stepUp && (
        <StepUpModal
          onClose={() => setStepUp(false)}
          onConfirmed={doErase}
        />
      )}
    </div>
  )
}
