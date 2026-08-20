import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, CheckCircle2, Loader2, XCircle, Zap } from 'lucide-react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import Badge from '../../components/Badge'
import { useAuth } from '../../hooks/useAuth'
import { useApiKeys, useCosts, useTestProvider } from './api'

const STATE_TONES = {
  ok: 'success',
  untested: 'info',
  failing: 'danger',
  missing: 'danger',
  not_configured: 'neutral',
}

const STATE_LABELS = {
  ok: 'Working',
  untested: 'Not tested yet',
  failing: 'Last call failed',
  missing: 'Required — not set',
  not_configured: 'Not configured',
}

export default function SettingsHome() {
  const { role } = useAuth()
  const isSuper = role === 'SUPER_ADMIN'
  const [days, setDays] = useState(30)

  const { data: keys, isLoading: keysLoading } = useApiKeys()
  const { data: costs, isLoading: costsLoading } = useCosts(days)

  return (
    <div className="space-y-6">
      <Link
        to="/leadgen"
        className="inline-flex items-center gap-1.5 text-sm text-tx-2 hover:text-tx"
      >
        <ArrowLeft size={14} /> Searches
      </Link>
      <header>
        <h1 className="text-xl font-semibold text-tx">Providers &amp; cost</h1>
        <p className="mt-1 text-sm text-tx-2">
          What lead generation is connected to, and what it has spent.
        </p>
      </header>

      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-tx">Spend</h2>
        <div className="flex gap-2">
          {[7, 30, 90].map((value) => (
            <button
              key={value}
              onClick={() => setDays(value)}
              className={
                'rounded-full px-3 py-1 text-xs font-semibold transition ' +
                (days === value
                  ? 'bg-brand text-white'
                  : 'bg-surface-2 text-tx-2 hover:bg-surface-3 hover:text-tx')
              }
            >
              {value} days
            </button>
          ))}
        </div>

        {costsLoading ? (
          <Spinner />
        ) : (
          <>
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              <Stat label="Total spend" value={`$${Number(costs.total_cost_usd).toFixed(2)}`} />
              <Stat
                label="Cost per lead"
                value={`$${Number(costs.cost_per_lead_usd).toFixed(4)}`}
              />
              <Stat
                label="Cost per imported"
                value={
                  costs.cost_per_imported_usd == null
                    ? '—'
                    : `$${Number(costs.cost_per_imported_usd).toFixed(3)}`
                }
                hint={costs.cost_per_imported_usd == null ? 'Nothing imported yet' : null}
              />
              <Stat label="Billed calls" value={costs.total_calls} />
            </div>

            {/* Says out loud that these rest on configured rates, not invoices.
                A figure that looks like accounting and is not should say so. */}
            {costs.rates_are_estimates && (
              <p className="text-xs text-tx-2">
                Figures use the prices configured in the environment, not provider invoices —
                treat them as estimates.
              </p>
            )}

            {costs.daily?.length > 0 && (
              <div className="rounded-card bg-surface p-4">
                <ResponsiveContainer width="100%" height={180}>
                  <BarChart data={costs.daily}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#332F45" vertical={false} />
                    <XAxis dataKey="day" stroke="#8b87a0" fontSize={11} />
                    <YAxis stroke="#8b87a0" fontSize={11} />
                    <Tooltip
                      contentStyle={{
                        background: '#262238',
                        border: 'none',
                        borderRadius: 10,
                        fontSize: 12,
                      }}
                      formatter={(value) => [`$${Number(value).toFixed(4)}`, 'Spend']}
                    />
                    <Bar dataKey="cost_usd" fill="#845AEA" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}

            {costs.by_provider?.length > 0 && (
              <div className="overflow-x-auto rounded-card bg-surface">
                <table className="w-full text-sm">
                  <thead className="border-b border-surface-2 text-left text-xs uppercase tracking-wide text-tx-2">
                    <tr>
                      <th className="p-3">Provider</th>
                      <th className="p-3">Calls</th>
                      <th className="p-3">Tokens</th>
                      <th className="p-3">Failures</th>
                      <th className="p-3">Cost</th>
                    </tr>
                  </thead>
                  <tbody>
                    {costs.by_provider.map((row) => (
                      <tr key={row.provider} className="border-b border-surface-2/50 last:border-0">
                        <td className="p-3 text-tx">{row.provider_label || row.provider}</td>
                        <td className="p-3 text-tx-2">{row.calls}</td>
                        <td className="p-3 text-tx-2">
                          {row.tokens_in || row.tokens_out
                            ? `${row.tokens_in} / ${row.tokens_out}`
                            : '—'}
                        </td>
                        <td className={`p-3 ${row.failures ? 'text-danger' : 'text-tx-2'}`}>
                          {row.failures || 0}
                        </td>
                        <td className="p-3 text-tx">${Number(row.cost_usd).toFixed(4)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-tx">Providers</h2>
        <p className="text-xs text-tx-2">
          Keys live in the server environment and are never stored in the database or shown
          here. Use Test to confirm one works.
        </p>
        {keysLoading ? (
          <Spinner />
        ) : (
          <div className="grid gap-3 lg:grid-cols-2">
            {keys.providers.map((provider) => (
              <ProviderCard key={provider.provider} provider={provider} canTest={isSuper} />
            ))}
          </div>
        )}
      </section>
    </div>
  )
}

function ProviderCard({ provider, canTest }) {
  const test = useTestProvider()
  const [result, setResult] = useState(null)

  return (
    <div className="rounded-card bg-surface p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-tx">{provider.label}</p>
          <p className="mt-1 text-xs text-tx-2">{provider.purpose}</p>
        </div>
        <Badge tone={STATE_TONES[provider.state]}>{STATE_LABELS[provider.state]}</Badge>
      </div>

      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-tx-2">
        <span>
          <code className="text-tx">{provider.env_var}</code>
        </span>
        <span>{provider.calls_24h} calls / 24h</span>
        <span>{provider.calls_30d} / 30d</span>
        <span>${Number(provider.cost_30d_usd).toFixed(3)} / 30d</span>
      </div>

      {canTest && (
        <div className="mt-3 flex items-center gap-3">
          <button
            onClick={() =>
              test.mutate(provider.provider, { onSuccess: (data) => setResult(data) })
            }
            disabled={test.isPending}
            className="inline-flex items-center gap-1.5 rounded-ctl bg-surface-2 px-3 py-1.5 text-xs font-semibold text-tx transition hover:bg-surface-3 disabled:opacity-50"
          >
            {test.isPending ? (
              <Loader2 size={12} className="animate-spin" />
            ) : (
              <Zap size={12} />
            )}
            Test connection
          </button>
          {result && (
            <span
              className={`flex items-center gap-1 text-xs ${result.ok ? 'text-success' : 'text-danger'}`}
            >
              {result.ok ? <CheckCircle2 size={12} /> : <XCircle size={12} />}
              {result.message}
            </span>
          )}
        </div>
      )}
    </div>
  )
}

function Stat({ label, value, hint }) {
  return (
    <div className="rounded-card bg-surface p-4">
      <p className="text-lg font-semibold text-tx">{value}</p>
      <p className="text-xs text-tx-2">{label}</p>
      {hint && <p className="mt-0.5 text-xs text-tx-2/70">{hint}</p>}
    </div>
  )
}

function Spinner() {
  return (
    <div className="flex justify-center py-12 text-tx-2">
      <Loader2 className="animate-spin" />
    </div>
  )
}
