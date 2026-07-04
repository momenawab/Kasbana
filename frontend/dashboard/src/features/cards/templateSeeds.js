// Template → card-flow mapping, kept separate from the picker component so the
// component file only exports a component (React Fast Refresh requirement).
//
// The backend /cards API is loyalty-only (STAMP/POINTS), so every template
// creates a real loyalty card seeded with that template's look. The eight pass
// styles differ visually (colors + the pass layout shown in the picker preview);
// they are not distinct backend pass types (no boarding/gift/event schema
// exists). Each seed sets the card type + solid brand colors matching the
// template's gallery theme; the merchant fills in name / reward / stamps next.
export const TEMPLATE_SEED = {
  loyalty: { type: 'STAMP', color_bg: '#C4211C', color_fg: '#FFFFFF', stamps_required: 5 },
  event: { type: 'STAMP', color_bg: '#1A1A1F', color_fg: '#FFFFFF', stamps_required: 8 },
  boarding: { type: 'STAMP', color_bg: '#F4CE2E', color_fg: '#3A2E00', stamps_required: 8 },
  membership: { type: 'STAMP', color_bg: '#3B2716', color_fg: '#FFFFFF', stamps_required: 8 },
  coupon: { type: 'STAMP', color_bg: '#EF6C00', color_fg: '#FFFFFF', stamps_required: 5 },
  giftcard: { type: 'STAMP', color_bg: '#5B1E66', color_fg: '#FFFFFF', stamps_required: 8 },
  invitation: { type: 'STAMP', color_bg: '#F4CE2E', color_fg: '#3A2E00', stamps_required: 8 },
  special: { type: 'STAMP', color_bg: '#C60E66', color_fg: '#FFFFFF', stamps_required: 8 },
}

// Every template can now be chosen and creates a real loyalty card.
export const PUBLISHABLE = new Set(Object.keys(TEMPLATE_SEED))
