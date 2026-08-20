# infra/ — DevOps & deployment

Infrastructure-as-code for Stampn. Lives in the `dev` monorepo and is published
to the **`infra`** branch by `distribute.yml`. **Edit here on `dev`, never on the
generated `infra` branch.**

## What's here

```
docker/Dockerfile      backend image (built in CI, context = ../backend)
compose.prod.yml       prod stack: web · worker · beat · postgres · redis · caddy
caddy/Caddyfile        reverse proxy + automatic HTTPS
.env.prod.example      template for the server's infra/.env (secrets — not committed)
scripts/provision.sh   one-time host setup (Docker + 4GB swap + dirs)
scripts/deploy.sh      pull image → migrate → roll services (run on the server)
scripts/backup.sh      nightly pg_dump → /opt/stampn/backups → off-box (S3)
scripts/verify_backup.sh  weekly: restore the latest dump into a throwaway DB
scripts/restore.sh     disaster recovery: restore a dump into the live DB
```

## How deployment works

1. **Build & deploy are gated by the `prod` branch.** Pushing to `dev` only runs
   CI; it does **not** deploy. To release, **promote `dev` → `prod`**:

   ```bash
   git checkout prod && git merge --ff-only dev && git push origin prod
   git checkout dev
   ```

2. Pushing `prod` triggers `.github/workflows/deploy-prod.yml`:
   - builds `infra/docker/Dockerfile` (context `backend/`) and pushes the image
     to `ghcr.io/momenawab/stampn-backend:<sha>` + `:latest`;
   - copies `infra/` to the EC2 box and runs `scripts/deploy.sh`, which pulls the
     image, applies migrations, and rolls `web`/`worker`/`beat`.

The t3.small **never builds** — it only pulls. That keeps the 2 GB box stable.

## First-time setup (once per server)

```bash
# 1. Provision the host (Docker + swap + /opt/stampn)
ssh -i key.pem ubuntu@13.49.70.197 'bash -s' < scripts/provision.sh

# 2. Put secrets on the server
scp -i key.pem .env.prod.example ubuntu@13.49.70.197:/opt/stampn/infra/.env
ssh -i key.pem ubuntu@13.49.70.197 'nano /opt/stampn/infra/.env'   # fill real values

# 3. Add GitHub Actions secrets (used by deploy-prod.yml):
#    EC2_HOST=13.49.70.197   EC2_USER=ubuntu   EC2_SSH_KEY=<contents of key.pem>

# 4. Schedule backups (nightly dump + weekly verified restore)
#    DO NOT SKIP THIS. It was missed on the first server and backups silently
#    never ran for 17 days — the failure is invisible until you need a restore.
#    The PATH line is REQUIRED: cron's default PATH is /usr/bin:/bin, which omits
#    /usr/local/bin where the AWS CLI lives. Without it backup.sh dumps fine and
#    then exits 1 at the S3 upload, every night, off-box copy never happening.
ssh -i key.pem ubuntu@<host> \
  '(echo "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin";
    crontab -l 2>/dev/null | grep -v "^PATH=";
    echo "30 2 * * * /opt/stampn/infra/scripts/backup.sh >> /opt/stampn/backups/backup.log 2>&1";
    echo "0 4 * * 0 /opt/stampn/infra/scripts/verify_backup.sh >> /opt/stampn/backups/verify.log 2>&1"
   ) | crontab -'

# 5. VERIFY it — a crontab that exists is not a backup that runs. Simulate cron's
#    stripped environment; anything less can pass by hand and fail at 02:30.
ssh -i key.pem ubuntu@<host> \
  'env -i SHELL=/bin/sh PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
     HOME=/home/ubuntu LOGNAME=ubuntu USER=ubuntu \
     /bin/sh -c /opt/stampn/infra/scripts/backup.sh'
# Want: "✓ Off-box copy stored". Then confirm the object landed:
#   aws s3 ls s3://stampn-db-backups/stampn/
```

Then promote to `prod` to ship.

## Backups & disaster recovery

The DB is the only irreplaceable state. Three scripts cover it:

- **`backup.sh`** (nightly, 02:30) — `pg_dump | gzip` to `/opt/stampn/backups`,
  integrity-checks the dump, ships it **off-box**, and prunes local copies >7 days.
