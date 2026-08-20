// Shared vocabulary for the Lead Generation screens.
//
// Mirrors leadgen/enums.py. Duplicated rather than fetched: these are a fixed
// code-level vocabulary, not admin-configurable like the CRM's dropdowns, so a
// round-trip would buy nothing and cost a loading state on every screen.

export const BUSINESS_TYPES = [
  { value: 'cafe', label: 'Cafe' },
  { value: 'coffee_shop', label: 'Coffee Shop' },
  { value: 'restaurant', label: 'Restaurant' },
  { value: 'bakery', label: 'Bakery' },
  { value: 'dessert', label: 'Dessert' },
  { value: 'pizza', label: 'Pizza' },
  { value: 'fast_food', label: 'Fast Food' },
  { value: 'gym', label: 'Gym' },
  { value: 'salon', label: 'Salon' },
  { value: 'retail', label: 'Retail' },
  { value: 'hotel', label: 'Hotel' },
  { value: 'hospital', label: 'Hospital' },
]

export const MAX_RESULTS = [25, 50, 100, 250, 500, 1000]

export const PRIORITIES = [
  { value: 'normal', label: 'Normal' },
  { value: 'high', label: 'High' },
  { value: 'background', label: 'Background' },
]

// Job status → Badge tone. Running is "info" rather than "success": it is not
// done yet, and a green pill on a half-finished job reads as finished.
export const JOB_TONES = {
  queued: 'neutral',
  running: 'info',
  paused: 'warn',
  completed: 'success',
  failed: 'danger',
  cancelled: 'neutral',
}

export const TERMINAL_STATUSES = ['completed', 'failed', 'cancelled']

export const SCORE_TONES = {
  hot: 'danger', // hot = red, the way a heat scale reads
  warm: 'warn',
  cold: 'info',
  ignore: 'neutral',
}

export const LEAD_STATES = [
  { value: 'discovered', label: 'Discovered' },
  { value: 'enriching', label: 'Enriching' },
  { value: 'ready', label: 'Ready for CRM' },
  { value: 'imported', label: 'Imported' },
  { value: 'duplicate', label: 'Duplicate' },
  { value: 'rejected', label: 'Rejected' },
  { value: 'failed', label: 'Failed' },
]

export const SCORE_LABELS = [
  { value: 'hot', label: 'Hot' },
  { value: 'warm', label: 'Warm' },
  { value: 'cold', label: 'Cold' },
  { value: 'ignore', label: 'Ignore' },
]

export const CONFIDENCE_TONES = { high: 'success', medium: 'warn', low: 'neutral' }

// Which stage of the pipeline a job is in, for the progress caption.
export const STAGE_LABELS = {
  discovery: 'Searching Google Places',
  deduplication: 'Removing duplicates',
  website_crawl: 'Crawling websites',
  owner_resolution: 'Resolving owners',
  scoring: 'Scoring leads',
  crm_match: 'Checking against CRM',
}

export function typeLabel(value) {
  return BUSINESS_TYPES.find((t) => t.value === value)?.label || value
}
