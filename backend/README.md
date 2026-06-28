# Kasbana — Backend (Django)

API and business logic for **Kasbana**, the digital loyalty platform. This is the
**`Backend`** branch.

> Status: scaffold ready — feature development not started yet.

## Stack

- **Django 5** + **Django REST Framework**
- **django-cors-headers** (so the React frontend at `kasbana.net` / localhost can
  call the API)
- Environment-driven settings (`python-dotenv`)
- SQLite for local dev; MySQL/Postgres in production

## Getting started

```bash
# from the Backend branch
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env               # then edit .env (set a real SECRET_KEY)

python manage.py migrate
python manage.py runserver
```

Check it's alive: <http://127.0.0.1:8000/api/health/> → `{"status": "ok", ...}`

Admin: create a superuser with `python manage.py createsuperuser`, then visit
`/admin/`.

## Layout

```
manage.py
requirements.txt
.env.example
kasbana/
  settings.py     # env-driven; CORS + DRF configured
  urls.py         # /admin, /api/health (add app routes here)
  wsgi.py / asgi.py
```

## Building features

1. Create an app: `python manage.py startapp cards`
2. Add it to `INSTALLED_APPS` in `kasbana/settings.py`.
3. Add its routes via `include('cards.urls')` in `kasbana/urls.py`.

## Configuration

All config comes from environment variables — see `.env.example`. Key ones:

| Variable               | Purpose                                  |
| ---------------------- | ---------------------------------------- |
| `DJANGO_SECRET_KEY`    | **Set a real value in production.**      |
| `DJANGO_DEBUG`         | `False` in production.                   |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated hostnames.               |
| `CORS_ALLOWED_ORIGINS` | Frontend origins allowed to call the API.|
| `DATABASE_*`           | Set for MySQL/Postgres; unset = SQLite.  |
