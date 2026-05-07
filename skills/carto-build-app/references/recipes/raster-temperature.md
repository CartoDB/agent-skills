# Recipe — raster temperature map

A vanilla TS app that renders a continuous raster (e.g. land-surface temperature) with a colormap and a continuous-gradient legend.

## Pre-reqs

- Vanilla scaffold from [`scaffold-vanilla.md`](../scaffold-vanilla.md).
- A scoped public token from [`auth-public-token.md`](../auth-public-token.md).
- A raster table in your warehouse, e.g. `demo.public.lst_celsius`.
- `npm install cartocolor` for the temperature palette (`@deck.gl/carto` v9 does **not** re-export `CARTOColors`).

## `index.html`

```html
<div id="app">
  <div id="map"></div>
  <canvas id="deck-canvas"></canvas>
  <div id="legend">
    <h4>Land surface temperature (°C)</h4>
    <div id="legend-bar"></div>
    <div id="legend-labels"></div>
  </div>
</div>
```

```css
#legend { position: absolute; bottom: 16px; right: 16px; background: #fff; padding: 12px 16px;
          border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,.1); font: 12px system-ui;
          width: 280px; }
#legend h4 { margin: 0 0 8px; font-size: 12px; }
#legend-bar { height: 14px; border-radius: 4px; }
#legend-labels { display: flex; justify-content: space-between; margin-top: 4px;
                 font-size: 11px; color: #444; }
```

## `index.ts`

```ts
import { Deck } from '@deck.gl/core';
import { RasterTileLayer, BASEMAP } from '@deck.gl/carto';
import { rasterSource } from '@carto/api-client';
import * as cartoColors from 'cartocolor';
import maplibregl from 'maplibre-gl';

const cartoConfig = {
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL,
  accessToken: import.meta.env.VITE_API_ACCESS_TOKEN,
  connectionName: import.meta.env.VITE_CONNECTION_NAME,
};

const INITIAL_VIEW_STATE = { longitude: -98.5, latitude: 39.5, zoom: 4, pitch: 0, bearing: 0 };

const TEMP_MIN = -10;
const TEMP_MAX = 45;
// `cartocolor` returns hex strings; deck.gl `getFillColor` wants `[r,g,b]`.
const TEMP_HEX = cartoColors.Temps[7] as string[];           // Temps/Tropic/Earth = divergent
const hexToRgb = (h: string): [number, number, number] => [
  parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16),
];
const TEMP_STOPS = TEMP_HEX.map(hexToRgb);

const dataSource = rasterSource({
  ...cartoConfig,
  tableName: 'demo.public.lst_celsius',
});

const map = new maplibregl.Map({
  container: 'map', style: BASEMAP.POSITRON_NOLABELS, interactive: false, ...INITIAL_VIEW_STATE,
});

new Deck({
  canvas: 'deck-canvas',
  initialViewState: INITIAL_VIEW_STATE,
  controller: true,
  layers: [
    new RasterTileLayer({
      id: 'lst',
      data: dataSource,
      opacity: 0.75,
      // For raster, the color comes from a sampled colormap function.
      // For demo, deck.gl auto-applies the source's metadata; for full control,
      // map raw values → palette index manually:
      getFillColor: (cell: any) => {
        const t = cell.properties.value as number;
        const ratio = (t - TEMP_MIN) / (TEMP_MAX - TEMP_MIN);
        const i = Math.max(0, Math.min(TEMP_STOPS.length - 1, Math.floor(ratio * TEMP_STOPS.length)));
        return TEMP_STOPS[i];
      },
    }),
  ],
  onViewStateChange: ({ viewState }) => {
    const { longitude, latitude, zoom, pitch, bearing } = viewState;
    map.jumpTo({ center: [longitude, latitude], zoom, pitch, bearing });
  },
});

// Continuous gradient legend (CSS gradient takes hex strings directly)
const bar = document.getElementById('legend-bar')!;
bar.style.background = `linear-gradient(to right, ${TEMP_HEX.join(',')})`;

const labels = document.getElementById('legend-labels')!;
labels.innerHTML = `<span>${TEMP_MIN}°</span><span>0°</span><span>${TEMP_MAX}°</span>`;
```

## Notes on raster styling

The example above shows the **manual** colormap path because it works for any raster. CARTO rasters often ship with metadata hints (`colorRange`, `tileStats`) that `RasterTileLayer` can use automatically — check the [`raster-temperature` upstream example](https://github.com/CartoDB/deck.gl-examples/tree/master/raster-temperature) for the data-driven approach.

## Extending

- **Hover readouts** → add `getTooltip` that reads `object.properties.value` and shows the actual temperature at that cell.
- **Time series of rasters** → add a year/month dropdown, swap `tableName` per selection. Since the source is recreated, deck.gl re-fetches automatically.
- **Combine with vector overlay** → add a `VectorTileLayer` of cities on top with `pointRadiusMinPixels: 2` so users can locate themselves on the heatmap.

## Gotchas

- **Raster cell size grows** with zoom-out. At zoom 4 you might have 1°×1° cells; at zoom 10, native resolution. Set `pickable: false` if you don't need hover (saves picking buffer memory).
- **Opacity below 0.6 makes basemap labels confusing.** Pair raster layers with `BASEMAP.POSITRON_NOLABELS` or `DARK_MATTER_NOLABELS` and add labels back as a top deck.gl layer if needed.
- **Temperature data is divergent** (negatives matter). Use a divergent palette (`Temps`, `Tropic`) and center the colormap on a meaningful value (e.g. 0°C), not on the data midpoint.
