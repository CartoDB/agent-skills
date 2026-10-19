# Auth — public app with API access token

For apps that show **public or shared data** to anyone (no login). The token ships in the bundle, so it must be **scoped tightly**.

**Best practice: one token, multiple grants.** Don't mint a separate token per table — bundle them into one token with one grant per source. The CLI supports this, but the syntax has a sharp edge (see below).

> Over an OAuth MCP session (no shell), mint, list, and inspect the same tokens with `manage_api_access_tokens`. Everything else in this file is CLI, and a **token-authenticated** MCP session can't mint tokens at all — fall back to the CLI.

## Issue the token autonomously

The agent should run these itself, not ask the user. Always pass `--json` and parse the result.

```bash
# 1. Read the region from tenant_id (tenant_domain has no region in it)
carto auth status --json
#    → { "tenant_id": "gcp-us-east1", "tenant_domain": "clausa.app.carto.com", ... }
#    → apiBaseUrl = "https://gcp-us-east1.api.carto.com"

# 2. Confirm connection name
carto connections list --json
#    → first row .name (typically "carto_dw")

# 3. Mint one token for ALL the sources the app reads
carto credentials create token --json \
  --connection carto_dw --source my_project.demo.points \
  --connection carto_dw --source my_project.demo.regions \
  --connection carto_dw --source my_project.demo.timeseries \
  --apis sql,maps \
  --referers 'http://localhost:5173*,https://myapp.example.com*'
#    → { "token": "eyJ...", "allowed_apis": [...], "grants": [ ...3 entries... ], "referers": [...] }
```

## Multi-grant syntax — the sharp edge

`--connection` and `--source` are paired **positionally** by the CLI. The Nth `--source` is matched to the Nth `--connection`. If you list more sources than connections, the extras default the connection to its prior value or `*` (full-connection access — the foot-gun this whole skill is meant to avoid).

**Always repeat `--connection` for every `--source`**, even when it's the same connection name:

```bash
# CORRECT — three grants, all on carto_dw
--connection carto_dw --source a \
--connection carto_dw --source b \
--connection carto_dw --source c

# WRONG — only the first grant is what you think; b and c silently
# fall back to source='*' on an undefined connection
--connection carto_dw --source a --source b --source c
```

You can also mix connections in one token:

```bash
carto credentials create token --json \
  --connection carto_dw      --source bigquery_project.demo.points \
  --connection snowflake_dw  --source MY_DB.PUBLIC.REGIONS \
  --apis sql,maps \
  --referers 'https://myapp.example.com*'
```

## Grants and API scopes — what a token actually authorises

Two independent axes. A request is allowed only if **both** pass. Getting this wrong is the most common cause of a 403 on a token that "looks right".

**1. `--apis` decides which API you may call.**

| Scope | Authorises |
|---|---|
| `maps` | Map instantiation + tiles — everything a source/layer needs |
| `sql` | `query()` from `@carto/api-client`, for queries a grant authorises (below) |

A `maps`-only token serves tiles but **rejects every `query()` call**, and vice versa. `sql,maps` covers both and is the right default for a read-only app.

**2. Each grant names a source you may read — an FQN *or* a SQL query.**

- **FQN grants accept wildcards, matched per dot-segment.** `my_project.demo.*` covers every table in that dataset; `2024_*` works inside a segment. A pattern must have the **same number of segments** as the target, so `my_project.*` does *not* match `my_project.demo.points`. A bare `*` grants everything on that connection (all-wildcard forms like `*.*` are rejected).
- **A grant can be a SQL query instead.** Any grant string containing whitespace is treated as SQL and matched **exactly** — normalised for whitespace, backticks/quotes, trailing `;`, and case, but never glob-matched.

### Consequences worth internalising

- **A `maps` + table grant does not authorise a `*QuerySource` over that table.** `vectorQuerySource` adds SQL on top, so it needs the query authorised — not just the table. This is the trap: the table renders fine via `vectorTableSource`, then swapping to a query source 403s.
- **To use a `*QuerySource`, grant that exact query.** `--apis maps --source "SELECT ... FROM ..."` with a `vectorQuerySource` running the identical query works. Keep the app's SQL byte-identical to the grant (whitespace and case are forgiven; a changed column list is not).
- **`filters`, `spatialFilters`, and models computed on the source need no extra grant.** They ride the existing source grant, so prefer them over minting query grants or pre-materialising one table per filter value.
- **Multiple grants go on one token** — see "Multi-grant syntax" above.

