# Kasbana — Backend (Django)

API and business logic for **Kasbana**, the digital loyalty platform. This is the
**`Backend`** branch.

> Status: **Phase 1.0 (Foundation & Contract) complete** — frozen `core/`,
> ledger, shared layer, wallet/billing seams, and the v1 OpenAPI contract.
> Phases 1.1 (Enrollment + Wallets), 1.2/1.3 (Loyalty + Dashboard) and 1.4
> (Billing + Messaging) build on top.

The single source of truth for every model, enum, field, endpoint, function
signature, env var and error code is **`main/docs/Walaa_Backend_Plan_and_Contract.md`**
(the Variable Contract). After the `core-v1` tag, any change to a shared name is
a joint PR to that document first, then code.

## Stack (contract §1)

- **Django 5** + **Django REST Framework**
- **JWT** auth (`djangorestframework-simplejwt`), email-based
- **drf-spectacular** (OpenAPI from code)
- **Celery + beat** on **Redis**; queues: `default`, `wallet`, `messaging`
- **PostgreSQL** in production (`DATABASE_URL`); SQLite fallback for local dev
- Quality gate: **ruff · black · mypy** (+ pytest, factory_boy)

## Getting started

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

cp .env.example .env               # then edit .env (set a real SECRET_KEY)

python manage.py migrate
python manage.py runserver
```

- Health: <http://127.0.0.1:8000/api/health/> → `{"status": "ok", ...}`
- API docs (Swagger): <http://127.0.0.1:8000/api/docs/>
- Live schema: <http://127.0.0.1:8000/api/schema/>
- Admin: `python manage.py createsuperuser`, then `/admin/`

Local dev uses SQLite and runs Celery tasks eagerly (no broker needed). Point
`DATABASE_URL` at Postgres and `REDIS_URL` at Redis for staging/prod.

## Layout (contract §2)

```
manage.py
config/                      project: split settings, urls, celery app
  settings/{base,dev,prod}.py
core/                        models · enums · constants · auth · ledger · tenancy  [FROZEN]
common/                      errors envelope · pagination · serializers · permissions · middleware
wallets/                     interfaces · service façade · tasks            (Phase 1.1)
billing/                     entitlements engine                            (Phase 1.4)
../contracts/openapi.yaml    frozen v1 API contract
```

All persistent models live in `core/` (one migration). `wallets`, `billing`
(and later `enrollment`, `messaging`) own behaviour but no models.

## The one chokepoint

Every balance mutation flows through **`core/ledger.py`** — no view writes to
`StampLedger` or `CustomerCard.stamp_count` directly. Loyalty (Joe) calls
`core.ledger.add_stamp(...)` then `wallets.service.push_update(card)` (a working
stub until Phase 1.1 makes it real). This keeps the parallel phases consistent.

## Settings module

Select with `DJANGO_SETTINGS_MODULE`:

- `config.settings.dev` — local (default for `manage.py`)
- `config.settings.prod` — production (used by `wsgi`/`asgi`)

## Configuration

All config is environment-driven — see `.env.example` (mirrors contract §3.8):
`SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `BASE_URL`, `DATABASE_URL`, `REDIS_URL`,
the Apple/Google wallet secrets (Phase 1.1) and Paymob/Fawry/WhatsApp keys
(Phase 1.4).

## Quality

```bash
ruff check .
black .
mypy .
pytest
```
