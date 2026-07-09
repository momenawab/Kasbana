// Toggle + Checkbox (spec §10). RTL-safe via logical utilities.
export function Toggle({ checked, onChange, label, disabled = false }) {
  return (
    <label className="inline-flex items-center gap-2 cursor-pointer">
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={`relative h-6 w-11 rounded-full transition disabled:opacity-50 ${
          checked ? 'bg-teal' : 'bg-tx-3'
        }`}
      >
        <span
          className={`absolute top-0.5 h-5 w-5 rounded-full bg-white transition-all ${
            checked ? 'start-[22px]' : 'start-0.5'
          }`}
        />
      </button>
      {label && <span className="text-sm text-tx">{label}</span>}
    </label>
  )
}

export function Checkbox({ checked, onChange, label, disabled = false }) {
  return (
    <label className="inline-flex items-center gap-2 cursor-pointer">
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
        className="h-4 w-4 rounded border-line text-violet focus:ring-violet"
      />
      {label && <span className="text-sm text-tx">{label}</span>}
    </label>
  )
}
