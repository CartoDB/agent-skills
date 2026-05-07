# Auth — M2M (backend / CI / scripted apps)

For non-interactive callers: backend services, ETL scripts, scheduled jobs, CI runners. **Don't ship M2M credentials to a browser** — the client secret is a real secret.

## Issue the M2M client autonomously

```bash
carto credentials create m2m --json --title "ETL bot"
#  → { "clientId": "...", "clientSecret": "..." }
```

Store both in a secret manager (or write to `.env` for local dev — gitignored).

## Use from the CLI

```bash
export CARTO_M2M_CLIENT_ID=...
export CARTO_M2M_CLIENT_SECRET=...
carto auth login --m2m                  # exchanges secret for a token, caches it
carto maps list --json                  # any command works after login
```

The token is cached in the CLI's profile store and refreshed automatically when expired.

For one-shot CI:

```bash
carto auth login --m2m \
  --client-id "$CARTO_M2M_CLIENT_ID" \
  --client-secret "$CARTO_M2M_CLIENT_SECRET" \
  --force
carto workflows list --json
```

## Use from a Node.js backend

The OAuth 2.0 client-credentials flow:

```ts
async function getCartoToken(): Promise<string> {
  const res = await fetch('https://auth.carto.com/oauth/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      grant_type: 'client_credentials',
      client_id: process.env.CARTO_M2M_CLIENT_ID,
      client_secret: process.env.CARTO_M2M_CLIENT_SECRET,
      audience: 'carto-cloud-native-api',
    }),
  });
  if (!res.ok) throw new Error(`Auth failed: ${res.status}`);
  const { access_token } = await res.json();
  return access_token;
}
```

Cache the token in memory until ~5 minutes before its `expires_in` boundary; refresh on demand.

Pass the token to `@carto/api-client` exactly like any other:

```ts
import { query } from '@carto/api-client';

const accessToken = await getCartoToken();
const result = await query({
  apiBaseUrl: 'https://gcp-us-east1.api.carto.com',
  accessToken,
  connectionName: 'carto_dw',
  sqlQuery: 'SELECT COUNT(*) FROM my_project.demo.points',
});
```

## Lifecycle

```bash
carto credentials list m2m --json
carto credentials get m2m <id>
carto credentials update m2m <id> ...
carto credentials delete m2m <id>      # or `revoke`
```

## When to use this vs alternatives

- **Frontend app, public data** → API access token. M2M overkill.
- **Frontend app, user data** → SPA OAuth. M2M would expose the secret.
- **Backend BFF that proxies for a frontend** → M2M on the backend, then mint short-lived tokens or proxy requests.
- **CI that runs `carto workflows`/`carto maps` commands** → M2M, set as repo secrets.

## Gotchas

- **Never ship the client secret to a browser.** If it's in `.env` consumed by Vite, it's in the bundle.
- **Audience is mandatory** — same as the SPA flow: `audience: 'carto-cloud-native-api'`.
- **Token TTL is short** (typically ~24h). Refresh on demand; don't pin tokens to long-running jobs.
- **One M2M client per workload.** Mixing CI and production scripts on one client makes rotation painful.
