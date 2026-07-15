# Pricing & plans — the new ladder

> **Status: decided, not implemented.** Written 2026-07-15 on `dev`.
>
> Supersedes the live catalogue (`billing/plans.py`). Nothing here is built yet.
> Blocked on the payment gateway approval (expected within ~2 days), which brings
> **recurring billing** — the thing this whole model depends on.

---

## 1. Where we are today

`billing/plans.py` — the shipped catalogue:

| | Cards | Locations | Staff | Customers | Branding | API | Analytics | Price |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Free | 1 | 1 | 2 | 200 | ✗ | ✗ | basic | 0 |
| Starter | 3 | 2 | 5 | 2,000 | ✗ | ✗ | basic | 299 EGP |
| Growth | 10 | 10 | 25 | 20,000 | ✓ | ✓ | full | 799 EGP |
| Chain | ∞ | ∞ | ∞ | ∞ | ✓ | ✓ | full | custom |

Facts that shape everything below (all verified in the code):

- **The 14-day trial runs at GROWTH level** (`TRIAL_PLAN = PlanTier.GROWTH`). Every
  merchant tastes the middle plan before paying. **This is the single biggest asset
  we have — keep it.** Loss aversion sells Growth without a single trick.
- **`Subscription.plan` defaults to `PlanTier.FREE`** (`billing/models.py:93`). Free
  is not just a pricing column — it is the **floor the billing system falls back to**
  when a trial lapses or a charge fails. Removing it is a code change, not a config one.
- **Logo + brand colours are NOT entitlement-gated.** `color_bg`, `color_fg` and
  `logo_url` live on Card/Merchant and every plan gets them. `custom_branding` only
  gates the *deep* design — pass templates, stamp icons/layout, custom stamp images,
  strip images, and the branded join page. **This is why a paid entry tier is honest:
  a Starter merchant still gets a real, branded Apple/Google pass.**
- **"Powered by Stampn" is mandatory on every plan** and no theme field suppresses it
  (`branding/qr.py::POWERED_BY`, `branding/poster.py`). It is therefore the cheapest
  premium feature we will ever build — see Chain.
- **Prices + limits already live in a DB table an admin can edit without a deploy**
  (`billing.models.Plan`; `PLAN_LIMITS` / `PLAN_PRICES_EGP` are only the seed +
  fallback). So re-pricing needs no deploy. Adding a *new tier* does need a migration.
- **The Paymob gateway has no recurring billing today** — `create_checkout` +
  `verify_and_parse` only, no card tokenisation, and no renewal task in
  `billing/tasks.py`. Unblocking this is the precondition for the model below.

---

## 2. The new ladder

**Free is removed. Starter becomes the entry plan.**

| | **Starter** | **Growth** ⭐ | **Chain** | **Custom** |
| --- | --- | --- | --- | --- |
| | One shop, done right | **Most popular** | Established brands | Enterprise |
| **Monthly** | **599 EGP** | **999 EGP** | **2,499 EGP** | Let's talk |
| **Annual** (2 months free) | 5,990 | **9,990** | 24,990 | — |
| Step up | — | 1.67× | 2.5× | — |

Every price sits under a round number, the middle one is obviously correct, and
there is no moment where growing costs a merchant double.

### Why 999 and not 1,399

999 gives up roughly **30% of ARPU** versus 1,399. It buys three things worth more:

1. **It is under 1,000.** A real psychological wall. "Under a thousand a month" is a
   sentence a café owner repeats to his partner.
2. **It kills the growth cliff.** Second branch used to mean 599 → 1,399 (**+133%**).
   Now it is 599 → 999 (**+67%**) — a shrug instead of a grievance.
3. **It lets us delete complexity.** At 999 we do **not** need per-location add-ons or
   customer overage: "just move to Growth" is the honest answer to every growing
   merchant. Less billing code, fewer edge cases, a simpler pricing page.

**999 is a land-grab price, chosen deliberately.** At this stage adoption beats ARPU:
every Growth merchant embeds their brand, their pass design and their customers in the
system, and that is switching cost. **Plan to raise Growth for *new* signups later**
(1,299 will be easy once there is lock-in) and grandfather the early merchants — "your
price is locked forever" is itself a strong acquisition message.

---

## 3. What each plan gets

