# Stampn — Client Dashboard — Full Build Specification

> **This is a complete implementation spec for the merchant-facing Client Dashboard.** It is meant to be handed to an AI coding agent or a developer and built exactly as written. Use the exact names, paths, tokens, routes, and API shapes — do not invent or rename anything. Build in the order in §17. Each screen has acceptance criteria; it's done only when all pass. This document is self-contained — no other file is required. **Scope:** the whole dashboard (every screen). **Out of scope:** the separate Admin Panel and the backend itself (it's consumed via the API contracts in §6).
>
> Product: an Arabic-first (RTL), mobile-responsive React web app where a merchant designs a **stamp card**, distributes it, watches customers + analytics, messages them, manages team & locations, and manages their subscription. v1 = **stamp cards only**; pricing = **14-day trial → Starter / Growth / Chain**.

---

## 1. Stack (exact)

- **React 18** + **Vite 5** (JavaScript), single app at `frontend/apps/dashboard`.
- Routing **react-router-dom 6** · server state **@tanstack/react-query 5** · HTTP **axios** (one instance).
- Forms **react-hook-form 7** + **zod** (`@hookform/resolvers`).
- i18n **react-i18next** + **i18next** (`ar` default, `en`).
- Charts **recharts** · QR **qrcode.react** · icons **lucide-react** · dates **dayjs**.
- Styling **Tailwind CSS 3** with the tokens in §3; RTL via logical utilities + `dir`.
- eslint + prettier.

```bash
npm create vite@latest dashboard -- --template react
npm i react-router-dom @tanstack/react-query axios react-hook-form zod @hookform/resolvers \
      react-i18next i18next recharts qrcode.react lucide-react dayjs
npm i -D tailwindcss postcss autoprefixer && npx tailwindcss init -p
```
Env: `VITE_API_URL` (e.g. `https://staging-api.stampn.app`). API base = `VITE_API_URL + "/api/v1"`.

## 2. Project structure (exact)

```
frontend/apps/dashboard/
  index.html                # loads Google Fonts: Space Grotesk, Inter, Cairo, IBM Plex Mono
  src/
    main.jsx                # providers: QueryClientProvider, BrowserRouter, I18nextProvider, ToastProvider
    App.jsx                 # routes + Shell
    lib/ api.js queryClient.js auth.js i18n.js format.js
    hooks/ usePlan.js useAuth.js useToast.js
    locales/ ar.json en.json
    components/             # design system (§10)
      Button Input Select Textarea Toggle Checkbox Table Modal Drawer Toast Tabs Badge
      KpiTile ColorPicker FileUpload DateRange Stepper EmptyState Skeleton Banner
      UpgradeDrawer QrBlock WalletPreview ChartLine ChartBar ChartDonut
    layout/ Shell.jsx Sidebar.jsx Topbar.jsx RequireAuth.jsx
    features/
      auth/        Login Signup Forgot Reset Invite
      onboarding/  Onboarding
      overview/    Overview
      cards/       CardsList CardDesigner CardDetail EnrollQr
      customers/   CustomersList CustomerProfile
      analytics/   Analytics
      campaigns/   CampaignsList CampaignCompose Automations
      locations/   LocationsList LocationDetail
      team/        Team
      billing/     Billing
      settings/    Settings
```

## 3. Design tokens — `tailwind.config.js`

```js
theme: { extend: {
  colors: {
    ink:   { DEFAULT:'#0E1B2A', 2:'#16293D', 3:'#26405A' },
    amber: { DEFAULT:'#E0A23B', d:'#C6862A', bg:'#FBF1DD' },
    clay:  { DEFAULT:'#C75D43', bg:'#FAE7E0' },
    teal:  { DEFAULT:'#1C7C73', bg:'#DFF0ED' },
    paper:'#FBF8F3', line:'#E7E1D6',
    tx:    { DEFAULT:'#1F2933', 2:'#566069', 3:'#8A949C' },
    success:'#1C7C73', warn:'#C6862A', danger:'#C0392B',
  },
  fontFamily: {
    head:['"Space Grotesk"','sans-serif'], body:['Inter','sans-serif'],
    ar:['Cairo','Tajawal','sans-serif'], mono:['"IBM Plex Mono"','monospace'],
  },
  borderRadius: { card:'12px', ctl:'8px' },
}}
```
Body: bg `paper`/white, text `tx`, font `body` (Arabic → `ar`). Primary action = `amber` (ink text). Spacing 4/8/12/16/24/32.

