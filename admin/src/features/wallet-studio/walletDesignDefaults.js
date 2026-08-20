// The empty wallet-design shape — every field the editor manages, at its
// "unset" value, so a card with no saved design edits the same object as one
// with. Blank/empty means "the backend decides" (wallets/design.py).
//
// Kept out of WalletDesignEditor.jsx because a file exporting both a component
// and a constant breaks React Fast Refresh
// (react-refresh/only-export-components). CardDesigner seeds new cards from it.
export const DEFAULTS = {
  label_color: '',
  apple_logo_text: '',
  apple_header: [],
  apple_primary: [],
  apple_secondary: [],
  apple_auxiliary: [],
  apple_back: [],
  apple_strip_enabled: true,
  strip_bg_color: '',
  strip_empty_url: '',
  strip_filled_url: '',
  stamp_icon: '',
  stamp_color: '',
  stamp_layout: '',
  google_title: '',
  google_subtitle: '',
  google_rows: [],
  google_stamp_hero: false,
  template_key: '',
  bottom_image_url: '',
  strip_bg_image_url: '',
  strip_stamps_visible: true,
}
