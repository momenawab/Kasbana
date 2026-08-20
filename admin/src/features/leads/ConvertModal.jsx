import { useState } from 'react'
import { AlertTriangle, ArrowRight, Building2, Check, Loader2, X } from 'lucide-react'
import { useConvertLead } from './api'
import { usePlans } from '../plans/api'
import { KIND, labelFor } from './crm'
import { normalizeError } from '../../lib/api'

// Convert To Merchant.
//
// The plan picker reads the *real* catalogue, not the lead's expected_plan:
// that field is a sales forecast in the spec's vocabulary (Trial/Basic/Pro),
// which does not map onto Stampn's actual tiers (Starter/Growth/Chain). Rather
// than guess a mapping and silently trial someone on a plan nobody chose, Sales
// confirms the plan here — one dropdown, and the only thing on this screen that
// isn't already filled in from the lead.
export default function ConvertModal({ lead, choices, onClose, onConverted }) {
  const [planKey, setPlanKey] = useState('')
  const [err, setErr] = useState('')
  const [undelivered, setUndelivered] = useState(false)
  const convert = useConvertLead()
  const { data: plans } = usePlans()

  // Public tiers are picked by their tier key; negotiated plans by their row
  // key. The backend resolves both — see crm_convert._resolve_plan.
  const options = (plans ?? []).filter((p) => !p.archived)

  async function submit(e) {
    e.preventDefault()
    setErr('')
    try {
      const result = await convert.mutateAsync({ leadId: lead.id, plan_key: planKey })
      onConverted?.(result)
      // The merchant exists either way — but if the setup link never went out,
      // closing on a green tick would leave Sales believing the owner had been
      // handed their account when nobody has told them anything.
      if (result?.email_sent === false) {
        setUndelivered(true)
        return
      }
      onClose()
    } catch (e2) {
      setErr(normalizeError(e2).message)
    }
  }

  const blockedReason = !lead.email
    ? 'This lead has no email address. The owner’s login and setup link both need one — add it first.'
    : null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={onClose}>
      <form
        onClick={(e) => e.stopPropagation()}
        onSubmit={submit}
        className="w-full max-w-lg rounded-card border border-line bg-surface p-5"
      >
        <div className="mb-4 flex items-start justify-between">
          <div className="flex items-center gap-2 text-tx">
            <Building2 size={17} className="text-success" />
            <h2 className="font-head font-semibold">Convert to Merchant</h2>
          </div>
          <button type="button" onClick={onClose} className="text-tx-3 hover:text-tx">
            <X size={18} />
          </button>
        </div>

        {undelivered ? (
          <div className="flex items-start gap-2 rounded-ctl border border-warn/40 bg-warn/10 p-3 text-sm text-warn">
            <AlertTriangle size={15} className="mt-0.5 shrink-0" />
            <div>
              <div className="font-semibold">Converted — but the setup email did not send</div>
              <div className="mt-1 text-xs opacity-90">
                {lead.business_name} is a live merchant and {lead.email} owns it, but they have
                not been told. Re-send the link from Merchants → Support → Send password reset.
              </div>
            </div>
          </div>
        ) : blockedReason ? (
          <div className="flex items-start gap-2 rounded-ctl border border-warn/40 bg-warn/10 p-3 text-sm text-warn">
            <AlertTriangle size={15} className="mt-0.5 shrink-0" />
            {blockedReason}
          </div>
        ) : (
          <>
            {/* What Sales is about to create, from data they already entered.
                Shown because "Convert" is irreversible and they should see
                exactly what carries across before it does. */}
            <div className="rounded-ctl border border-line bg-bg p-3">
              <div className="mb-2 text-xs text-tx-3">This will create</div>
              <ul className="flex flex-col gap-1.5 text-sm text-tx-2">
                <Carry label="Merchant" value={lead.business_name} />
                <Carry label="Owner" value={`${lead.name || lead.business_name} · ${lead.email}`} />
                <Carry label="First branch" value={`Main Branch · ${lead.address || lead.area || 'no address'}`} />
                {lead.logo_url && <Carry label="Logo" value="Reused from the lead" />}
                <Carry label="Category" value={labelFor(choices, KIND.CATEGORY, lead.category)} />
              </ul>
            </div>

            <label className="mt-4 flex flex-col gap-1 text-xs text-tx-3">
              Plan sold
              <select
                value={planKey}
                onChange={(e) => setPlanKey(e.target.value)}
                className="rounded-ctl border border-line bg-bg px-3 py-2 text-sm text-tx focus:border-brand focus:outline-none"
              >
                <option value="">Default trial — no plan agreed yet</option>
                {options.map((p) => (
                  <option key={p.key} value={p.key}>
                    {p.name}
                  </option>
                ))}
              </select>
            </label>

            {/* The single most important thing on this screen: Sales must not
                leave thinking the merchant is paying. */}
            <div className="mt-3 rounded-ctl border border-line bg-bg p-3 text-xs text-tx-3">
              The merchant starts a <span className="text-tx-2">14-day trial</span>
              {planKey ? ' on the plan above' : ''}, and sets their own password from a link we
              email them. Nothing is charged — they subscribe through the normal checkout, and
              payment activates the plan.
            </div>

            {err && <div className="mt-3 text-sm text-danger">{err}</div>}
          </>
        )}

        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-ctl border border-line px-4 py-2 text-sm text-tx-2 hover:text-tx"
          >
            {undelivered ? 'Close' : 'Cancel'}
          </button>
          <button
            type="submit"
            hidden={undelivered}
            disabled={convert.isPending || Boolean(blockedReason)}
            className="flex items-center gap-2 rounded-ctl bg-success px-4 py-2 text-sm font-semibold text-bg hover:opacity-90 disabled:opacity-50"
          >
            {convert.isPending ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <ArrowRight size={14} />
            )}
            Convert
          </button>
        </div>
      </form>
    </div>
  )
}

function Carry({ label, value }) {
  return (
    <li className="flex items-start gap-2">
      <Check size={13} className="mt-1 shrink-0 text-success" />
      <span>
        <span className="text-tx-3">{label}: </span>
        {value}
      </span>
    </li>
  )
}
