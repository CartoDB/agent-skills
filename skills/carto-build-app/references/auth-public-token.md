# Auth — public app with API access token

For apps that show **public or shared data** to anyone (no login). The token ships in the bundle, so it must be **scoped tightly**.

## Issue the token

```bash
carto credentials create token \
  --connection carto_dw \
  --source my_project.demo.points \
  --apis sql,maps \
  --referer https://myapp.example.com
```

Flags:
- `--connection` — connection *name* (from `carto connections list --json`).
- `--source` — table / tileset / query the token can read. **Repeat the flag** for multiple sources.
- `--apis` — comma-separated subset of `sql,maps,imports,lds`. For a read-only deck.gl app, `sql,maps` is enough. Never include `imports` or `lds` in a public bundle.
- `--referer` — restricts the `Referer` header browsers send. Required for public apps. Use the production domain, plus `--referer http://localhost:5173` while developing.

The command prints a token string. Treat it as a public secret: it's safe in the bundle but only because it's scoped.

## Wire it into the app

`.env` (Vite):

```bash
VITE_API_BASE_URL=https://gcp-us-east1.api.carto.com
VITE_API_ACCESS_TOKEN=eyJhbGciOi...
VITE_CONNECTION_NAME=carto_dw
```

`apiBaseUrl` comes from `carto auth status` — the tenant domain tells you the region. Common values:

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
carto credentials list tokens --json          # find IDs
carto credentials get token <id>              # inspect scopes
carto credentials update token <id> ...       # rotate scoping
carto credentials delete token <id>           # revoke
```

## Gotchas

- **No `--source` = full-connection access.** Always pass `--source`. A token without source restriction can read every table on the connection.
- **`--referer` must include dev origins.** A token scoped to `https://myapp.example.com` won't work from `http://localhost:5173`. Either issue two tokens or include both referers.
- **Tokens don't expire by default**, so rotate on a schedule and on incidents (`credentials delete` then `create` fresh).
- **Don't use this for private data.** If the user has data their users shouldn't see, use [`auth-private-oauth.md`](auth-private-oauth.md) — the bundle is world-readable.
