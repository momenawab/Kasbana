// The CRM vocabulary, as the console sees it.
//
// Every dropdown, badge and colour on these screens resolves through here, and
// here reads from GET /crm/choices — the rows an admin edits in Settings → CRM
// Configuration. Nothing in this feature hardcodes a status list: relabel
// "Hot Lead" to "Chase Now" in settings and it changes everywhere at once.
//
// What is NOT here: any logic keyed off a particular slug. The backend owns
// that (scoring, conversion, the KPI counts), precisely so an admin adding a
// status cannot break it.
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../../lib/api'

export const KIND = {
  STATUS: 'status',
  PRIORITY: 'priority',
  TEMPERATURE: 'temperature',
  SOURCE: 'source',
  CATEGORY: 'category',
  EXPECTED_PLAN: 'expected_plan',
  CONTACT_METHOD: 'contact_method',
  NEXT_ACTION: 'next_action',
}

// Lead type is the one dropdown with no CrmChoice behind it: it is not
// configurable — a lead came from the website or it did not.
export const LEAD_TYPES = [
  { slug: 'website', label: 'Website' },
  { slug: 'manual', label: 'Manual' },
]

export function useCrmChoices() {
  return useQuery({
    queryKey: ['crm-choices'],
    queryFn: async () => (await api.get('/crm/choices')).data,
    staleTime: 5 * 60 * 1000,
    // Group once here rather than filtering the flat list in every picker.
    select: (rows) => {
      const byKind = {}
      for (const row of rows) (byKind[row.kind] ||= []).push(row)
      return byKind
    },
  })
}

// Settings → CRM Configuration reads the retired rows too: the pickers only
// want what can still be chosen, but the settings screen has to show what has
// been switched off, or there is no way to switch it back on.
export function useAllCrmChoices() {
  return useQuery({
    queryKey: ['crm-choices', 'all'],
    queryFn: async () => (await api.get('/crm/choices', { params: { include_inactive: '1' } })).data,
    select: (rows) => {
      const byKind = {}
      for (const row of rows) (byKind[row.kind] ||= []).push(row)
      return byKind
    },
  })
}

// One invalidation for both views — the settings screen writes, every picker in
// the CRM reads, and they must not disagree about what exists.
function invalidateChoices(qc) {
  qc.invalidateQueries({ queryKey: ['crm-choices'] })
}

export function useCreateCrmChoice() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body) => (await api.post('/crm/choices', body)).data,
    onSuccess: () => invalidateChoices(qc),
  })
}

export function useUpdateCrmChoice() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, ...patch }) => (await api.patch(`/crm/choices/${id}`, patch)).data,
    onSuccess: () => invalidateChoices(qc),
  })
}

export function useDeleteCrmChoice() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id) => (await api.delete(`/crm/choices/${id}`)).data,
    onSuccess: () => invalidateChoices(qc),
  })
}

// A slug's configured label, falling back to a de-slugged version of itself.
// The fallback matters: a lead can hold a value whose choice row was
// deactivated, and history must stay readable rather than render blank.
export function labelFor(choices, kind, slug) {
  if (!slug) return '—'
  const hit = choices?.[kind]?.find((c) => c.slug === slug)
  return hit?.label ?? titleCase(slug)
}

export function colorFor(choices, kind, slug) {
  return choices?.[kind]?.find((c) => c.slug === slug)?.color || ''
}

export function optionsFor(choices, kind) {
  return choices?.[kind] ?? []
}

export function titleCase(slug = '') {
  return String(slug)
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

// A new custom choice's slug, derived from its label rather than typed.
//
// The slug is what the database and every lead store, and the server refuses to
// re-slug a row afterwards — so a typo here would be permanent. Deriving it
// removes the chance to make one.
//
// Shape matches Django's SlugField and the built-in slugs in console/crm.py:
// lowercase, words joined by underscores. Accents are stripped via NFD so
// "Café" becomes "cafe" (matching the seeded category) rather than "caf".
export function slugify(label = '') {
  return String(label)
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '') // combining diacritical marks
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_|_$/g, '')
}

// Lead score → the bar's colour. Thresholds, not the score's own meaning: the
// backend decides what a score *is*, this only decides when it looks urgent.
export function scoreTone(score) {
  if (score >= 70) return { bar: 'bg-success', text: 'text-success' }
  if (score >= 40) return { bar: 'bg-warn', text: 'text-warn' }
  return { bar: 'bg-tx-3', text: 'text-tx-3' }
}

// Temperature and priority read as colour more than text in a dense table.
export const TEMPERATURE_TONE = { hot: 'danger', warm: 'warn', cold: 'info' }
export const PRIORITY_TONE = { high: 'danger', medium: 'warn', low: 'neutral' }
