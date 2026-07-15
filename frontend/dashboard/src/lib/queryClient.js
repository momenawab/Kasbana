import { QueryClient, QueryCache, MutationCache } from '@tanstack/react-query'
import * as Sentry from '@sentry/react'

// Report query/mutation failures to Sentry (Phase 3). captureException is a safe
// no-op when Sentry.init never ran (no VITE_SENTRY_DSN), so dev/mocks stay silent.
// Expected-and-handled failures (401 refresh, PLAN_LIMIT → UpgradeDrawer) are
// dropped so the noise floor stays low; everything else is a real bug worth an issue.
function reportQueryError(error) {
  const status = error?.response?.status
  const code = error?.response?.data?.error?.code
  if (status === 401 || code === 'PLAN_LIMIT') return
  Sentry.captureException(error)
}

export const queryClient = new QueryClient({
  queryCache: new QueryCache({ onError: reportQueryError }),
  mutationCache: new MutationCache({ onError: reportQueryError }),
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false, staleTime: 30_000 },
  },
})
