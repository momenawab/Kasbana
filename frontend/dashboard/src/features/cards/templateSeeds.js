// Template → card-flow mapping, kept separate from the picker component so the
// component file only exports a component (React Fast Refresh requirement).

// Templates that can actually be created/published today. The /cards API is
// STAMP/POINTS only, so the other seven pass types are preview-only for now.
export const PUBLISHABLE = new Set(['loyalty'])

// Partial card-form seed applied when a publishable template is chosen. Only
// visual/structural defaults — the merchant supplies the real content next.
export const TEMPLATE_SEED = {
  loyalty: { type: 'STAMP', color_bg: '#C4211C', color_fg: '#FFFFFF', stamps_required: 5 },
}
