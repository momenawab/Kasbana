# Stampn / Kasbana — Secret Rotation Runbook

> Companion to [`Admin-Incident-Runbook.md`](./Admin-Incident-Runbook.md) (which
> covers *responding* to an incident). This one covers *rotating* the credentials
> the platform holds — routinely, or because one leaked.
>
> Every procedure here was written against the code on `dev` as of **2026-07-14**
> and names the real blast radius. Where a secret does nothing, this file says so
> rather than inventing a ceremony for it.

---

## Where secrets live

There is exactly one secret store in production, and it is not in git.

| What | Where | Loaded by |
| --- | --- | --- |
| Env secrets | `/opt/stampn/infra/.env` on the EC2 box | `env_file: [.env]` in `compose.prod.yml:17` — passed to `web`, `worker`, `beat` |
| Key/cert files | `/opt/stampn/secrets/` on the box | bind-mounted read-only at `/secrets` (`compose.prod.yml:26`) |
| Template (no real values) | `infra/.env.prod.example` (committed) | nothing — reference only |

`infra/.env` is **never** committed. If you find it in git history, treat every
value in it as leaked and rotate all of them.

All commands below run from `/opt/stampn/infra` on the server:

```bash
ssh <box>
cd /opt/stampn/infra
COMPOSE="docker compose -f compose.prod.yml"
```

---

## Blast radius — read this before rotating anything

