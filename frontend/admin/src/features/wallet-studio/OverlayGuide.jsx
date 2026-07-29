// The reference panel that sits beside the JSON editors.
//
// Everything here is the sort of thing that is otherwise learned by having a
// pass rejected on a real phone: which keys the platform owns, which regions
// Apple caps and at what, which tokens resolve per customer, and what the image
// slots actually are. Kept next to the editor because an admin authoring raw
// pass JSON should not have to hold Apple's PassKit reference in their head.
//
// The locked-key list mirrors wallets/overlay.py (LOCKED_APPLE /
// LOCKED_GOOGLE_*). If that changes, change it here — the backend rejects the
// key either way, but a stale list here wastes the admin's time.
import { useState } from 'react'
import { ChevronDown, Lock, Sparkles } from 'lucide-react'

const TOKENS = [
  ['{balance}', 'Earned/goal, e.g. 3/8'],
  ['{stamps}', 'Stamps collected'],
  ['{points}', 'Points collected'],
  ['{goal}', 'Stamps required'],
  ['{remaining}', 'Stamps still needed'],
  ['{reward}', 'Reward title'],
  ['{merchant}', 'Business name'],
  ['{program}', 'Card name'],
]

const LOCKED = [
  'formatVersion',
  'passTypeIdentifier',
  'teamIdentifier',
  'serialNumber',
  'authenticationToken',
  'webServiceURL',
  'barcode / barcodes',
  'voided',
]

const REGIONS = [
  ['headerFields', 'up to 3', 'top-right, beside the logo'],
  ['primaryFields', 'up to 1', 'large, overlaid on the strip'],
  ['secondaryFields', 'up to 4', 'row beneath the strip'],
  ['auxiliaryFields', 'up to 4', 'bottom row'],
  ['backFields', 'unbounded', 'back of the pass'],
]

const SNIPPETS = [
  {
    name: 'Nearby lock-screen suggestion',
    why: 'The pass surfaces on the customer’s lock screen near the shop. Up to 10 points.',
    json: {
      locations: [{ latitude: 30.0444, longitude: 31.2357, relevantText: 'Your card is here ☕' }],
      maxDistance: 150,
    },
  },
  {
    name: 'Custom strip artwork',
    why: 'Turns off Apple’s gloss so a photo strip is not washed out.',
    json: { suppressStripShine: true },
  },
  {
    name: 'Clickable link on the back',
    why: 'attributedValue renders real HTML links; plain value does not.',
    json: {
      storeCard: {
        backFields: [
          {
            key: 'menu',
            label: 'Menu',
            value: 'View our menu',
            attributedValue: '<a href="https://example.com">View our menu</a>',
          },
        ],
      },
    },
  },
  {
    name: 'Right-aligned balance',
    why: 'Per-field alignment — not exposed by any template.',
    json: {
      storeCard: {
        headerFields: [
          {
            key: 'balance',
            label: 'STAMPS',
            value: '{balance}',
            textAlignment: 'PKTextAlignmentRight',
          },
        ],
      },
    },
  },
  {
    name: 'Remove a generated field',
    why: 'null deletes a key the builder added (RFC 7386 merge-patch).',
    json: { logoText: null },
  },
]

function Section({ title, icon: Icon, children, open: initial = false }) {
  const [open, setOpen] = useState(initial)
  return (
    <div className="rounded-ctl border border-line">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm font-semibold text-tx"
      >
        {Icon && <Icon size={14} className="shrink-0 text-tx-3" />}
        <span className="flex-1">{title}</span>
        <ChevronDown
          size={14}
          className={`shrink-0 text-tx-3 transition ${open ? 'rotate-180' : ''}`}
        />
      </button>
      {open && <div className="border-t border-line px-3 py-2.5">{children}</div>}
    </div>
  )
}

