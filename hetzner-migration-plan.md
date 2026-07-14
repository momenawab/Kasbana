# Leaving AWS → Hetzner: specs, security, backups

> **Status: decided, not started.** Written 2026-07-15 on `dev`.
>
> **How to use this file.** Send it back to me and we build the migration plan
> proper — the ordered runbook, the cutover, the rollback. Everything below is the
> *decision record* that plan will be built on: what to buy, what it costs, what
> changes about security, and how backups get fixed. Nothing here has been executed.
>
> **Context.** AWS becomes test/dev only. Production (`api.stampn.net`,
> `admin.stampn.net`) moves off EC2 `13.49.70.197` (eu-north-1). The dashboard and
> marketing site are **not** affected — they are static on Hostinger and stay there.

---

## 1. What the box actually runs

From [`infra/compose.prod.yml`](./infra/compose.prod.yml) — six containers, one host:

| Service | Notes |
| --- | --- |
| `web` | gunicorn, **2 workers × 4 threads** (`infra/docker/Dockerfile:40-42`) |
| `worker` | Celery, **concurrency 2**, queues `default,wallet,messaging` |
| `beat` | Celery beat (DatabaseScheduler) |
| `db` | Postgres 16-alpine → `pgdata` volume |
| `redis` | Redis 7, capped `--maxmemory 256mb`, **no persistence** (`--save "" --appendonly no`) |
| `caddy` | TLS + serves `/media` from the shared volume. Only host ports: **80, 443** |

Postgres and Redis are **not** published to the host — they sit on the internal
Docker network. That keeps the public attack surface to 80/443 + SSH.

Two environment quirks that must survive the move:

- **Container DNS.** The host's systemd-resolved stub (`127.0.0.53`) is unreachable
  from inside containers, breaking all outbound DNS (ACME, Apple, Google, Sentry).
  Worked around by pinning `dns: ["8.8.8.8","1.1.1.1"]` on the app anchor + caddy.
  Re-check on the new host; the fix is harmless if it turns out to be unnecessary.
- **Media is served by Caddy, not Django** (`handle_path /media/*` → `/srv/media`),
  via the `media` volume mounted into both `web` and `caddy:ro`.

---

## 2. Server spec

**Minimum: 2 vCPU · 4 GB RAM · 40 GB NVMe.**

Today's box is a **t3.small (2 vCPU / 2 GB)** and the compose header admits what
that means: *"Memory is kept modest to fit 2 GB + swap."* It boots on 2 GB; it does
not comfortably *run* on it. Swap on a host that also carries Postgres is the worst
place to have it — under pressure the database pages to disk and latency collapses.

Rough steady-state, adding up: Postgres 150–250 MB · Redis 30–80 MB · Caddy ~40 MB ·
gunicorn 400–500 MB (2 workers) · Celery worker 500–600 MB (parent + 2 children) ·
beat 100–150 MB · OS + dockerd 250–350 MB. **≈1.6–2.2 GB at idle.** 4 GB is the first
size with real headroom.

**The memory pressure point is the Celery worker**, not the web tier: it does the
Pillow work — the 1125×369 Apple strip, the Google hero, poster PDFs — and with
concurrency 2 two of those can land at once. That is the likeliest OOM trigger.

> **Unverified.** These are derived from the stack, not measured. I was blocked from
> SSHing into prod to run `free`/`docker stats`/`dmesg`. **First action of the
> migration plan: measure the live box** and replace these estimates with real
> numbers. If actual usage is far under, 4 GB still stands as the floor — but it is
> worth knowing before we size up.

---

## 3. Platform + price

**Hetzner Cloud CX22 — 2 vCPU / 4 GB / 40 GB NVMe — ~€4.50/mo.**

| Line item | ~Cost/mo |
| --- | --- |
| CX22 (x86) | €4.50 |
| IPv4 address | €0.50 |
| Automated backups (20%) | €0.90 |
| **Total** | **≈ €6** |