| Secret | What breaks the moment you rotate it | Who notices |
| --- | --- | --- |
| `SECRET_KEY` | **Every merchant *and* admin is logged out.** Pending password-reset and invite links die. | Everyone, immediately |
| `POSTGRES_PASSWORD` | Nothing, if `DATABASE_URL` is updated in the same edit. The whole stack is down between the two. | Nobody, if done right |
| `EMAIL_HOST_PASSWORD` | Outbound mail (password reset, invites, admin replies to contact messages) fails silently-ish until fixed. | Support, on the next reply |
| `PAYMOB_API_KEY` | Checkout stops. | Merchants trying to subscribe |
| `PAYMOB_HMAC_SECRET` | **Inbound webhooks start failing signature verification** — subscriptions stop being marked paid. Must be rotated in the Paymob dashboard *and* here in the same window. | Silently — billing state drifts |
| `GOOGLE_SA_KEY` (`google-sa.json`) | Google Wallet pass creation + stamp-update pushes fail. Existing passes on phones keep working but stop updating. | Merchants stamping |
| `APPLE_PASS_CERT` (`pass.p12`) | Apple pass signing fails. **Currently no impact — Apple is off in prod.** | Nobody today |
| `SENTRY_DSN` | Error reporting goes dark. Not really a secret (it's in the frontend bundles), but rotate it if it's being abused. | Nobody, until you need it |

### The one that is *not* a secret rotation

`WALLET_AUTH_TOKEN_SECRET` and `PASS_BARCODE_SECRET` appear in
`backend/.env.example` and in `config/settings/base.py:301-302`, and they look
like they should be rotated. **They are dead settings — no code reads them.**
Verified with a whole-repo grep: the only hits are the settings declaration and
the two `.env.example` lines.

The Apple pass `authenticationToken` is **not** derived from a global secret. It
is `CustomerCard.auth_token` (`core/models.py:138`), a **random per-row column**
minted by `_generate_auth_token()` at enrollment and compared constant-time in
`wallets/apple_webservice/auth.py:26`.

Consequence: **there is no global lever to invalidate wallet pass tokens.** A
single leaked pass token exposes exactly one customer card, and the fix is to
reissue that card's pass, not to rotate a platform secret. Do not add a
"rotate wallet secret" step to any checklist — it would do nothing and give false
confidence.

---

## Rotating `SECRET_KEY`

Django's `SECRET_KEY` signs merchant JWTs **and** admin JWTs — `SIMPLE_JWT`
(`base.py:262-267`) declares no `SIGNING_KEY`, so SimpleJWT falls back to
`SECRET_KEY`, and `console/auth.py:69` mints admin tokens with the same
`AccessToken` class. Rotating it is a **platform-wide forced logout**. Schedule
it; don't do it at 2pm on a weekday.

```bash
# 1. Generate a new key
NEW=$(docker compose -f compose.prod.yml run --rm web \
  python -c "from django.core.management.utils import get_random_secret_key as k; print(k())")

# 2. Back up the env file, then edit SECRET_KEY= in place
cp .env .env.bak.$(date +%F-%H%M)
$EDITOR .env

# 3. Roll the containers that read it
docker compose -f compose.prod.yml up -d web worker beat

# 4. Verify
curl -fsS https://api.stampn.net/api/health/ && echo OK
```

Then confirm a merchant can log in fresh and an admin can log in fresh (the admin
will also be prompted for MFA). Delete `.env.bak.*` once you're satisfied.

**If your goal is "log everyone out right now," don't rotate `SECRET_KEY`.**
There is a cleaner lever: `AdminSession` rows carry the `sid` embedded in admin
tokens and are checked on every request (`console/auth.py:93-97`), so revoking
the rows kills those tokens immediately without touching merchants:

```bash
docker compose -f compose.prod.yml exec web python manage.py shell -c "
from django.utils import timezone
from console.models import AdminSession
n = AdminSession.objects.filter(revoked=False).update(revoked=True, revoked_at=timezone.now())
print(f'revoked {n} admin session(s)')
"
```

Set `revoked_at` alongside `revoked` — the session list and audit trail read it.

---

## Rotating the database password

`POSTGRES_PASSWORD` and `DATABASE_URL` both contain it. **Edit them together** —
if they disagree, the app cannot reach its own database.

```bash
cp .env .env.bak.$(date +%F-%H%M)

# 1. Change the password inside Postgres first
docker compose -f compose.prod.yml exec db \
  psql -U "$POSTGRES_USER" -c "ALTER USER $POSTGRES_USER WITH PASSWORD 'NEW_PASSWORD';"

# 2. Update BOTH lines in .env: POSTGRES_PASSWORD= and the password inside DATABASE_URL=
$EDITOR .env

# 3. Roll the app (NOT db — restarting it would not re-read the password anyway)
docker compose -f compose.prod.yml up -d web worker beat

# 4. Verify
docker compose -f compose.prod.yml exec web python manage.py showmigrations --plan | tail -1
curl -fsS https://api.stampn.net/api/health/ && echo OK
```

`POSTGRES_PASSWORD` is only consumed by the `db` container **on first
initialisation** — the volume already exists, so changing it in `.env` alone does
not change the actual password. That is why step 1 (`ALTER USER`) is the real
rotation and the env edit only keeps the clients in sync.

---

## Rotating the Paymob credentials

The dangerous half is `PAYMOB_HMAC_SECRET`, because a mismatch fails **silently
in the inbound direction**: webhooks arrive, fail verification, get rejected, and
subscriptions quietly stop being marked paid. Nothing pages you.

1. In the Paymob dashboard, generate the new API key / HMAC secret.
2. Edit `PAYMOB_API_KEY` and `PAYMOB_HMAC_SECRET` in `/opt/stampn/infra/.env`.
   > `infra/.env.prod.example` historically listed only `PAYMOB_API_KEY`. The
   > backend reads `PAYMOB_HMAC_SECRET` too (`base.py:310`) — make sure the real
   > `.env` has it.
3. `docker compose -f compose.prod.yml up -d web worker`
4. **Verify inbound:** trigger a test webhook from the Paymob dashboard and
   confirm it is accepted, not 4xx'd. Do not consider the rotation done until an
   inbound webhook has verified against the new secret.

Keep the window between (1) and (3) as short as possible; webhooks that land in
it are rejected.

---

## Rotating the Google Wallet service-account key

```bash
# 1. In Google Cloud console: create a new key on the SAME service account,
#    download the JSON. Do NOT delete the old key yet.

# 2. Copy it onto the box, replacing the mounted file
scp google-sa-new.json <box>:/tmp/
ssh <box>
sudo cp /opt/stampn/secrets/google-sa.json /opt/stampn/secrets/google-sa.json.bak
sudo mv /tmp/google-sa-new.json /opt/stampn/secrets/google-sa.json
sudo chmod 600 /opt/stampn/secrets/google-sa.json

# 3. Roll — the file is read at startup
cd /opt/stampn/infra && docker compose -f compose.prod.yml up -d web worker
```

**Verify before deleting the old key:** issue a pass and stamp a card, and
confirm the pass updates on a real phone. Only then delete the old key in the
Google Cloud console. The path (`GOOGLE_SA_KEY_PATH=/secrets/google-sa.json`)
does not change, so no env edit is needed.

---

## Rotating the Apple Pass Type ID certificate

Apple is **not live in prod** (`apple_pass_url` is null; the enroll page shows
only Google Wallet), so today this is a no-op. When Apple goes live:

1. Renew the Pass Type ID cert in the Apple Developer portal, export `pass.p12`.
2. `sudo cp pass.p12 /opt/stampn/secrets/pass.p12 && sudo chmod 600 …`
3. Update `APPLE_PASS_CERT_PASSWORD` in `infra/.env` if the export password changed.
4. `docker compose -f compose.prod.yml up -d web worker`
5. Verify by signing one pass and adding it to a real iPhone.

The WWDR intermediate (`/secrets/wwdr.pem`) also expires — replace it the same
way. An expired WWDR breaks signing even with a valid `pass.p12`.

---

## Rotating the SMTP password

```bash
# 1. Change it in Hostinger for contact@stampn.net
# 2. Update EMAIL_HOST_PASSWORD in /opt/stampn/infra/.env
# 3. Roll
docker compose -f compose.prod.yml up -d web worker
# 4. Verify — send a real message
docker compose -f compose.prod.yml exec web python manage.py shell -c \
  "from django.core.mail import send_mail; send_mail('rotation test','ok',None,['you@example.com'])"
```

Mail is sent from the `worker` as well as `web` (admin contact replies), so roll
both.

---

## After any rotation

- [ ] `curl -fsS https://api.stampn.net/api/health/` returns OK
- [ ] A merchant can log in to `app.stampn.net`
- [ ] An admin can log in to `admin.stampn.net` (MFA prompt appears)
- [ ] `docker compose -f compose.prod.yml logs --tail=100 web worker` — no auth/credential errors
- [ ] The secret is updated in the team's password manager, not just on the box
- [ ] `.env.bak.*` files deleted from the server
- [ ] If the rotation was triggered by a **leak**, record it per
      [`Admin-Incident-Runbook.md`](./Admin-Incident-Runbook.md)

---

## Appendix — the two prod checks that need server access

These are the open Phase F items in [`finalize-plan.md`](../../finalize-plan.md).
Neither can be closed from code; run them on the box / against prod.

### 1. Backup cron is actually installed

`infra/scripts/backup.sh` (nightly) and `infra/scripts/verify_backup.sh` (weekly)
exist in the repo, but existing in git is not the same as being in a crontab.

```bash
ssh <box>

# Are the two lines actually installed?
crontab -l | grep -E "backup\.sh|verify_backup\.sh"

# Expected — exactly these two (from the script headers):
#   30 2 * * * /opt/stampn/infra/scripts/backup.sh >> /opt/stampn/backups/backup.log 2>&1
#   0 4 * * 0 /opt/stampn/infra/scripts/verify_backup.sh >> /opt/stampn/backups/verify.log 2>&1

# Did last night's run actually produce a dump?
ls -lh /opt/stampn/backups/ | tail -5
tail -20 /opt/stampn/backups/backup.log

# Is it going OFF the box? An on-box-only backup is not a backup.
grep BACKUP_S3 /opt/stampn/infra/.env
aws s3 ls s3://<bucket>/stampn/ | tail -5
```

If a line is missing, install it (the script headers carry the exact
`crontab -` incantation). **`BACKUP_S3` empty means backups die with the server** —
that is the finding to escalate, not a cron nit.

### 2. Every admin completed forced MFA enrolment

`AdminUser.mfa_enabled` (`console/models.py:35`) only flips true after a TOTP code
is verified, so this is a straight query:

```bash
cd /opt/stampn/infra
docker compose -f compose.prod.yml exec web python manage.py shell -c "
from console.models import AdminUser
rows = AdminUser.objects.filter(is_active=True, mfa_enabled=False)
print(f'{rows.count()} active admin(s) WITHOUT MFA:')
for a in rows:
    print(' -', a.email, a.role)
"
```

**Pass = zero rows.** Any name that prints is an active admin who can log in with
a password alone — chase them to enrol, or deactivate the account.
