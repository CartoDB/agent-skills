# Recipe — vanilla points + widgets

A single-file vanilla TS app: points on a map, a stat KPI, a category bar chart, a histogram, all filtering against the viewport.

## Pre-reqs

- Vanilla scaffold from [`scaffold-vanilla.md`](../scaffold-vanilla.md).
- A scoped public token from [`auth-public-token.md`](../auth-public-token.md).
- A table of points in your warehouse, e.g. `demo.public.stores(id, geom, category, revenue)`.

## `package.json` additions

Add to `dependencies`:

```text
"echarts": "^5.5.1"
```

## `index.html` — add a side panel

```html
<div id="app">
  <div id="map"></div>
  <canvas id="deck-canvas"></canvas>
  <aside id="panel">
    <h3>Stores</h3>
    <div class="kpi">Total revenue: <span id="kpi-total">—</span></div>
    <div id="chart-cat" class="chart"></div>
    <div id="chart-hist" class="chart"></div>
  </aside>
</div>
```

```css
#panel { position: absolute; top: 16px; right: 16px; width: 320px; background: #fff;
         padding: 16px; border-radius: 8px; box-shadow: 0 2px 12px rgba(0,0,0,.12);
         font: 13px system-ui; }
.kpi { margin-bottom: 12px; font-size: 14px; }
.chart { height: 200px; margin: 8px 0; }
```

## `index.ts`

```ts
import { Deck } from '@deck.gl/core';
import { VectorTileLayer, BASEMAP } from '@deck.gl/carto';
import {
  vectorTableSource,
  createViewportSpatialFilter,
} from '@carto/api-client';
import maplibregl from 'maplibre-gl';
import * as echarts from 'echarts';

const cartoConfig = {
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL,
  accessToken: import.meta.env.VITE_API_ACCESS_TOKEN,
  connectionName: import.meta.env.VITE_CONNECTION_NAME,
};

const INITIAL_VIEW_STATE = { longitude: -73.97, latitude: 40.75, zoom: 12, pitch: 0, bearing: 0 };

const dataSource = vectorTableSource({
  ...cartoConfig,
  tableName: 'demo.public.stores',
});

const map = new maplibregl.Map({
  container: 'map', style: BASEMAP.POSITRON, interactive: false, ...INITIAL_VIEW_STATE,
});

const deck = new Deck({
  canvas: 'deck-canvas',
  initialViewState: INITIAL_VIEW_STATE,
  controller: true,
  layers: [
    new VectorTileLayer({
      id: 'stores',
      data: dataSource,
      pickable: true,
      pointRadiusMinPixels: 3,
      getFillColor: [200, 0, 80],
    }),
  ],
  getTooltip: ({ object }) => object && {
    html: `<b>${object.properties.id}</b><br>${object.properties.category} — $${object.properties.revenue}`,
  },
  onViewStateChange: ({ viewState }) => {
    const { longitude, latitude, zoom, pitch, bearing } = viewState;
    map.jumpTo({ center: [longitude, latitude], zoom, pitch, bearing });
    onMove();
  },
});

const catChart = echarts.init(document.getElementById('chart-cat')!);
const histChart = echarts.init(document.getElementById('chart-hist')!);

let lastFire = 0;
function onMove() {
  const t = Date.now();
  lastFire = t;
  setTimeout(() => { if (lastFire === t) refresh(); }, 300);
}

async function refresh() {
  const { widgetSource } = await dataSource;
  const viewport = deck.getViewports()[0];
  const spatialFilter = createViewportSpatialFilter(viewport.getBounds());

  const [total, byCat, hist] = await Promise.all([
    widgetSource.getFormula({ column: 'revenue', operation: 'sum', spatialFilter }),
    widgetSource.getCategories({ column: 'category', operation: 'count', spatialFilter }),
    widgetSource.getHistogram({
      column: 'revenue',
      ticks: [0, 10_000, 50_000, 100_000, 500_000],
      spatialFilter,
    }),
  ]);

  document.getElementById('kpi-total')!.textContent = total.value.toLocaleString();

  catChart.setOption({
    grid: { left: 80, right: 16, top: 16, bottom: 24 },
    xAxis: { type: 'value' },
    yAxis: { type: 'category', data: byCat.map((c) => c.name) },
    series: [{ type: 'bar', data: byCat.map((c) => c.value) }],
  });

  histChart.setOption({
    grid: { left: 40, right: 16, top: 16, bottom: 24 },
    xAxis: { type: 'category', data: hist.map((b, i) => `${b.tick}+`) },
    yAxis: { type: 'value' },
    series: [{ type: 'bar', data: hist.map((b) => b.value) }],
  });
}

refresh();
```

That's the whole app — ~80 lines. Run `npm run dev`, pan the map, watch the panel update.

## Extending

- **Click a category bar to filter** → see [`filters.md`](../filters.md). Add `chart.on('click', ...)` to mutate `filters` and call `deck.setProps({ layers: [...] })` with a new source.
- **Time series** → add `getTimeSeries` and a third chart. Same pattern.
- **Color-by-category** → swap `getFillColor: [200,0,80]` for `colorCategories({...})` from [`layers.md`](../layers.md), add a legend from [`legend.md`](../legend.md).
