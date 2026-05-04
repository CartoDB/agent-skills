# Scaffold — vanilla TypeScript + Vite + MapLibre

The default for **demos, learning, and tiny apps**. Mirrors the [CartoDB/deck.gl-examples](https://github.com/CartoDB/deck.gl-examples) layout exactly — every example in that repo follows this shape, so the user can read upstream code and recognize the pattern.

## File layout

```
my-app/
├── index.html
├── index.ts
├── style.css
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
    "build": "tsc && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "@deck.gl/core": "^9.2.0",
    "@deck.gl/layers": "^9.2.0",
    "@deck.gl/geo-layers": "^9.2.0",
    "@deck.gl/aggregation-layers": "^9.2.0",
    "@deck.gl/extensions": "^9.2.0",
    "@deck.gl/carto": "^9.2.0",
    "@carto/api-client": "^0.5.21",
    "maplibre-gl": "^3.5.2"
  },
  "devDependencies": {
    "typescript": "^5.4.0",
    "vite": "^4.5.0"
  }
}
```

Add `echarts` only if widgets are involved. Add `@auth0/auth0-spa-js` only for private apps.

## `tsconfig.json`

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "isolatedModules": true,
    "types": ["vite/client"]
  },
  "include": ["index.ts", "src"]
}
```

## `index.html`

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>My CARTO App</title>
    <link rel="stylesheet" href="https://unpkg.com/maplibre-gl@3.5.2/dist/maplibre-gl.css" />
    <link rel="stylesheet" href="./style.css" />
  </head>
  <body>
    <div id="app">
      <div id="map"></div>
      <canvas id="deck-canvas"></canvas>
    </div>
    <script type="module" src="./index.ts"></script>
  </body>
</html>
```

`#map` and `#deck-canvas` are stacked. The deck.gl canvas handles interaction; MapLibre is a passive basemap. See [`basemap-and-view.md`](basemap-and-view.md).

## `style.css`

```css
* { box-sizing: border-box; }
html, body { margin: 0; height: 100%; font-family: system-ui, sans-serif; }
#app { position: relative; height: 100vh; width: 100vw; }
#map, #deck-canvas { position: absolute; top: 0; left: 0; height: 100%; width: 100%; }
```

## `.env.example`

```bash
VITE_API_BASE_URL=https://gcp-us-east1.api.carto.com
VITE_API_ACCESS_TOKEN=your-scoped-token
VITE_CONNECTION_NAME=carto_dw
```

`.env` is gitignored. `.env.example` is committed.

## `index.ts` skeleton

```ts
import { Deck } from '@deck.gl/core';
import { BASEMAP } from '@deck.gl/carto';
import maplibregl from 'maplibre-gl';

const cartoConfig = {
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL,
  accessToken: import.meta.env.VITE_API_ACCESS_TOKEN,
  connectionName: import.meta.env.VITE_CONNECTION_NAME,
};

const INITIAL_VIEW_STATE = {
  longitude: -73.97,
  latitude: 40.75,
  zoom: 12,
  pitch: 0,
  bearing: 0,
};

// 1. Build a data source — see references/data-sources.md
// 2. Build a layer — see references/layers.md
// 3. Wire up deck.gl + MapLibre

const map = new maplibregl.Map({
  container: 'map',
  style: BASEMAP.POSITRON,
  interactive: false,
  ...INITIAL_VIEW_STATE,
});

const deck = new Deck({
  canvas: 'deck-canvas',
  initialViewState: INITIAL_VIEW_STATE,
  controller: true,
  layers: [/* ... */],
  onViewStateChange: ({ viewState }) => {
    const { longitude, latitude, ...rest } = viewState;
    map.jumpTo({ center: [longitude, latitude], ...rest });
  },
});
```

## Optional add-ons

- **Side panel** — add `<aside id="panel">` to `index.html` and grid-layout it in `style.css`. Mount widget charts into `<div>`s with `echarts.init(node)`.
- **Routing** — none. If the user wants routes, switch to React.
- **State management** — none. If the user wants Redux/Zustand-grade state, switch to React.

## When to recommend this scaffold

- Demos / examples / tutorials.
- One-screen apps with at most a side panel.
- The user explicitly says "no React" or "keep it simple".

For anything bigger, [`scaffold-react.md`](scaffold-react.md).
