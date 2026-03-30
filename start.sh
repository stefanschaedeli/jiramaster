#!/bin/bash
set -e

cd "$(dirname "$0")"

# Create venv if missing
if [ ! -d "venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv venv
fi

# Install/update dependencies
echo "Installing dependencies..."
venv/bin/pip install -r requirements.txt --quiet

# Merge macOS system keychain certs (incl. corporate CA) into the certifi bundle.
# This fixes SSL errors on networks that use a TLS inspection proxy.
CERTIFI_BUNDLE=$(venv/bin/python -c "import certifi; print(certifi.where())")
SYSTEM_CERTS=$(python3 -c "import ssl; print(ssl.get_default_verify_paths().cafile)")
if [ -f "$SYSTEM_CERTS" ]; then
  # Export any extra certs from the macOS System keychain
  EXTRA=$(security find-certificate -a -p /Library/Keychains/System.keychain 2>/dev/null)
  if [ -n "$EXTRA" ]; then
    # Append only if not already present (compare lengths)
    BUNDLE_SIZE=$(wc -c < "$CERTIFI_BUNDLE")
    SYSTEM_SIZE=$(wc -c < "$SYSTEM_CERTS")
    if [ "$BUNDLE_SIZE" -lt "$SYSTEM_SIZE" ]; then
      echo "Merging system CA certs into certifi bundle..."
      cat "$SYSTEM_CERTS" >> "$CERTIFI_BUNDLE"
    fi
  fi
fi
export SSL_CERT_FILE="$CERTIFI_BUNDLE"
export REQUESTS_CA_BUNDLE="$CERTIFI_BUNDLE"

# Start the app
echo "Starting JiraMaster on http://127.0.0.1:5000"
venv/bin/python app.py
