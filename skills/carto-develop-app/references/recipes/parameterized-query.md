# Recipe — parameterized query with dropdown + slider

A vanilla TS app where the user picks a region and a minimum revenue threshold, and the map re-fetches against a parameterized SQL source.

## Pre-reqs

- Vanilla scaffold from [`scaffold-vanilla.md`](../scaffold-vanilla.md).
- A scoped public token from [`auth-public-token.md`](../auth-public-token.md).

## `index.html`

```html
<div id="app">
  <div id="map"></div>
  <canvas id="deck-canvas"></canvas>
  <aside id="panel">
    <h3>Filter stores</h3>
    <label>Region
      <select id="region">
        <option value="NY">New York</option>
        <option value="CA">California</option>
        <option value="TX">Texas</option>
      </select>
    </label>
    <label>Min revenue: <output id="min-out">0</output>
      <input id="min" type="range" min="0" max="500000" step="1000" value="0" />
    </label>
    <div class="kpi">Visible: <span id="kpi">—</span></div>
  </aside>
</div>
```

```css
#panel label { display: block; margin: 12px 0; font-size: 13px; }
#panel select, #panel input { width: 100%; margin-top: 4px; }
.kpi { margin-top: 12px; font-size: 14px; font-weight: 600; }
```

## `index.ts`

```ts
import { Deck } from '@deck.gl/core';
import { VectorTileLayer, BASEMAP } from '@deck.gl/carto';
import { vectorQuerySource, query } from '@carto/api-client';
import maplibregl from 'maplibre-gl';

const cartoConfig = {
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL,
  accessToken: import.meta.env.VITE_API_ACCESS_TOKEN,
  connectionName: import.meta.env.VITE_CONNECTION_NAME,
};

const INITIAL_VIEW_STATE = { longitude: -98.5, latitude: 39.5, zoom: 4, pitch: 0, bearing: 0 };

let region = 'NY';
let minRevenue = 0;

function buildSource() {
  return vectorQuerySource({
    ...cartoConfig,
    sqlQuery: `
      SELECT id, geom, name, region, revenue
      FROM demo.public.stores
      WHERE region = @region
        AND revenue >= @min
    `,
    queryParameters: { region, min: minRevenue },
  });
}

let dataSource = buildSource();

const map = new maplibregl.Map({
  container: 'map', style: BASEMAP.POSITRON, interactive: false, ...INITIAL_VIEW_STATE,
});

const deck = new Deck({
  canvas: 'deck-canvas',
  initialViewState: INITIAL_VIEW_STATE,
  controller: true,
  layers: [layer()],
  onViewStateChange: ({ viewState }) => {
    const { longitude, latitude, zoom, pitch, bearing } = viewState;
    map.jumpTo({ center: [longitude, latitude], zoom, pitch, bearing });
  },
});

function layer() {
  return new VectorTileLayer({
    id: 'stores',
    data: dataSource,
    pickable: true,
    pointRadiusMinPixels: 3,
    getFillColor: [40, 140, 80],
  });
}

document.getElementById('region')!.addEventListener('change', (e) => {
  region = (e.target as HTMLSelectElement).value;
  rebuild();
});

const minOut = document.getElementById('min-out')!;
let sliderTimer: number | undefined;
document.getElementById('min')!.addEventListener('input', (e) => {
  const v = +(e.target as HTMLInputElement).value;
  minOut.textContent = v.toLocaleString();
  if (sliderTimer) clearTimeout(sliderTimer);
  sliderTimer = window.setTimeout(() => { minRevenue = v; rebuild(); }, 200);
});

async function rebuild() {
  dataSource = buildSource();
  deck.setProps({ layers: [layer()] });

  // Refresh the count via a separate query()
  const { rows } = await query({
    ...cartoConfig,
    sqlQuery: 'SELECT COUNT(*) AS n FROM demo.public.stores WHERE region = @region AND revenue >= @min',
    queryParameters: { region, min: minRevenue },
  });
  document.getElementById('kpi')!.textContent = rows[0].n.toLocaleString();
}

rebuild();
```

## Why two patterns in one app

- The **layer** uses `vectorQuerySource` because it needs to be tile-aware and fast across pans/zooms.
- The **count** uses `query()` because it's a single number that doesn't need tiling.

Both share the same `queryParameters` shape, so the parameter contract is in one place.

## Extending

- **Multi-region select** → swap `region = @region` for `region IN UNNEST(@regions)` (BigQuery / Snowflake) or `region = ANY(@regions)` (Postgres). Pass an array.
- **Date range** → add two date inputs and `created_at BETWEEN @start AND @end`.
- **Save query as a workflow** → see [`workflows-and-sql.md`](../workflows-and-sql.md) — call the workflow's stored proc instead of inlining SQL.

## Gotchas

- **Don't string-concat user input into `sqlQuery`** — use `queryParameters`. The temptation is real because it feels simpler; it's also a SQL injection foot-gun.
- **Source recreation triggers a full re-fetch.** Throttle aggressive inputs (sliders, search-as-you-type) with a 150–250 ms debounce.
- **`query()` row limits** — the SQL API caps result size. For counts and small results it's fine; for large data you want a query source, not `query()`.