Versus a t3.medium at roughly $30/mo **plus AWS egress**. Hetzner includes 20 TB of
traffic, so the bandwidth bill goes to zero. Latency to Egypt also *improves* —
Falkenstein/Nuremberg is closer than Stockholm (`eu-north-1`).

> Prices checked 2026-07-15 and are approximate. **Re-verify before purchase.**

### Take the x86 CX22, not the cheaper ARM CAX11 (€3.79)

`.github/workflows/deploy-prod.yml` sets **no `platforms:`** on
`docker/build-push-action` and runs on `ubuntu-latest` — so
`ghcr.io/momenawab/stampn-backend` is built **amd64-only**. ARM would need a
multi-arch build plus Pillow/psycopg re-verified on aarch64. That is real work and
real risk to save **€0.70/month**. Not worth it. CX22 is a genuine drop-in: same
architecture, the Compose stack lifts over untouched.

### Before committing: check startup credits

[AWS Activate](https://aws.amazon.com/activate/) gives startups $1k–$5k self-serve.
At this usage that is *years* of runway, and it would keep managed RDS on the table
instead of us becoming the DBA. Twenty minutes to check. **The trap:** credits expire
in 1–2 years and by then you've built around expensive managed services. Only take
them while staying portable — which, with Compose, we are.

### Fallbacks if Hetzner rejects the signup

Hetzner routinely holds non-EU signups (Egypt included) for ID verification, and
sometimes rejects them. **Do not cancel AWS until a Hetzner box is actually running.**
Fallback: Contabo (~€5.50/mo, 8 GB) — but it is oversold and CPU-throttles under
sustained load, which is exactly the Pillow work we do. Hostinger VPS is worth a look
since we already bill there, but compare the **renewal** price, not the promo sticker.

---

## 4. Security

**Hetzner is not a downgrade.** ISO 27001, EU/GDPR data centres, free always-on DDoS
protection. And the shared-responsibility line barely moves: we already run a raw
Ubuntu VM with Docker, no IAM, no KMS, no Secrets Manager — the Apple pass cert and
Google SA key are plain files in `/opt/stampn/secrets`. That is identical on Hetzner.

### The one thing that genuinely changes

**AWS attaches a deny-by-default firewall (the Security Group) to every instance.
Hetzner attaches nothing.** A fresh Hetzner box answers on every port.

And critically: **there is no firewall config anywhere in this repo.** No `ufw`, no
`iptables`, no `fail2ban` in `infra/` or the workflows. Today's network protection is
an AWS Security Group configured in the console — it lives outside version control and
**it will not come with us.**

Exposure is small (only 80/443 published; Postgres/Redis internal), so the real risk
is **SSH brute-forcing on 22**, which begins within minutes of the box going live.

### Hardening checklist — do this *before* pointing DNS

1. **Attach a Hetzner Cloud Firewall** (free): inbound `80`, `443`, and `22`
   **from our IP only**. Deny the rest.
2. **Key-only SSH**: `PasswordAuthentication no`, `PermitRootLogin no`.
3. **`fail2ban`** — one `apt install`, kills SSH brute-force.
4. **`unattended-upgrades`** for automatic security patches.

**Use the Hetzner Cloud Firewall, not `ufw`.** Docker writes its own iptables rules
that **bypass `ufw`**, so a ufw-only setup is a false sense of safety the moment a port
is published. The Cloud Firewall runs *outside* the host — Docker cannot punch through it.

---

## 5. Backups — the actual risk

Everything lives on one box: API, Postgres, TLS, and the wallet signing certs. **If
that disk dies, every merchant's loyalty data is gone and the business is over.** No
hosting bill compares to that. This is the part of the move that must not be deferred.

### What to back up

- **Postgres (`pgdata`)** — the business. Merchants, customers, the stamp ledger.
- **`media` volume** — uploaded logos, covers, posters. Not regenerable.
- **`/opt/stampn/secrets`** — Apple pass cert, Google SA key. Re-issuable, painfully.
- **`.env`** — DB password, `SECRET_KEY`, API keys. Losing `SECRET_KEY` breaks
  every session and token.
- **Redis — skip.** Already `--save "" --appendonly no`: a cache and a Celery broker.

### Two layers, because they fail differently

**Layer 1 — Hetzner automated backups (~€0.90/mo).** Whole-box snapshots. Fixes "the
disk died". Does **not** fix a dropped table (the snapshot faithfully copies the
mistake), and does **not** fix losing the Hetzner account.

