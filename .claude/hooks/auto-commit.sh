#!/usr/bin/env bash
# Auto-commit hook: bumps patch version and commits all staged/unstaged changes
# Triggered on Stop event after Claude completes work

cd "$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0

# Only run if there are uncommitted changes (tracked files only)
if git diff --quiet && git diff --cached --quiet; then
  exit 0
fi

# Read current version
VERSION_FILE="VERSION"
if [ ! -f "$VERSION_FILE" ]; then
  exit 0
fi

CURRENT=$(cat "$VERSION_FILE" | tr -d '[:space:]')
MAJOR=$(echo "$CURRENT" | cut -d. -f1)
MINOR=$(echo "$CURRENT" | cut -d. -f2)
PATCH=$(echo "$CURRENT" | cut -d. -f3)

# Bump patch
NEW_PATCH=$((PATCH + 1))
NEW_VERSION="${MAJOR}.${MINOR}.${NEW_PATCH}"
echo "$NEW_VERSION" > "$VERSION_FILE"

# Stage everything (excluding gitignored files)
git add -A

# Build a 5-line commit message from the diff summary
CHANGED_FILES=$(git diff --cached --name-only | head -10 | tr '\n' ' ')
FILE_COUNT=$(git diff --cached --name-only | wc -l | tr -d ' ')
INSERTIONS=$(git diff --cached --stat | tail -1 | grep -oE '[0-9]+ insertion' | grep -oE '[0-9]+' || echo "0")
DELETIONS=$(git diff --cached --stat | tail -1 | grep -oE '[0-9]+ deletion' | grep -oE '[0-9]+' || echo "0")

git commit -m "$(cat <<EOF
chore: bump to v${NEW_VERSION}

Files changed (${FILE_COUNT}): ${CHANGED_FILES}
Insertions: +${INSERTIONS:-0}  Deletions: -${DELETIONS:-0}
Automated patch release — changes committed by Claude Code session
EOF
)"

echo "{\"systemMessage\": \"Auto-committed: v${CURRENT} → v${NEW_VERSION}\"}"
