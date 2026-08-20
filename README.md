# Stampn Stampn

**Stampn** is a digital loyalty and rewards platform for cafés, restaurants,
salons, gyms, and shops. Businesses create stamp and points cards that customers
add to **Apple Wallet** and **Google Wallet**, collect rewards, and get notified
automatically — **no app to download**. Built for Egypt, Arabic-first.

> Digital loyalty cards that live in your customers' phone wallet — no app needed.
> كروت ولاء رقمية في محفظة عملائك — من غير أي تطبيق.

- **Website:** https://stampn.net
- **Contact:** contact@stampn.net

---

## Repository layout

Development happens on the **`dev`** branch (a monorepo). Pushing `dev` runs an
Action that distributes each part to its own branch automatically.

| Branch         | Holds                                  | Source folder on `dev` |
| -------------- | -------------------------------------- | ---------------------- |
| **`dev`**      | The whole project (work here)          | —                      |
| **`main`**     | Docs / project overview                | `main/`                |
| **`frontend`** | Vite + React site (bilingual EN/AR)    | `frontend/`            |
| **`Backend`**  | Django API                             | `backend/`             |
| **`deployment`** | Built static site (served by Hostinger) | _built from_ `frontend/` |

### Deploy flow

```
push to dev ──▶ Action:
   main/      → main
   frontend/  → frontend
   backend/   → Backend
   build      → deployment → Hostinger
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for details.

---

## Working on each part (from the `dev` branch)

```bash
# Frontend (React)
cd frontend && npm install && npm run dev

# Backend (Django)
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && python manage.py runserver
```

Ship a change:

```bash
git add -A && git commit -m "your change" && git push origin dev
```
