# Runs the NOAVIA test frontend locally against the real live n8n webhook.
# Reads the webhook secret from the repo-root .env (gitignored, never
# committed) instead of hardcoding it here.

$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$envFile = Join-Path $repoRoot ".env"

if (-not (Test-Path $envFile)) {
    Write-Error "Missing $envFile — expected NOAVIA_LIVE_WEBHOOK_SECRET to be set there."
    exit 1
}

$secretLine = Select-String -Path $envFile -Pattern "^NOAVIA_LIVE_WEBHOOK_SECRET=" | Select-Object -First 1
if (-not $secretLine) {
    Write-Error "NOAVIA_LIVE_WEBHOOK_SECRET not found in $envFile"
    exit 1
}
$secret = ($secretLine.Line -split "=", 2)[1].Trim()

$env:NOAVIA_TEST_MODE = "false"
$env:NOAVIA_N8N_PUBLIC_WEBHOOK_URL = "https://n8n.saiyudh.com/webhook/noavia/tickets/v1"
$env:NOAVIA_N8N_WEBHOOK_HEADER_NAME = "X-NOAVIA-Webhook-Secret"
$env:NOAVIA_N8N_WEBHOOK_HEADER_VALUE = $secret

Write-Host "Starting NOAVIA test frontend in LIVE mode against https://n8n.saiyudh.com ..." -ForegroundColor Yellow
Write-Host "Submissions from this form are REAL tickets sent to the live webhook." -ForegroundColor Yellow

Push-Location $PSScriptRoot
try {
    py -m pip install -q -r requirements.txt
    py -m uvicorn app:app --host 127.0.0.1 --port 8081
} finally {
    Pop-Location
}
