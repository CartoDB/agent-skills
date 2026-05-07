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
    "@deck.gl/core": "^9.2.2",
    "@deck.gl/layers": "^9.2.2",
    "@deck.gl/geo-layers": "^9.2.6",
    "@deck.gl/aggregation-layers": "^9.2.6",
    "@deck.gl/extensions": "^9.2.6",
    "@deck.gl/carto": "^9.2.2",
    "@carto/api-client": "^0.5.24",
    "maplibre-gl": "^5.12.0"
  },
  "devDependencies": {
    "typescript": "~5.8.3",
    "vite": "^6.0.0"
  }
}
```

Add `cartocolor` for legends, `echarts` for widgets, `@auth0/auth0-spa-js` for private apps.

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
    <link rel="stylesheet" href="https://unpkg.com/maplibre-gl@5/dist/maplibre-gl.css" />
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

Meridian-inspired defaults. Override these tokens for a custom theme — see [`design-and-theming.md`](design-and-theming.md).

```css
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');

:root {
  --color-primary: #036FE2;
  --color-primary-light: #358BE7;
  --color-primary-dark: #024D9E;
  --color-bg: #F8F9F9;
  --color-surface: #FFFFFF;
  --color-text: #2C3032;
  --color-text-secondary: #6F777C;
  --color-border: #E1E3E4;
  --font-family: 'Inter', system-ui, -apple-system, sans-serif;
  --radius-sm: 4px;
  --radius-md: 8px;
  --shadow-md: 0 4px 12px rgba(44,48,50,0.10);
}

* { box-sizing: border-box; margin: 0; }
html, body { height: 100%; font: 400 14px/1.5 var(--font-family); color: var(--color-text); background: var(--color-bg); }
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

- **Side panel** — add `<aside id="panel">` to `index.html` and style with the design tokens (see [`design-and-theming.md`](design-and-theming.md)). Mount widget charts into `<div>`s with `echarts.init(node)`.
- **Routing** — none. If the user wants routes, switch to React.
- **State management** — none. If the user wants Redux/Zustand-grade state, switch to React.

## When to recommend this scaffold

- Demos / examples / tutorials.
- One-screen apps with at most a side panel.
- The user explicitly says "no React" or "keep it simple".

For anything bigger, [`scaffold-react.md`](scaffold-react.md).
