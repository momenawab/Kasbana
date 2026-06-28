# Graph Report - .  (2026-06-28)

## Corpus Check
- Corpus is ~11,957 words - fits in a single context window. You may not need a graph.

## Summary
- 120 nodes · 164 edges · 13 communities (9 shown, 4 thin omitted)
- Extraction: 90% EXTRACTED · 10% INFERRED · 0% AMBIGUOUS · INFERRED: 16 edges (avg confidence: 0.83)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_React UI Components & i18n|React UI Components & i18n]]
- [[_COMMUNITY_Architecture & Deploy Pipeline|Architecture & Deploy Pipeline]]
- [[_COMMUNITY_Backend Loyalty & Wallet Plan|Backend Loyalty & Wallet Plan]]
- [[_COMMUNITY_Frontend Package Manifest|Frontend Package Manifest]]
- [[_COMMUNITY_Brand Identity & Favicon|Brand Identity & Favicon]]
- [[_COMMUNITY_Django Settings|Django Settings]]
- [[_COMMUNITY_Django URL Routing|Django URL Routing]]
- [[_COMMUNITY_Vercel Config|Vercel Config]]
- [[_COMMUNITY_ASGI Entrypoint|ASGI Entrypoint]]
- [[_COMMUNITY_WSGI Entrypoint|WSGI Entrypoint]]

## God Nodes (most connected - your core abstractions)
1. `useLang()` - 15 edges
2. `Walaa Backend Plan & Variable Contract` - 9 edges
3. `PAGE_PATHS` - 6 edges
4. `Kasbana Django Backend API` - 6 edges
5. `Kasbana Vite+React Frontend` - 6 edges
6. `Kasbana Favicon (SVG)` - 6 edges
7. `distribute.yml CI Workflow` - 5 edges
8. `Kasbana Architecture Doc` - 5 edges
9. `Backend Work Brief — Momen` - 5 edges
10. `scripts` - 4 edges

## Surprising Connections (you probably didn't know these)
- `Dev Branch Fan-out Distribution` --semantically_similar_to--> `App Ownership = Conflict Avoidance`  [INFERRED] [semantically similar]
  .github/workflows/distribute.yml → main/docs/Walaa_Backend_Plan_and_Contract.md
- `Kasbana Full Project Plan (PDF)` --references--> `Kasbana Loyalty Platform`  [INFERRED]
  main/docs/Kasbana_Full_Project_Plan.pdf → README.md
- `Shared Data Model (Merchant…WalletRegistration)` --conceptually_related_to--> `Kasbana Django Backend API`  [INFERRED]
  main/docs/Walaa_Backend_Plan_and_Contract.md → backend/README.md
- `Walaa Backend Plan & Contract (PDF)` --references--> `Walaa Backend Plan & Variable Contract`  [INFERRED]
  main/docs/Walaa_Backend_Plan_and_Contract.pdf → main/docs/Walaa_Backend_Plan_and_Contract.md
- `CI/CD Distribution Pipeline` --references--> `distribute.yml CI Workflow`  [EXTRACTED]
  main/docs/ARCHITECTURE.md → .github/workflows/distribute.yml

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Frozen-Contract Parallel Backend Development** — docs_walaa_backend_plan_and_contract_variable_contract, docs_walaa_backend_plan_and_contract_core_ledger, docs_kasbana_backend_brief_momen_brief, docs_kasbana_backend_brief_joe_brief, docs_walaa_backend_plan_and_contract_parallel_merge [INFERRED 0.85]
- **dev Branch Distribution to Deployment** — readme_dev_branch_sot, workflows_distribute_workflow, readme_branch_map, readme_hostinger_deploy [INFERRED 0.85]
- **Enrollment-Stamp-Wallet Loyalty Flow** — docs_kasbana_backend_brief_momen_enrollment_wallets, docs_kasbana_backend_brief_joe_loyalty_engine, docs_walaa_backend_plan_and_contract_wallets_facade, readme_wallet_loyalty [INFERRED 0.75]

## Communities (13 total, 4 thin omitted)

### Community 0 - "React UI Components & i18n"
Cohesion: 0.17
Nodes (14): Footer(), Header(), Seo(), LangContext, LANGS, localizePath(), PAGE_PATHS, translations (+6 more)

### Community 1 - "Architecture & Deploy Pipeline"
Cohesion: 0.09
Nodes (26): Kasbana Django Backend API, Environment-driven Django Settings, /api/health Endpoint, Backend Python Dependencies, CI/CD Distribution Pipeline, frontend/src/config.js (domain/contact), Kasbana Architecture Doc, Kasbana Full Project Plan (PDF) (+18 more)

### Community 2 - "Backend Loyalty & Wallet Plan"
Cohesion: 0.14
Nodes (20): Server-side Anti-Fraud (cooldown/velocity), Backend Work Brief — Joe, Phase 1.3 Dashboard API (Joe), Phase 1.2 Loyalty Engine + Anti-Fraud (Joe), Code-Against-Stubs Strategy, Phase 1.4 Billing + Messaging (Momen), Backend Work Brief — Momen, Phase 1.1 Enrollment + Wallets (Momen) (+12 more)

### Community 3 - "Frontend Package Manifest"
Cohesion: 0.11
Nodes (17): dependencies, react, react-dom, react-helmet-async, react-router-dom, description, devDependencies, vite (+9 more)

### Community 4 - "Brand Identity & Favicon"
Cohesion: 0.39
Nodes (8): Kasbana Brand Identity, Gold Outer Ring, Faint Gold Inner Ring, Rounded Navy Background Tile, Navy and Gold Color Palette, Brand Seal / Medallion Motif, Gold Five-Pointed Star, Kasbana Favicon (SVG)

### Community 6 - "Django URL Routing"
Cohesion: 0.50
Nodes (3): health(), URL configuration for the Kasbana backend., Simple health check so deploys can be verified.

## Knowledge Gaps
- **28 isolated node(s):** `name`, `private`, `version`, `type`, `description` (+23 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Kasbana Django Backend API` connect `Architecture & Deploy Pipeline` to `Backend Loyalty & Wallet Plan`?**
  _High betweenness centrality (0.065) - this node is a cross-community bridge._
- **Why does `Shared Data Model (Merchant…WalletRegistration)` connect `Backend Loyalty & Wallet Plan` to `Architecture & Deploy Pipeline`?**
  _High betweenness centrality (0.057) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `Kasbana Django Backend API` (e.g. with `Kasbana Vite+React Frontend` and `Kasbana Architecture Doc`) actually correct?**
  _`Kasbana Django Backend API` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `Kasbana Vite+React Frontend` (e.g. with `Kasbana Django Backend API` and `Kasbana Architecture Doc`) actually correct?**
  _`Kasbana Vite+React Frontend` has 3 INFERRED edges - model-reasoned connections that need verification._
- **What connects `ASGI config for the Kasbana backend.`, `Django settings for the Kasbana backend.  Configuration is driven by environment`, `URL configuration for the Kasbana backend.` to the rest of the system?**
  _38 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Architecture & Deploy Pipeline` be split into smaller, more focused modules?**
  _Cohesion score 0.09230769230769231 - nodes in this community are weakly interconnected._
- **Should `Backend Loyalty & Wallet Plan` be split into smaller, more focused modules?**
  _Cohesion score 0.1368421052631579 - nodes in this community are weakly interconnected._