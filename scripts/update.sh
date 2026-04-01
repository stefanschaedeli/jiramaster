#!/bin/bash
set -e

cd "$(dirname "$0")/.."

# Ensure logs directory exists
mkdir -p logs
UPDATE_LOG="logs/update.log"
exec > >(tee -a "$UPDATE_LOG") 2>&1

echo ""
echo "=== JiraMaster update — $(date) ==="

# --- Wait for JiraMaster to shut itself down (port 5000 to be free) ---
echo "Waiting for JiraMaster to shut down (port 5000)..."
WAIT_SECS=0
MAX_WAIT=15
while [ "$WAIT_SECS" -lt "$MAX_WAIT" ]; do
    if ! lsof -iTCP:5000 -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo "  Port 5000 is free."
        break
    fi
    sleep 1
    WAIT_SECS=$((WAIT_SECS + 1))
    echo "  Still waiting... (${WAIT_SECS}s)"
done

if [ "$WAIT_SECS" -ge "$MAX_WAIT" ]; then
    echo "WARNING: Port 5000 still in use after ${MAX_WAIT}s. Attempting forced cleanup..."
    PIDS=$(lsof -iTCP:5000 -sTCP:LISTEN -t 2>/dev/null || true)
    if [ -n "$PIDS" ]; then
        echo "  Killing PIDs: $PIDS"
        echo "$PIDS" | xargs kill -9 2>/dev/null || true
        sleep 1
    fi
fi

# --- Git update ---
echo "Fetching latest code from GitHub..."

if ! command -v git &>/dev/null; then
    echo "ERROR: git not found on PATH. Please install git."
    exit 1
fi

BEFORE=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
echo "  Current version : $BEFORE"

git fetch --quiet origin
git reset --hard origin/main
git clean -fd \
    --exclude=".work" \
    --exclude="logs" \
    --exclude="venv" \
    --exclude="config.json" \
    --exclude=".secret_key" \
    --exclude="assignees.json" \
    --exclude="labels.json"

AFTER=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
echo "  Updated version : $AFTER"

if [ "$BEFORE" = "$AFTER" ]; then
    echo "Already up to date."
else
    echo "Update applied: $BEFORE -> $AFTER"
fi

# --- Launch the app ---
echo ""
echo "Launching JiraMaster..."
exec "$(dirname "$0")/start.sh"
