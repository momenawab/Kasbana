import { useRef, useState } from 'react'
import { ImagePlus, Loader2 } from 'lucide-react'
import { useUploadLeadLogo } from './api'
import { normalizeError } from '../../lib/api'

// The lead's business logo. Sales grabs it off the shop's Instagram or website
// while qualifying, and conversion carries it onto the merchant — so the
// merchant never gets asked for something we already had.
//
// `accept` mirrors the server's allowlist (common/uploads.py). It is a
// convenience that filters the file picker, not a check: the server's is the
// one that counts, and it re-validates the type against the extension.
const ACCEPT = 'image/jpeg,image/png,image/webp'

export default function LeadLogo({ lead, canManage }) {
  const input = useRef(null)
  const [err, setErr] = useState('')
  const upload = useUploadLeadLogo()

  async function pick(e) {
    const file = e.target.files?.[0]
    if (!file) return
    setErr('')
    try {
      await upload.mutateAsync({ leadId: lead.id, file })
    } catch (e2) {
      setErr(normalizeError(e2).message)
    } finally {
      // Clear the input so picking the same file twice still fires onChange.
      e.target.value = ''
    }
  }

  return (
    <div>
      <div className="flex items-center gap-3">
        <div className="flex h-14 w-14 shrink-0 items-center justify-center overflow-hidden rounded-ctl border border-line bg-bg">
          {lead.logo_url ? (
            <img src={lead.logo_url} alt="" className="h-full w-full object-contain" />
          ) : (
            <ImagePlus size={18} className="text-tx-3" />
          )}
        </div>

        {canManage && (
          <div>
            <button
              type="button"
              onClick={() => input.current?.click()}
              disabled={upload.isPending}
              className="flex items-center gap-2 rounded-ctl border border-line px-3 py-1.5 text-xs text-tx-2 hover:border-brand hover:text-brand disabled:opacity-50"
            >
              {upload.isPending && <Loader2 size={12} className="animate-spin" />}
              {lead.logo_url ? 'Replace logo' : 'Upload logo'}
            </button>
            <div className="mt-1 text-xs text-tx-3">JPG, PNG or WebP · max 5 MB</div>
          </div>
        )}
      </div>

      <input
        ref={input}
        type="file"
        accept={ACCEPT}
        onChange={pick}
        className="hidden"
        aria-label="Upload business logo"
      />
      {err && <div className="mt-2 text-xs text-danger">{err}</div>}
    </div>
  )
}
