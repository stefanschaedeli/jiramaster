#!/bin/bash
set -e

cd "$(dirname "$0")/.."

# Ensure logs directory exists
mkdir -p logs
UPDATE_LOG="logs/update.log"
exec > >(tee -a "$UPDATE_LOG") 2>&1

echo ""
echo "=== JiraMaster update — $(date) ==="

# --- Stop any running JiraMaster instance ---
echo "Stopping any running JiraMaster processes..."
KILLED=0
while IFS= read -r pid; do
    echo "  Stopping PID $pid"
    kill -TERM "$pid" 2>/dev/null || true
    KILLED=$((KILLED + 1))
done < <(pgrep -f "python.*app\.py" 2>/dev/null || true)

if [ "$KILLED" -eq 0 ]; then
    echo "  No running JiraMaster process found."
else
    # Give processes a moment to release file locks
    sleep 1
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
