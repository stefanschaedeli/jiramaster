#!/usr/bin/env bash
# Auto-commit hook: analyzes diff magnitude, bumps version accordingly, commits
# - patch: small changes (≤5 files, ≤50 lines net)
# - minor: significant changes (new files, features, >50 lines net or >5 files)
# - major: large architectural changes (>20 files or >300 lines net) — prompts user to confirm

cd "$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0

# Only run if there are uncommitted changes
if git diff --quiet && git diff --cached --quiet; then
  exit 0
fi

VERSION_FILE="VERSION"
if [ ! -f "$VERSION_FILE" ]; then
  exit 0
fi

CURRENT=$(cat "$VERSION_FILE" | tr -d '[:space:]')
MAJOR=$(echo "$CURRENT" | cut -d. -f1)
MINOR=$(echo "$CURRENT" | cut -d. -f2)
PATCH=$(echo "$CURRENT" | cut -d. -f3)

# Stage everything so we can analyse the full diff
git add -A

# Gather diff stats
FILE_COUNT=$(git diff --cached --name-only | wc -l | tr -d ' ')
NEW_FILES=$(git diff --cached --name-only --diff-filter=A | wc -l | tr -d ' ')
INSERTIONS=$(git diff --cached --stat | tail -1 | grep -oE '[0-9]+ insertion' | grep -oE '[0-9]+' || echo "0")
DELETIONS=$(git diff --cached --stat | tail -1 | grep -oE '[0-9]+ deletion' | grep -oE '[0-9]+' || echo "0")
NET_LINES=$(( ${INSERTIONS:-0} - ${DELETIONS:-0} ))
ABS_NET=${NET_LINES#-}   # absolute value
CHANGED_FILES=$(git diff --cached --name-only | head -10 | tr '\n' ' ')

# Classify the release type
if [ "$FILE_COUNT" -gt 20 ] || [ "$ABS_NET" -gt 300 ]; then
  RELEASE_TYPE="major"
elif [ "$FILE_COUNT" -gt 5 ] || [ "$ABS_NET" -gt 50 ] || [ "$NEW_FILES" -gt 0 ]; then
  RELEASE_TYPE="minor"
else
  RELEASE_TYPE="patch"
fi

# Bump the right component
if [ "$RELEASE_TYPE" = "major" ]; then
  NEW_VERSION="$((MAJOR + 1)).0.0"
  LABEL="major"
elif [ "$RELEASE_TYPE" = "minor" ]; then
  NEW_VERSION="${MAJOR}.$((MINOR + 1)).0"
  LABEL="minor"
else
  NEW_VERSION="${MAJOR}.${MINOR}.$((PATCH + 1))"
  LABEL="patch"
fi

echo "$NEW_VERSION" > "$VERSION_FILE"
git add VERSION

# Capture the last meaningful commit message (the one before this version bump)
# to use as the release description
LAST_COMMIT_MSG="$(git log --format='%B' -1 HEAD 2>/dev/null | sed '/^Co-Authored-By:/d' | sed '/^$/d' | head -20)"

# Version bump commit (minimal — the real description lives on the tag/release)
git commit -m "chore: bump to v${NEW_VERSION} (${LABEL} release)"

# Annotated tag with the real change description
TAG_MSG="$(cat <<EOF
v${NEW_VERSION} (${LABEL} release)

${LAST_COMMIT_MSG}
EOF
)"
git tag -a "v${NEW_VERSION}" -m "${TAG_MSG}"

BRANCH="$(git rev-parse --abbrev-ref HEAD)"
git push --set-upstream origin "$BRANCH" 2>/dev/null && \
  git push origin "v${NEW_VERSION}" 2>/dev/null && \
  PUSHED="pushed + tagged" || PUSHED="push failed"

# Create GitHub release with the same description (requires gh CLI)
if command -v gh &>/dev/null; then
  gh release create "v${NEW_VERSION}" \
    --title "v${NEW_VERSION}" \
    --notes "${LAST_COMMIT_MSG}" 2>/dev/null || true
fi

echo "{\"systemMessage\": \"Auto-committed: v${CURRENT} → v${NEW_VERSION} (${LABEL}) — ${PUSHED}\"}"