| | Starter | Growth ⭐ | Chain | Custom |
| --- | --- | --- | --- | --- |
| Locations | 2 | 10 | ∞ | ∞ |
| Cards | 3 | 10 | ∞ | ∞ |
| Staff | 5 | 25 | ∞ | ∞ |
| Customers | 2,000 | 20,000 | 100,000 | ∞ |
| Apple + Google wallet passes | ✓ | ✓ | ✓ | ✓ |
| **Your logo + brand colours on the pass** | ✓ | ✓ | ✓ | ✓ |
| Enrollment QR + printable poster | ✓ | ✓ | ✓ | ✓ |
| Customer export (CSV) | ✓ | ✓ | ✓ | ✓ |
| Basic analytics | ✓ | — | — | — |
| **Full pass design** (templates, stamp icons/layout, custom stamp + strip images) | ✗ | **✓** | ✓ | ✓ |
| **Branded join page** (theme, cover, fonts, custom copy) | ✗ | **✓** | ✓ | ✓ |
| Full analytics | ✗ | ✓ | ✓ | ✓ |
| Specialised staff roles | ✗ | ✓ | ✓ | ✓ |
| Automations | 1 | 5 | ∞ | ∞ |
| Referral program | ✗ | ✓ | ✓ | ✓ |
| **White-label — no "Powered by Stampn"** | ✗ | ✗ | **✓** | ✓ |
| Custom join-page domain | ✗ | ✗ | ✓ | ✓ |
| Account manager + SLA | ✗ | ✗ | ✓ | ✓ |
| Read-only API | ✗ | ✗ | ✓ | ✓ |
| **Full API + webhooks → your POS/ERP** | ✗ | ✗ | ✗ | **✓** |
| **We build the integration** | ✗ | ✗ | ✗ | **✓** |
| SSO | ✗ | ✗ | ✗ | ✓ |

### The story each tier tells

- **Starter (599)** — *one shop, done properly.* Real Apple/Google passes carrying your
  logo and your colours. A genuine product, not a crippled demo. **It must stay
  credible**: if a small café is happy here forever, that is a win, not a failure.
  Never let Starter become a decoy nobody could rationally pick.
- **Growth (999) — the hero.** *Your brand, everywhere.* Full art-direction of the pass
  and the join page. This is what the trial already gives them, so this is what they
  lose by not upgrading. The card designer already shows the whole design section
  **locked, with an upgrade nudge**, to every Starter merchant — that is the best
  salesman in the product. Do not weaken it.
- **Chain (2,499)** — *for established brands.* Sells **status, not limits**. The pitch
  is removing "Powered by Stampn" from your customers' screens, your own domain, and a
  human who answers the phone. Unlimited is a footnote.
- **Custom** — *integrate Stampn into your system.* Not "an API key": **we connect
  Stampn to your POS/ERP.** Webhooks, two-way sync, and we build the connector. That is
  a project, and it is priced like one. **Never show a number** — a number invites
  comparison; silence signals bespoke.

### The upgrade triggers are honest ones

A merchant moves up when they **open a branch**, **hit a customer ceiling**, or **start
caring how their brand looks**. All three are moments they are *winning*. We grow with
them; we never punish them for growing. That distinction is the difference between an
upgrade they are proud of and one they tell their friends about — badly.

---

## 4. What has to be built

Do not sell any of this before it exists.

| Item | Why | Effort |
| --- | --- | --- |
| **Recurring billing (card-on-file)** | Everything depends on it. Without it, every month is a fresh chance for a merchant to quit. | Blocked on gateway approval |
| **White-label flag** (suppress "Powered by Stampn") | Chain's entire pitch. Currently hard-coded and mandatory. | **Small — do this first** |
| **`CUSTOM` plan tier** | Enum is `FREE/STARTER/GROWTH/CHAIN`. Prices/limits are DB-editable, but a new tier needs a migration. | Small |
| **Locked state to replace Free** | `Subscription.plan` defaults to FREE — it is the fallback floor. See §5. | Medium |
| **Annual billing** | Does not exist at all (single monthly `Decimal`). Cuts churn, pulls cash forward. | Medium |
| **Read-only API gate** (Chain) | `api` is a single bool today. | Small |
| **Webhooks + POS/ERP integration** | Custom's whole reason to exist. | Large |
| Custom domain, SSO, SLA tooling | Chain/Custom promises. | Large |

---

## 5. Open decisions — resolve before implementing

**1. When a merchant stops paying, what do their customers see?**
Real people are carrying wallet passes with stamps on them. **Recommendation: passes
keep working and stamps are preserved. Freeze the merchant's dashboard, never the
customer's card.** Their customers did nothing wrong, and breaking their passes
punishes the people whose trust the product runs on. This is currently decided by
accident (everyone falls back to FREE limits) — decide it deliberately.

**2. API moves from Growth → Chain/Custom.** `api: True` is on Growth today, so this is
a **downgrade for existing Growth merchants** — they need grandfathering.

**3. Existing Free merchants** need a migration path and a notice period. Comms work,
not just SQL.

**4. Per-location pricing for chains — revisit later.** A 20-location chain on Chain
pays ~125 EGP/location while a single café pays 599. Our biggest, happiest customers
are our worst-monetised ones. Not urgent; genuinely where the money is later.

---

## 6. Bottom line

**599 → 999 → 2,499 → Custom.** Prices are fair — Starter is about *six extra coffees a
month*, and that is the pitch. The real competitor is not Loopy Loyalty at $25; it is a
**paper stamp card that costs 200 EGP once**. So sell what paper cannot do: you learn
who your customers are, you can reach them, you can see the data, and they cannot lose
the card.

The ladder is designed so the middle plan is the obvious one, the top plan sells status,
and Custom sells integration. But the highest-leverage item on this page is not a price
— it is **recurring billing**. Everything else is downstream of it.
