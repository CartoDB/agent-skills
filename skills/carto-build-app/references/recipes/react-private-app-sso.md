# Recipe — React private app with corporate SSO

Delta from [`react-private-app-oauth.md`](react-private-app-oauth.md). Same React structure, same `Map.tsx`, same `.env` plus two new vars. The difference is in `auth.ts`.

## Pre-reqs

- The OAuth recipe working first.
- SSO enabled on the org (Enterprise Medium plan and above).
- `VITE_ORGANIZATION_ID` from CARTO support.
- `VITE_ACCOUNTS_URL` (typically `https://app.carto.com/`).

## `.env` additions

```bash
VITE_ORGANIZATION_ID=org_xxx
VITE_ACCOUNTS_URL=https://app.carto.com/
```

## `src/auth.ts` — SSO version

```ts
import { createAuth0Client, type Auth0Client } from '@auth0/auth0-spa-js';

const FORCE_LOGIN_PARAM = 'force-login';
const USER_METADATA_KEY = 'http://app.carto.com/user_metadata';

let auth0Client: Auth0Client | null = null;

export async function initAuth(): Promise<string> {
  if (!auth0Client) {
    auth0Client = await createAuth0Client({
      domain: 'auth.carto.com',
      clientId: import.meta.env.VITE_CLIENT_ID,
      authorizationParams: {
        redirect_uri: window.location.origin,
        audience: 'carto-cloud-native-api',
        organization: import.meta.env.VITE_ORGANIZATION_ID,
      },
      cacheLocation: 'localstorage',
    });
  }

  if (location.search.includes('code=') && location.search.includes('state=')) {
    await auth0Client.handleRedirectCallback();
    window.history.replaceState({}, document.title, window.location.pathname);
  }

  if (!(await auth0Client.isAuthenticated())) {
    await auth0Client.loginWithRedirect();
    return '';
  }

  // First-time provisioning gate
  const user = await auth0Client.getUser();
  if (!user?.[USER_METADATA_KEY]) {
    const accountsUrl = import.meta.env.VITE_ACCOUNTS_URL;
    const orgId = import.meta.env.VITE_ORGANIZATION_ID;
    const redirectUri = `${window.location.origin}?${FORCE_LOGIN_PARAM}=1`;
    window.location.href =
      `${accountsUrl}sso/${orgId}?redirectUri=${encodeURIComponent(redirectUri)}`;
    return '';
  }

  // Force fresh login after provisioning so the new token has full claims
  if (new URLSearchParams(location.search).has(FORCE_LOGIN_PARAM)) {
    await auth0Client.logout({ logoutParams: { returnTo: window.location.origin } });
    return '';
  }

  return auth0Client.getTokenSilently();
}

export async function logout() {
  if (!auth0Client) return;
  await auth0Client.logout({ logoutParams: { returnTo: window.location.origin } });
}

export async function getUser() {
  if (!auth0Client) return null;
  return auth0Client.getUser();
}
```

## What stays the same

- `App.tsx`, `Map.tsx`, `style.css` from the OAuth recipe — unchanged.
- The token returned by `getTokenSilently()` works identically.

## First-login flow

1. User visits the app → no Auth0 session → `loginWithRedirect()` → IdP login page.
2. IdP returns the user → app loads → `user_metadata` is missing.
3. App redirects to `${accountsUrl}sso/${organizationId}?redirectUri=...` for CARTO-side provisioning.
4. CARTO finishes provisioning → redirects back to the app with `?force-login=1`.
5. App sees the param → logs out of Auth0 → next request triggers a fresh login → `user_metadata` is now present → `getTokenSilently()` returns a real token.

The dance only happens once per user.

## Extending

- **Group-based access** → CARTO syncs IdP groups; check `user[USER_METADATA_KEY].groups` to gate UI. Backend should still enforce — SPA gates are advisory.
- **Multiple orgs** → one OAuth client per org. Pick the org based on a tenant subdomain (`acme.myapp.com`) and load the right `VITE_ORGANIZATION_ID` per host.

## Gotchas

- **Provisioning loop.** If the IdP doesn't send the right claims, `user_metadata` never lands. Symptoms: app loops between `/sso/...` and home. Log `await getUser()` during dev — if the metadata key is missing after step 5, fix the IdP claim mapping before debugging the app.
- **`VITE_ACCOUNTS_URL` trailing slash matters** — code concatenates `sso/...` directly.
- **Logout doesn't terminate the IdP session.** For shared devices, also redirect to the IdP's logout endpoint or use `federated: true`.
