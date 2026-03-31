$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# Ensure logs directory exists and tee all output there
if (-not (Test-Path "logs")) { New-Item -ItemType Directory -Path "logs" | Out-Null }
$startupLog = "logs\startup.log"
Start-Transcript -Path $startupLog -Append | Out-Null
Write-Host ""
Write-Host "=== JiraMaster startup - $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ==="

# Create venv if missing
if (-not (Test-Path "venv")) {
    Write-Host "Creating virtual environment..."
    python -m venv venv
}

# Install/update dependencies
Write-Host "Installing dependencies..."
& venv\Scripts\pip install -r requirements.txt --quiet

# Merge Windows system CA certs (incl. corporate proxy CA) into the certifi bundle.
# This fixes SSL errors on networks that use a TLS inspection proxy.
# No admin privileges required — reads from the current user and machine root stores.
$certifiBundle = & venv\Scripts\python -c "import certifi; print(certifi.where())"
$marker = "# --- Windows system certs appended by JiraMaster ---"

if (-not (Select-String -Path $certifiBundle -Pattern $marker -Quiet -ErrorAction SilentlyContinue)) {
    Write-Host "Merging Windows system CA certs into certifi bundle..."

    # Collect certs from both stores (LocalMachine\Root is readable without admin)
    $certs = @()
    $certs += Get-ChildItem -Path Cert:\CurrentUser\Root -ErrorAction SilentlyContinue
    $certs += Get-ChildItem -Path Cert:\LocalMachine\Root -ErrorAction SilentlyContinue
    $certs += Get-ChildItem -Path Cert:\LocalMachine\CA -ErrorAction SilentlyContinue

    if ($certs.Count -gt 0) {
        # Deduplicate by thumbprint
        $seen = @{}
        $pemLines = @($marker)
        foreach ($cert in $certs) {
            if ($seen.ContainsKey($cert.Thumbprint)) { continue }
            $seen[$cert.Thumbprint] = $true
            $b64 = [Convert]::ToBase64String($cert.RawData, [Base64FormattingOptions]::InsertLineBreaks)
            $pemLines += "-----BEGIN CERTIFICATE-----"
            $pemLines += $b64
            $pemLines += "-----END CERTIFICATE-----"
        }
        Add-Content -Path $certifiBundle -Value ($pemLines -join "`n") -Encoding UTF8
        Write-Host "  Appended $($seen.Count) unique certificates."
    } else {
        Write-Host "  No additional system certificates found."
    }
} else {
    Write-Host "System CA certs already merged into certifi bundle."
}

$env:SSL_CERT_FILE = $certifiBundle
$env:REQUESTS_CA_BUNDLE = $certifiBundle
Write-Host "SSL_CERT_FILE=$env:SSL_CERT_FILE"
Write-Host "REQUESTS_CA_BUNDLE=$env:REQUESTS_CA_BUNDLE"

# Start the app
Write-Host "Starting JiraMaster on http://127.0.0.1:5000"
try {
    & venv\Scripts\python app.py
} finally {
    Stop-Transcript | Out-Null
}