export default function OverlayGuide({ onInsert }) {
  return (
    <div className="flex flex-col gap-2">
      <div className="rounded-ctl border border-brand/30 bg-brand-bg/40 px-3 py-2.5">
        <p className="text-xs leading-relaxed text-tx-2">
          The JSON is <strong className="text-tx">merged over</strong> the pass the template already
          builds — you only write what you want to change, and every smart default (contact links,
          powered-by, the message field) survives. Nested objects merge, arrays replace whole, and{' '}
          <code className="text-brand">null</code> deletes a key.
        </p>
        <p className="mt-1.5 text-xs leading-relaxed text-tx-3">
          The <strong className="text-tx-2">Current pass</strong> panel above shows what this card
          renders today — copy from it rather than writing from scratch.
        </p>
      </div>

      <Section title="Value tokens — resolve per customer" icon={Sparkles} open>
        <p className="mb-2 text-xs text-tx-3">
          Write these inside any string. A literal number freezes every customer at that value.
        </p>
        <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
          {TOKENS.map(([token, meaning]) => (
            <div key={token} className="contents">
              <dt className="font-mono text-brand">{token}</dt>
              <dd className="text-tx-3">{meaning}</dd>
            </div>
          ))}
        </dl>
      </Section>

      <Section title="Keys the platform owns" icon={Lock}>
        <p className="mb-2 text-xs text-tx-3">
          Rejected on save. They decide whether a pass can update over APNs and whether its QR
          resolves at the till — overriding them would break passes already in wallets.
        </p>
        <ul className="flex flex-wrap gap-1">
          {LOCKED.map((key) => (
            <li
              key={key}
              className="rounded bg-surface-2 px-1.5 py-0.5 font-mono text-[11px] text-tx-3"
            >
              {key}
            </li>
          ))}
        </ul>
      </Section>

      <Section title="Apple field regions">
        <p className="mb-2 text-xs text-tx-3">
          Apple fixes the positions — a storeCard has these four regions and no more. Write them
          under <code className="text-brand">storeCard</code>.
        </p>
        <dl className="flex flex-col gap-1 text-xs">
          {REGIONS.map(([key, cap, where]) => (
            <div key={key} className="flex items-baseline gap-2">
              <dt className="font-mono text-tx-2">{key}</dt>
              <dd className="text-tx-3">
                {cap} · {where}
              </dd>
            </div>
          ))}
        </dl>
      </Section>

      <Section title="Images a storeCard accepts">
        <ul className="flex flex-col gap-1 text-xs text-tx-3">
          <li>
            <span className="font-mono text-tx-2">icon</span> — 29×29 pt (@2x/@3x). Required.
          </li>
          <li>
            <span className="font-mono text-tx-2">logo</span> — up to 160×50 pt. Top-left.
          </li>
          <li>
            <span className="font-mono text-tx-2">strip</span> — 375×123 pt (1125×369 @3x). The only
            full-bleed canvas.
          </li>
        </ul>
        <p className="mt-2 text-xs text-tx-3">
          There is no <span className="font-mono">background</span> image on a storeCard — that is
          eventTicket only. Upload strip artwork in the Editor tab rather than here; it is
          cover-cropped for both Apple and Google.
        </p>
      </Section>

      <Section title="Google: two halves">
        <p className="text-xs text-tx-3">
          Google splits one pass into a <code className="text-brand">class</code> (per card, shared
          by every member) and an <code className="text-brand">object</code> (per customer). Write{' '}
          <code className="text-brand">{'{"class": {…}, "object": {…}}'}</code>. Tokens resolve only
          in the object half — a class has no customer to resolve against.
        </p>
      </Section>

      <Section title="Snippets">
        <div className="flex flex-col gap-2">
          {SNIPPETS.map((snippet) => (
            <div key={snippet.name} className="rounded border border-line p-2">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="text-xs font-semibold text-tx">{snippet.name}</p>
                  <p className="text-[11px] leading-snug text-tx-3">{snippet.why}</p>
                </div>
                <button
                  type="button"
                  onClick={() => onInsert?.(snippet.json)}
                  className="shrink-0 rounded border border-line px-2 py-1 text-[11px] font-semibold text-tx-2 hover:border-brand hover:text-brand"
                >
                  Insert
                </button>
              </div>
            </div>
          ))}
        </div>
      </Section>
    </div>
  )
}
