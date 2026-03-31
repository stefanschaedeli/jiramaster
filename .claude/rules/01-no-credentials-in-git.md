# Rule: No Credentials in Git

NEVER commit these files — they are gitignored and must stay that way:
- `config.json` (Jira URL, email, API token, project key)
- `.secret_key` (Flask session secret)
- `assignees.json`, `labels.json` (cached Jira data)
- `.mcp.json` (MCP server config with tokens)
- Any `.env` file

NEVER hardcode tokens or secrets in `.mcp.json` — always use `${ENV_VAR}` substitution:
```json
{ "env": { "GITHUB_TOKEN": "${GITHUB_TOKEN}" } }
```

If you accidentally stage a credentials file, unstage it immediately and verify it is in `.gitignore`.