## 4. Data shapes (objects the API returns)

```jsonc
Merchant      { id, name, slug, status:"trial"|"active"|"suspended", plan, trial_ends_at,
                logo_url, color_bg, color_fg }
Entitlements  { plan, limits:{max_cards,max_locations,max_staff,max_customers},
                features:{ whatsapp:bool, export:bool, api:bool, automations:int,
                           analytics:"basic"|"full" },
                usage:{ cards, locations, staff, customers, whatsapp_used, whatsapp_quota } }
Card          { id, type:"STAMP", name, stamps_required, reward_title, reward_description,
                color_bg, color_fg, logo_url, status:"DRAFT"|"ACTIVE"|"ARCHIVED",
                holders, stamps_issued, rewards_redeemed }
CustomerCard  { id, customer_name, customer_phone, stamp_count, stamps_required,
                wallet_platform:"APPLE"|"GOOGLE"|null, status, birthday, consent_at,
                last_event_at, enrolled_at }
Campaign      { id, channel:"PUSH"|"WHATSAPP"|"BOTH", audience, message, status,
                schedule_at, sent_at, stats:{delivered,opened} }
Automation    { key:"reward_ready"|"expiry"|"birthday"|"winback"|"welcome",
                enabled, channel, timing, template }
Location      { id, name, address, lat, lng, staff_count, stamps_issued }
Staff         { id, name, email, role:"OWNER"|"ADMIN"|"SCANNER", location_id, is_active }
```

## 5. API client (`lib/api.js`)

axios instance, `baseURL = VITE_API_URL + "/api/v1"`. Request interceptor adds `Authorization: Bearer <access>`. Response interceptor: on **401** → call `POST /auth/refresh` once, retry, else `auth.logout()`. Error body shape: `{ error:{ code, message, fields } }` — map `fields` to form fields, `message` to a toast, and special-case `PLAN_LIMIT` → open UpgradeDrawer. All lists may be cursor-paginated `{ next, previous, results }`. All money is **EGP**.

## 6. API endpoint contracts (everything the dashboard calls)

```jsonc
// auth
POST /auth/token     {email,password} -> {access,refresh}
POST /auth/refresh   {refresh} -> {access}
POST /auth/signup    {business_name,owner_name,email,phone,password,consent} -> {access,refresh}
POST /auth/forgot    {email} -> {ok}
POST /auth/reset     {token,password} -> {ok}
GET  /auth/invite/{t} -> {merchant_name,role,email}
POST /auth/invite/{t} {password} -> {access,refresh}
GET  /me             -> {merchant:Merchant, entitlements:Entitlements, staff:{role}}

// cards
GET  /cards          -> {results:[Card]}
POST /cards          {name,stamps_required,reward_title,reward_description,color_bg,color_fg,logo_url,status} -> Card
GET  /cards/{id}     -> Card
PATCH /cards/{id}    {...partial} -> Card
GET  /cards/{id}/stats -> {holders,stamps_issued,rewards_redeemed,completion_rate,apple_count,google_count}
GET  /cards/{id}/qr  -> {join_url,qr_svg,poster_pdf_url}
POST /uploads        (multipart) -> {url}

// customers
GET  /customers?card&status&segment&search&cursor -> {next,results:[CustomerCard]}
GET  /customers/{id} -> CustomerCard
GET  /customers/{id}/timeline -> {results:[{event_type,delta,balance_after,staff_name,location,gps,at}]}
POST /customers/{id}/message {channel,text} -> {ok}
DELETE /customers/{id} -> {ok}
POST /loyalty/stamp  {customer_card_id,delta} -> {stamp_count,stamps_required,reward_ready}
POST /loyalty/redeem {customer_card_id,reward_id} -> {redemption_id,status,stamp_count}

// analytics
GET /analytics/summary -> {enrollments,active_cards,redemptions,apple_count,google_count,repeat_rate}
GET /analytics/timeseries?from&to&metric=joins|stamps|redemptions -> {points:[{date,value}]}
GET /analytics/retention?from&to -> {curve:[{day,retained_pct}],at_risk_count}
GET /analytics/by_location?from&to -> {results:[{location_id,name,stamps,redemptions}]}
GET /activity?limit -> {results:[{type,actor_name,customer_name,location,at}]}

// engage
GET  /campaigns      -> {results:[Campaign]}
POST /campaigns      {channel,audience,message,schedule_at|null} -> Campaign
GET  /segments       -> {results:[{key,label,count}]}
GET  /automations    -> {results:[Automation]}
PATCH /automations/{key} {enabled,channel,timing,template} -> Automation

// locations & team
GET /locations -> {results:[Location]}    POST /locations {name,address,lat,lng} -> Location
PATCH /locations/{id} {...} -> Location    GET /locations/{id}/stats -> {stamps,redemptions,customers}
GET /staff -> {results:[Staff]}    POST /staff/invite {email,role,location_id} -> {ok}
PATCH /staff/{id} {role,location_id,is_active} -> Staff

// billing & settings
GET  /billing -> {plan,trial_ends_at,price_egp,usage,next_renewal,payment_method}
POST /billing/subscribe {plan} -> {checkout_url}
GET  /billing/invoices -> {results:[{id,date,amount_egp,status,pdf_url}]}
POST /billing/cancel {reason} -> {ok}
GET/PATCH /settings/business {name,legal_name,logo_url,color_bg,color_fg,contact,address} -> Merchant
GET/PATCH /settings/account  {language,notifications:{email,whatsapp}} -> {ok}
POST /settings/account/password {current,new} -> {ok}
```

