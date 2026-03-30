#!/bin/bash
# Claude Code Project Setup Script
# Run this in any new project to scaffold the Claude Code configuration
# Usage: bash setup-claude.sh

set -e

echo "🤖 Setting up Claude Code configuration..."

# ── Create directory structure ────────────────────────────────────────────────
mkdir -p .claude/agents .claude/skills .claude/commands
echo "✅ Created .claude/ directory structure"

# ── .gitignore entries ───────────────────────────────────────────────────────
if [ -f ".gitignore" ]; then
  if ! grep -q "CLAUDE.local.md" .gitignore; then
    echo "" >> .gitignore
    echo "# Claude Code personal config (keep out of version control)" >> .gitignore
    echo "CLAUDE.local.md" >> .gitignore
    echo "✅ Added CLAUDE.local.md to .gitignore"
  fi
else
  echo "CLAUDE.local.md" > .gitignore
  echo "✅ Created .gitignore with CLAUDE.local.md"
fi

# ── CLAUDE.md (only if it doesn't exist) ─────────────────────────────────────
if [ ! -f "CLAUDE.md" ]; then
  cat > CLAUDE.md << 'EOF'
# CLAUDE.md — Project Configuration
# Run /init inside Claude Code to auto-generate this from your project structure.
# Or fill in the sections below manually.

## Build Commands
- `npm run dev`       → Start dev server
- `npm run build`     → Build for production
- `npm run test`      → Run tests
- `npm run lint`      → Lint and auto-fix
- `npm run typecheck` → TypeScript check

## Code Style
- [Add your conventions here]

## Architecture
- [Describe your project structure here]

## Critical Rules
- NEVER commit secrets or .env files
- ALWAYS run typecheck after editing TypeScript
- [Add your project-specific rules]
EOF
  echo "✅ Created CLAUDE.md template (fill this in!)"
else
  echo "⏭️  CLAUDE.md already exists — skipping"
fi

# ── settings.json ─────────────────────────────────────────────────────────────
if [ ! -f ".claude/settings.json" ]; then
  cat > .claude/settings.json << 'EOF'
{
  "permissions": {
    "allow": [
      "Bash(npm run lint)",
      "Bash(npm run test)",
      "Bash(npm run test:*)",
      "Bash(npm run typecheck)",
      "Bash(git status)",
      "Bash(git diff)"
    ],
    "deny": [
      "Read(.env*)",
      "Read(~/.ssh/*)",
      "Bash(rm -rf:*)",
      "Bash(sudo:*)"
    ]
  }
}
EOF
  echo "✅ Created .claude/settings.json"
fi

# ── .mcp.json stub ────────────────────────────────────────────────────────────
if [ ! -f ".mcp.json" ]; then
  cat > .mcp.json << 'EOF'
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": { "GITHUB_TOKEN": "${GITHUB_TOKEN}" }
    }
  }
}
EOF
  echo "✅ Created .mcp.json (add your MCP servers here)"
fi

echo ""
echo "🎉 Done! Next steps:"
echo ""
echo "  1. Open Claude Code in this project:"
echo "     cd $(pwd) && claude"
echo ""
echo "  2. Auto-generate your CLAUDE.md:"
echo "     /init"
echo ""
echo "  3. Customize CLAUDE.md with your build commands and rules"
echo ""
echo "  4. Set environment variables for MCP servers:"
echo "     export GITHUB_TOKEN='ghp_...'"
echo "     echo 'export GITHUB_TOKEN=...' >> ~/.zshrc"
echo ""
echo "  5. Check MCP server status inside Claude Code:"
echo "     /mcp"
