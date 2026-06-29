no# Kasbana Dashboard — Direction C Mockup Plan ("Bold Modern")

## Context

Kasbana's marketing site (`frontend/`) and backend scaffold (1.0 / 1.1) are done. The next deliverable is the merchant-facing **Client Dashboard** — a brand-new React app at `frontend/apps/dashboard`, fully specced in `main/docs/Frontend-dashboard-plan.md` (tokens §3, data shapes §4, API contracts §6, screens §14, build order §17). API source of truth: `contracts/openapi.yaml`.

Before any React is written, we want to **see the look & feel** as a static HTML mockup of the **main dashboard (Overview) screen**, in **both Arabic (RTL) and English (LTR)**. From the three candidate directions, the chosen one is **Direction C — "Bold Modern"**: dark ink sidebar, colored KPI tiles, oversized numbers, high contrast, confident. This plan builds that one mockup to a high-fidelity, browser-openable standard for sign-off on the visual identity. The signed-off tokens then anchor the real React build (separate effort, per spec §17).

## Direction C — visual identity

All on the spec's §3 palette — amber `#E0A23B` (+`d #C6862A`, `bg #FBF1DD`) · ink `#0E1B2A` (+`2 #16293D`, `3 #26405A`) · teal `#1C7C73` (+`bg #DFF0ED`) · clay `#C75D43` (+`bg #FAE7E0`) · paper `#FBF8F3` · line `#E7E1D6` · text `#1F2933`/`#566069`/`#8A949C`. Fonts: Space Grotesk (display), Inter (body), Cairo/Tajawal (Arabic), IBM Plex Mono (numbers).

- **Dark ink sidebar** (`ink`/`ink.2` surface, amber active item, lucide icons), full-height.
- **Colored KPI tiles** — the 4 KPIs as solid color blocks (amber / clay / teal / ink), oversized mono numbers, white/ink text per contrast, delta chips.
- **High contrast, confident:** large Space Grotesk headings, bold section dividers, paper page background with white content cards.
- Wallet-style accent consistent with the brand (amber primary actions, ink text on amber).

## Build — single deliverable

**Output:** `main/docs/mockups/dashboard/direction-c.html` — one self-contained file, opens via `file://`, no build step. (Lives under `main/docs/`, published to the docs branch, never part of the frontend build, safe to delete after selection.)

**Tech (dependency-light, CDN only):**
- Tailwind **Play CDN** with an inline `tailwind.config` defining the §3 token families above.
- Google Fonts: Space Grotesk, Inter, Cairo, Tajawal, IBM Plex Mono.
- `lucide` icons via CDN; the 14-day chart drawn as an inline SVG line/area; QR + logo as placeholder SVGs.
- **AR/EN toggle button** in the topbar that flips `document.documentElement.dir` (`rtl`/`ltr`), swaps the font stack (Cairo ↔ Inter), and swaps a small inline strings map. **Logical utilities only** (`ps/pe/ms/me`, `text-start/end`, `start-0/end-0`) — never `pl/pr/left/right` — so RTL is correct and the file demonstrates the discipline the real app requires (spec §7, §16).

**Screen content** — the Overview screen inside the Shell (spec §9 + §14 "Overview"):
- **Shell:** dark ink `Sidebar` (Overview active, then Cards, Customers, Analytics, Messaging, Locations, Team, Billing, Settings) + `Topbar` (logo + merchant name, **ع/EN toggle**, **trial countdown chip**, account menu).
- **Trial Banner** above content.
- **4 colored KpiTiles:** active customers, stamps this week, rewards redeemed, new joins — each with a deltaPct chip.
- **14-day line chart** with a metric switch (joins / stamps / redemptions).
- **Activity feed:** joins / stamps / redemptions rows with actor + location + relative time.
- **Quick actions:** Share QR, New campaign, View customers.
- **Responsive:** sidebar collapses to a bottom nav under `md`; verify at ~360px and desktop.

## Verification

Open `main/docs/mockups/dashboard/direction-c.html` in a browser:
1. Toggle **EN ↔ AR** — layout mirrors correctly, Arabic uses Cairo, no clipped/overflowing text, icons and chips flip sides.
2. Resize to **~360px** — sidebar becomes bottom nav, KPI tiles stack, chart and feed remain readable; and at **desktop** the full layout shows.
3. Confirm the **Bold Modern** identity reads as intended (dark sidebar, colored KPI blocks, oversized numbers, high contrast) on the on-brand palette.

Success = sign-off on Direction C (or specific tweaks noted). Approved tokens/decisions are then carried into the real `tailwind.config.js` when the React dashboard build begins (spec §17, separate effort).
