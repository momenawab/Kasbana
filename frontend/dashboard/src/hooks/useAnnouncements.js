// In-app platform announcements (Phase 10). The admin console broadcasts to a
// merchant segment; the dashboard shows unread ones as a dismissible banner and
// marks them read (which feeds the admin open-rate stat).
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../lib/api'
import { hasSession } from '../lib/auth'

export function useAnnouncements() {
  return useQuery({
    queryKey: ['announcements'],
    queryFn: async () => (await api.get('/announcements')).data,
    enabled: hasSession(),
  })
}

export function useMarkAnnouncementRead() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id) => api.post(`/announcements/${id}/read`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['announcements'] }),
  })
}
