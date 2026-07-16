# Hetzner cutover runbook — EC2 `13.49.70.197` → CX33

> **Status: not started. Pre-flight MEASURED 2026-07-16** against live prod (read-only).
> Companion to [`hetzner-migration-plan.md`](./hetzner-migration-plan.md) (the decision
> record). This is the ordered runbook plan §6 asked for.
>
> **The rule:** the EC2 box stays running and DNS stays switchable until the new host
> has proven itself for days. Nothing here terminates anything.

---

## ⚠️ 0. Two things found during pre-flight that are NOT migration issues

**Fix the first one today. It is unrelated to Hetzner and it is live right now.**

### 0.1 ~~Backups have never run~~ — FIXED on the old box 2026-07-16

**Found:** backups had never run once. Production was unprotected for 17 days.

```
crontab -l          -> no crontab for ubuntu
sudo crontab -l     -> no crontab for root         (cron service: active, but empty)
/opt/stampn/backups/backup.log -> did not exist    ← proof it had never executed
aws s3 ls s3://stampn-db-backups/stampn/
                    -> stampn-2026-06-30-1401.sql.gz    ← ONE file. 17 days old.
```

`infra/README.md` documents the cron install as first-time setup step 4. **It was never
run on the server.** `backup.sh` worked fine — proven by hand on 2026-06-30 — it was
simply never *scheduled*.

**Fixed:** cron installed, and `backup.sh` run by hand. S3 now holds fresh dumps
(`stampn-2026-07-16-2131/2132.sql.gz`, ~50 KB each vs the 14 KB from June).

### 0.1b The PATH trap — why the obvious fix was still broken

Installing the crontab from `infra/README.md` **was not enough, and failed silently:**

```
aws lives at:  /usr/local/bin/aws
cron's PATH:   /usr/bin:/bin        ← /usr/local/bin is NOT in it
/etc/crontab:  no PATH line

$ env -i PATH=/usr/bin:/bin sh -c /opt/stampn/infra/scripts/backup.sh
  ▶ Dumping database ... ✓ Dump OK (51116 bytes)
  ✗ BACKUP_S3 is set but the AWS CLI is not installed — cannot ship off-box
  exit 1
```

The job would have dumped correctly and **failed the S3 upload every single night**,
while the crontab looked perfectly healthy. Exactly what plan §5 warns about: *"A
silently broken cron is worse than no backup, because you believe you're covered."*

