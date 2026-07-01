# Stampn Stampn

**Stampn** is a digital loyalty and rewards platform for cafés, restaurants,
salons, gyms, and shops. Businesses create stamp and points cards that customers
add to **Apple Wallet** and **Google Wallet**, collect rewards, and get notified
automatically — **no app to download**. Built for Egypt, Arabic-first.

- **Website:** https://stampn.net
- **Contact:** contact@stampn.net

---

## 🧭 How this repo works — you only touch `dev`

`dev` is the **single source of truth**: a monorepo with everything in one place.

```
dev/
  main/       → docs (project overview)
  frontend/   → React site (bilingual EN + AR)
  backend/    → Django API
  .github/workflows/distribute.yml
```

When you **push to `dev`**, one GitHub Action automatically distributes each
folder to its own branch — you don't do anything else:

```
git push origin dev
        │
        ▼  (.github/workflows/distribute.yml)
  ┌──────────────────────────────────────────────┐
  │  main/       →  main        (docs)            │
  │  frontend/   →  frontend    (source)          │
  │  backend/    →  Backend     (source)          │
  │  build       →  deployment  →  Hostinger      │
  └──────────────────────────────────────────────┘
```

> Anything you put in the **`main/`** folder is what ends up on the `main`
> branch — it's docs-only by design.

> **Edit only `dev`.** The `main`, `frontend`, `Backend`, and `deployment`
> branches are **generated** — anything committed to them directly will be
> overwritten on the next push to `dev`.

### Branches

| Branch         | What it holds                          | From folder | Generated? |
| -------------- | -------------------------------------- | ----------- | ---------- |
| **`dev`**      | The whole project (you work here)      | —           | no — source |
| **`main`**     | Docs / project overview                | `main/`     | yes        |
| **`frontend`** | Just `frontend/` at root               | `frontend/` | yes        |
| **`Backend`**  | Just `backend/` at root                | `backend/`  | yes        |
| **`deployment`** | Built static site (served by Hostinger) | _built_   | yes        |

---

## Quick start

```bash
# Frontend (React)
cd frontend
npm install && npm run dev        # http://localhost:5173

# Backend (Django)
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate && python manage.py runserver
```

## Make a change & ship it

```bash
git add -A
git commit -m "your change"
git push origin dev               # → distributes everywhere automatically
```

---

## Configuration

| What            | Where                              |
| --------------- | ---------------------------------- |
| Web3Forms key   | `frontend/src/pages/Support.jsx`   |
| Contact / domain| `frontend/src/config.js`           |
| Backend env     | `backend/.env.example` → `.env`    |

See `frontend/README.md` and `backend/README.md` for details.

---

## Notes

- The distribution pushes use `GITHUB_TOKEN`, so they don't trigger each other
  (no loops).
- To stop the automation, disable or delete `.github/workflows/distribute.yml`.
