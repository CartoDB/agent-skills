# Auth — hosted on CARTO (`carto app deploy`)

For internal apps: CARTO hosts the static bundle at `https://<workspace>/app/<slug>/` behind the organization login and hands the app **the viewer's own token** at runtime. No OAuth client, no API token, no `.env` secret, no hosting to set up. The app runs as whoever opens it and sees exactly what they can see.

Based on the [Build a hosted application](https://docs.carto.com/carto-for-developers/guides/build-a-hosted-application) guide. Command reference: [`carto app`](https://docs.carto.com/carto-for-agents/cli/command-reference/app).

## When to pick it

Cues: "hosted on CARTO", "internal tool", "for my team / org", "no infrastructure", "deploy it for me", `carto app deploy`. Not for anonymous / public access (use [`auth-public-token.md`](auth-public-token.md) and host elsewhere) and not when the app needs its own server.

## Preflight

```bash
carto app --help          # group is advertised; if the command is unknown, upgrade the CLI
carto app schema --json   # carto.json manifest schema, every field described
carto app schema carto-info --json
```

Deploying needs the Hosted Apps flag on the account. If `carto app deploy` exits with `Hosted apps are not enabled for this account` (`--json`: `"code": "hosted-apps-feature-disabled"`), stop and tell the user to ask their CARTO administrator for access. Do not fall back to another auth model silently.

## Scaffold rules

- `base: './'` in `vite.config.ts` — the bundle is served under `/app/<slug>/`.
- `index.html` at the root of the deployed directory. Limits: 1000 files, 25 MB per file, 50 MB total.
- No `VITE_ACCESS_TOKEN`, no `VITE_CLIENT_ID`. Credentials come from `./carto-info.json` at runtime.
- Dev server: add a `serve`-only Vite middleware that answers `/carto-info.json` from the current CLI profile in `~/.carto_credentials.json` (`profiles[current_profile].token`, `tenant_id` → `https://<tenant_id>.api.carto.com`). Same code path locally and deployed; nothing written to disk.

## `carto-session.ts`

```ts
export interface CartoSession {
  accessToken: string;
  apiBaseUrl: string;
  aiBaseUrl?: string;
  expiresAt?: number;                     // unix seconds; token AND session
  user?: { id: string; accountId: string; email: string | null };
}

export async function loadCartoSession(): Promise<CartoSession> {
  const res = await fetch('./carto-info.json', { credentials: 'include', cache: 'no-store' });
  if (res.status === 401) renewSession();
  if (!res.ok) throw new Error(`carto-info.json returned HTTP ${res.status}`);
  return res.json();
}

export function renewSession(): never {
  const slug = location.pathname.split('/')[2];
  location.assign(`/app/_session?slug=${slug}`);   // sign-in round trip, back with a fresh token
  throw new Error('Renewing the CARTO session');
}
```

Then `apiBaseUrl` + `accessToken` go straight into `vectorTableSource(...)`, widget calls and `fetch(`${apiBaseUrl}/v3/...`)`, exactly like the other auth models.

**Session rules.** The session lasts at most one hour and never outlives the token. Re-fetching `carto-info.json` returns the **same** token: it is not a refresh. Renew via the `/app/_session` navigation shortly before `expiresAt` (save UI state first) or on the first `401`. Never cache or persist the token.

## Backend: named sources in `carto.json`

Ship a `carto.json` next to `index.html` to register parametrized queries at deploy; the app invokes them by name and never carries SQL:

```json
{
  "connections": [{
    "name": "warehouse",
    "provider": "bigquery",
    "sources": {
      "stores_in_state": { "sql": "SELECT cartodb_id, storetype, revenue, geom FROM my_project.retail.stores WHERE state = @state" }
    }
  }]
}
```

- `connections[].name` is a real connection or a handle mapped at deploy: `--connection warehouse=carto_dw`. Validate the real name with `carto connections list --json`.
- Each source is registered as `<slug>_<key>` (`store-explorer_stores_in_state`); keep slug + key within the named-source rules (lowercase, digits, `-`/`_`, ≤ 50 chars).
- Invoke: `POST ${apiBaseUrl}/v3/sql/<connection>/query` with `{ "q": "<slug>_<key>", "queryParameters": { "state": "CA" } }`, or as the `sqlQuery` of a `vectorQuerySource`. Terminal check: `carto sql query <connection> "<slug>_<key>" --param state=CA`.
- Writes: a source may be `INSERT` / `UPDATE` / `DELETE` with `@param`s. It runs as the viewer, so editors need write access on the connection. Use the sync `/query` endpoint and read back to confirm.
- `namespace` / `migrations` are accepted but **not executed** today; `apis` is informational. Don't design around them.

## Deploy cycle

```bash
npm run build
carto app deploy ./dist --name "<App name>" --slug <slug> [--connection <handle>=<real>] --json
carto app share <slug> --org            # private until shared; --group / --user for a subset
carto app versions <slug>               # rollback: carto app rollback <slug> <version>
```

Add `"deploy": "npm run build && carto app deploy dist --name \"…\" --slug <slug>"` to `package.json`. End by printing the app URL from the deploy output.

## Not supported

Anonymous / public access, custom domains, server-side code, cross-organization sharing. If the prompt needs any of these, this is not the auth model.
