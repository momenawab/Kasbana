import { useState } from 'react'
import { ExternalLink, Loader2, MapPin, Phone, User, X } from 'lucide-react'
import Badge from '../../components/Badge'
import { CONFIDENCE_TONES, SCORE_TONES, typeLabel } from './constants'
import { useGeneratedLead, useSetOwner } from './api'

const TABS = ['Overview', 'Score', 'Contact', 'Website', 'Owner', 'Raw']

export default function LeadDrawer({ leadId, onClose, canManage }) {
  const [tab, setTab] = useState('Overview')
  const { data: lead, isLoading } = useGeneratedLead(leadId)

  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-black/60" onClick={onClose}>
      <aside
        className="h-full w-full max-w-xl overflow-y-auto bg-surface p-5"
        onClick={(event) => event.stopPropagation()}
      >
        {isLoading || !lead ? (
          <div className="flex justify-center py-20 text-tx-2">
            <Loader2 className="animate-spin" />
          </div>
        ) : (
          <>
            <header className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <h2 className="text-lg font-semibold text-tx">{lead.business_name}</h2>
                <p className="mt-1 flex items-center gap-1.5 text-sm text-tx-2">
                  <MapPin size={13} /> {lead.address || '—'}
                </p>
              </div>
              <button onClick={onClose} className="text-tx-2 hover:text-tx">
                <X size={18} />
              </button>
            </header>

            <div className="mt-3 flex flex-wrap items-center gap-2">
              <Badge tone={SCORE_TONES[lead.score_label]}>
                {lead.fit_score} · {lead.score_label || 'unscored'}
              </Badge>
              <Badge>{typeLabel(lead.category)}</Badge>
              {lead.branch_count > 1 && <Badge tone="brand">{lead.branch_count} branches</Badge>}
              {lead.business_status === 'CLOSED_PERMANENTLY' && (
                <Badge tone="danger">Permanently closed</Badge>
              )}
              {lead.imported_at && <Badge tone="success">Imported</Badge>}
            </div>

            <nav className="mt-5 flex gap-1 overflow-x-auto border-b border-surface-2">
              {TABS.map((name) => (
                <button
                  key={name}
                  onClick={() => setTab(name)}
                  className={
                    'whitespace-nowrap px-3 py-2 text-sm transition ' +
                    (tab === name
                      ? 'border-b-2 border-brand font-semibold text-tx'
                      : 'text-tx-2 hover:text-tx')
                  }
                >
                  {name}
                </button>
              ))}
            </nav>

            <div className="py-4">
              {tab === 'Overview' && <Overview lead={lead} />}
              {tab === 'Score' && <ScoreTab lead={lead} />}
              {tab === 'Contact' && <ContactTab lead={lead} />}
              {tab === 'Website' && <WebsiteTab lead={lead} />}
              {tab === 'Owner' && <OwnerTab lead={lead} canManage={canManage} />}
              {tab === 'Raw' && (
                <pre className="overflow-x-auto rounded-ctl bg-surface-2 p-3 text-xs text-tx-2">
                  {JSON.stringify(lead.raw_places, null, 2)}
                </pre>
              )}
            </div>
          </>
        )}
      </aside>
    </div>
  )
}

