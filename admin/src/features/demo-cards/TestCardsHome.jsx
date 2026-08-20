import { useState } from 'react'
import { Loader2, Trash2, Wallet } from 'lucide-react'
import { useCreateDemoCard, useDeleteDemoCard, useDemoCards } from './api'
import { useDemoCardPass } from './api'
import CardPreview from './CardPreview'
import PassResult from './PassResult'
import { normalizeError } from '../../lib/api'
import { shortDate } from '../../lib/format'

// Test Cards — build a prospect's branded wallet pass for a proposal.
//
// Same fields as the merchant dashboard's Card Designer, plus the business name
// (free text: the prospect has not signed up, so there is no merchant to pick).
// Everything created here is demo data — flagged and excluded from the merchant
// directory, analytics, revenue and lifecycle.
const EMPTY = {
  merchant_name: '',
  name: '',
  type: 'STAMP',
  stamps_required: 8,
  reward_title: '',
  reward_description: '',
  color_bg: '#0E1B2A',
  color_fg: '#FFFFFF',
  logo_url: '',
  hero_image_url: '',
  single_use: false,
  referral_enabled: false,
  preview_stamps: 3,
}

export default function TestCardsHome() {
  const [form, setForm] = useState(EMPTY)
  const [err, setErr] = useState('')
  const [platform, setPlatform] = useState('APPLE')
  const [result, setResult] = useState(null)
  const [reopenId, setReopenId] = useState(null)

  const { data: cards, isLoading } = useDemoCards()
  const create = useCreateDemoCard()
  const del = useDeleteDemoCard()
  // Passes are generated on demand, so reopening an old card refetches them.
  const { data: reopened } = useDemoCardPass(reopenId)

  const set = (k) => (v) => setForm((f) => ({ ...f, [k]: v }))
  const setEvt = (k) => (e) => set(k)(e.target.value)
  const canSubmit =
    form.merchant_name.trim() && form.name.trim() && form.reward_title.trim() && !create.isPending

  async function submit(e) {
    e.preventDefault()
    setErr('')
    try {
      const created = await create.mutateAsync({
        ...form,
        stamps_required: Number(form.stamps_required),
        preview_stamps: Number(form.preview_stamps),
      })
      setResult(created)
      setForm(EMPTY)
    } catch (e2) {
      setErr(normalizeError(e2).message)
    }
  }

  async function remove(cardId, merchantName) {
    if (!window.confirm(`Delete the test card for ${merchantName}?`)) return
    try {
      await del.mutateAsync(cardId)
    } catch (e2) {
      window.alert(normalizeError(e2).message)
    }
  }

  // Reopening an existing card shows the same result panel as a fresh create.
  const reopenRow = cards?.find((c) => c.card_id === reopenId)
  const shownResult =
    result || (reopenRow && reopened ? { ...reopenRow, ...reopened } : null)

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h1 className="font-head text-2xl font-bold text-tx">Test Cards</h1>
        <p className="mt-1 text-sm text-tx-3">
          Build a branded wallet card for a prospect and show it to them during a proposal — no
          merchant account needed. Test cards never appear in the merchant directory or analytics.
        </p>
      </div>

      <div className="grid gap-5 lg:grid-cols-[1fr_320px]">
        {/* Builder */}
        <form onSubmit={submit} className="rounded-card border border-line bg-surface p-5">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Field
              label="Business name"
              required
              placeholder="Cafe Blooms"
              value={form.merchant_name}
              onChange={setEvt('merchant_name')}
              hint="Shown as the brand on the wallet pass"
            />
            <Field
              label="Program name"
              required
              placeholder="Coffee Club"
              value={form.name}
              onChange={setEvt('name')}
            />
            <Picker label="Card type" value={form.type} onChange={setEvt('type')}>
              <option value="STAMP">Stamp card</option>
              <option value="POINTS">Points</option>
            </Picker>
            <Field
              label="Stamps required"
              type="number"
              min={1}
              max={30}
              value={form.stamps_required}
              onChange={setEvt('stamps_required')}
            />
            <Field
              label="Reward title"
              required
              placeholder="Free latte"
              value={form.reward_title}
              onChange={setEvt('reward_title')}
            />
            <Field
              label="Stamps to pre-fill"
              type="number"
              min={0}
              max={30}
              value={form.preview_stamps}
              onChange={setEvt('preview_stamps')}
              hint="Makes the demo pass look already in use"
            />
            <Field
              label="Logo URL"
              placeholder="https://…"
              value={form.logo_url}
              onChange={setEvt('logo_url')}
            />
            <Field
              label="Hero image URL"
              placeholder="https://…"
              value={form.hero_image_url}
              onChange={setEvt('hero_image_url')}
            />
            <Field
              label="Background colour"
              type="color"
              value={form.color_bg}
              onChange={setEvt('color_bg')}
            />
            <Field
              label="Text colour"
              type="color"
              value={form.color_fg}
              onChange={setEvt('color_fg')}
            />
          </div>

          <label className="mt-3 flex flex-col gap-1 text-xs text-tx-3">
            Reward description
            <textarea
              value={form.reward_description}
              onChange={setEvt('reward_description')}
              rows={2}
              className={inputClass}
            />
          </label>

          {err && <div className="mt-3 text-sm text-danger">{err}</div>}

          <div className="mt-5 flex justify-end">
            <button
              type="submit"
              disabled={!canSubmit}
              className="flex items-center gap-2 rounded-ctl bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-brand-d disabled:opacity-50"
            >
              {create.isPending ? <Loader2 size={14} className="animate-spin" /> : <Wallet size={15} />}
              Create test card
            </button>
          </div>
        </form>

        {/* Live preview */}
        <div className="flex flex-col items-center gap-3 rounded-card border border-line bg-bg p-5">
          <div className="flex gap-1 rounded-ctl border border-line p-1">
            {['APPLE', 'GOOGLE'].map((p) => (
              <button
                key={p}
                type="button"
                onClick={() => setPlatform(p)}
                className={
                  'rounded-ctl px-3 py-1 text-xs font-semibold ' +
                  (platform === p ? 'bg-brand text-white' : 'text-tx-2 hover:text-tx')
                }
              >
                {p === 'APPLE' ? 'Apple' : 'Google'}
              </button>
            ))}
          </div>
          <CardPreview platform={platform} form={form} merchantName={form.merchant_name} />
        </div>
      </div>

      {/* Previously built cards */}
      <div className="rounded-card border border-line bg-surface p-5">
        <h2 className="mb-3 font-head font-semibold text-tx">Previously built</h2>
        {isLoading ? (
          <Loader2 className="mx-auto my-4 animate-spin text-tx-3" />
        ) : !cards?.length ? (
          <p className="py-4 text-center text-sm text-tx-3">No test cards yet.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {cards.map((c) => (
              <li
                key={c.card_id}
                className="flex flex-wrap items-center justify-between gap-3 rounded-ctl border border-line bg-bg px-3 py-2"
              >
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium text-tx">{c.merchant_name}</div>
                  <div className="truncate text-xs text-tx-3">
                    {c.card_name} · {shortDate(c.created_at)} ·{' '}
                    <span className="font-num">
                      {c.stamp_count}/{c.stamps_required} stamps
                    </span>
                  </div>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => {
                      setResult(null)
                      setReopenId(c.card_id)
                    }}
                    className="flex items-center gap-1.5 rounded-ctl border border-line px-3 py-1.5 text-xs text-tx-2 hover:border-brand hover:text-brand"
                  >
                    <Wallet size={13} /> Show pass
                  </button>
                  <button
                    onClick={() => remove(c.card_id, c.merchant_name)}
                    disabled={del.isPending}
                    className="flex items-center gap-1.5 rounded-ctl border border-danger/50 px-3 py-1.5 text-xs text-danger hover:bg-danger hover:text-white disabled:opacity-60"
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      {shownResult && (
        <PassResult
          result={shownResult}
          onClose={() => {
            setResult(null)
            setReopenId(null)
          }}
        />
      )}
    </div>
  )
}

const inputClass =
  'rounded-ctl border border-line bg-bg px-3 py-2 text-sm text-tx placeholder:text-tx-3 focus:border-brand focus:outline-none'

function Field({ label, required, hint, ...props }) {
  return (
    <label className="flex flex-col gap-1 text-xs text-tx-3">
      <span>
        {label}
        {required && <span className="ml-0.5 text-danger">*</span>}
      </span>
      <input {...props} required={required} className={inputClass} />
      {hint && <span className="text-[11px] text-tx-3 opacity-80">{hint}</span>}
    </label>
  )
}

function Picker({ label, children, ...props }) {
  return (
    <label className="flex flex-col gap-1 text-xs text-tx-3">
      {label}
      <select {...props} className={inputClass}>
        {children}
      </select>
    </label>
  )
}
