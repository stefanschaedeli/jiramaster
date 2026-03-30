$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# Create venv if missing
if (-not (Test-Path "venv")) {
    Write-Host "Creating virtual environment..."
    python -m venv venv
}

# Install/update dependencies
Write-Host "Installing dependencies..."
& venv\Scripts\pip install -r requirements.txt --quiet

# Start the app
Write-Host "Starting JiraMaster on http://127.0.0.1:5000"
& venv\Scripts\python app.py