function Overview({ lead }) {
  return (
    <dl className="grid grid-cols-2 gap-3 text-sm">
      <Row label="Rating">{lead.rating ? `${lead.rating} ★` : 'Not yet rated'}</Row>
      <Row label="Reviews">{lead.reviews_count}</Row>
      <Row label="Photos">{lead.photos_count}</Row>
      <Row label="Status">{lead.business_status || '—'}</Row>
      <Row label="State">{lead.state}</Row>
      <Row label="Discovered">{new Date(lead.created_at).toLocaleDateString()}</Row>
      {lead.google_maps_url && (
        <div className="col-span-2">
          <a
            href={lead.google_maps_url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 text-sm text-brand hover:underline"
          >
            Open in Google Maps <ExternalLink size={13} />
          </a>
        </div>
      )}
      {lead.crm_match && (
        <p className="col-span-2 rounded-ctl bg-surface-2 px-3 py-2 text-xs text-warn">
          Matches an existing CRM lead on {lead.crm_match_reason}. Importing needs
          confirmation.
        </p>
      )}
    </dl>
  )
}

// The itemised score. Zero-point rows are shown too: "we looked and found
// nothing" is different information from "we never looked", and a rep
// disputing a score needs to tell them apart.
function ScoreTab({ lead }) {
  if (!lead.score_breakdown?.length) return <Empty>Not scored yet.</Empty>
  return (
    <ul className="space-y-1.5">
      {lead.score_breakdown.map((row) => (
        <li
          key={row.key}
          className="flex items-start justify-between gap-3 rounded-ctl bg-surface-2 px-3 py-2"
        >
          <div className="min-w-0">
            <p className="text-sm text-tx">{row.label}</p>
            <p className="truncate text-xs text-tx-2">{row.detail}</p>
          </div>
          <span
            className={
              'shrink-0 text-sm font-semibold ' +
              (row.points > 0 ? 'text-success' : row.points < 0 ? 'text-danger' : 'text-tx-2')
            }
          >
            {row.points > 0 ? `+${row.points}` : row.points}
          </span>
        </li>
      ))}
    </ul>
  )
}

function ContactTab({ lead }) {
  const emails = lead.website_profile?.emails ?? []
  return (
    <div className="space-y-4 text-sm">
      <div>
        <p className="mb-1 text-xs uppercase tracking-wide text-tx-2">Phone</p>
        {lead.phone_e164 || lead.phone ? (
          <a
            href={`tel:${lead.phone_e164 || lead.phone}`}
            className="inline-flex items-center gap-1.5 text-tx hover:text-brand"
          >
            <Phone size={13} /> {lead.phone_e164 || lead.phone}
          </a>
        ) : (
          <span className="text-tx-2">None on the listing</span>
        )}
      </div>
      <div>
        <p className="mb-1 text-xs uppercase tracking-wide text-tx-2">Email</p>
        {emails.length ? (
          emails.map((email) => (
            <a key={email} href={`mailto:${email}`} className="block text-tx hover:text-brand">
              {email}
            </a>
          ))
        ) : (
          <span className="text-tx-2">None published</span>
        )}
      </div>
      <div>
        <p className="mb-1 text-xs uppercase tracking-wide text-tx-2">Social</p>
        {lead.socials?.length ? (
          <div className="flex flex-wrap gap-2">
            {lead.socials.map((social) => (
              <a
                key={social.platform}
                href={social.url}
                target="_blank"
                rel="noreferrer"
                className="rounded-full bg-surface-2 px-3 py-1 text-xs text-tx-2 hover:text-tx"
              >
                {social.platform}
              </a>
            ))}
          </div>
        ) : (
          <span className="text-tx-2">None found</span>
        )}
      </div>
    </div>
  )
}

function WebsiteTab({ lead }) {
  const profile = lead.website_profile
  if (!lead.website) return <Empty>No website on the Google listing.</Empty>
  if (!profile)
    return (
      <Empty>
        {lead.website_domain
          ? 'Not crawled yet.'
          : 'The listed website is a social or marketplace page, not the business’s own site — so there was nothing to crawl.'}
      </Empty>
    )

  return (
    <div className="space-y-3 text-sm">
      <a
        href={lead.website}
        target="_blank"
        rel="noreferrer"
        className="inline-flex items-center gap-1.5 text-brand hover:underline"
      >
        {lead.website_domain || lead.website} <ExternalLink size={13} />
      </a>
      {profile.error && <p className="text-xs text-warn">{profile.error}</p>}
      {profile.legal_entity && <Row label="Operating company">{profile.legal_entity}</Row>}
      {profile.meta_description && (
        <p className="rounded-ctl bg-surface-2 px-3 py-2 text-xs text-tx-2">
          {profile.meta_description}
        </p>
      )}
      <VendorList label="POS" items={profile.pos_vendors} />
      <VendorList label="Loyalty" items={profile.loyalty_vendors} tone="text-warn" />
      <VendorList label="Payments" items={profile.payment_providers} />
      <VendorList label="Delivery" items={profile.delivery_platforms} />
      <VendorList label="Reservations" items={profile.reservation_platforms} />
      <VendorList label="Tech" items={profile.technologies} />
    </div>
  )
}

// The manual path. Automated discovery only reads what a business publishes
// about itself, so anything a rep learns another way lands here — and outranks
// every automated candidate.
function OwnerTab({ lead, canManage }) {
  const [name, setName] = useState('')
  const [role, setRole] = useState('')
  const [note, setNote] = useState('')
  const save = useSetOwner()

  return (
    <div className="space-y-4">
      {lead.owner_name ? (
        <div className="rounded-ctl bg-surface-2 px-3 py-2">
          <p className="flex items-center gap-1.5 text-sm text-tx">
            <User size={13} /> {lead.owner_name}
          </p>
          <p className="mt-0.5 text-xs text-tx-2">
            from {lead.owner_name_source?.replace(/_/g, ' ')} ·{' '}
            <Badge tone={CONFIDENCE_TONES[lead.owner_name_confidence]}>
              {lead.owner_name_confidence} confidence
            </Badge>
          </p>
        </div>
      ) : (
        <p className="rounded-ctl bg-surface-2 px-3 py-2 text-sm text-tx-2">
          No owner name published. Most small businesses here don’t list one — ask on the
          first call, then record it below.
        </p>
      )}

      {lead.owner_candidates?.length > 0 && (
        <div>
          <p className="mb-1.5 text-xs uppercase tracking-wide text-tx-2">All candidates</p>
          <ul className="space-y-1.5">
            {lead.owner_candidates.map((candidate) => (
              <li key={candidate.id} className="rounded-ctl bg-surface-2 px-3 py-2">
                <p className="text-sm text-tx">
                  {candidate.name}
                  {candidate.role && <span className="text-tx-2"> · {candidate.role}</span>}
                </p>
                <p className="text-xs text-tx-2">{candidate.source_display}</p>
                {candidate.evidence_text && (
                  <p className="mt-1 line-clamp-2 text-xs italic text-tx-2">
                    “{candidate.evidence_text}”
                  </p>
                )}
                {candidate.evidence_url && (
                  <a
                    href={candidate.evidence_url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-xs text-brand hover:underline"
                  >
                    Check the source
                  </a>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {canManage && (
        <form
          className="space-y-2 rounded-ctl bg-surface-2 p-3"
          onSubmit={(event) => {
            event.preventDefault()
            save.mutate({ leadId: lead.id, name, role, note }, { onSuccess: () => setName('') })
          }}
        >
          <p className="text-xs font-semibold text-tx">Record an owner you found yourself</p>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Owner name"
            className="w-full rounded-ctl bg-surface px-3 py-2 text-sm text-tx outline-none"
          />
          <input
            value={role}
            onChange={(e) => setRole(e.target.value)}
            placeholder="Role (optional)"
            className="w-full rounded-ctl bg-surface px-3 py-2 text-sm text-tx outline-none"
          />
          <input
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="How you found out (optional)"
            className="w-full rounded-ctl bg-surface px-3 py-2 text-sm text-tx outline-none"
          />
          <button
            type="submit"
            disabled={!name.trim() || save.isPending}
            className="w-full rounded-ctl bg-brand px-3 py-2 text-sm font-semibold text-white disabled:opacity-50"
          >
            Save owner
          </button>
        </form>
      )}
    </div>
  )
}

function VendorList({ label, items, tone = 'text-tx' }) {
  if (!items?.length) return null
  return (
    <Row label={label}>
      <span className={tone}>{items.join(', ')}</span>
    </Row>
  )
}

function Row({ label, children }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-tx-2">{label}</dt>
      <dd className="text-sm text-tx">{children}</dd>
    </div>
  )
}

function Empty({ children }) {
  return <p className="py-6 text-center text-sm text-tx-2">{children}</p>
}
