#!/usr/bin/env bash
# Handles "confirm major" user prompt — executes a major version bump and commit

INPUT=$(cat)
PROMPT=$(echo "$INPUT" | jq -r '.prompt // ""' | tr '[:upper:]' '[:lower:]')

# Only act on "confirm major"
if [[ "$PROMPT" != *"confirm major"* ]]; then
  exit 0
fi

cd "$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0

VERSION_FILE="VERSION"
if [ ! -f "$VERSION_FILE" ]; then
  exit 0
fi

CURRENT=$(cat "$VERSION_FILE" | tr -d '[:space:]')
MAJOR=$(echo "$CURRENT" | cut -d. -f1)

NEW_VERSION="$((MAJOR + 1)).0.0"
echo "$NEW_VERSION" > "$VERSION_FILE"

git add -A

FILE_COUNT=$(git diff --cached --name-only | wc -l | tr -d ' ')
CHANGED_FILES=$(git diff --cached --name-only | head -10 | tr '\n' ' ')
INSERTIONS=$(git diff --cached --stat | tail -1 | grep -oE '[0-9]+ insertion' | grep -oE '[0-9]+' || echo "0")
DELETIONS=$(git diff --cached --stat | tail -1 | grep -oE '[0-9]+ deletion' | grep -oE '[0-9]+' || echo "0")

git commit -m "$(cat <<EOF
feat!: bump to v${NEW_VERSION} (major release)

Files changed (${FILE_COUNT}): ${CHANGED_FILES}
Insertions: +${INSERTIONS:-0}  Deletions: -${DELETIONS:-0}
Major version release confirmed by user — committed by Claude Code session
EOF
)"

echo "{\"hookSpecificOutput\": {\"hookEventName\": \"UserPromptSubmit\", \"additionalContext\": \"Major release committed: v${CURRENT} → v${NEW_VERSION}\"}}"
