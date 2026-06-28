# Kasbana onboarding (Windows PowerShell) — mirror of scripts/onboard.sh.
#
# Usage (from a folder where you want the repo):
#   powershell -ExecutionPolicy Bypass -File .\scripts\onboard.ps1
#
# Prereqs: git, python (3.11+), optionally node/npm. You need write access to
# the repo (ask Momen to add you as a collaborator) to push to `dev`.

$ErrorActionPreference = "Stop"
$RepoUrl = "https://github.com/momenawab/Kasbana.git"
$Branch  = "dev"

function Say($m)  { Write-Host "`n> $m" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "✓ $m" -ForegroundColor Green }
function Warn($m) { Write-Host "! $m" -ForegroundColor Yellow }

# 1. Locate or clone
$inRepo = $false
try {
  if ((git rev-parse --is-inside-work-tree 2>$null) -eq "true") {
    if ((git remote get-url origin 2>$null) -match "Kasbana") { $inRepo = $true }
  }
} catch {}

if ($inRepo) {
  $Root = git rev-parse --show-toplevel
  Say "Using existing clone at $Root"
} else {
  Say "Cloning $RepoUrl"
  git clone $RepoUrl
  $Root = Join-Path (Get-Location) "Kasbana"
}
Set-Location $Root

Say "Switching to '$Branch'"
git checkout $Branch
try { git pull origin $Branch } catch { Warn "Could not pull — continuing" }

# 2. Backend
Say "Backend: virtualenv + dependencies"
Set-Location (Join-Path $Root "backend")
python -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip | Out-Null
& .\.venv\Scripts\pip.exe install -r requirements-dev.txt
if (-not (Test-Path ".env")) { Copy-Item .env.example .env; Ok "created backend/.env" }

Say "Backend: migrate + test"
& .\.venv\Scripts\python.exe manage.py migrate
& .\.venv\Scripts\pytest.exe -q
Ok "Backend ready: cd backend; .\.venv\Scripts\Activate.ps1; python manage.py runserver"

# 3. Frontend (optional)
if (Get-Command npm -ErrorAction SilentlyContinue) {
  Say "Frontend: npm install"
  Set-Location (Join-Path $Root "frontend")
  npm install
  Ok "Frontend ready: cd frontend; npm run dev"
} else {
  Warn "npm not found — skipping frontend setup"
}

Write-Host @"

----------------------------------------------------------------------------
 KASBANA — HOW THE REPO WORKS
----------------------------------------------------------------------------
 * Edit ONLY the 'dev' branch (monorepo: main/ frontend/ backend/ infra/ contracts/).
 * Pushing 'dev' auto-distributes each folder to its own branch (distribute.yml)
   and runs backend CI (backend-ci.yml). Never edit generated branches directly.
 * Ship:  git add -A; git commit -m "msg"; git push origin dev   (no deploy)
 * Production (Momen owns it): promote dev -> prod to deploy onto EC2:
     git checkout prod; git merge --ff-only dev; git push origin prod; git checkout dev
     Live: https://api.kasbana.net  ·  admin https://admin.kasbana.net/admin/
 * Ownership: Momen -> core/common/config/enrollment/wallets/billing/infra;
   Joe -> loyalty/dashboard. Shared core/, common/, contracts/ change by PR only.
----------------------------------------------------------------------------
"@ -ForegroundColor Gray

Ok "Onboarding complete"
