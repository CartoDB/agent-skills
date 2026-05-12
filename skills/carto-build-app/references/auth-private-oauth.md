# Auth — private app with CARTO OAuth (Auth0 SPA)

For apps where users log in with their CARTO account. Uses the **Auth0 OAuth 2.0 authorization code flow** with a **SPA OAuth client** registered in CARTO. Token is fetched at runtime — never bundled.

Based on the [Build a Private Application](https://docs.carto.com/carto-for-developers/guides/build-a-private-application) guide.

## Register the SPA OAuth client autonomously

The agent runs this and parses the JSON — no user interview required.

```bash
carto credentials create spa --json \
  --title "My CARTO App" \
  --callback http://localhost:5173 \
  --logout-url http://localhost:5173 \
  --web-origin http://localhost:5173 \
  --allowed-origin http://localhost:5173 \
  --login-uri http://localhost:5173
#  → { "clientId": "...", "clientSecret": "..." }
```

For a production origin, repeat each flag with the prod URL (`--callback https://myapp.example.com`, etc.). Auth0 requires exact matches per scheme/host/port.

The SPA flow uses **only `clientId`** — never the secret in the browser.

## Install Auth0 SDK

```bash
npm install @auth0/auth0-spa-js
```

## `.env`

```bash
VITE_API_BASE_URL=https://gcp-us-east1.api.carto.com
VITE_CLIENT_ID=YOUR_SPA_CLIENT_ID
VITE_CONNECTION_NAME=carto_dw
```

No `accessToken` — it comes from Auth0 at runtime.

## `auth.ts`

```ts
import { createAuth0Client, type Auth0Client } from '@auth0/auth0-spa-js';

let auth0Client: Auth0Client;

export async function initAuth(): Promise<string> {
  auth0Client = await createAuth0Client({
    domain: 'auth.carto.com',
    clientId: import.meta.env.VITE_CLIENT_ID,
    authorizationParams: {
      redirect_uri: window.location.origin,
      audience: 'carto-cloud-native-api',
    },
    cacheLocation: 'localstorage',
  });

  // Handle the post-login redirect
  if (location.search.includes('code=') && location.search.includes('state=')) {
    await auth0Client.handleRedirectCallback();
    window.history.replaceState({}, document.title, window.location.pathname);
  }

  if (!(await auth0Client.isAuthenticated())) {
    await auth0Client.loginWithRedirect();
    return ''; // redirected; never reached
  }

  return auth0Client.getTokenSilently();
}

export function logout() {
  return auth0Client.logout({ logoutParams: { returnTo: window.location.origin } });
}
```

## Wire into the app

```ts
import { initAuth } from './auth';
import { vectorTableSource } from '@carto/api-client';

const accessToken = await initAuth();

const cartoConfig = {
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL,
  accessToken,
  connectionName: import.meta.env.VITE_CONNECTION_NAME,
};

const dataSource = vectorTableSource({
  ...cartoConfig,
  tableName: 'my_project.private.customers',
});
```

For React, do `initAuth()` in a top-level effect and gate the rest of the tree on the resolved token (recipe in [`recipes/react-private-app-oauth.md`](recipes/react-private-app-oauth.md)).

## Token refresh

`getTokenSilently()` refreshes automatically using a refresh token in `localStorage`. For long-running views, re-call it before expensive ops — Auth0 returns the cached token if still valid, or refreshes silently if not.

## Gotchas

- **`audience` must be exactly `'carto-cloud-native-api'`.** Without it, the issued token is not accepted by CARTO APIs.
- **`domain: 'auth.carto.com'`** is hard-coded — it's CARTO's tenant in Auth0, not your subdomain.
- **Callback URL must match exactly** what was registered (scheme, host, port, trailing slash). `http://localhost:5173/` ≠ `http://localhost:5173`.
- **Don't store the token outside Auth0's cache.** Use `getTokenSilently()` each time you need it; don't stash it in app state for hours.
- **Logout doesn't invalidate the CARTO session server-side** — it clears Auth0's local cache. For shared devices that's a real concern; couple it with `federated: true` if needed.

## SSO variant

If the user signs in with a corporate IdP (Okta, Azure AD, Google Workspace via SSO), use [`auth-private-sso.md`](auth-private-sso.md) — same SDK, extra `organization` parameter and a first-login provisioning dance.