## 7. i18n + RTL (`lib/i18n.js`)

i18next init; `lng` from localStorage `stampn_lang` (default `ar`); resources from `locales/`. **Every visible string is an i18n key — no hardcoded copy.** On language change set `document.documentElement.lang` + `dir` (`ar`→`rtl`, `en`→`ltr`). Use Tailwind logical utilities (`ps/pe/ms/me`, `text-start/end`) only — never `pl/pr/left/right`. `ar.json` is the source of truth; `en.json` mirrors its keys.

## 8. Auth (`lib/auth.js`, `layout/RequireAuth.jsx`)

`access` in memory + `refresh` in `localStorage` (`stampn_refresh`). `login()` → `POST /auth/token` → save → `GET /me` cache merchant+entitlements. `logout()` clears tokens + query cache → `/login`. `RequireAuth` guards protected routes (no session → `/login?next=<path>`). After login: if `merchant.status==="trial"` and onboarding incomplete → `/onboarding`.

## 9. App shell + routing

Routes:
```
public:    /login /signup /forgot /reset/:token /invite/:token
protected (in Shell): /onboarding · / · /cards /cards/new /cards/:id /cards/:id/edit /cards/:id/qr
  /customers /customers/:id · /analytics · /campaigns /campaigns/new /automations
  /locations /locations/:id · /team · /billing · /settings
```
**Shell:** `Sidebar` (Overview, Cards, Customers, Analytics, Messaging, Locations, Team, Billing, Settings — lucide icons) → bottom nav under `md`. `Topbar`: logo+name, language toggle (ع/EN), **trial countdown chip** when `status==="trial"` (from `trial_ends_at`), account menu (settings, logout). Render a trial **Banner** above content when trialing; render a **soft-lock overlay** (data visible, actions disabled, "Choose a plan" CTA) when the trial has expired and plan is still trial.

## 10. Design-system components (`components/`)

All accessible (labels, focus ring, keyboard), RTL-safe, light theme. Required prop contracts:

