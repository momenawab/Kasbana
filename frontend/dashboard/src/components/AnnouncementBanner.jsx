import { Megaphone, X } from 'lucide-react'
import { useAnnouncements, useMarkAnnouncementRead } from '../hooks/useAnnouncements'

// Shows the most recent UNREAD platform announcement as a dismissible banner.
// Dismiss = mark read (feeds the admin open-rate stat).
export default function AnnouncementBanner() {
  const { data } = useAnnouncements()
  const markRead = useMarkAnnouncementRead()

  const unread = (data ?? []).filter((a) => !a.read)
  if (unread.length === 0) return null
  const a = unread[0]

  return (
    <div className="flex items-start justify-between gap-3 bg-brand/10 px-4 py-2 text-sm text-tx">
      <div className="flex items-start gap-2">
        <Megaphone size={16} className="mt-0.5 shrink-0 text-brand" />
        <div>
          <span className="font-semibold">{a.title}</span>{' '}
          <span className="text-tx-2">{a.body}</span>
        </div>
      </div>
      <button
        onClick={() => markRead.mutate(a.id)}
        aria-label="Dismiss"
        className="shrink-0 rounded-ctl p-1 text-tx-2 hover:bg-brand/20 hover:text-tx"
      >
        <X size={16} />
      </button>
    </div>
  )
}
