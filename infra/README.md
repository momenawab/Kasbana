# infra/ — DevOps & deployment

Infrastructure-as-code for Kasbana. Lives in the `dev` monorepo and is published
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
scripts/backup.sh      nightly pg_dump → /opt/kasbana/backups (+ optional S3)
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
     to `ghcr.io/momenawab/kasbana-backend:<sha>` + `:latest`;
   - copies `infra/` to the EC2 box and runs `scripts/deploy.sh`, which pulls the
     image, applies migrations, and rolls `web`/`worker`/`beat`.

The t3.small **never builds** — it only pulls. That keeps the 2 GB box stable.

## First-time setup (once per server)

```bash
# 1. Provision the host (Docker + swap + /opt/kasbana)
ssh -i key.pem ubuntu@13.49.70.197 'bash -s' < scripts/provision.sh

# 2. Put secrets on the server
scp -i key.pem .env.prod.example ubuntu@13.49.70.197:/opt/kasbana/infra/.env
ssh -i key.pem ubuntu@13.49.70.197 'nano /opt/kasbana/infra/.env'   # fill real values

# 3. Add GitHub Actions secrets (used by deploy-prod.yml):
#    EC2_HOST=13.49.70.197   EC2_USER=ubuntu   EC2_SSH_KEY=<contents of key.pem>

# 4. Schedule nightly backups
ssh -i key.pem ubuntu@13.49.70.197 \
  '(crontab -l 2>/dev/null; echo "30 2 * * * /opt/kasbana/infra/scripts/backup.sh >> /opt/kasbana/backups/backup.log 2>&1") | crontab -'
```

Then promote to `prod` to ship.

## GitHub Actions secrets

| Secret | Value |
|---|---|
| `EC2_HOST` | `13.49.70.197` |
| `EC2_USER` | `ubuntu` (Amazon Linux: `ec2-user`) |
| `EC2_SSH_KEY` | full contents of the `.pem` private key |

`GITHUB_TOKEN` (auto-provided) is used to push to and pull from GHCR.

## Wallet credentials (Phase 1.1)

Certs/keys live in `/opt/kasbana/secrets` (mounted read-only into the
containers at `/secrets`). The app runs as uid **10001**, so the files must be
readable by it:

```bash
# Google service-account key
scp -i key.pem google-sa.json ubuntu@13.49.70.197:/opt/kasbana/secrets/
ssh -i key.pem ubuntu@13.49.70.197 \
  'sudo chmod 755 /opt/kasbana/secrets && \
   sudo chown 10001:10001 /opt/kasbana/secrets/google-sa.json && \
   sudo chmod 600 /opt/kasbana/secrets/google-sa.json'
```

Then set in `infra/.env`: `GOOGLE_WALLET_ISSUER_ID`, `GOOGLE_SA_KEY_PATH=/secrets/google-sa.json`
(Apple: `APPLE_PASS_CERT_PATH=/secrets/pass.p12`, `APPLE_WWDR_CERT_PATH=/secrets/wwdr.pem`).
Verify with: `docker compose -f compose.prod.yml exec web python manage.py google_wallet_check`.

## HTTPS / Apple Wallet

Apple Wallet requires valid HTTPS on a real hostname. Point an A record
(e.g. `api.kasbana.net`) at the box, set `DOMAIN=api.kasbana.net` in
`infra/.env`, and Caddy provisions a Let's Encrypt cert automatically. Until DNS
is ready, `DOMAIN=:80` serves plain HTTP for bring-up.

## Manual ops on the server

```bash
cd /opt/kasbana/infra
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