**Layer 2 — nightly offsite logical backup. This is the one that matters.**
`pg_dump` + media/secrets, encrypted, pushed to **a different company** — Backblaze B2
or Cloudflare R2. The database is small; a compressed dump should land in the free
tier or cost cents. This is what survives both a fat-fingered `DELETE` *and* Hetzner
deleting the account.

Both layers together: **under €2/month.** Cost was never the obstacle.

### The design

**restic → Backblaze B2** (encryption, dedup, retention, integrity checks in one tool
instead of a pile of shell scripts):

```
pg_dump -Fc  →  restic backup (dump + media + secrets + .env)  →  B2
restic forget --keep-daily 7 --keep-weekly 4 --keep-monthly 6 --prune
```

Nightly cron. `pg_dump` takes an MVCC snapshot — consistent without stopping the app.

**Encryption is not optional here.** Those dumps carry customer phone numbers, names,
emails and (as of this week) birthdays — PDPL-regulated personal data about to sit in
third-party object storage. restic encrypts by default. **The repo password must live
somewhere that is not only on the box being backed up.**

### The two things everyone skips

1. **Alert on failure.** A silently broken cron is worse than no backup, because you
   believe you're covered. We already run Sentry — use **Sentry Cron Monitoring**: no
   check-in, you get paged. Free, already paid for.
2. **Test the restore.** A backup never restored is a hope, not a backup. Monthly,
   restore the latest dump into a throwaway Postgres container and assert something
   real — row counts, or that migrations apply cleanly. **Highest-value item on this
   page.**

### PITR: deferred, deliberately

Continuous WAL archiving (pgBackRest / wal-g) buys point-in-time recovery to the
second, at the cost of real complexity. Nightly dumps mean a worst case of **losing up
to 24 hours of stamps**. Acceptable at current volume. Revisit when losing a day of
transactions actually hurts.

---

## 6. Open questions / to resolve when we build the plan

- **Measure the live box first** (blocked this session — needs explicit approval to
  SSH `13.49.70.197`). Replaces §2's estimates with real numbers.
- **Postgres version + data size** — drives dump/restore time and the cutover window.
- **DNS TTL** on `api.stampn.net` / `admin.stampn.net` — must be lowered *ahead* of
  cutover or the switch drags.
- **Cutover shape** — how much downtime is acceptable? Determines whether we do a
  simple dump→restore→repoint, or set up streaming replication for a near-zero-downtime
  switch. Simple is almost certainly right at this size.
- **Apple Wallet is still blocked** on Apple developer approval (no `pass.p12`), so
  `/opt/stampn/secrets` may not yet hold that cert. Confirm what's actually in there
  before we plan to copy it.
- **Rollback**: keep the EC2 box running and DNS switchable until the new host has
  proven itself for a few days. Do not terminate early.

---

## 7. Bottom line

Hetzner is the right move **because the tooling already fits it** — Compose + GHCR +
CI deploy is exactly what a VPS wants; a PaaS would mean rebuilding all of it. It is
*not* the right move merely because it's cheap: the saving is ~$300/year, which is not
what makes or breaks this company.

**Spend part of that saving on the backups above.** Cheap hosting is only a win if the
data survives it. The migration and the backup work should land together — arriving on
Hetzner already protected, rather than promising to get to it later.