- **Button** `{variant:'primary'|'secondary'|'ghost'|'danger',size,loading,disabled,iconStart,onClick}` (primary=amber bg/ink text).
- **Input/Textarea/Select** `{label,name,value,onChange,error,hint,required}` (error shown below in danger).
- **Toggle/Checkbox** `{checked,onChange,label}`.
- **Table** `{columns:[{key,label,render?,sortable?}],rows,loading,emptyState,onRowClick,pagination}` (Skeleton rows on load; stacks to cards < md).
- **Modal/Drawer** `{open,onClose,title,children,footer}` (Drawer slides from inline-end, RTL aware).
- **Toast** via `useToast()` → `{success,error,info}`.
- **Tabs** `{tabs,active,onChange}` · **Badge** `{tone,children}` · **KpiTile** `{label,value,deltaPct?,icon}`.
- **ColorPicker** `{value,onChange}` (hex + swatches) · **FileUpload** `{accept,onUploaded(url)}` (posts `/uploads`, preview) · **DateRange** `{value:{from,to},onChange}` · **Stepper** `{steps,current}`.
- **EmptyState** `{icon,title,body,action}` · **Skeleton** `{w,h,rounded}` · **Banner** `{tone,children,action}`.
- **UpgradeDrawer** (opened by gating; current vs next plan, the locked feature, CTA → `/billing`).
- **QrBlock** `{value,size}` (qrcode.react + download PNG/SVG).
- **ChartLine/Bar/Donut** (recharts wrappers, token colors).

## 11. WalletPreview (`components/WalletPreview.jsx`)

Props: `{platform:'APPLE'|'GOOGLE',logoUrl,colorBg,colorFg,merchantName,programName,rewardTitle,stampsRequired,stampCount=0}`. Parent-controlled Apple⇄Google toggle.
- **Apple:** rounded `storeCard` (~340×210), `colorBg` bg / `colorFg` text; top row logo+merchantName; primary field "Stamps {stampCount}/{stampsRequired}"; secondary "Reward: {rewardTitle}"; QR strip at bottom; soft shadow.
- **Google:** loyalty-object style — colored top band with logo+programName; hero balance "{stampCount}/{stampsRequired}"; reward text; barcode block.
- Updates live as props change (used by the Card Designer). Renders LTR + RTL.

## 12. usePlan() + gating (`hooks/usePlan.js`)

Reads `entitlements` from the `/me` query. Returns `{plan, can(feature), limit(key), usage(key), atLimit(key)}`. Gated control pattern: locked control renders with a lock icon and `onClick` opens **UpgradeDrawer** (never hide silently); over-limit create buttons are disabled and open the drawer; server `PLAN_LIMIT` opens the same drawer. Capabilities: `whatsapp`, `export`, `api`, `automations` (int), `analytics` (`basic`/`full`); limits: `max_cards/locations/staff/customers`.

## 13. Global patterns

Loading = Skeleton (lists/cards) or button spinner (actions). Empty = EmptyState + CTA. Error = inline field errors (`error.fields`) + toast (`error.message`) + route-level error boundary. Destructive = confirm Modal. Optimistic updates for toggles + stamp actions (rollback on error). Mobile-first; verify at 360px and desktop.

---

## 14. Screens — full spec

Format: **route · data/API · layout · fields+validation · states · gating · acceptance.**

### Login `/login`
Fields: email, password, remember. Submit → `auth.login`. `UNAUTHENTICATED` → "Wrong email or password". Links: forgot, signup. **Accept:** valid creds → `/` (or `?next`); invalid → inline error; refresh keeps session.

### Signup `/signup`
react-hook-form+zod: business_name, owner_name, email, phone (EG), password (≥8), consent (required, PDPL). Submit → `POST /auth/signup` → save tokens → `/onboarding`. **Accept:** duplicate email = field error; success starts 14-day trial.

### Forgot `/forgot` · Reset `/reset/:token`
Forgot: email → `POST /auth/forgot` → success msg. Reset: password + confirm → `POST /auth/reset` → `/login`. **Accept:** invalid/expired token shows clear message.

### Invite `/invite/:token`
`GET /auth/invite/:token` shows merchant+role; set password → `POST /auth/invite/:token` → logged in. **Accept:** expired token handled.

### Onboarding `/onboarding`
3-step Stepper: (1) branding — logo (FileUpload), color_bg, color_fg → `PATCH /settings/business`; (2) first card — name, stamps_required (1–30), reward_title → `POST /cards` (ACTIVE); (3) done — `QrBlock` from `/cards/:id/qr` + WalletPreview. Skippable/resumable. **Accept:** completing leaves one ACTIVE card + QR; skipping → "Finish setup" tile on Overview.

