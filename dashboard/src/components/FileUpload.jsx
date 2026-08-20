import { useState } from 'react'
import { UploadCloud } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import api, { normalizeError } from '../lib/api'
import { useToast } from '../hooks/useToast'

// FileUpload (spec §10) — POSTs to /uploads, returns {url}, calls onUploaded.
// `initial` seeds the preview with an already-saved image (e.g. the current
// logo) so the control reflects saved state instead of always looking empty.
export default function FileUpload({ accept = 'image/*', onUploaded, label, initial = null }) {
  const { t } = useTranslation()
  const toast = useToast()
  const [busy, setBusy] = useState(false)
  const [preview, setPreview] = useState(initial)

  async function handle(e) {
    const file = e.target.files?.[0]
    if (!file) return
    setBusy(true)
    const form = new FormData()
    form.append('file', file)
    try {
      const { data } = await api.post('/uploads', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setPreview(data.url)
      onUploaded?.(data.url)
    } catch (err) {
      toast.error(normalizeError(err).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      {label && <span className="mb-1 block text-sm text-tx-2">{label}</span>}
      <label className="flex cursor-pointer items-center gap-3 rounded-ctl border border-dashed border-line bg-surface p-3 hover:border-violet">
        {preview ? (
          <img src={preview} alt="" className="h-12 w-12 rounded-ctl object-cover" />
        ) : (
          <span className="flex h-12 w-12 items-center justify-center rounded-ctl bg-paper text-tx-3">
            <UploadCloud size={20} />
          </span>
        )}
        <span className="text-sm text-tx-2">
          {busy ? t('common.loading') : t('common.upload', 'Upload an image')}
        </span>
        <input type="file" accept={accept} onChange={handle} disabled={busy} className="hidden" />
      </label>
    </div>
  )
}
