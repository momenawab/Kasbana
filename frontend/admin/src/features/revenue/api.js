import { useQuery } from '@tanstack/react-query'
import api from '../../lib/api'

export function useRevenue(params) {
  return useQuery({
    queryKey: ['revenue', params],
    queryFn: async () => (await api.get('/analytics/revenue', { params })).data,
    keepPreviousData: true,
  })
}

// CSV export is an authenticated GET returning a file — fetch it as a blob
// through the api client (so the bearer token is attached), then trigger a
// browser download. A plain <a href> would miss the auth header.
export async function downloadRevenueCsv(params) {
  const res = await api.get('/analytics/revenue/export', { params, responseType: 'blob' })
  const url = URL.createObjectURL(res.data)
  const a = document.createElement('a')
  a.href = url
  const from = params?.from || 'start'
  const to = params?.to || 'today'
  a.download = `revenue_${from}_${to}.csv`
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
