# Recipe — React private app with CARTO OAuth

A React app gated by CARTO login. Users authenticate via Auth0; the token flows into `@carto/api-client` exactly like a static token.

## Pre-reqs

- React scaffold from [`scaffold-react.md`](../scaffold-react.md).
- A SPA OAuth client from [`auth-private-oauth.md`](../auth-private-oauth.md).
- `@auth0/auth0-spa-js` installed.

## `.env`

```bash
VITE_API_BASE_URL=https://gcp-us-east1.api.carto.com
VITE_CLIENT_ID=YOUR_SPA_CLIENT_ID
VITE_CONNECTION_NAME=carto_dw
```

## `src/auth.ts`

```ts
import { createAuth0Client, type Auth0Client } from '@auth0/auth0-spa-js';

let auth0Client: Auth0Client | null = null;

export async function initAuth(): Promise<string> {
  if (!auth0Client) {
    auth0Client = await createAuth0Client({
      domain: 'auth.carto.com',
      clientId: import.meta.env.VITE_CLIENT_ID,
      authorizationParams: {
        redirect_uri: window.location.origin,
        audience: 'carto-cloud-native-api',
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

## `src/App.tsx`

```tsx
import { useEffect, useState } from 'react';
import { initAuth, logout, getUser } from './auth';
import Map from './components/Map';

export default function App() {
  const [accessToken, setAccessToken] = useState<string>('');
  const [user, setUser] = useState<{ name?: string; email?: string } | null>(null);

  useEffect(() => {
    initAuth().then(async (token) => {
      if (!token) return;     // redirected to login; never resolves here
      setAccessToken(token);
      setUser(await getUser());
    });
  }, []);

  if (!accessToken) {
    return <div className="loading">Signing you in…</div>;
  }

  return (
    <div className="app">
      <header>
        <span>Hello, {user?.name ?? user?.email ?? 'CARTO user'}</span>
        <button onClick={logout}>Log out</button>
      </header>
      <Map accessToken={accessToken} />
    </div>
  );
}
```

## `src/components/Map.tsx`

```tsx
import { useMemo } from 'react';
import DeckGL from '@deck.gl/react';
import { VectorTileLayer, BASEMAP } from '@deck.gl/carto';
import { vectorTableSource } from '@carto/api-client';
import { Map as MaplibreMap } from 'react-map-gl/maplibre';

const INITIAL_VIEW_STATE = { longitude: -73.97, latitude: 40.75, zoom: 12, pitch: 0, bearing: 0 };

export default function Map({ accessToken }: { accessToken: string }) {
  const dataSource = useMemo(() => vectorTableSource({
    apiBaseUrl: import.meta.env.VITE_API_BASE_URL,
    accessToken,
    connectionName: import.meta.env.VITE_CONNECTION_NAME,
    tableName: 'private_project.private_dataset.customer_locations',
  }), [accessToken]);

  const layers = [
    new VectorTileLayer({
      id: 'customers',
      data: dataSource,
      pickable: true,
      pointRadiusMinPixels: 3,
      getFillColor: [40, 100, 200],
    }),
  ];

  return (
    <DeckGL initialViewState={INITIAL_VIEW_STATE} controller layers={layers}>
      <MaplibreMap mapStyle={BASEMAP.POSITRON} />
    </DeckGL>
  );
}
```

## `src/style.css`

```css
* { box-sizing: border-box; }
html, body, #root { margin: 0; height: 100%; font-family: system-ui, sans-serif; }
.app { position: relative; height: 100vh; }
header { position: absolute; top: 16px; left: 16px; z-index: 1; background: #fff;
         padding: 8px 12px; border-radius: 6px; display: flex; gap: 12px; align-items: center;
         box-shadow: 0 2px 8px rgba(0,0,0,.1); }
.loading { display: grid; place-items: center; height: 100vh; color: #666; }
```

## Token refresh in long sessions

`getTokenSilently()` returns a cached token if valid, refreshes otherwise. For long-running views, re-call before expensive operations:

```tsx
const refreshAndQuery = async () => {
  const fresh = await getTokenSilently();
  setAccessToken(fresh);
  // re-fetch / re-query with `fresh`
};
```

## Extending

- **SSO** → swap `auth.ts` for the SSO version in [`auth-private-sso.md`](../auth-private-sso.md). Everything else stays.
- **Role-based UI gating** → read claims from `getUser()` and conditionally render. Don't trust client-side gates for security; the backend / CARTO API still enforces.
- **Backend BFF** → use M2M from [`auth-m2m.md`](../auth-m2m.md) on a Node server, keep the SPA flow only for user identity, proxy CARTO calls server-side.
