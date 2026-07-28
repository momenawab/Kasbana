import { useState } from 'react'
import { QRCodeSVG } from 'qrcode.react'
import { Apple, Check, Copy, Smartphone, X } from 'lucide-react'
import Stamper from './Stamper'

// Post-creation panel: the two add-to-wallet buttons plus a QR code.
//
// The QR matters more than the buttons here. The console runs on a desktop, and
// a .pkpass downloaded on a desktop does nothing — you scan the QR with the
// phone you are about to hand the prospect.
function CopyButton({ value }) {
  const [done, setDone] = useState(false)
  if (!value) return null
  return (
    <button
      type="button"
      onClick={() => {
        navigator.clipboard?.writeText(value)
        setDone(true)
        setTimeout(() => setDone(false), 1500)
      }}
      className="flex items-center gap-1.5 rounded-ctl border border-line px-3 py-1.5 text-xs text-tx-2 hover:border-brand hover:text-brand"
    >
      {done ? <Check size={13} /> : <Copy size={13} />}
      {done ? 'Copied' : 'Copy link'}
    </button>
  )
}

function WalletTile({ platform, url }) {
  const isApple = platform === 'apple'
  const Icon = isApple ? Apple : Smartphone
  const label = isApple ? 'Apple Wallet' : 'Google Wallet'

  return (
    <div className="flex flex-col items-center gap-3 rounded-card border border-line bg-bg p-4">
      <div className="flex items-center gap-2 text-sm font-semibold text-tx">
        <Icon size={16} /> {label}
      </div>

      {url ? (
        <>
          <div className="rounded-lg bg-white p-2">
            <QRCodeSVG value={url} size={132} />
          </div>
          <p className="text-center text-[11px] text-tx-3">Scan with the phone</p>
          <div className="flex w-full flex-col gap-2">
            <a
              href={url}
              target="_blank"
              rel="noreferrer"
              className="flex items-center justify-center gap-1.5 rounded-ctl bg-brand px-3 py-2 text-sm font-semibold text-white hover:bg-brand-d"
            >
              <Icon size={15} /> Add to {label}
            </a>
            <CopyButton value={url} />
          </div>
        </>
      ) : (
        <p className="py-6 text-center text-xs text-tx-3">
          Not available — {label} credentials are not configured on this environment.
        </p>
      )}
    </div>
  )
}

export default function PassResult({ result, onClose }) {
  const noPasses = !result.apple_pass_url && !result.google_save_url

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/50 p-4">
      <div className="my-8 w-full max-w-xl rounded-card border border-line bg-surface p-5">
        <div className="mb-4 flex items-start justify-between">
          <div>
            <h2 className="font-head text-lg font-semibold text-tx">Test card ready</h2>
            <p className="mt-0.5 text-xs text-tx-3">
              {result.card_name} · {result.merchant_name}
            </p>
          </div>
          <button onClick={onClose} className="text-tx-3 hover:text-tx">
            <X size={18} />
          </button>
        </div>

        {noPasses && (
          <div className="mb-4 rounded-ctl border border-warn/40 bg-warn/10 p-3 text-xs text-warn">
            The card was created, but no wallet passes could be generated — neither Apple nor
            Google credentials are configured on this environment.
          </div>
        )}

        <div className="grid gap-3 sm:grid-cols-2">
          <WalletTile platform="apple" url={result.apple_pass_url} />
          <WalletTile platform="google" url={result.google_save_url} />
        </div>

        {/* Live stamping — once the pass is on a phone, this is the demo. */}
        <div className="mt-3">
          <Stamper
            cardId={result.card_id}
            initialCount={result.stamp_count ?? 0}
            stampsRequired={result.stamps_required ?? 8}
          />
        </div>

        <div className="mt-5 flex justify-end">
          <button
            onClick={onClose}
            className="rounded-ctl border border-line px-4 py-2 text-sm text-tx-2 hover:text-tx"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  )
}
