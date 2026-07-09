// Tabs (spec §10) — {tabs:[{key,label}], active, onChange}.
export default function Tabs({ tabs, active, onChange }) {
  return (
    <div role="tablist" className="flex gap-1 border-b border-line">
      {tabs.map((tab) => {
        const selected = tab.key === active
        return (
          <button
            key={tab.key}
            role="tab"
            aria-selected={selected}
            onClick={() => onChange(tab.key)}
            className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium transition ${
              selected
                ? 'border-violet text-slate'
                : 'border-transparent text-tx-2 hover:text-slate'
            }`}
          >
            {tab.label}
          </button>
        )
      })}
    </div>
  )
}
