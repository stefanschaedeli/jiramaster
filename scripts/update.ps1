$ErrorActionPreference = "Continue"
Set-Location (Split-Path $PSScriptRoot -Parent)

# Output goes to update.log via the caller's redirection (>> logs\update.log 2>&1).
# Ensure the logs directory exists in case the script is run standalone.
if (-not (Test-Path "logs")) { New-Item -ItemType Directory -Path "logs" | Out-Null }

Write-Host ""
Write-Host "=== JiraMaster update - $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ==="

# --- Wait for JiraMaster to shut itself down (port 5000 to be free) ---
Write-Host "Waiting for JiraMaster to shut down (port 5000)..."
$waitSecs = 0
$maxWait = 15
while ($waitSecs -lt $maxWait) {
    $listener = Get-NetTCPConnection -LocalPort 5000 -State Listen -ErrorAction SilentlyContinue
    if (-not $listener) {
        Write-Host "  Port 5000 is free."
        break
    }
    Start-Sleep -Seconds 1
    $waitSecs++
    Write-Host "  Still waiting... (${waitSecs}s)"
}

if ($waitSecs -ge $maxWait) {
    Write-Host "WARNING: Port 5000 still in use after ${maxWait}s. Attempting forced cleanup..." -ForegroundColor Yellow
    $listener = Get-NetTCPConnection -LocalPort 5000 -State Listen -ErrorAction SilentlyContinue
    if ($listener) {
        $pids = $listener | Select-Object -ExpandProperty OwningProcess -Unique
        foreach ($pid in $pids) {
            Write-Host "  Killing PID $pid"
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
        }
        Start-Sleep -Seconds 1
    }
}

# --- Git update (overwrite local changes if needed) ---
Write-Host "Fetching latest code from GitHub..."

# Check git is available
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: git not found on PATH. Please install Git for Windows." -ForegroundColor Red
    exit 1
}

$before = git rev-parse --short HEAD 2>$null
Write-Host "  Current version : $before"

# Discard local modifications so git pull can fast-forward cleanly.
# Config files (config.json, .secret_key, assignees.json, labels.json) are
# gitignored and will NOT be touched.
git fetch --quiet origin
git reset --hard origin/main 2>&1 | Write-Host
git clean -fd --exclude=".work" --exclude="logs" --exclude="venv" --exclude="config.json" --exclude=".secret_key" --exclude="assignees.json" --exclude="labels.json" 2>&1 | Write-Host

$after = git rev-parse --short HEAD 2>$null
Write-Host "  Updated version  : $after"

if ($before -eq $after) {
    Write-Host "Already up to date."
} else {
    Write-Host "Update applied: $before -> $after"
}

# --- Launch the app ---
Write-Host ""
Write-Host "Launching JiraMaster..."
& "$PSScriptRoot\start.ps1"
