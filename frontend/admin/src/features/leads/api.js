import { useInfiniteQuery, useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../../lib/api'

// Strip empty filters so a cleared chip sends nothing rather than `?status=`.
// The backend treats an empty value as "no filter" either way; this just keeps
// the query key — and so the cache — from splitting on meaningless differences.
function clean(filters) {
  return Object.fromEntries(
    Object.entries(filters).filter(([, v]) => v !== '' && v != null && v.length !== 0),
  )
}

// Everything a lead write can change, so one invalidation covers the table, the
// cards and the lead itself. Listed in one place because forgetting one is how
// a KPI card ends up disagreeing with the row right under it.
function invalidateLeads(qc) {
  qc.invalidateQueries({ queryKey: ['leads'] })
  qc.invalidateQueries({ queryKey: ['lead-kpis'] })
  qc.invalidateQueries({ queryKey: ['lead'] })
}

// The pipeline, cursor-paginated. `next` is a full URL — we pull the cursor out
// of it for the following page so the table can grow with "Load more".
export function useLeads(filters) {
  const params = clean(filters)
  return useInfiniteQuery({
    queryKey: ['leads', params],
    queryFn: async ({ pageParam }) => {
      const q = pageParam ? { ...params, cursor: pageParam } : params
      return (await api.get('/leads', { params: q })).data
    },
    initialPageParam: null,
    getNextPageParam: (lastPage) =>
      lastPage.next ? new URL(lastPage.next).searchParams.get('cursor') : undefined,
  })
}

// The KPI cards. Takes the same filters as the table so the cards describe the
// slice on screen rather than contradicting it.
export function useLeadKpis(filters) {
  const params = clean(filters)
  return useQuery({
    queryKey: ['lead-kpis', params],
    queryFn: async () => (await api.get('/leads/kpis', { params })).data,
    placeholderData: (prev) => prev, // keep the old numbers while refiltering
  })
}

export function useLead(id) {
  return useQuery({
    queryKey: ['lead', id],
    queryFn: async () => (await api.get(`/leads/${id}`)).data,
    enabled: Boolean(id),
  })
}

export function useCreateLead() {
  const qc = useQueryClient()
  return useMutation({
    // `force` bypasses the duplicate warning — the "Create anyway" button. It is
    // a query-string flag rather than part of the body so it reads as what it
    // is: an instruction to the endpoint, not a field of the lead.
    mutationFn: async ({ force, ...body }) =>
      (await api.post('/leads', force ? { ...body, force: true } : body)).data,
    onSuccess: () => invalidateLeads(qc),
  })
}

export function useUpdateLead() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, ...body }) => (await api.patch(`/leads/${id}`, body)).data,
    onSuccess: () => invalidateLeads(qc),
  })
}

export function useDeleteLead() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id) => (await api.delete(`/leads/${id}`)).data,
    onSuccess: () => invalidateLeads(qc),
  })
}

// Probe for duplicates as the Add Lead form is filled, so a collision surfaces
// while the user is still typing rather than as a 409 after they submit.
export function useDuplicateCheck({ phone, email, business_name }) {
  const params = clean({ phone, email, business_name })
  return useQuery({
    queryKey: ['lead-duplicates', params],
    queryFn: async () => (await api.get('/leads/duplicates', { params })).data,
    enabled: Object.keys(params).length > 0,
  })
}

export function useLogCall() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ leadId, ...body }) => (await api.post(`/leads/${leadId}/calls`, body)).data,
    onSuccess: () => invalidateLeads(qc),
  })
}

// Upload the business logo onto a lead. Carried to Merchant.logo_url at
// conversion, so nobody re-uploads it. Multipart — let the browser set the
// boundary; naming the content-type ourselves omits it and the request fails.
export function useUploadLeadLogo() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ leadId, file }) => {
      const body = new FormData()
      body.append('file', file)
      return (await api.post(`/leads/${leadId}/logo`, body)).data
    },
    onSuccess: () => invalidateLeads(qc),
  })
}

// Convert To Merchant. Creates a real, billable account — the mutation the rest
// of this feature exists to reach.
export function useConvertLead() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ leadId, plan_key }) =>
      (await api.post(`/leads/${leadId}/convert`, { plan_key })).data,
    onSuccess: () => {
      invalidateLeads(qc)
      // A conversion creates a merchant, so the merchant directory is stale too.
      qc.invalidateQueries({ queryKey: ['merchants'] })
    },
  })
}

// A lead's likely duplicates, for the merge picker on its detail page.
export function useLeadDuplicates(leadId) {
  return useQuery({
    queryKey: ['lead-duplicates-of', leadId],
    queryFn: async () => (await api.get(`/leads/${leadId}/duplicates`)).data,
    enabled: Boolean(leadId),
  })
}

// Merge another lead into this one. The lead in the path survives; the absorbed
// one is folded in and deleted.
export function useMergeLead() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ survivorId, absorbedId }) =>
      (await api.post(`/leads/${survivorId}/merge`, { absorbed_id: absorbedId })).data,
    onSuccess: () => invalidateLeads(qc),
  })
}

// Step 1 of import: upload the file, get back columns, a suggested mapping, a
// sample, and how many are already in the pipeline. Writes nothing.
export function useImportPreview() {
  return useMutation({
    mutationFn: async (file) => {
      const body = new FormData()
      body.append('file', file)
      return (await api.post('/leads/import/preview', body)).data
    },
  })
}

// Step 2: upload the same file again with the confirmed mapping. The file is
// re-sent rather than parked server-side — the browser already holds it, and a
// temp file keyed to a session is state to expire and leak.
export function useImportLeads() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ file, mapping, source, assigned_sales, skip_duplicates }) => {
      const body = new FormData()
      body.append('file', file)
      body.append('mapping', JSON.stringify(mapping))
      if (source) body.append('source', source)
      if (assigned_sales) body.append('assigned_sales', assigned_sales)
      body.append('skip_duplicates', skip_duplicates ? 'true' : 'false')
      return (await api.post('/leads/import', body)).data
    },
    onSuccess: () => invalidateLeads(qc),
  })
}

// Who a lead can be assigned to. Note this is /leads/sales-users, not /admins:
// that endpoint gates on ADMINS_MANAGE, which Sales does not hold, so pointing
// the picker at it would 403 for the role that lives in this screen.
export function useSalesUsers() {
  return useQuery({
    queryKey: ['lead-sales-users'],
    queryFn: async () => (await api.get('/leads/sales-users')).data,
    staleTime: 5 * 60 * 1000, // the sales team does not change mid-session
  })
}