- **A table grant never authorises SQL over that table, not even `SELECT * FROM <table>`.** `query()` 403s unless that exact query text is a grant. Grant every query the app runs (`--apis sql --source "<sql>"`), keep the text constant and pass inputs as named `queryParameters` (`@name`), so one grant serves every value. A changed query needs a new grant (`update --add-grant` or a fresh token).

If you need arbitrary, user-driven SQL over a table, pre-aggregate into a granted table and read it with a table source.

## Flag reference

- `--connection <name>` — connection *name* (from `carto connections list --json`). **Repeat for every `--source`.**
- `--source <fully.qualified.identifier>` — table / tileset / query. Repeat for each grant.
- `--apis <csv>` — comma-separated subset of `sql,maps,imports,lds`. For a read-only deck.gl app, `sql,maps` is enough. Never include `imports` or `lds` in a public bundle.
- `--referers <csv>` — comma-separated allowed referer patterns. Use the **plural** form (`--referers a,b`) — `--referer` (singular) is overwritten if repeated, only the last one wins. Required for public apps. Patterns support wildcards: `*` matches one or more characters, `?` matches exactly one. Matching is against the browser's full `Referer` (page URL), not the origin — so `http://localhost:5173*` is the safe local-dev form. Quote the value so your shell doesn't glob the `*`. See the referer-matching note in Gotchas.
- `--json` — emit the token record `{ "token": ..., "allowed_apis": [...], "grants": [...], "referers": [...] }`. There is no separate `id`: the `token` string itself is what `get` / `update` / `delete token` take. Always pass it; never scrape pretty-printed output.

The token is safe in the bundle *only because it's scoped*.

## Wire it into the app

Write `.env` directly from the JSON outputs above — don't ask the user for any of these:

```bash
VITE_API_BASE_URL=https://gcp-us-east1.api.carto.com
VITE_API_ACCESS_TOKEN=eyJhbGciOi...
VITE_CONNECTION_NAME=carto_dw
```

`apiBaseUrl` is `https://<tenant_id>.api.carto.com`, from `carto auth status --json`'s `tenant_id` (not `tenant_domain`, the organization's own domain, which has no region in it). Common values:

| Region | URL |
|---|---|
| GCP US East 1 | `https://gcp-us-east1.api.carto.com` |
| GCP EU West 1 | `https://gcp-eu-west1.api.carto.com` |
| AWS US East 1 | `https://aws-us-east-1.api.carto.com` |

Pass to source helpers:

```ts
import { vectorTableSource } from '@carto/api-client';

const cartoConfig = {
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL,
  accessToken: import.meta.env.VITE_API_ACCESS_TOKEN,
  connectionName: import.meta.env.VITE_CONNECTION_NAME,
};

const dataSource = vectorTableSource({
  ...cartoConfig,
  tableName: 'my_project.demo.points',
});
```

Every other source helper (`vectorQuerySource`, `h3TableSource`, `rasterSource`, …) takes the same `cartoConfig` shape.

## Lifecycle

```bash
carto credentials list tokens --json                              # each record's "token" is its ID
carto credentials get token <token> --json                        # inspect grants
carto credentials update token <token> --add-grant carto_dw,my.new.table   # add ONE grant
carto credentials update token <token> --referers a,b             # rewrite referers
carto credentials delete token <token>                            # revoke
```

These take the full token string, not its name or the JWT's own id claim.

`update --add-grant` takes one `connection,source` pair per invocation. To add several, call it repeatedly or just re-issue the token from scratch with the full grant list — usually simpler.

## Gotchas

- **No `--source` = full-connection access.** A grant without source restriction reads every table on that connection. (Multi-grant `--connection` pairing and `--referers` plural form are covered above — both are common 403 causes.)
- **Referers 403 with a valid-looking token.** The browser sends its whole page URL as `Referer` (site root carries a trailing slash: `http://localhost:5173/`), so a literal `http://localhost:5173` grant has no wildcard and every tile 403s with body `{"error":"Unauthorized referer"}` — while the token *call* succeeds, so HTTP status alone misleads. Diagnose: DevTools → Network → a failed tile's request `Referer` vs `carto credentials get token <token> --json`. An **empty** referers list means "allow any" — fine locally, never in production.
- **Tokens don't expire by default** — rotate on a schedule and on incidents (`credentials delete` then `create` fresh).
- **Vite reads `.env` only at startup — restart the dev server after minting a new token.** A reload keeps serving the old value baked into the bundle, so the app 403s while the same token succeeds from curl. Also check console-error timestamps after any restart before concluding a request still fails.
- **Don't use this for private data** — the bundle is world-readable. Use [`auth-private-oauth.md`](auth-private-oauth.md).
