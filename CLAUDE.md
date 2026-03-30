# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Repository Is

This is a **Claude Code workspace template** — a scaffolding toolkit for setting up Claude Code configuration in any new project. It is not an application with a build system; there is no `package.json` or `src/` directory.

## Key Files

- **`setup-claude.sh`** — Run this in any new project to scaffold Claude Code config. It creates `.claude/` structure, a `CLAUDE.md` template, `.claude/settings.json`, and `.mcp.json`.
- **`.claude/settings.json`** — Defines allowed/denied Bash and Read operations for Claude Code in this project.
- **`.mcp.json`** — Declares MCP servers (currently GitHub). The token here must be an env var (`${GITHUB_TOKEN}`), never a hardcoded value.
- **`CLAUDE.local.md`** — Personal overrides (gitignored, not committed).

## MCP: GitHub Integration

The GitHub MCP server (`@modelcontextprotocol/server-github`) is configured in `.mcp.json`. It requires:

```bash
export GITHUB_TOKEN='ghp_...'
```

Check MCP server status inside Claude Code with `/mcp`.

## Using This Template in a New Project

```bash
cd /path/to/new-project
bash /path/to/JiraMaster/setup-claude.sh
```

Then run `/init` inside Claude Code to auto-generate a project-specific CLAUDE.md.

## Critical Rules

- NEVER hardcode tokens or secrets in `.mcp.json` — always use `${ENV_VAR}` substitution
- `CLAUDE.local.md` must stay in `.gitignore` (personal config)
