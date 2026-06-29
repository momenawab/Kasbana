// ColorPicker (spec §10) — native swatch + hex input + brand presets.
const PRESETS = ['#0E1B2A', '#E0A23B', '#1C7C73', '#C75D43', '#16293D', '#FFFFFF']

export default function ColorPicker({ value = '#0E1B2A', onChange, label }) {
  return (
    <div>
      {label && <span className="mb-1 block text-sm text-tx-2">{label}</span>}
      <div className="flex items-center gap-2">
        <input
          type="color"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="h-9 w-10 cursor-pointer rounded-ctl border border-line"
          aria-label={label || 'color'}
        />
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="w-28 rounded-ctl border border-line px-2 py-1.5 font-mono text-sm uppercase"
        />
        <div className="flex gap-1">
          {PRESETS.map((c) => (
            <button
              key={c}
              type="button"
              onClick={() => onChange(c)}
              style={{ background: c }}
              className="h-6 w-6 rounded-full border border-line"
              aria-label={c}
            />
          ))}
        </div>
      </div>
    </div>
  )
}
