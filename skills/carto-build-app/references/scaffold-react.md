# Scaffold — React + Vite + `@deck.gl/react`

The **production default**. Use for any app that will be shipped, has more than one screen, has user state, or will be maintained by a team.

## File layout

```
my-app/
├── index.html
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── auth.ts            # only for private apps
│   ├── components/
│   │   ├── Map.tsx
│   │   ├── Legend.tsx
│   │   └── Panel.tsx
│   └── style.css
├── .env
├── .env.example
├── package.json
├── tsconfig.json
└── vite.config.ts
```

## `package.json`

```json
{
  "name": "my-carto-app",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^19.1.0",
    "react-dom": "^19.1.0",
    "@deck.gl/core": "^9.2.2",
    "@deck.gl/react": "^9.2.2",
    "@deck.gl/layers": "^9.2.2",
    "@deck.gl/geo-layers": "^9.2.6",
    "@deck.gl/aggregation-layers": "^9.2.6",
    "@deck.gl/extensions": "^9.2.6",
    "@deck.gl/carto": "^9.2.2",
    "@carto/api-client": "^0.5.24",
    "maplibre-gl": "^5.12.0",
    "react-map-gl": "^8.1.0"
  },
  "devDependencies": {
    "@types/react": "^19.1.0",
    "@types/react-dom": "^19.1.0",
    "@vitejs/plugin-react": "^4.5.2",
    "typescript": "~5.8.3",
    "vite": "^6.0.0"
  }
}
```

Add `cartocolor` for legends, `@auth0/auth0-spa-js` for OAuth/SSO, `echarts` + `echarts-for-react` for widgets.

These versions track the [CartoDB/deck.gl-examples](https://github.com/CartoDB/deck.gl-examples) React reference (`ai-tools-advanced-integrations/frontend-integration/react/package.json`). React 19 + Vite 6 + react-map-gl 8 + MapLibre GL 5 are the current peer-tested combination.

## `vite.config.ts`

```ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
});
```

## `src/main.tsx`

```tsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './style.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
```

## `src/App.tsx`

```tsx
import { useEffect, useState } from 'react';
import Map from './components/Map';

export default function App() {
  const [accessToken, setAccessToken] = useState<string>(
    import.meta.env.VITE_API_ACCESS_TOKEN ?? '',
  );

  // For private apps, replace the line above with:
  // useEffect(() => { initAuth().then(setAccessToken); }, []);

  if (!accessToken) return <div>Loading…</div>;
  return <Map accessToken={accessToken} />;
}
```

## `src/components/Map.tsx`

```tsx
import { useMemo } from 'react';
import DeckGL from '@deck.gl/react';
import { VectorTileLayer, BASEMAP } from '@deck.gl/carto';
import { vectorTableSource } from '@carto/api-client';
import { Map as MaplibreMap } from 'react-map-gl/maplibre';

const INITIAL_VIEW_STATE = {
  longitude: -73.97,
  latitude: 40.75,
  zoom: 12,
  pitch: 0,
  bearing: 0,
};

export default function Map({ accessToken }: { accessToken: string }) {
  const dataSource = useMemo(() => vectorTableSource({
    apiBaseUrl: import.meta.env.VITE_API_BASE_URL,
    accessToken,
    connectionName: import.meta.env.VITE_CONNECTION_NAME,
    tableName: 'my_project.demo.points',
  }), [accessToken]);

  const layers = [
    new VectorTileLayer({
      id: 'points',
      data: dataSource,
      pointRadiusMinPixels: 3,
      getFillColor: [200, 0, 80],
    }),
  ];

  return (
    <DeckGL initialViewState={INITIAL_VIEW_STATE} controller layers={layers}>
      <MaplibreMap mapStyle={BASEMAP.POSITRON} />
    </DeckGL>
  );
}
```

`@deck.gl/react` handles canvas + view state; `react-map-gl/maplibre` renders the basemap as a child component, fully synced.

## State patterns

- **Filters** — keep the shared `filters` object in a `useState` or `useReducer` at `<App>` level, pass to source factories *and* widgets. Mutating triggers re-render → re-fetch.
- **Spatial filter** — `useState` for `viewState`, debounce 300 ms before recomputing `createViewportSpatialFilter(...)` (use `useDeferredValue` or a small custom hook).
- **Auth** — `initAuth()` in a top-level effect, gate the tree on the token.

## When to recommend this scaffold

- The user mentions "production", "users", "auth", "deploy", "team", "Vercel/Netlify".
- More than one screen / panel / route.
- Anything beyond a single map + side panel.

For learning examples or single-file demos, [`scaffold-vanilla.md`](scaffold-vanilla.md). For Vue or Angular, [`scaffold-vue-angular.md`](scaffold-vue-angular.md).
