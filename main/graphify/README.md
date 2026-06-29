# Stampn — Knowledge Graph

Generated with [graphify](https://github.com/safishamsi/graphify) over the whole
project (frontend, backend, docs, brand assets). It maps how the codebase, the
deploy pipeline, and the backend plans connect.

## Files

| File              | What it is                                                   |
| ----------------- | ------------------------------------------------------------ |
| `graph.html`      | Interactive graph — **open in any browser**, no server needed |
| `graph.json`      | Raw graph data (GraphRAG-ready)                              |
| `GRAPH_REPORT.md` | Plain-language audit: god nodes, surprising links, questions |

## Snapshot

- **120 nodes · 164 edges · 13 communities** across 35 files (~12k words).
- Biggest hubs: `useLang()` (frontend i18n), the **Walaa Backend Plan & Variable
  Contract**, and the **Django Backend API** — which bridges the deploy pipeline
  and the backend loyalty/wallet plan.
- Communities cleanly separate: React UI + i18n, the architecture/deploy
  pipeline, the backend loyalty & wallet plan, the brand/favicon, and the Django
  config (settings, URLs, WSGI/ASGI).

## Regenerate

```bash
/graphify .        # rebuilds into graphify-out/, then copy into main/graphify/
```

> The live working directory `graphify-out/` is git-ignored; this folder holds
> the committed snapshot that ships to the `main` branch.
