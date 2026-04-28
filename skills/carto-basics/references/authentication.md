# Authentication

The CLI supports three authentication modes: **interactive browser**, **headless callback** (for sandboxed/remote environments), and **API token**.

## Interactive browser login (local machines)

```bash
carto auth login                          # default profile, production tenant
carto auth login production               # explicit profile name
carto auth login --organization-name "cartodb"   # SSO login
```

Opens a browser window, completes OAuth, and stores credentials locally. After login:

```bash
carto auth status                         # tenant, org, user, available profiles
carto auth whoami                         # current user only
```

`--organization-name` is required for SSO orgs. Use quotes if the org name contains spaces.

## Headless callback (sandboxed agents)

When the harness can't open a browser, use the two-step `--no-launch-browser` flow:

```bash
# 1. Start the auth flow — the CLI prints a URL and exits
carto auth login --no-launch-browser

# 2. Ask the user to open the printed URL in their browser, complete OAuth,
#    and copy the callback URL they land on
#    (it starts with https://carto.com/cli-callback?code=...&state=...)

# 3. Pass that URL back to the CLI to finish authentication
carto auth login --callback "https://carto.com/cli-callback?code=...&state=..."
```

Credentials persist after step 3 — subsequent commands work as if you had used the browser flow.

## API tokens

Bypass OAuth entirely with an API Access Token:

```bash
export CARTO_API_TOKEN="your-api-token"
carto maps list
```

Or pass per-command:

```bash
carto maps list --token "your-api-token"
```

API tokens from the Developer section of the CARTO Workspace have **limited scope** (typically scoped to specific connections, sources, and APIs). For full-platform access, prefer `auth login` (OAuth).

## Other auth subcommands

```bash
carto auth logout [profile]               # remove stored credentials
carto auth use <profile>                  # switch default profile
```

## Environments

Most users never set this. CARTO support may instruct you to point the CLI at staging or a dedicated environment:

```bash
carto auth login --env production         # default
carto auth login --env staging            # only on instruction from CARTO support
```

Or via env var: `CARTO_AUTH_ENV=staging`.
