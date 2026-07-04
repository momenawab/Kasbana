# Apple Wallet — Go-Live Setup

> How to turn on Apple Wallet passes in production. The code path is complete and
> tested; it stays dormant until the signing certificates are provided. This is
> the runbook for producing those certs and wiring them in.
>
> Grounded in the actual implementation: `backend/wallets/apple/config.py`
> (loads the certs), `signing.py` (builds the `.pkpass`), `apns.py` (live push).

## What the backend needs

`config.py` loads, at startup, from `settings.WALLET["APPLE"]`:

| Setting (env var) | What it is | Format |
|---|---|---|
| `PASS_TYPE_ID` (`APPLE_PASS_TYPE_ID`) | The registered Pass Type ID | string, e.g. `pass.net.stampn.loyalty` |
| `TEAM_ID` (`APPLE_TEAM_ID`) | Your Apple Developer Team ID | 10-char string |
| `PASS_CERT_PATH` (`APPLE_PASS_CERT_PATH`) | Pass-signing cert **+ private key** | **`.p12`** (PKCS#12) |
| `PASS_CERT_PASSWORD` (`APPLE_PASS_CERT_PASSWORD`) | Password on the `.p12` | string |
| `WWDR_CERT_PATH` (`APPLE_WWDR_CERT_PATH`) | Apple WWDR intermediate | **PEM** (`.pem`) |
| `APNS_USE_SANDBOX` (`APNS_USE_SANDBOX`) | Use APNs sandbox host | `true`/`false` (prod = `false`) |

When `PASS_CERT_PATH` is empty or missing, the wallet layer no-ops and
`POST /enroll/{token}` returns a null `apple_pass_url` — which is why only the
Google button shows today. The **same `.p12`** is reused as the APNs credential
for live pass updates (`apns.py`), so one certificate covers both.

## One-time setup

### 1. Confirm the Apple Developer account
Enroll in the Apple Developer Program ($99/yr). Company enrollment requires a
D-U-N-S number and authority to bind the org; individual enrollment is simpler.
Approve the confirmation email, then verify access to **Certificates,
Identifiers & Profiles**.

### 2. Team ID
Membership details → copy the 10-character Team ID → `APPLE_TEAM_ID`.

### 3. Register a Pass Type ID
Identifiers → **+** → **Pass Type IDs** → register e.g. `pass.net.stampn.loyalty`
(this repo's default) → set `APPLE_PASS_TYPE_ID` to the exact same string.

> ⚠️ It **must** match the setting. The generated `pass.json` stamps
> `passTypeIdentifier`/`teamIdentifier` from these settings; any mismatch with
> the signing cert makes iOS refuse to install the pass.

### 4. Create the pass-signing certificate (on a Mac)
1. Keychain Access → Certificate Assistant → **Request a Certificate from a
   Certificate Authority** → save the `.certSigningRequest` to disk.
2. In the portal, open the Pass Type ID → **Create Certificate** → upload the
   CSR → download the resulting `.cer`.
3. Double-click the `.cer` to import into Keychain. Find it, expand to reveal the
   **private key**, right-click → **Export** as `pass.p12`, set a password.
4. → `APPLE_PASS_CERT_PATH` (the file) + `APPLE_PASS_CERT_PASSWORD`.

### 5. WWDR intermediate certificate
Download the current **G4** "Worldwide Developer Relations" certificate from
Apple's PKI page (DER `.cer`). The code loads PEM, so convert:

```
openssl x509 -inform der -in AppleWWDRCAG4.cer -out wwdr.pem
```

→ `APPLE_WWDR_CERT_PATH`. It must be the WWDR cert that chains to your signing
cert (G4 as of this writing).

### 6. Provision + wire the env
The prod stack already mounts a host secrets dir read-only into every app
container: `/opt/stampn/secrets` on the box → `/secrets` in the container (see
`infra/compose.prod.yml`). So:

1. Copy both files to **`/opt/stampn/secrets/`** on the prod box (owned by the
   container app UID `10001`, mode `640` — matching the Google SA key):
   ```
   scp -i key.pem Certificates.p12 wwdr.pem ubuntu@<box>:/tmp/
   ssh -i key.pem ubuntu@<box> '
     sudo mv /tmp/Certificates.p12 /tmp/wwdr.pem /opt/stampn/secrets/ &&
     sudo chown 10001:10001 /opt/stampn/secrets/Certificates.p12 /opt/stampn/secrets/wwdr.pem &&
     sudo chmod 640 /opt/stampn/secrets/Certificates.p12 /opt/stampn/secrets/wwdr.pem'
   ```
2. Add to the stack's env file (**`/opt/stampn/infra/.env`**, the `env_file`
   compose loads; not tracked in git, so it survives deploys) — paths are the
   **in-container** `/secrets/…`:
   ```
   APPLE_PASS_TYPE_ID=pass.net.stampn.loyalty
   APPLE_TEAM_ID=W96BM9T4C3
   APPLE_PASS_CERT_PATH=/secrets/Certificates.p12
   APPLE_PASS_CERT_PASSWORD=          # empty — the .p12 is passwordless (verified)
   APPLE_WWDR_CERT_PATH=/secrets/wwdr.pem
   APNS_USE_SANDBOX=false
   ```
3. Redeploy (re-pull + `up -d`, or re-run the prod deploy). The wallet layer
   auto-detects the certs; `apple_pass_url` starts coming back non-null.

> **Verified 2026-07-04** against the exact loaders the backend uses
> (`cryptography` pkcs12 + `load_pem_x509_certificate`): the `.p12` contains the
> private key + cert, loads with **no password**, Pass Type ID
> `pass.net.stampn.loyalty`, Team ID **W96BM9T4C3**, issued by Apple WWDR **G4**,
> pass cert valid to **2027‑08‑02**; `wwdr.pem` is the G4 intermediate (to 2030)
> and **chains correctly** to the pass cert. Source files currently live on the
> owner's Mac at `~/Documents/Certificates.p12` and `~/Downloads/wwdr.pem` — they
> still need to be copied to the box per step 1.
>
> Note: the `.p12` uses Keychain's legacy RC2‑40 cipher, so the OpenSSL **CLI**
> needs `-legacy` to read it — irrelevant to the app, which uses `cryptography`.

### 7. Enable the Apple button (frontend)
`frontend/dashboard/src/features/enroll/Enroll.jsx` currently omits the Apple
button on purpose. Once `apple_pass_url` is non-null, show an "Add to Apple
Wallet" badge on iOS (small change — mirrors the existing Google button block).

### 8. Real-device smoke test
On an actual iPhone: enroll → **Add to Apple Wallet** → install → stamp in the
cashier → confirm the APNs push refreshes the pass balance. Also confirm the
pass renders (logo, colors, strip) as expected.

## Ongoing
- **Expiry:** the pass-signing cert is valid ~1 year. Rotate it (repeat steps
  4 + 6) before it lapses, or new/updated passes stop signing. Track the expiry
  date; add it to the secret-rotation runbook.
- **APNs:** keep `APNS_USE_SANDBOX=false` in prod. Sandbox is only for test
  builds installed via a development profile.
- **Renewed WWDR:** if Apple rolls a new WWDR generation, re-download + re-convert
  and update `APPLE_WWDR_CERT_PATH`.
