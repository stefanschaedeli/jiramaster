# Rule: All Jira API Calls Through JiraClient

NEVER call `requests.get/post/put/delete` directly from route handlers or any module other than `jira_client.py`.

All Jira REST API interactions MUST go through `JiraClient` in `jira_client.py`. It handles:
- Authentication (Basic auth with API token)
- SSL/CA bundle resolution (TLS inspection proxy support via `REQUESTS_CA_BUNDLE`)
- Proxy configuration
- Consistent error logging and error message extraction
- Session reuse

To add a new Jira API call:
1. Add a method to `JiraClient` in `jira_client.py`
2. Call it from the route via `client = JiraClient(cfg); result, err = client.new_method(...)`
3. Handle the `(result, error_message)` tuple — `err` is `None` on success
