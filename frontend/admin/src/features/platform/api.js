import { useQuery } from '@tanstack/react-query'
import api from '../../lib/api'

export function usePlatformAnalytics() {
  return useQuery({
    queryKey: ['platform-analytics'],
    queryFn: async () => (await api.get('/analytics/platform')).data,
  })
}
