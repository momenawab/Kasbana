// The leads table's columns, in table order.
//
// Lives apart from LeadsTable.jsx so both the table and the column picker can
// import it without a component file exporting non-components (which breaks
// fast refresh).
//
// `sort` is the API's sort key — a column without one is not sortable, which is
// the honest signal for a field the backend has no ordering for.
//
// `default: false` starts hidden. There are fifteen columns' worth of data
// here; showing all of them at once makes the first screen unreadable, so the
// ones that answer "who do I call next" are on and the rest are one click away.
export const COLUMNS = [
  { key: 'business', label: 'Business', sort: 'business_name', always: true },
  { key: 'owner', label: 'Owner', sort: 'name' },
  { key: 'phone', label: 'Phone' },
  { key: 'area', label: 'Area', sort: 'area', default: false },
  { key: 'category', label: 'Category', default: false },
  { key: 'assigned_sales', label: 'Assigned' },
  { key: 'priority', label: 'Priority', sort: 'priority' },
  { key: 'status', label: 'Status', sort: 'status' },
  { key: 'temperature', label: 'Temp', sort: 'temperature', default: false },
  { key: 'lead_score', label: 'Score', sort: 'lead_score' },
  { key: 'lead_type', label: 'Type', sort: 'lead_type', default: false },
  { key: 'source', label: 'Source', sort: 'source', default: false },
  { key: 'next_follow_up_at', label: 'Next follow-up', sort: 'next_follow_up_at' },
  { key: 'last_activity', label: 'Last activity', default: false },
  { key: 'created_at', label: 'Created', sort: 'created_at' },
]

export const DEFAULT_VISIBLE = COLUMNS.filter((c) => c.default !== false).map((c) => c.key)
