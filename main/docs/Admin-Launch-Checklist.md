# Admin Panel — Phase 15 Launch & Security Checklist

> The go/no-go gate for launching `admin.stampn.net`. Items marked **[code ✅]**
> ship in the Phase 15 code. Items marked **[owner: …]** are infra/process steps
> the team completes out-of-band before sign-off.

## Authentication & sessions
- [x] **[code ✅]** MFA/TOTP enrolment + login challenge; forced enrolment for
      privileged roles (Super-admin, Finance, Support, Marketing, Engineering),
      never a lockout (forced-setup token flow).
- [x] **[code ✅]** Brute-force lockout (5 fails → 15-min lock) + `admin_auth`
      throttle (10/min).
- [x] **[code ✅]** Session tracking; device/session list; "log out everywhere";
      per-session revoke; refresh rotation with reuse-detection.
- [x] **[code ✅]** Step-up re-auth on the sensitive merchant-erase.
- [x] **[code ✅]** Super-admin **Reset MFA** recovery path.
- [ ] **[owner: eng]** Seed each real team member as an `AdminUser`; confirm each
      completes MFA enrolment on first login.
- [ ] **[owner: eng]** Decide access-token lifetime for prod (currently 30 min).

## Edge / network
- [ ] **[owner: infra]** Collect the team's static egress IPs / VPN ranges.
- [ ] **[owner: infra]** Activate the edge allowlist from
      `infra/caddy/Caddyfile.admin-allowlist.example` with the real IPs; verify
      from an allowed **and** a blocked IP before walking away.
- [ ] **[owner: infra]** Confirm HTTPS (Let's Encrypt) is valid on the admin host.

## Observability
- [x] **[code ✅]** Backend Sentry (guarded by `SENTRY_DSN`).
- [x] **[code ✅]** Admin-frontend Sentry browser SDK (guarded by
      `VITE_SENTRY_DSN`, tagged `app:admin-console`).
- [ ] **[owner: infra]** Set `VITE_SENTRY_DSN` (+ `VITE_SENTRY_ENVIRONMENT`,
      `VITE_SENTRY_RELEASE`) in the admin frontend build env; confirm a test
      error surfaces in Sentry.
- [ ] **[owner: eng]** Confirm the admin-panel deploy env carries `REDIS_URL`
      (shared throttle + cache) and the Celery result backend is reachable.

## Security review / pentest
- [x] **[code ✅]** Automated security suite green: auth-boundary (merchant token
      rejected), permission-matrix (role separation), MFA gate, lockout, session
      revoke, refresh reuse-detection, step-up, audit-completeness
      (`tests/test_console_security.py`, `test_console_auth.py`,
      `test_rbac_roles.py`, `test_tenancy.py`).
- [ ] **[owner: security]** Manual pentest pass: cross-tenant leakage probes,
      impersonation-abuse, IDOR on `/api/admin/v1/*`, token-boundary fuzzing.
- [ ] **[owner: eng]** `pip-audit` / dependency vulnerability scan on the backend
      image; `npm audit` on the admin frontend.

## Data / operations
- [ ] **[owner: infra]** Confirm the admin data (Postgres) is inside the existing
      backup schedule; do one test restore.
- [ ] **[owner: eng]** Load-test the cross-tenant analytics queries (revenue,
      platform, lifecycle) at expected merchant volume; add DB indexes if any
      query is slow. (Most console list endpoints are already indexed +
      cursor-paginated; the analytics aggregates are the ones to watch.)
- [x] **[code ✅]** Incident runbook for a compromised admin account
      (`main/docs/Admin-Incident-Runbook.md`).

## Sign-off
- [ ] **[owner: eng lead]** All boxes above checked; launch approved.