- **`verify_backup.sh`** (weekly, Sun 04:00) — restores the *latest* dump into a
  throwaway Postgres container and asserts it loads (migrations + `core_merchant`).
  A backup you've never restored is a guess; this makes it a guarantee. Never
  touches prod.
- **`restore.sh <dump.sql.gz>`** — disaster recovery. Resets the schema and
  restores a dump into the **live** DB (destructive; asks you to type the DB name).

**Off-box storage (do this — a backup only on the same server is not a backup):**
set in `infra/.env`:

```bash
BACKUP_S3=s3://your-bucket/stampn
```

and give the box an IAM role / `aws configure` with `s3:PutObject` on that bucket.
`backup.sh` then uploads each dump and **fails loudly** if it can't (cron logs it).
Without `BACKUP_S3` the script still runs but warns that the dump is on-box only.

**To recover** (e.g. server lost): provision a fresh box, pull a dump from S3
(`aws s3 cp s3://your-bucket/stampn/<file> .`), then `scripts/restore.sh <file>`.

## GitHub Actions secrets

| Secret | Value |
|---|---|
| `EC2_HOST` | `13.49.70.197` |
| `EC2_USER` | `ubuntu` (Amazon Linux: `ec2-user`) |
| `EC2_SSH_KEY` | full contents of the `.pem` private key |

`GITHUB_TOKEN` (auto-provided) is used to push to and pull from GHCR.

## Wallet credentials (Phase 1.1)

Certs/keys live in `/opt/stampn/secrets` (mounted read-only into the
containers at `/secrets`). The app runs as uid **10001**, so the files must be
readable by it:

```bash
# Google service-account key
scp -i key.pem google-sa.json ubuntu@13.49.70.197:/opt/stampn/secrets/
# Make EVERY secret readable by uid 10001 (not just the Google key — the Apple
# cert/key live here too). Re-run this after any host migration / re-copy.
ssh -i key.pem ubuntu@13.49.70.197 \
  'sudo chown -R 10001:10001 /opt/stampn/secrets && \
   sudo chmod 750 /opt/stampn/secrets && \
   sudo chmod 640 /opt/stampn/secrets/*'
```

Then set in `infra/.env`: `GOOGLE_WALLET_ISSUER_ID`, `GOOGLE_SA_KEY_PATH=/secrets/google-sa.json`
(Apple: `APPLE_PASS_CERT_PATH=/secrets/pass.p12`, `APPLE_WWDR_CERT_PATH=/secrets/wwdr.pem`).
Verify with: `docker compose -f compose.prod.yml exec web python manage.py google_wallet_check`.

> **Troubleshooting — passes don't update after a stamp.** If `google_wallet_check`
> passes but the worker logs `PermissionError: [Errno 13] ... '/secrets/google-sa.json'`,
> the secrets aren't owned by uid 10001 (common right after a host migration that
> re-copied them as root). Re-run the `chown -R 10001:10001` block above; no
> redeploy needed — the next stamp re-runs `wallets.tasks.push_pass_update` and
> reads the key live.

## HTTPS / Apple Wallet

Apple Wallet requires valid HTTPS on a real hostname. Point an A record
(e.g. `api.stampn.net`) at the box, set `DOMAIN=api.stampn.net` in
`infra/.env`, and Caddy provisions a Let's Encrypt cert automatically. Until DNS
is ready, `DOMAIN=:80` serves plain HTTP for bring-up.

## Manual ops on the server

```bash
cd /opt/stampn/infra
docker compose -f compose.prod.yml ps
docker compose -f compose.prod.yml logs -f web
docker compose -f compose.prod.yml exec web python manage.py createsuperuser
IMAGE_TAG=latest bash scripts/deploy.sh
```

## Notes for the t3.small

- 4 GB swap is added by `provision.sh` — keep it.
- Postgres + Redis + app + Caddy fit in ~2 GB for light traffic. When traffic
  grows, the first move is Postgres → managed RDS, then bump the instance.
- Region is currently eu-north-1 (Stockholm). For Egypt-first latency,
  me-central-1 (UAE) / me-south-1 (Bahrain) are closer.
