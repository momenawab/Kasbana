import { useInfiniteQuery } from '@tanstack/react-query'
import api from '../../lib/api'

// Strip empty filter values so we don't send `?actor=` etc.
function clean(filters) {
  return Object.fromEntries(Object.entries(filters).filter(([, v]) => v !== '' && v != null))
}

// The audit trail, cursor-paginated. `next` is a full URL — we pull the cursor
// out of it for the following page so the list can grow with "Load more".
export function useAudit(filters) {
  const params = clean(filters)
  return useInfiniteQuery({
    queryKey: ['audit', params],
    queryFn: async ({ pageParam }) => {
      const q = pageParam ? { ...params, cursor: pageParam } : params
      return (await api.get('/audit', { params: q })).data
    },
    initialPageParam: null,
    getNextPageParam: (lastPage) => {
      if (!lastPage.next) return undefined
      return new URL(lastPage.next).searchParams.get('cursor')
    },
  })
}

// CSV export of the filtered trail — authenticated blob download (a plain
// <a href> would miss the bearer token), mirroring the revenue export.
export async function downloadAuditCsv(filters) {
  const res = await api.get('/audit/export', { params: clean(filters), responseType: 'blob' })
  const url = URL.createObjectURL(res.data)
  const a = document.createElement('a')
  a.href = url
  a.download = 'audit_log.csv'
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
