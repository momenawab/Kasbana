// Input · Textarea · Select — share the same label/error/hint shell (spec §10).
function Shell({ label, name, error, hint, required, children }) {
  return (
    <label className="block" htmlFor={name}>
      {label && (
        <span className="mb-1 block text-sm text-tx-2">
          {label}
          {required && <span className="text-danger"> *</span>}
        </span>
      )}
      {children}
      {error ? (
        <span className="mt-1 block text-xs text-danger">{error}</span>
      ) : hint ? (
        <span className="mt-1 block text-xs text-tx-3">{hint}</span>
      ) : null}
    </label>
  )
}

const base =
  'w-full rounded-ctl border bg-white px-3 py-2 text-tx outline-none focus:border-amber'
const ring = (error) => (error ? 'border-danger' : 'border-line')

export function Input({ label, name, error, hint, required, className = '', ...props }) {
  return (
    <Shell label={label} name={name} error={error} hint={hint} required={required}>
      <input id={name} name={name} className={`${base} ${ring(error)} ${className}`} {...props} />
    </Shell>
  )
}

export function Textarea({ label, name, error, hint, required, rows = 4, className = '', ...props }) {
  return (
    <Shell label={label} name={name} error={error} hint={hint} required={required}>
      <textarea
        id={name}
        name={name}
        rows={rows}
        className={`${base} ${ring(error)} ${className}`}
        {...props}
      />
    </Shell>
  )
}

export function Select({ label, name, error, hint, required, options = [], className = '', ...props }) {
  return (
    <Shell label={label} name={name} error={error} hint={hint} required={required}>
      <select id={name} name={name} className={`${base} ${ring(error)} ${className}`} {...props}>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </Shell>
  )
}
