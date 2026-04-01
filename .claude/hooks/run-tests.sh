#!/usr/bin/env bash
# Pre-commit test gate: runs pytest before any git commit.
# Blocks the commit if tests fail.

cd "$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0

# Only gate on git commit commands
if [ -z "$CLAUDE_TOOL_INPUT" ]; then
  exit 0
fi

# Check if this is a git commit invocation
echo "$CLAUDE_TOOL_INPUT" | grep -q '"git commit' || exit 0

# Skip version-bump-only commits from the auto-commit hook
echo "$CLAUDE_TOOL_INPUT" | grep -q 'chore: bump to v' && exit 0

VENV_PYTHON="venv/bin/python3"
if [ ! -x "$VENV_PYTHON" ]; then
  VENV_PYTHON="python3"
fi

echo "Running tests before commit..."
if "$VENV_PYTHON" -m pytest tests/ -q --tb=short 2>&1; then
  echo "Tests passed."
  exit 0
else
  echo "{\"decision\": \"block\", \"reason\": \"Tests failed — fix before committing. Run: venv/bin/python3 -m pytest tests/ -v\"}"
  exit 1
fi
