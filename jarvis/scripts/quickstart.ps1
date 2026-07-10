#Requires -Version 5.1
<#
  JARVIS one-command local setup for Windows.
  Detects Python 3.11+, creates an isolated virtualenv, installs
  dependencies, saves your Anthropic API key, seeds demo data, launches the
  server, and opens your browser.

  Run from the jarvis\ directory:
      powershell -ExecutionPolicy Bypass -File scripts\quickstart.ps1
  or just double-click scripts\quickstart.bat
#>

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

function Say($m)  { Write-Host "> $m"  -ForegroundColor Cyan }
function Good($m) { Write-Host "OK $m" -ForegroundColor Green }
function Warn($m) { Write-Host "!  $m" -ForegroundColor Yellow }

Write-Host ""
Write-Host "  J A R V I S  -  local quickstart" -ForegroundColor White
Write-Host ""

# ---- 1. Find Python 3.11+ --------------------------------------------------
$pyExe = $null; $pyArgs = @()
$tries = @(
    @{ cmd = "py";      args = @("-3.12") },
    @{ cmd = "py";      args = @("-3.11") },
    @{ cmd = "python";  args = @() },
    @{ cmd = "python3"; args = @() }
)
foreach ($t in $tries) {
    if (Get-Command $t.cmd -ErrorAction SilentlyContinue) {
        try {
            $probe = $t.args + @("-c", "import sys;print('%d.%d' % sys.version_info[:2])")
            $v = (& $t.cmd @probe 2>$null)
            if ($v -match '^3\.(\d+)$' -and [int]$Matches[1] -ge 11) {
                $pyExe = $t.cmd; $pyArgs = $t.args; break
            }
        } catch { }
    }
}
if (-not $pyExe) {
    Write-Host "X Python 3.11+ is required but was not found." -ForegroundColor Red
    Write-Host "  Install it from https://www.python.org/downloads/ (check 'Add python.exe to PATH'), then re-run."
    exit 1
}
$pyVer = (& $pyExe @($pyArgs + @("--version")))
Good "Using $pyVer"

# ---- 2. Virtualenv + deps --------------------------------------------------
if (-not (Test-Path ".venv")) {
    Say "Creating virtual environment (.venv)..."
    & $pyExe @($pyArgs + @("-m", "venv", ".venv"))
}
$venvPy = Join-Path ".venv" "Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    Write-Host "X Virtual environment creation failed." -ForegroundColor Red
    exit 1
}
Say "Installing dependencies (first run takes a minute)..."
& $venvPy -m pip install --quiet --upgrade pip
& $venvPy -m pip install --quiet -r requirements-dev.txt
Good "Dependencies installed"

# ---- 3. Configuration ------------------------------------------------------
if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env" }
$envText = Get-Content ".env" -Raw
if ($envText -match '(?m)^ANTHROPIC_API_KEY=\s*$') {
    Write-Host ""
    Warn "No ANTHROPIC_API_KEY set yet. Chat needs one (get it at https://console.anthropic.com/)."
    $key = Read-Host "  Paste your Anthropic API key (or press Enter to skip)"
    if ($key) {
        $envText = [regex]::Replace($envText, '(?m)^ANTHROPIC_API_KEY=.*$', "ANTHROPIC_API_KEY=$key")
        Set-Content ".env" $envText -NoNewline
        Good "API key saved to .env"
    } else {
        Warn "Skipped - edit .env later. The UI still works; chat will ask you to add a key."
    }
}

# ---- 4. Seed demo data -----------------------------------------------------
Say "Seeding demo data (memories, tasks, automations)..."
try { & $venvPy "scripts\seed_examples.py" | Out-Null; Good "Demo user ready: demo@jarvis.app / demopassword123" }
catch { Warn "Seeding skipped (already present)" }

# ---- 5. Launch -------------------------------------------------------------
$port = if ($env:JARVIS_PORT) { $env:JARVIS_PORT } else { "8700" }
$url  = "http://localhost:$port"
Write-Host ""
Good "Starting JARVIS..."
Write-Host ""
Write-Host "  Open $url in your browser" -ForegroundColor White
Write-Host "  Log in with demo@jarvis.app / demopassword123, or create your own account."
Write-Host "  Press Ctrl+C to stop."
Write-Host ""

# Open the browser a few seconds after the server starts (best-effort).
Start-Job -ScriptBlock { Start-Sleep -Seconds 3; Start-Process $using:url } | Out-Null

& $venvPy -m uvicorn server.main:app --host 127.0.0.1 --port $port