Fix — a `PATH` line at the top of the crontab (now installed, and re-verified under
cron's stripped environment → `✓ Off-box copy stored`):

```
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
30 2 * * * /opt/stampn/infra/scripts/backup.sh >> /opt/stampn/backups/backup.log 2>&1
0 4 * * 0 /opt/stampn/infra/scripts/verify_backup.sh >> /opt/stampn/backups/verify.log 2>&1
```

**The lesson for §7: test under `env -i`, not by hand.** A script that passes
interactively can still fail at 02:30. `infra/README.md` now carries both the PATH line
and the verification step.

> Silver lining: the DB is 12 MB and the whole business is 110 stamps / 49 cards, so the
> 17-day-old dump was not as catastrophic a fallback as it sounds. That is luck, not
> design, and it stops being true as you grow.

### 0.2 `admin.stampn.net` is NOT on EC2 — do not flip its DNS

```
api.stampn.net.    300 IN A 13.49.70.197     ← EC2. This one moves.
admin.stampn.net.  300 IN A 82.198.227.4     ← Hostinger (LiteSpeed/hpanel). STAYS.
```

`82.198.227.4` is Hostinger, serving static HTML. The admin console is a built SPA
(`.github/workflows/deploy-admin.yml` → `frontend/admin/`) that calls `api.stampn.net`
from the browser. **`hetzner-migration-plan.md` §"Context" is wrong on this point** —
it lists `admin.stampn.net` as moving off EC2. It is not on EC2 to move.

The `admin.stampn.net { ... }` block in `caddy/Caddyfile:26-34` is **dead config**: DNS
has not pointed at it for some time, so it never fires. Caddy will still try to get a
Let's Encrypt cert for that hostname and fail, because the domain does not resolve to
the box — noisy logs, no impact.

**Consequence: only `api.stampn.net` is flipped at cutover.** Flipping `admin` would
point the console's hostname at a Django-admin redirect and take it down. My earlier
draft of §6 said to flip both. It was wrong.

`ALLOWED_HOSTS` / CSRF / CORS already list `admin.stampn.net` and must keep doing so —
that is the SPA's browser origin calling the API. No change.

---

## 1. Pre-flight — DONE, measured 2026-07-16

Plan §2 flagged its numbers as estimates and said measuring was the first action. Done:

| | Plan §2 estimate | **Measured** |
| --- | --- | --- |
| Containers, total | 1.6–2.2 GB | **~541 MiB** |
| System used / available | — | **1.0 GiB used, 857 MiB available** (of 1.9 GiB) |
| Swap | "the worst place to have it" | **66 MB of 4 GB touched** |
| OOM kills | "the likeliest trigger" (Celery+Pillow) | **zero, in 18 days uptime** |

Per-container: `web` 207 MiB · `worker` 190 MiB · `beat` 99 MiB · `db` 30 MiB ·
`caddy` 12 MiB · `redis` 3 MiB. Load average `0.00`.

**Plan §2 overestimated by ~3-4x, and the t3.small was never actually in trouble.** See
§8 for what that means for the CX33 — short version: nothing to undo.

> Caveat: this is one snapshot at idle. It cannot see a Pillow spike. But *zero OOM
> kills in 18 days on 2 GB* is strong evidence the spikes aren't landing either.

**Cutover window: seconds — once the TTL is lowered (§1.1).** Everything else follows:

| Fact | Value | Why it matters |
| --- | --- | --- |
| Postgres | **16.14** | Matches `postgres:16-alpine` → clean lift, no re-plan |
| DB size | **12 MB** | Dump/restore is instant |
| Biggest tables | `core_stampledger` 110, `core_customercard` 49 | Early-stage; small blast radius |
| `media` volume | **51 files, 3.4 MB** (`stampn_media`) | Baseline to verify the copy against |
| Volume names | `stampn_media`, `stampn_pgdata` (+ caddy, redis) | My assumption confirmed |
| DB name/user | `stampn` / `stampn` | **Not** `kasbana` — the template drifted |
| DNS TTL | ⚠️ **14400 (4 hours)** — see §1.1 | **Gates the cutover.** Must be lowered first |
| Deployed image | `ghcr.io/momenawab/stampn-backend:db8819977f9c` | Pin the new box to this |
| Container DNS | **works** (`sentry.io` → resolved) | Plan §2's `127.0.0.53` quirk; keep the pin |
| Paymob keys | **all empty** → stub mode | Billing is not live; not a cutover concern |

### 1.1 DNS TTL — ⚠️ **NOT DONE. This is now the only thing gating cutover.**

**Measured 2026-07-16, from the authoritative nameserver:**

```
dig +noall +answer @cosmos.dns-parking.com api.stampn.net A
  api.stampn.net.    14400  IN  A  13.49.70.197      ← FOUR HOURS, not 300
```

DNS is hosted at **Hostinger** (`cosmos`/`nova.dns-parking.com`). The domain is
registered at **Namecheap**, but the nameservers delegate to Hostinger — so the record
is edited in Hostinger's hPanel → DNS Zone Editor, not at Namecheap.

> **An earlier draft of this file said the TTL was "already 300 — cut whenever ready."
> That was wrong, and it was the most dangerous error in it.** `dig` from the EC2 box
> returned `300`, but that was a **cached value mid-countdown**, not the record's TTL —
> resolvers decrement the number as the lease ages. **To read a record's real TTL, query
> the authoritative NS (`dig @<ns> <name>`). Never trust a resolver's answer.**

**Why it gates everything:** flip the A record while the TTL is 14400 and resolvers keep
handing out `13.49.70.197` for **up to 4 more hours** — with the writers stopped per §6
step 2. That is not a seconds-long cutover; that is a half-day outage.

```
1. NOW — Hostinger hPanel: api.stampn.net A record, set TTL 300.
   LEAVE THE IP AT 13.49.70.197. You are shortening the lease, not moving anything.
   *** Do NOT touch admin.stampn.net (TTL 1800 -> 82.198.227.4, Hostinger). §0.2 ***

2. WAIT 4 HOURS. Non-negotiable: caches populated before step 1 still hold the old
   14400 lease and won't re-ask until it expires. The wait is what makes the flip fast.

3. Confirm the short TTL is live before cutting over:
     dig +noall +answer @cosmos.dns-parking.com api.stampn.net   # want 300
     dig +noall +answer @8.8.8.8 api.stampn.net                  # want <=300
     dig +noall +answer @1.1.1.1 api.stampn.net                  # want <=300

4. Then run §6. The flip propagates in ~5 minutes.
```

> The 4 hours are dead time, not work — start it and do something else.
> Cutting over at TTL 14400 *is* survivable (the old box serves reads and errors, not
> corruption) but stamps written in the window are lost and rollback stays ambiguous
> for 4 hours. Not worth it. Wait.

### Apple Wallet certs — plan §6's open question, resolved

All three exist, already owned by uid **10001**:

```
Certificates.p12   3299 B   10001:10001    ← NOT "pass.p12"
google-sa.json     2361 B   10001:10001
wwdr.pem           1562 B   10001:10001
APPLE_PASS_CERT_PATH=/secrets/Certificates.p12   ← .env matches the real filename
APPLE_TEAM_ID=W96BM9T4C3     APPLE_PASS_TYPE_ID=pass.net.stampn.loyalty
```

Plan §6 assumed Apple was still blocked and `pass.p12` might not exist. It's there under
a different name, and `.env` already points at it. **Copy `/opt/stampn/secrets` wholesale
(§4) and don't "fix" the filename** — the env var is the contract, and it's correct.

---

## 2. Provision the CX33 — firewall first

### 2.1 Hetzner Cloud Firewall — before the box is reachable

Plan §4 is right twice: this is the one thing that genuinely changes (AWS attaches a
deny-by-default Security Group; Hetzner attaches nothing), and it must be the **Cloud
Firewall, not `ufw`** — Docker writes its own iptables rules straight through ufw.

| Direction | Port | Source |
| --- | --- | --- |
| in | 22 | **your IP only** |
| in | 80 | any (ACME + redirect) |
| in | 443 | any |
| in | anything else | deny |

SSH brute-forcing starts minutes after the box goes live.

### 2.2 Non-root deploy user

Hetzner's Ubuntu image gives you `root`; plan §4 wants `PermitRootLogin no`. So
`EC2_USER` cannot stay `ubuntu`-on-EC2 semantics — make a `deploy` user.

```bash
ssh root@<NEW_IP> '
  adduser --disabled-password --gecos "" deploy
  usermod -aG sudo deploy
  mkdir -p /home/deploy/.ssh && cp /root/.ssh/authorized_keys /home/deploy/.ssh/
  chown -R deploy:deploy /home/deploy/.ssh && chmod 700 /home/deploy/.ssh
'
```

### 2.3 Harden SSH

```bash
ssh root@<NEW_IP> '
  sed -i "s/^#*PasswordAuthentication.*/PasswordAuthentication no/" /etc/ssh/sshd_config
  sed -i "s/^#*PermitRootLogin.*/PermitRootLogin no/"               /etc/ssh/sshd_config
  systemctl restart ssh
  apt-get update && apt-get install -y fail2ban unattended-upgrades
  systemctl enable --now fail2ban
'
```

> **Confirm `ssh deploy@<NEW_IP>` works in a second terminal BEFORE closing the root
> session.** Locking yourself out of a fresh box costs a rebuild.

### 2.4 Run the existing provisioner

```bash
ssh deploy@<NEW_IP> 'bash -s' < infra/scripts/provision.sh
ssh deploy@<NEW_IP>   # log out/in so the docker group applies
```

Swap: `provision.sh` adds 4 GB, sized for a 2 GB box. Measured usage is 66 MB. On 8 GB
it's pure insurance — harmless, keep it, `vm.swappiness=10` means it's never touched.

---

## 3. Repo changes — commit before cutover

1. **`infra/caddy/Caddyfile:37`** — `http://13.49.70.197` → `http://<NEW_IP>`. This is
   the §5.3 bring-up path, so it must be right *before* verification.
2. **`infra/scripts/provision.sh`** — add the AWS CLI (`awscli` v2). `backup.sh:42-45`
   hard-fails without it. Prod has `aws-cli/2.35.12` **from the EC2 AMI, not from
   provisioning** — a fresh Hetzner box will not have it.
3. **`infra/.env.prod.example:10-12`** — stale comment says the Caddyfile uses
   `api.kasbana.net`/`admin.kasbana.net`. It uses `stampn.net`. Also `POSTGRES_DB`/
   `POSTGRES_USER` say `kasbana`; prod is `stampn`. Rebrand leftovers (`a6a0c7c`).

Optional cleanup, not cutover-blocking: drop the dead `admin.stampn.net` block
(`Caddyfile:26-34`, see §0.2), and `compose.prod.yml:89` still passes `DOMAIN: ${DOMAIN}`
which `.env` no longer defines (harmless compose warning).

---

## 4. Seed `.env` and secrets

```bash
# .env — copy from the OLD box. Do NOT rebuild from the template (it has drifted).
ssh -i ~/Downloads/googleone.pem ubuntu@13.49.70.197 'sudo cat /opt/stampn/infra/.env' > /tmp/prod.env
scp /tmp/prod.env deploy@<NEW_IP>:/opt/stampn/infra/.env
shred -u /tmp/prod.env    # SECRET_KEY (64c), POSTGRES_PASSWORD (32c), SENTRY_DSN just transited your laptop

# ALLOWED_HOSTS currently ends in: ...,13.49.70.197,localhost,127.0.0.1
# Add <NEW_IP> so the §5.3 bare-IP bring-up isn't rejected by Django.
ssh deploy@<NEW_IP> 'nano /opt/stampn/infra/.env'
```

```bash
# secrets/ — all three files confirmed present (§1).
ssh -i ~/Downloads/googleone.pem ubuntu@13.49.70.197 'sudo tar -C /opt/stampn/secrets -czf - .' | \
  ssh deploy@<NEW_IP> 'sudo tar -C /opt/stampn/secrets -xzf -'

# Re-assert uid 10001 — infra/README.md:110-113 says do this after any host migration.
ssh deploy@<NEW_IP> '
  sudo chown -R 10001:10001 /opt/stampn/secrets
  sudo chmod 750 /opt/stampn/secrets
  sudo chmod 640 /opt/stampn/secrets/*
'
```

> Skip the `chown` and you get the failure documented at `infra/README.md:120-125`:
> `google_wallet_check` passes, but the worker throws `PermissionError` on
> `/secrets/google-sa.json` and passes silently stop updating after a stamp.

---

## 5. Dry run — ✅ EXECUTED AND PASSED 2026-07-16

**Done. The CX33 (`204.168.234.205`) is provisioned, loaded, and verified.** Everything
below has been run; §6 re-runs §5.1 + §5.2 with fresh data at cutover.

| Step | Result |
| --- | --- |
| Firewall attached | ✅ 5432 flips refuse(0.15s) → drop(75s timeout) |
| SSH hardened | ✅ root denied, password auth off, fail2ban **4 IPs already banned** |
| `provision.sh` | ✅ Docker 29.6.2, Compose 5.3.1, AWS CLI 2.36.1, 4 GB swap |
| `.env` copied | ✅ md5 identical, 35 lines, + `204.168.234.205` in `ALLOWED_HOSTS` |
| Secrets copied | ✅ all 3 md5-identical, perms preserved, uid 10001 |
| DB restored | ✅ 12 MB; **110 stamps / 124 migrations / 264 perms** — exact match |
| Media copied | ✅ **51 files / 3.4 MB; md5-of-md5s identical** |
| Stack up | ✅ all six containers, `web` + `db` healthy |
| Container DNS | ✅ resolves (plan §2's `127.0.0.53` quirk — keep the pin) |
| Google Wallet | ✅ **"Authenticated to the Wallet API"** — secrets readable by uid 10001 |
| Health | ✅ `200 {"status": "ok", "service": "stampn-backend"}` |

**Caddy is deliberately STOPPED** on the new box (see the rate-limit note in §5.3).
The other five containers are up. Nothing is serving public traffic; DNS still points
at EC2 and prod is untouched.

Two findings that changed this document: the bare-IP `curl` returns **301, not 200**
(and always did — the old box does too), and Caddy **burns ACME rate limits** whenever
it runs before DNS moves. Both are written up below.

<details>
<summary>Original instructions (re-run these at cutover)</summary>

12 MB of DB and 3.4 MB of media means this is fast. Do it anyway: it surfaces surprises
while nothing is at stake. §6 then re-runs these exact commands with fresh data.

### 5.1 Database

```bash
ssh -i ~/Downloads/googleone.pem ubuntu@13.49.70.197 \
  'cd /opt/stampn/infra && set -a; . ./.env; set +a; \
   docker compose -f compose.prod.yml exec -T db \
     pg_dump -U "$POSTGRES_USER" --no-owner --no-acl "$POSTGRES_DB" < /dev/null | gzip' > /tmp/prod.sql.gz

scp /tmp/prod.sql.gz deploy@<NEW_IP>:/opt/stampn/backups/

ssh deploy@<NEW_IP> 'cd /opt/stampn/infra && set -a; . ./.env; set +a; \
  docker compose -f compose.prod.yml up -d db && sleep 10 && \
  gunzip -c /opt/stampn/backups/prod.sql.gz | \
    docker compose -f compose.prod.yml exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

> **`< /dev/null` on every `docker compose exec -T` that isn't being piped into.**
> Learned the hard way during recon: `exec -T` still attaches stdin, so over an
> `ssh 'bash -s' < script` pipe it will silently eat the rest of the script.

### 5.2 Media — the step with no safety net

Nothing backs this up. Verify counts; don't trust a clean exit. **Baseline: 51 files, 3.4 MB.**

```bash
ssh -i ~/Downloads/googleone.pem ubuntu@13.49.70.197 \
  'sudo docker run --rm -v stampn_media:/src alpine tar -C /src -czf - .' > /tmp/media.tar.gz

ssh deploy@<NEW_IP> 'docker volume create stampn_media && \
  docker run --rm -i -v stampn_media:/dst alpine tar -C /dst -xzf -' < /tmp/media.tar.gz

# Must print 51 on both.
ssh -i ~/Downloads/googleone.pem ubuntu@13.49.70.197 'sudo docker run --rm -v stampn_media:/m alpine find /m -type f | wc -l'
ssh deploy@<NEW_IP> 'docker run --rm -v stampn_media:/m alpine find /m -type f | wc -l'
```

### 5.3 Stack up on plain HTTP, verified

DNS still points at EC2, so Caddy cannot get a cert (ACME needs the domain to resolve
here). That's what the bare-IP block from §3 is for.

```bash
ssh deploy@<NEW_IP> 'cd /opt/stampn/infra && \
  echo <GHCR_TOKEN> | docker login ghcr.io -u <GHCR_USER> --password-stdin && \
  IMAGE_TAG=db8819977f9c bash scripts/deploy.sh'
```

> **Pin `IMAGE_TAG` to `db8819977f9c`** — what prod runs today (§1). Using `latest`
> deploys whatever CI last built, which mixes an untested code change into a host
> migration.

**Verify — and `curl` from your laptop will NOT return 200. That is correct.**

`HTTPS_ENABLED=true` → Django's `SECURE_SSL_REDIRECT` → any request Django believes is
plain HTTP gets a **301 to `https://<NEW_IP>/`**, which has no cert. Sending
`-H "X-Forwarded-Proto: https"` does **not** help: Caddy's `reverse_proxy` *overwrites*
that header with the real request scheme (`http`). You cannot spoof it from outside.

```bash
curl -o /dev/null -w '%{http_code}' -H "X-Forwarded-Proto: https" http://<NEW_IP>/api/health/
# -> 301.  MEASURED: the OLD EC2 box returns 301 on the identical call. Not a regression.
```

The compose healthcheck (`compose.prod.yml:42-43`) works because it runs **inside** the
container against `localhost:8000`, never touching Caddy. So test the way it does:

```bash
docker compose -f compose.prod.yml exec -T web python -c "
import urllib.request
r = urllib.request.Request('http://localhost:8000/api/health/', headers={'X-Forwarded-Proto':'https'})
resp = urllib.request.urlopen(r); print(resp.status, resp.read().decode())
" < /dev/null
# -> 200 {"status": "ok", "service": "stampn-backend"}   (identical on both boxes)
```

Or just read `docker compose ps`: `web` reporting **`(healthy)`** *is* that check passing.

> Do **not** "fix" the 301 by setting `HTTPS_ENABLED=false`. It works, and forgetting to
> flip it back breaks Apple Wallet, which requires real HTTPS.

### ⚠️ Stop Caddy during the dry run — it burns Let's Encrypt rate limits

The moment Caddy starts, it tries to obtain a cert for `api.stampn.net`. During the dry
run DNS still points at **EC2**, so the ACME challenge is served by the *old* box, which
404s, and validation fails — every 120s, forever.

```
"could not get certificate from issuer" ... "13.49.70.197: Invalid response from
https://api.stampn.net/.well-known/acme-challenge/...: 404"
```

**Measured: 6 failed attempts in ~3 minutes** before this was caught. Let's Encrypt
allows **5 failed validations per hostname per account per hour**. Burn them here and
the real cutover can be rate-limited and unable to issue — turning a seconds-long
switch into an hour of downtime.

```bash
# Right after deploy.sh during a DRY RUN, stop Caddy. Everything else stays up.
docker compose -f compose.prod.yml stop caddy
```

The limit resets hourly, so a burned dry run is recoverable — just don't cut over
within the hour. **§6 orders this correctly: DNS first, Caddy second.**

</details>

Also confirm:

- `docker compose -f compose.prod.yml ps` → all six up, `web`+`db` healthy
- Container DNS: `... exec -T web python -c "import socket; print(socket.gethostbyname('sentry.io'))" < /dev/null`
- `... exec -T web python manage.py google_wallet_check < /dev/null`
- `core_stampledger` = **110**, `core_customercard` = **49** (must match §1)
- `docker stats --no-stream` — first real numbers on 8 GB

---

## 6. Cutover

**Ordering rule: DNS is flipped BEFORE Caddy starts.** Caddy cannot get a cert until
`api.stampn.net` resolves here, and every attempt it makes beforehand is a *failed*
validation against the hourly rate limit (§5.3). So Caddy stays stopped until the A
record moves. This is the opposite of the obvious order and it matters.

```
1. Announce a short read-only window. (12 MB DB → seconds, not minutes.)
2. OLD box: stop the writers, leave the DB up.
     docker compose -f compose.prod.yml stop web worker beat
3. Re-run §5.1 + §5.2 with fresh data. Drop/recreate the DB on the new box first so the
   restore lands on a clean schema (see restore.sh for the pattern).
4. NEW box: deploy, then IMMEDIATELY stop Caddy (DNS hasn't moved yet — see §5.3):
     IMAGE_TAG=db8819977f9c bash scripts/deploy.sh
     docker compose -f compose.prod.yml stop caddy
5. Verify with Caddy still DOWN — everything worth checking is internal anyway:
     docker compose -f compose.prod.yml ps               # web (healthy)
     ... exec -T web python manage.py google_wallet_check < /dev/null
     row counts == 110 stamps / 49 cards / 124 migrations
6. Flip DNS — api.stampn.net  A -> 204.168.234.205
   *** PRECONDITION: §1.1 done and the 4h wait elapsed. Verify FIRST: ***
     dig +noall +answer @cosmos.dns-parking.com api.stampn.net   # MUST show 300
   *** DO NOT TOUCH admin.stampn.net — it is Hostinger, not EC2. See §0.2. ***
   Wait for it to actually move before step 7:
     until dig +short @8.8.8.8 api.stampn.net | grep -q 204.168.234.205; do sleep 5; done
7. NOW start Caddy. Its first ACME attempt should succeed:
     docker compose -f compose.prod.yml start caddy
     docker compose -f compose.prod.yml logs -f caddy    # "certificate obtained"
   Caddy will ALSO fail for admin.stampn.net (dead block, §0.2). Expected. Ignore.
8. curl -sI https://api.stampn.net/api/health/                  # 200, server: gunicorn
   curl -sI https://admin.stampn.net/                           # 200, server: LiteSpeed (untouched)
9. Stamp one card end-to-end and confirm the wallet pass updates (exercises worker +
   /secrets + outbound DNS in one shot — the three things most likely to break).
10. OLD box: leave web/worker/beat STOPPED, box ALIVE. Do not terminate.
```

> **Why stop the writers but not the DB:** `pg_dump` is consistent on a live DB, but a
> stamp written between the dump and the DNS flip lands on the old box and vanishes.

> **Both boxes briefly answer for `api.stampn.net`** while DNS propagates. The old one
> has no writers — it serves reads and errors, not corruption.

---

## 7. Post-cutover — not migrated until backups run

### Issue #1, now **confirmed** rather than suspected

```
Arn: arn:aws:sts::<ACCOUNT>:assumed-role/stampn-ec2-backups/i-0feda2fc4f0e76731
~/.aws/credentials: does not exist
```

An **EC2 instance profile** (role `stampn-ec2-backups`), which Hetzner has no equivalent
for. `backup.sh:47`'s `aws s3 cp` authenticates via IMDS metadata that will not exist on
the new box. The AWS CLI itself came from the AMI, not from `provision.sh` (§3, item 2).

```bash
# 1. Create a real IAM USER (not a role) with s3:PutObject on stampn-db-backups. Keys.
ssh deploy@<NEW_IP> 'aws configure'          # needs the awscli from §3

# 2. BACKUP_S3 survives the .env copy — confirm: s3://stampn-db-backups/stampn
ssh deploy@<NEW_IP> 'grep BACKUP_S3 /opt/stampn/infra/.env'

# 3. Run it by hand — want the line: ✓ Off-box copy stored
ssh deploy@<NEW_IP> '/opt/stampn/infra/scripts/backup.sh'

# 4. Cron. It does NOT come across with the infra sync. THIS IS THE STEP THAT WAS
#    MISSED ON THE OLD BOX (§0.1) — do not miss it twice. The PATH line is not
#    optional; without it the S3 upload fails nightly and silently (§0.1b).
ssh deploy@<NEW_IP> '(echo "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin";
   crontab -l 2>/dev/null | grep -v "^PATH=";
   echo "30 2 * * * /opt/stampn/infra/scripts/backup.sh >> /opt/stampn/backups/backup.log 2>&1";
   echo "0 4 * * 0 /opt/stampn/infra/scripts/verify_backup.sh >> /opt/stampn/backups/verify.log 2>&1"
  ) | crontab -'

# 5. Prove it under cron's ACTUAL environment — not by hand. §0.1b is the whole
#    reason: by-hand passes, cron fails, and nothing tells you.
ssh deploy@<NEW_IP> 'env -i SHELL=/bin/sh PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
   HOME=/home/deploy LOGNAME=deploy USER=deploy \
   /bin/sh -c /opt/stampn/infra/scripts/backup.sh'
# Want "✓ Off-box copy stored", then confirm the object actually landed:
ssh deploy@<NEW_IP> 'aws s3 ls s3://stampn-db-backups/stampn/ | tail -3'
```

**Keeping the AWS S3 bucket is correct, not lazy.** Plan §5 wants the offsite copy at a
*different company* than the host. Hetzner box → AWS S3 satisfies that with zero rewrite.
The restic/B2 design in plan §5 solved a problem that only existed while the host was
also AWS. Revisit only if AWS goes away entirely.

### Then redirect deploys

| Secret | New value |
| --- | --- |
| `EC2_HOST` | `<NEW_IP>` |
| `EC2_USER` | `deploy` (was `ubuntu`) |
| `EC2_SSH_KEY` | private key matching §2.2's `authorized_keys` |

Names stay `EC2_*` — renaming touches `deploy-prod.yml` for zero benefit. Promote
`dev` → `prod` and confirm the pipeline lands on Hetzner. **Not done until a CI deploy
has succeeded against the new box.**

Still open from plan §5: **nothing alerts on backup failure** — which is exactly why
§0.1 went unnoticed for 17 days. Sentry Cron Monitoring is free and already paid for.
Not a cutover blocker; is the reason this class of bug is invisible.

---

## 8. Deliberately NOT doing

- **Re-sizing the CX33.** Measurement (§1) says containers use ~541 MiB and the 2 GB
  t3.small has had zero OOM kills in 18 days. CX22 (4 GB) would have been ample; CX33
  (8 GB) is ~8x the real footprint. **It costs ~€4/mo more than needed — keep it and
  move on.** Rebuilding to save €4 is not worth a day of your time, and the headroom
  absorbs the Pillow spikes this snapshot couldn't see.
- **Raising gunicorn workers / Celery concurrency.** Now genuinely justified by the
  spare RAM — and still not now. Move like-for-like, or a perf regression and a host
  change are tangled and you can't tell which broke it. Separate commit, after §1's
  numbers exist for the new box.
- **Postgres tuning.** Same reasoning. 12 MB DB — it fits in RAM regardless.
- **ARM/CAX.** Plan §3 settled it: GHCR image is amd64-only. CX33 is x86.
- **Terminating EC2.** Plan §6. Stays until the new box has days of proving.
- **Renaming the `Certificates.p12` file** (§1). `.env` points at it correctly.
- **Domain work.** `a6a0c7c` moved Kasbana → Stampn; `stampn.net` is current.

---

## 9. Rollback

Cheap, because nothing was destroyed:

```
1. Flip DNS back: api.stampn.net A -> 13.49.70.197     (300s TTL)
2. OLD box: docker compose -f compose.prod.yml start web worker beat
3. Done — it holds the data as of the §6 freeze.
```

**The one-way door:** stamps written to the *new* box after cutover don't exist on the
old one. Rolling back more than a few minutes past step 6 loses that window. Past ~an
hour, fix forward instead — or dump the new box and restore onto the old, which is this
runbook in reverse.
