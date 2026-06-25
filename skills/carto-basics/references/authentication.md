# Authentication

The CLI supports three authentication modes: **interactive browser**, **headless callback**, and **API token**.

> **Agents: default to the headless callback flow** (`--no-launch-browser`, below). An agent driving a shell can't complete a browser OAuth — plain `carto auth login` opens a browser and blocks on a localhost callback (port 3003), which hangs in a sandbox and isn't something the agent can click through anywhere. The headless flow works everywhere — sandbox *and* laptop — so prefer it unless a human is actively at the same machine. **Do not** prompt the user for an M2M / API token as a substitute for headless login.

## Interactive browser login (human at the machine)

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

**Don't reach for a token to dodge a headless login.** If you're in a sandbox and OAuth needs setup, run `carto auth login --no-launch-browser` — do not ask the user to generate and paste an M2M / API token instead. Tokens are for unattended automation (CI, scheduled jobs) where no human is available to complete a one-time callback, not a workaround for "no browser."

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
