import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api from '../../lib/api'
import { TERMINAL_STATUSES } from './constants'

// Strip empty filters so a cleared chip sends nothing rather than `?state=`,
// and so the query key — and the cache — does not split on meaningless
// differences. Same reasoning as features/leads/api.js.
function clean(filters) {
  return Object.fromEntries(
    Object.entries(filters).filter(([, v]) => v !== '' && v != null && v.length !== 0),
  )
}

function cursorOf(next) {
  return next ? new URL(next).searchParams.get('cursor') : undefined
}

// A running job's counters change every few seconds, and the operator is
// watching them. Polling only while something is unfinished keeps an idle
// screen quiet rather than hammering the API all day.
function pollWhileRunning(query) {
  const pages = query.state.data?.pages ?? []
  const jobs = pages.flatMap((page) => page.results ?? [])
  const busy = jobs.some((job) => !TERMINAL_STATUSES.includes(job.status))
  return busy ? 4000 : false
}

export function useJobs(filters = {}) {
  const params = clean(filters)
  return useInfiniteQuery({
    queryKey: ['leadgen-jobs', params],
    queryFn: async ({ pageParam }) =>
      (await api.get('/leadgen/jobs', { params: pageParam ? { ...params, cursor: pageParam } : params }))
        .data,
    initialPageParam: null,
    getNextPageParam: (last) => cursorOf(last.next),
    refetchInterval: pollWhileRunning,
  })
}

export function useJob(jobId) {
  return useQuery({
    queryKey: ['leadgen-job', jobId],
    enabled: !!jobId,
    queryFn: async () => (await api.get(`/leadgen/jobs/${jobId}`)).data,
    refetchInterval: (query) =>
      query.state.data && !TERMINAL_STATUSES.includes(query.state.data.status) ? 3000 : false,
  })
}

export function useJobLogs(jobId, level = '') {
  return useQuery({
    queryKey: ['leadgen-job-logs', jobId, level],
    enabled: !!jobId,
    queryFn: async () =>
      (await api.get(`/leadgen/jobs/${jobId}/logs`, { params: clean({ level }) })).data,
    refetchInterval: 8000,
  })
}

// Everything a job or import can change. Listed once because forgetting one is
// how a progress bar ends up disagreeing with the table under it.
function invalidateAll(qc) {
  qc.invalidateQueries({ queryKey: ['leadgen-jobs'] })
  qc.invalidateQueries({ queryKey: ['leadgen-job'] })
  qc.invalidateQueries({ queryKey: ['leadgen-leads'] })
  qc.invalidateQueries({ queryKey: ['leadgen-lead'] })
}

export function useCreateJob() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (payload) => (await api.post('/leadgen/jobs', payload)).data,
    onSuccess: () => invalidateAll(qc),
  })
}

export function useJobAction() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ jobId, action }) =>
      (await api.post(`/leadgen/jobs/${jobId}/${action}`, {})).data,
    onSuccess: () => invalidateAll(qc),
  })
}

export function useGeneratedLeads(filters = {}) {
  const params = clean(filters)
  return useInfiniteQuery({
    queryKey: ['leadgen-leads', params],
    queryFn: async ({ pageParam }) =>
      (await api.get('/leadgen/leads', { params: pageParam ? { ...params, cursor: pageParam } : params }))
        .data,
    initialPageParam: null,
    getNextPageParam: (last) => cursorOf(last.next),
  })
}

export function useGeneratedLead(leadId) {
  return useQuery({
    queryKey: ['leadgen-lead', leadId],
    enabled: !!leadId,
    queryFn: async () => (await api.get(`/leadgen/leads/${leadId}`)).data,
  })
}

export function useSetOwner() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ leadId, ...body }) =>
      (await api.post(`/leadgen/leads/${leadId}/owner`, body)).data,
    onSuccess: () => invalidateAll(qc),
  })
}

export function useImportLeads() {
  const qc = useQueryClient()
  return useMutation({
    // A partial import answers 201 with a `skipped` list, a fully blocked one
    // answers 409 with the same shape. Both are useful outcomes rather than
    // errors, so the 409 body is unwrapped here instead of thrown — the caller
    // shows the same "what happened" panel either way.
    mutationFn: async (payload) => {
      try {
        return (await api.post('/leadgen/leads/import', payload)).data
      } catch (err) {
        if (err?.response?.status === 409 && err.response.data?.skipped) {
          return err.response.data
        }
        throw err
      }
    },
    onSuccess: () => invalidateAll(qc),
  })
}
