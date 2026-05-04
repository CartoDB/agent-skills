# Auth — private app with corporate SSO

Delta from [`auth-private-oauth.md`](auth-private-oauth.md). Same SPA OAuth client and `@auth0/auth0-spa-js`, plus an `organization` parameter and first-login provisioning. Required for orgs that route auth through their IdP (Okta, Azure AD, Google Workspace, etc. — Enterprise Medium plan and above).

Based on [Build a Private Application Using SSO](https://docs.carto.com/carto-for-developers/guides/build-a-private-application-using-sso).

## What changes

1. The SPA OAuth client is the same — created with `carto credentials create spa` exactly as in the non-SSO flow.
2. The app passes `organization: <ORG_ID>` in `authorizationParams` so Auth0 redirects to the IdP.
3. First-time SSO users have no `user_metadata` yet. The app must redirect them to `${accountsUrl}sso/${organizationId}` to complete CARTO-side provisioning, then force a re-login.

## Get the organization ID

CARTO support provides this when SSO is enabled for the org. There's no CLI command for it (yet) — capture it once and store as an env var.

## `.env`

```bash
VITE_API_BASE_URL=https://gcp-us-east1.api.carto.com
VITE_CLIENT_ID=YOUR_SPA_CLIENT_ID
VITE_ORGANIZATION_ID=YOUR_ORG_ID_FROM_CARTO_SUPPORT
VITE_ACCOUNTS_URL=https://app.carto.com/
VITE_CONNECTION_NAME=carto_dw
```

`VITE_ACCOUNTS_URL` must end with `/` — the code concatenates `sso/...` onto it.

## `auth.ts` (SSO version)

```ts
import { createAuth0Client, type Auth0Client } from '@auth0/auth0-spa-js';

const FORCE_LOGIN_PARAM = 'force-login';
const USER_METADATA_KEY = 'http://app.carto.com/user_metadata';

let auth0Client: Auth0Client;

export async function initAuth(): Promise<string> {
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

  if (location.search.includes('code=') && location.search.includes('state=')) {
    await auth0Client.handleRedirectCallback();
    window.history.replaceState({}, document.title, window.location.pathname);
  }

  if (!(await auth0Client.isAuthenticated())) {
    await auth0Client.loginWithRedirect();
    return '';
  }

  // Provisioning gate: first-time SSO user has no user_metadata
  const user = await auth0Client.getUser();
  if (!user?.[USER_METADATA_KEY]) {
    const accountsUrl = import.meta.env.VITE_ACCOUNTS_URL;
    const orgId = import.meta.env.VITE_ORGANIZATION_ID;
    const redirectUri = `${window.location.origin}?${FORCE_LOGIN_PARAM}=1`;
    window.location.href =
      `${accountsUrl}sso/${orgId}?redirectUri=${encodeURIComponent(redirectUri)}`;
    return '';
  }

  // Force re-login after provisioning so the new token has full claims
  if (new URLSearchParams(location.search).has(FORCE_LOGIN_PARAM)) {
    await auth0Client.logout({ logoutParams: { returnTo: window.location.origin } });
    return '';
  }

  return auth0Client.getTokenSilently();
}
```

## Gotchas

- **`organization` must be present** in `authorizationParams` for both `loginWithRedirect` and `getTokenSilently`. The Auth0 SDK threads it automatically once it's in `createAuth0Client` config.
- **`VITE_ACCOUNTS_URL` needs the trailing slash** — the guide's URL construction concatenates `sso/...` directly.
- **Provisioning loop foot-gun.** If the IdP-side claim mapping is wrong, `user_metadata` never lands and the app loops between `/sso/{orgId}` and the home route. Log the full `getUser()` payload during dev.
- **Group / role mapping** is configured server-side in the SSO settings page (`carto-user-manual/settings/sso.md`). The app code does not handle role checks — gate features off your own data, not the IdP groups.
- **Multi-tenant apps** — the guide assumes one org per app instance. For multi-tenant SaaS, you need a tenant picker before `initAuth()` and one OAuth client per tenant.

## What stays the same

The token returned by `getTokenSilently()` works identically with `vectorTableSource`, `h3QuerySource`, etc. The data layer is unchanged from [`auth-private-oauth.md`](auth-private-oauth.md).
