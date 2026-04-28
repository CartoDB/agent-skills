# Global options and environment variables

## Flags accepted by every command

| Option | Description |
|---|---|
| `--json` | Output in JSON. **Always pass this when an agent will parse the result.** |
| `--debug` | Print the request method, URL, and headers. Useful for support tickets. |
| `--yes`, `-y` | Skip the confirmation prompt for destructive commands. |
| `--token <token>` | Override the stored API token for this command only. |
| `--base-url <url>` | Override the base API URL (rarely needed; usually env-driven). |
| `--profile <name>` | Use a specific profile (default: `"default"`). |
| `--version`, `-v` | Show the CLI version. |
| `--help`, `-h` | Show command help. |

### Confirmation behavior

Destructive commands (`maps delete`, `workflows delete`, `connections delete`, `users delete`, `admin batch-delete`) require typing the literal word **`delete`** to confirm. Pass `--yes` or `--json` to skip — `--json` implies non-interactive mode.

## Environment variables

| Variable | Purpose |
|---|---|
| `CARTO_API_TOKEN` | API token for auth (overrides stored OAuth credentials). |
| `CARTO_PROFILE` | Profile to use (overrides `current_profile` in config). |
| `CARTO_AUTH_ENV` | Auth environment. Only set if instructed by CARTO support. |
| `CARTO_AUTH_PORT` | Local callback port for browser-based login (default: `3003`). |

## Output patterns

- **Human output** — default; columns and headings tuned for terminals.
- **JSON output** — `--json`; stable schema, suitable for `jq`/agents.

For long lists, prefer `--all` (paginates internally) or explicit `--page-size`/`--page` over scraping default output:

```bash
carto maps list --all --json | jq '.[] | {id, name}'
```

## Async behavior

Long-running operations:

- `imports create` — polls until the import finishes; pass `--async` to return immediately.
- `sql job` — polls until the job completes; no timeout; no `--async`.
- `activity export` — waits and downloads files to disk.

For agents, the default (poll-to-completion) is usually correct. Switch to `--async` only when you need to fan out parallel jobs and reconcile later.
