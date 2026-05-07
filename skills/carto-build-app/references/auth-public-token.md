# Auth — public app with API access token

For apps that show **public or shared data** to anyone (no login). The token ships in the bundle, so it must be **scoped tightly**.

**Best practice: one token, multiple grants.** Don't mint a separate token per table — bundle them into one token with one grant per source. The CLI supports this, but the syntax has a sharp edge (see below).

## Issue the token autonomously

The agent should run these itself, not ask the user. Always pass `--json` and parse the result.

```bash
# 1. Read region from tenant domain
carto auth status --json
#    → { "tenant": { "domain": "gcp-us-east1.app.carto.com", ... } }
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
  --referers http://localhost:5173,https://myapp.example.com
#    → { "token": "eyJ...", "id": "tok_...", "grants": [ ...3 entries... ] }
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
  --referers https://myapp.example.com
```

## Flag reference

- `--connection <name>` — connection *name* (from `carto connections list --json`). **Repeat for every `--source`.**
- `--source <fully.qualified.identifier>` — table / tileset / query. Repeat for each grant.
- `--apis <csv>` — comma-separated subset of `sql,maps,imports,lds`. For a read-only deck.gl app, `sql,maps` is enough. Never include `imports` or `lds` in a public bundle.
- `--referers <csv>` — comma-separated allowed origins. Use the **plural** form (`--referers a,b`) — `--referer` (singular) is overwritten if repeated, only the last one wins. Required for public apps.
- `--json` — emit `{ "token": ..., "id": ..., "grants": [...] }`. Always pass it; never scrape pretty-printed output.

The token is safe in the bundle *only because it's scoped*.

## Wire it into the app

Write `.env` directly from the JSON outputs above — don't ask the user for any of these:

```bash
VITE_API_BASE_URL=https://gcp-us-east1.api.carto.com
VITE_API_ACCESS_TOKEN=eyJhbGciOi...
VITE_CONNECTION_NAME=carto_dw
```

`apiBaseUrl` is derived from `carto auth status --json`'s tenant domain. Common values:

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
carto credentials list tokens --json                              # find IDs
carto credentials get token <id> --json                           # inspect grants
carto credentials update token <id> --add-grant carto_dw,my.new.table   # add ONE grant
carto credentials update token <id> --referers a,b                # rewrite referers
carto credentials delete token <id>                               # revoke
```

`update --add-grant` takes one `connection,source` pair per invocation. To add several, call it repeatedly or just re-issue the token from scratch with the full grant list — usually simpler.

## Gotchas

- **One token, multiple grants — not multiple tokens.** Bundling sources into a single token keeps the bundle small, lets the app reuse one `accessToken`, and consolidates rotation. Mint per-table tokens only when the *referer* set actually differs.
- **`--connection` must repeat alongside every `--source`** (positional pairing). See "Multi-grant syntax" above.
- **No `--source` = full-connection access.** A grant without source restriction reads every table on that connection.
- **Use `--referers` (plural, CSV) — not repeated `--referer`.** The CLI parser overwrites repeated `--referer`; only the last wins. `--referers http://localhost:5173,https://myapp.example.com` is the correct form.
- **Tokens don't expire by default**, so rotate on a schedule and on incidents (`credentials delete` then `create` fresh).
- **Don't use this for private data.** If the user has data their users shouldn't see, use [`auth-private-oauth.md`](auth-private-oauth.md) — the bundle is world-readable.