### Overview `/` · data `/analytics/summary`,`/analytics/timeseries`,`/activity`
Trial Banner (if trialing); KpiTiles (active customers, stamps this week, rewards redeemed, new joins, each deltaPct); 14-day ChartLine (metric switch); activity feed (joins/stamps/redemptions with actor+location+relative time); quick actions (Share QR, New campaign, View customers); "Finish setup" if onboarding incomplete. **Accept:** KPIs/chart/feed render live; deltas vs previous period; fresh-account empty state.

### Cards list `/cards` · data `/cards`
Grid of cards (mini WalletPreview, name, status Badge, holders, stamps_issued). "New card" → `/cards/new`, **disabled at `atLimit('max_cards')`** (UpgradeDrawer). Row actions: open, edit, duplicate, archive (confirm). Empty → "Create your first card". **Accept:** limit opens upgrade drawer; archive confirms.

### Card Designer `/cards/new`, `/cards/:id/edit`
Two-pane: left form, right **live WalletPreview** (Apple⇄Google). Form (rhf+zod): name (required), stamps_required (slider+number 1–30), reward_title (required), reward_description, logo (FileUpload), color_bg (ColorPicker, default merchant brand), color_fg, collect-birthday toggle. Preview updates on every change. Buttons: Save draft (`DRAFT`) / Publish (`ACTIVE`) → `POST /cards` or `PATCH /cards/:id`. Unsaved-changes guard. Editing a published card warns it re-provisions existing holders' passes. **Accept:** preview mirrors the form for both platforms; publish creates/updates an ACTIVE card; validation blocks empties.

### Card detail `/cards/:id` · data `/cards/:id`,`/cards/:id/stats`
WalletPreview; stat KpiTiles (holders, stamps_issued, rewards_redeemed, completion_rate, Apple/Google donut); link to QR; actions edit/duplicate/archive. **Accept:** stats render; actions work.

### Enrollment QR `/cards/:id/qr` · data `/cards/:id/qr`
Big QrBlock (download PNG/SVG), copy join_url, "Download poster" (poster_pdf_url), **WhatsApp share** (`https://wa.me/?text=<msg+url>`), embed snippet. **Accept:** QR → join_url; downloads work; WhatsApp prefilled.

### Customers list `/customers` · data `/customers`
Debounced search; filter chips (card, status, segment lapsed>30d / reward-ready, location); Table `[name,phone,card,stamps X/N,last visit,joined,wallet]` (cursor pagination, row→profile); bulk-select; **Export CSV** (gated by `can('export')`). Empty → "Share your join QR". **Accept:** filters/search/pagination work; export gated on Starter; row opens profile.

### Customer profile `/customers/:id` · data `/customers/:id`,`/customers/:id/timeline`
Header (name, phone, wallet Badge, joined, birthday); stamp progress + reward-ready Badge; **timeline** (enroll, each stamp w/ staff+location+GPS, redemptions, messages); actions: add/remove stamp (`/loyalty/stamp` ±1), mark redeemed (`/loyalty/redeem`), send message (Modal: channel+text → `/customers/:id/message`); Data&privacy: consent + **Delete data** (confirm → `DELETE /customers/:id`). Manual stamp respects cooldown (`COOLDOWN_ACTIVE`→toast). **Accept:** timeline chronological; manual actions update progress optimistically; delete confirms; message sends.

### Analytics `/analytics` · data `/analytics/*`
DateRange + location filter; charts — joins (ChartLine), stamps (ChartBar), redemptions (ChartBar), retention curve (ChartLine), repeat-visit + at-risk (KpiTiles), Apple/Google split (ChartDonut), by-location (ChartBar); Export report. Gating: Starter (`features.analytics==='basic'`) → summary KPIs + joins chart only, rest locked (UpgradeDrawer); export gated. **Accept:** full charts for Growth+; basic view for Starter; filters re-query.

### Campaigns `/campaigns` + compose `/campaigns/new` · data `/campaigns`,`/segments`
List: Table (channel, audience, status, sent_at, delivered/opened). Compose: channel (PUSH/WHATSAPP/BOTH) → audience (`/segments`: all, lapsed, reward-ready, by card/location) → message (textarea AR/EN + preview) → send now/schedule → `POST /campaigns`. Show remaining WhatsApp allowance (`entitlements.usage`); if WhatsApp & `!can('whatsapp')` or quota exhausted → block + UpgradeDrawer. **Accept:** push sends; WhatsApp gating+allowance enforced; scheduled shows scheduled.

