$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

# Ensure logs directory exists
if (-not (Test-Path "logs")) { New-Item -ItemType Directory -Path "logs" | Out-Null }
$updateLog = "logs\update.log"
Start-Transcript -Path $updateLog -Append | Out-Null

Write-Host ""
Write-Host "=== JiraMaster update - $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ==="

# --- Stop any running JiraMaster instance (python app.py on port 5000) ---
Write-Host "Stopping any running JiraMaster processes..."
$killed = 0
Get-Process -Name "python" -ErrorAction SilentlyContinue | ForEach-Object {
    try {
        $cmd = (Get-CimInstance Win32_Process -Filter "ProcessId = $($_.Id)" -ErrorAction SilentlyContinue).CommandLine
        if ($cmd -match "app\.py") {
            Write-Host "  Stopping PID $($_.Id): $cmd"
            Stop-Process -Id $_.Id -Force
            $killed++
        }
    } catch {
        # Process may have already exited
    }
}
if ($killed -eq 0) { Write-Host "  No running JiraMaster process found." }

# Give processes a moment to release file locks
if ($killed -gt 0) { Start-Sleep -Seconds 1 }

# --- Git update (overwrite local changes if needed) ---
Write-Host "Fetching latest code from GitHub..."

# Check git is available
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: git not found on PATH. Please install Git for Windows." -ForegroundColor Red
    Stop-Transcript | Out-Null
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

Stop-Transcript | Out-Null

# --- Launch the app ---
Write-Host ""
Write-Host "Launching JiraMaster..."
& "$PSScriptRoot\start.bat"
