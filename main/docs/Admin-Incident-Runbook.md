# Admin Panel — Incident Runbook

> Phase 15. What to do when an admin account is compromised (or suspected), and
> the routine recovery paths. The admin console is the highest-value target in
> the system — treat any suspicion as real until disproven.

## Roles & access
- **Recovery path of last resort:** SSH to the prod box + the `createadmin`
  management command. This always works even if every session is revoked and
  MFA is locked.
  ```
  docker compose -f infra/compose.prod.yml exec web \
    python manage.py createadmin --email you@stampn.net --role SUPER_ADMIN --force
  ```
- All admin actions are in the **Audit Log** (`/audit` in the console, or the
  `AdminAuditLog` table). Every login, MFA enrolment, session revoke, step-up,
  and sensitive action is recorded with actor + IP + user-agent.

---

## Scenario 1 — a specific admin account is compromised
Symptoms: unexpected logins, actions the admin didn't take, a lost/stolen device.

1. **Revoke their access now.** In the console → **Admin Team** → open the admin
   → **Deactivate** (`PATCH /admins/{id}` `is_active=false`). Deactivation makes
   every one of their tokens fail on the next request (the auth layer checks
   `is_active`).
2. **Kill their sessions + MFA.** **Reset MFA** on that admin
   (`POST /admins/{id}/reset-mfa`) — this clears their TOTP secret **and revokes
   all their sessions**. Combined with step 1, all their tokens are dead.
3. **Rotate the password.** `createadmin --force` with a new password (or have
   them go through forced re-enrolment on next login once reactivated).
4. **Review the blast radius.** Filter the Audit Log by `actor` = their email
   over the suspicious window. Pay attention to: `merchant.delete`,
   `merchant.data_export`, `impersonate`, `admin.invite`, `admin.update`,
   billing actions. Note anything that needs reverting or customer notification.
5. **Reactivate** only after the password is rotated and MFA re-enrolled.

## Scenario 2 — you don't know which account, but something is wrong
1. **Turn on maintenance mode** (Operations → Settings) if merchant-facing data
   integrity is at risk — this 503s merchant traffic while you investigate; the
   console stays reachable.
2. **Force a fleet-wide re-login.** The fastest blunt instrument is to bump the
   JWT signing key (`SECRET_KEY` / SimpleJWT signing key) via infra env and
   redeploy — every existing admin (and merchant) token becomes invalid. Use
   only in a real incident; it logs everyone out.
3. Alternatively, per-admin: revoke sessions for each admin
   (`DELETE /auth/sessions` runs as that admin; as an operator use Reset MFA,
   which revokes sessions, or Deactivate).
4. Work the Audit Log from the top (most recent) down.

## Scenario 3 — an admin is locked out (lost authenticator)
This is routine, not an incident:
1. A super-admin opens **Admin Team** → the admin → **Reset MFA**.
2. The admin logs in with their password and is **forced to re-enrol** MFA
   (privileged roles) on that next login. No lockout.
3. If the admin also forgot their password, `createadmin --force` resets it.

## Scenario 4 — brute-force in progress
- Accounts auto-lock for 15 min after 5 consecutive failed passwords
  (`console.security.LOCKOUT_*`). The `admin_auth` throttle (10/min) caps the
  rate per client. `admin.login_locked` events appear in the Audit Log.
- If a single source IP is hammering, block it at the edge (Caddy) — see
  `infra/caddy/Caddyfile.admin-allowlist.example`.

---

## Preventive posture (steady state)
- **MFA** is enforced for all privileged roles (forced enrolment on first login).
- **Sessions** are listable + revocable per admin (Security screen); refresh
  tokens rotate with reuse-detection (a stolen refresh token self-destructs the
  session on reuse).
- **Step-up** re-auth guards the irreversible merchant-erase.
- **Edge allowlist** (optional, drafted) restricts the console to team IPs.
- **Sentry** captures backend + admin-frontend errors (tag `app:admin-console`).
- **Backups:** the admin data (Postgres) is covered by the platform's existing
  database backup; no separate store. Restore = the standard DB restore path.
