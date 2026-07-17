import { useRef, useState } from 'react'
import {
  AlertTriangle,
  ArrowRight,
  Check,
  FileSpreadsheet,
  Loader2,
  Upload,
  X,
} from 'lucide-react'
import { useImportLeads, useImportPreview, useSalesUsers } from './api'
import { KIND, optionsFor } from './crm'
import { normalizeError } from '../../lib/api'

// Import wizard: Upload → Map → Result. Three steps because the whole point is
// that nothing is written until a human has seen the mapping — a spreadsheet
// imported blind puts phone numbers in the area field of four hundred leads and
// nobody notices until they call one.
const STEPS = ['upload', 'map', 'result']

export default function ImportModal({ choices, onClose, onDone }) {
  const [step, setStep] = useState('upload')
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState(null)
  const [mapping, setMapping] = useState({})
  const [source, setSource] = useState('other')
  const [assigned, setAssigned] = useState('')
  const [skipDuplicates, setSkipDuplicates] = useState(true)
  const [result, setResult] = useState(null)
  const [err, setErr] = useState('')

  const runPreview = useImportPreview()
  const runImport = useImportLeads()
  const { data: salesUsers } = useSalesUsers()

  async function onPick(f) {
    if (!f) return
    setFile(f)
    setErr('')
    try {
      const data = await runPreview.mutateAsync(f)
      setPreview(data)
      setMapping(data.suggested_mapping)
      setStep('map')
    } catch (e) {
      setErr(normalizeError(e).message)
    }
  }

  async function submit() {
    setErr('')
    try {
      const summary = await runImport.mutateAsync({
        file,
        mapping,
        source,
        assigned_sales: assigned,
        skip_duplicates: skipDuplicates,
      })
      setResult(summary)
      setStep('result')
    } catch (e) {
      setErr(normalizeError(e).message)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/50 p-4">
      <div className="my-8 w-full max-w-3xl rounded-card border border-line bg-surface p-5">
        <div className="mb-4 flex items-start justify-between">
          <div>
            <h2 className="font-head text-lg font-semibold text-tx">Import Leads</h2>
            <p className="mt-0.5 text-xs text-tx-3">
              CSV or Excel. Nothing is imported until you confirm the mapping.
            </p>
          </div>
          <button onClick={onClose} className="text-tx-3 hover:text-tx">
            <X size={18} />
          </button>
        </div>

        <Stepper step={step} />

        {err && (
          <div className="mb-4 flex items-start gap-2 rounded-ctl border border-danger/40 bg-danger/10 p-3 text-sm text-danger">
            <AlertTriangle size={15} className="mt-0.5 shrink-0" />
            {err}
          </div>
        )}

        {step === 'upload' && <UploadStep onPick={onPick} busy={runPreview.isPending} />}

        {step === 'map' && preview && (
          <MapStep
            preview={preview}
            mapping={mapping}
            setMapping={setMapping}
            source={source}
            setSource={setSource}
            assigned={assigned}
            setAssigned={setAssigned}
            skipDuplicates={skipDuplicates}
            setSkipDuplicates={setSkipDuplicates}
            salesUsers={salesUsers ?? []}
            choices={choices}
            onBack={() => setStep('upload')}
            onSubmit={submit}
            busy={runImport.isPending}
          />
        )}

        {step === 'result' && result && (
          <ResultStep
            result={result}
            onClose={() => {
              onDone?.(result)
              onClose()
            }}
          />
        )}
      </div>
    </div>
  )
}

function Stepper({ step }) {
  const at = STEPS.indexOf(step)
  const labels = ['Upload file', 'Map columns', 'Done']
  return (
    <div className="mb-5 flex items-center gap-2">
      {labels.map((label, i) => (
        <div key={label} className="flex items-center gap-2">
          <div
            className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-semibold ${
              i < at
                ? 'bg-success text-bg'
                : i === at
                  ? 'bg-brand text-white'
                  : 'bg-surface-2 text-tx-3'
            }`}
          >
            {i < at ? <Check size={13} /> : i + 1}
          </div>
          <span className={`text-xs ${i === at ? 'text-tx' : 'text-tx-3'}`}>{label}</span>
          {i < labels.length - 1 && <div className="mx-1 h-px w-6 bg-line" />}
        </div>
      ))}
    </div>
  )
}

function UploadStep({ onPick, busy }) {
  const input = useRef(null)
  const [dragging, setDragging] = useState(false)

  return (
    <div>
      <button
        type="button"
        onClick={() => input.current?.click()}
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragging(false)
          onPick(e.dataTransfer.files?.[0])
        }}
        className={`flex w-full flex-col items-center gap-3 rounded-card border-2 border-dashed p-10 transition ${
          dragging ? 'border-brand bg-brand-bg/30' : 'border-line hover:border-brand/50'
        }`}
      >
        {busy ? (
          <Loader2 size={28} className="animate-spin text-brand" />
        ) : (
          <Upload size={28} className="text-tx-3" />
        )}
        <div className="text-center">
          <div className="text-sm font-medium text-tx">
            {busy ? 'Reading your file…' : 'Drop a file here, or click to choose'}
          </div>
          <div className="mt-1 text-xs text-tx-3">CSV or Excel (.xlsx) · up to 5 MB</div>
        </div>
      </button>

      <input
        ref={input}
        type="file"
        accept=".csv,.xlsx,.xlsm,text/csv"
        onChange={(e) => onPick(e.target.files?.[0])}
        className="hidden"
      />

      <div className="mt-4 rounded-ctl border border-line bg-bg p-3 text-xs text-tx-3">
        Your file needs a header row with at least a <b className="text-tx-2">business name</b> and
        a <b className="text-tx-2">phone</b> column. Everything else is optional and you map it on
        the next step.
      </div>
    </div>
  )
}

function MapStep({
  preview,
  mapping,
  setMapping,
  source,
  setSource,
  assigned,
  setAssigned,
  skipDuplicates,
  setSkipDuplicates,
  salesUsers,
  choices,
  onBack,
  onSubmit,
  busy,
}) {
  const setColumn = (column, field) => {
    const next = { ...mapping }
    if (field) {
      // One field per column: clear any other column that already claimed it,
      // so two columns can't both map to phone and silently fight.
      for (const [c, f] of Object.entries(next)) if (f === field && c !== column) delete next[c]
      next[column] = field
    } else {
      delete next[column]
    }
    setMapping(next)
  }

  const mappedFields = new Set(Object.values(mapping))
  const missingRequired = preview.fields
    .filter((f) => f.required && !mappedFields.has(f.field))
    .map((f) => f.label)
  const canImport = missingRequired.length === 0 && !busy

  return (
    <div>
      <div className="mb-3 flex items-center justify-between text-sm">
        <span className="text-tx-2">
          {preview.total_rows.toLocaleString()} row{preview.total_rows === 1 ? '' : 's'} found
        </span>
        {preview.existing_matches > 0 && (
          <span className="text-warn">
            {preview.existing_matches} already in the pipeline
          </span>
        )}
      </div>

      {/* Map each column to a field. The sample value under each column is what
          makes a wrong guess obvious before it is applied. */}
      <div className="max-h-64 overflow-y-auto rounded-ctl border border-line">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-surface-2 text-xs text-tx-3">
            <tr>
              <th className="px-3 py-2 text-left font-medium">Your column</th>
              <th className="px-3 py-2 text-left font-medium">Sample</th>
              <th className="px-3 py-2 text-left font-medium">Imports as</th>
            </tr>
          </thead>
          <tbody>
            {preview.columns.map((column) => (
              <tr key={column} className="border-t border-line/60">
                <td className="px-3 py-2 font-medium text-tx">{column}</td>
                <td className="max-w-[160px] truncate px-3 py-2 text-tx-3">
                  {preview.sample[0]?.[column] || '—'}
                </td>
                <td className="px-3 py-2">
                  <select
                    value={mapping[column] || ''}
                    onChange={(e) => setColumn(column, e.target.value)}
                    className="w-full rounded-ctl border border-line bg-bg px-2 py-1 text-sm text-tx focus:border-brand focus:outline-none"
                  >
                    <option value="">— Don’t import —</option>
                    {preview.fields.map((f) => (
                      <option key={f.field} value={f.field}>
                        {f.label}
                        {f.required ? ' *' : ''}
                      </option>
                    ))}
                  </select>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {missingRequired.length > 0 && (
        <div className="mt-3 flex items-center gap-2 text-xs text-warn">
          <AlertTriangle size={13} />
          Map a column to {missingRequired.join(' and ')} — a lead needs {missingRequired.length > 1 ? 'them' : 'it'}.
        </div>
      )}

      <div className="mt-4 grid grid-cols-1 gap-3 border-t border-line pt-4 sm:grid-cols-2">
        <label className="flex flex-col gap-1 text-xs text-tx-3">
          Source for all imported leads
          <select
            value={source}
            onChange={(e) => setSource(e.target.value)}
            className="rounded-ctl border border-line bg-bg px-3 py-2 text-sm text-tx focus:border-brand focus:outline-none"
          >
            {optionsFor(choices, KIND.SOURCE).map((c) => (
              <option key={c.slug} value={c.slug}>
                {c.label}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1 text-xs text-tx-3">
          Assign all to
          <select
            value={assigned}
            onChange={(e) => setAssigned(e.target.value)}
            className="rounded-ctl border border-line bg-bg px-3 py-2 text-sm text-tx focus:border-brand focus:outline-none"
          >
            <option value="">Unassigned</option>
            {salesUsers.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name || a.email}
              </option>
            ))}
          </select>
        </label>
      </div>

      <label className="mt-3 flex items-center gap-2 text-sm text-tx-2">
        <input
          type="checkbox"
          checked={skipDuplicates}
          onChange={(e) => setSkipDuplicates(e.target.checked)}
          className="accent-brand"
        />
        Skip rows that already exist (by phone, email or business name)
      </label>

      <div className="mt-5 flex justify-between">
        <button
          onClick={onBack}
          className="rounded-ctl border border-line px-4 py-2 text-sm text-tx-2 hover:text-tx"
        >
          Back
        </button>
        <button
          onClick={onSubmit}
          disabled={!canImport}
          className="flex items-center gap-2 rounded-ctl bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-brand-d disabled:opacity-50"
        >
          {busy ? <Loader2 size={14} className="animate-spin" /> : <ArrowRight size={14} />}
          Import {preview.total_rows.toLocaleString()} row{preview.total_rows === 1 ? '' : 's'}
        </button>
      </div>
    </div>
  )
}

function ResultStep({ result, onClose }) {
  return (
    <div>
      <div className="mb-4 flex flex-col items-center gap-2 py-4">
        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-success/20">
          <Check size={24} className="text-success" />
        </div>
        <div className="text-lg font-semibold text-tx">Import complete</div>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <Tally label="Created" value={result.created} tone="text-success" />
        <Tally label="Skipped" value={result.skipped} tone="text-warn" />
        <Tally label="Failed" value={result.failed} tone={result.failed ? 'text-danger' : 'text-tx-3'} />
      </div>

      {/* Detail only when there is something to act on — a clean import needs no
          list of nothing. */}
      {result.skipped_rows?.length > 0 && (
        <Detail
          title={`Skipped as duplicates (${result.skipped})`}
          rows={result.skipped_rows.map((r) => `Row ${r.row}: ${r.business_name} — ${r.reason}`)}
        />
      )}
      {result.failed_rows?.length > 0 && (
        <Detail
          title={`Failed (${result.failed})`}
          rows={result.failed_rows.map((r) => `Row ${r.row}: ${r.reason}`)}
          tone="text-danger"
        />
      )}

      <div className="mt-5 flex justify-end">
        <button
          onClick={onClose}
          className="rounded-ctl bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-brand-d"
        >
          Done
        </button>
      </div>
    </div>
  )
}

function Tally({ label, value, tone }) {
  return (
    <div className="rounded-card border border-line bg-bg p-4 text-center">
      <div className={`font-num text-3xl ${tone}`}>{value}</div>
      <div className="mt-1 text-xs text-tx-3">{label}</div>
    </div>
  )
}

function Detail({ title, rows, tone = 'text-tx-3' }) {
  return (
    <div className="mt-4">
      <div className="mb-1 flex items-center gap-1.5 text-xs text-tx-3">
        <FileSpreadsheet size={12} />
        {title}
      </div>
      <ul className={`max-h-32 overflow-y-auto rounded-ctl border border-line bg-bg p-2 text-xs ${tone}`}>
        {rows.map((r, i) => (
          <li key={i} className="py-0.5">
            {r}
          </li>
        ))}
      </ul>
    </div>
  )
}