### Automations `/automations` · data `/automations`
List of 5 (reward_ready, expiry, birthday, winback, welcome); each a row with Toggle + config (channel, timing, template) → `PATCH /automations/:key`. Gate enabled count by `features.automations`. **Accept:** toggling persists; exceeding allowed count opens UpgradeDrawer.

### Locations `/locations` + detail `/locations/:id` · data `/locations`,`/locations/:id/stats`
List Table `[name,address,staff_count,stamps_issued]`; "Add location" Modal (name, address, lat/lng) → `POST /locations`, **disabled at `atLimit('max_locations')`**. Detail: edit (`PATCH`), map pin, per-location KpiTiles, assigned staff. **Accept:** add gated at limit; edit persists; stats render.

### Team `/team` · data `/staff`
Table `[name,role,location,status]`; "Invite" Modal (email, role, location) → `POST /staff/invite`, **disabled at `atLimit('max_staff')`**. Row: change role/location (`PATCH /staff/:id`), deactivate. Rule: can't remove/deactivate the **last Owner** (disable + tooltip). **Accept:** invite gated; role edits persist; last-Owner protected.

### Billing `/billing` · data `/billing`,`/billing/invoices`
Current plan + **trial countdown**; plan comparison (Starter/Growth/Chain, EGP prices, feature matrix, current highlighted); Upgrade/Downgrade → `POST /billing/subscribe` → redirect `checkout_url`; usage bars vs limits (`entitlements.usage`); payment method; invoices Table (date, amount, status, pdf_url); Cancel (confirm Modal + reason → `/billing/cancel`). Downgrade exceeding new limits warns first. **Accept:** plan + trial correct; subscribe → checkout; usage bars match; invoices download.

### Settings `/settings` (Tabs) · data `/settings/business`,`/settings/account`
- **Business:** name, legal_name, logo, default color_bg/color_fg, contact, address → `PATCH /settings/business`.
- **Branding:** defaults inherited by new cards.
- **Notifications:** owner email/WhatsApp alert toggles → `PATCH /settings/account`.
- **Language:** AR/EN default (writes `stampn_lang` + pref).
- **Data & privacy:** export my data, retention note, request deletion (PDPL).
- **Account:** change password (`/settings/account/password`), sessions/logout, delete account (confirm).
**Accept:** each tab saves + reflects immediately; language toggle flips `dir`.

---

## 15. Plan-gating matrix

| Capability | Trial | Starter | Growth | Chain |
|---|---|---|---|---|
| `max_cards` | all | 1 | 5 | ∞ |
| `max_locations` | all | 1 | 5 | ∞ |
| `max_staff` | all | 3 | 15 | ∞ |
| `max_customers` | full | ~500 | ~5,000 | ∞ |
| wallet push | ✓ | ✓ | ✓ | ✓ |
| `whatsapp` | ✓ | basic | higher | highest |
| `automations` | all | 1–2 | all | all |
| `analytics` | full | basic | full | full |
| `export` | ✓ | — | ✓ | ✓ |
| `api` | — | — | — | ✓ |

Numbers are anchors to confirm with real pricing. Every gated control → lock badge → UpgradeDrawer.

## 16. Quality requirements (apply to every screen)

RTL + Arabic and English both correct · responsive at 360px + desktop · all states (loading/empty/error/gated/over-limit/success) · gating via `usePlan` where specified · all copy via i18n (no hardcoded strings) · no `left/right`/`pl/pr` CSS (logical only) · requests match §6 shapes · keyboard + screen-reader accessible · EGP for all money · lint clean.

## 17. Build order

1. §1–§9 scaffolding (app, structure, tokens, data shapes, API client, i18n/RTL, auth, shell+routing).
2. §10 components → §11 WalletPreview → §12 usePlan.
3. Auth + Onboarding.
4. Cards (list → designer → detail → QR).
5. Overview + Customers (list → profile) + Analytics.
6. Campaigns + Automations.
7. Locations + Team + Billing + Settings.
8. Pass §16 on every screen.

> Build against a mock of §6 first; when the backend is live on staging, set `VITE_API_URL` and re-verify all API-backed screens.
