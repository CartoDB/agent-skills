# Recipe — React H3 aggregation

A React + Vite app that renders an H3-aggregated dataset (population by H3 cell) with 3D extrusion, a category legend, and a viewport KPI.

## Pre-reqs

- React scaffold from [`scaffold-react.md`](../scaffold-react.md).
- A scoped public token from [`auth-public-token.md`](../auth-public-token.md).
- An H3-aggregated table, e.g. `demo.public.population_h3(h3, population)`.

## `src/App.tsx`

```tsx
import { useMemo, useState } from 'react';
import DeckGL from '@deck.gl/react';
import { H3TileLayer, BASEMAP, colorBins } from '@deck.gl/carto';
import { h3TableSource } from '@carto/api-client';
import { Map as MaplibreMap } from 'react-map-gl/maplibre';
import Legend from './components/Legend';
import KPI from './components/KPI';

const INITIAL_VIEW_STATE = {
  longitude: -98.5, latitude: 39.5, zoom: 4, pitch: 45, bearing: 0,
};

const POP_DOMAIN = [100, 1_000, 10_000, 100_000, 1_000_000];
const POP_PALETTE = 'Sunset' as const;

export default function App() {
  const accessToken = import.meta.env.VITE_API_ACCESS_TOKEN;

  const dataSource = useMemo(() => h3TableSource({
    apiBaseUrl: import.meta.env.VITE_API_BASE_URL,
    accessToken,
    connectionName: import.meta.env.VITE_CONNECTION_NAME,
    tableName: 'demo.public.population_h3',
    aggregationExp: 'SUM(population) AS population',
    aggregationResLevel: 4,
  }), [accessToken]);

  const layers = useMemo(() => [
    new H3TileLayer({
      id: 'pop',
      data: dataSource,
      pickable: true,
      filled: true,
      extruded: true,
      getFillColor: colorBins({
        attr: 'population',
        domain: POP_DOMAIN,
        colors: POP_PALETTE,
      }),
      getElevation: (d: any) => d.properties.population / 50,
      elevationScale: 1,
    }),
  ], [dataSource]);

  return (
    <div className="app">
      <DeckGL
        initialViewState={INITIAL_VIEW_STATE}
        controller
        layers={layers}
        getTooltip={({ object }: any) => object && {
          html: `<b>H3 ${object.id}</b><br>Population: ${object.properties.population.toLocaleString()}`,
        }}
      >
        <MaplibreMap mapStyle={BASEMAP.POSITRON} />
      </DeckGL>
      <KPI dataSource={dataSource} />
      <Legend title="Population" domain={POP_DOMAIN} palette={POP_PALETTE} />
    </div>
  );
}
```

## `src/components/KPI.tsx`

```tsx
import { useEffect, useState } from 'react';
import type { H3TableSourceResult } from '@carto/api-client';

export default function KPI({ dataSource }: { dataSource: Promise<H3TableSourceResult> }) {
  const [total, setTotal] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const { widgetSource } = await dataSource;
      const result = await widgetSource.getFormula({ column: 'population', operation: 'sum' });
      if (!cancelled) setTotal(result.value);
    })();
    return () => { cancelled = true; };
  }, [dataSource]);

  return (
    <div className="kpi-card">
      <div className="kpi-label">Total population</div>
      <div className="kpi-value">{total ? total.toLocaleString() : '—'}</div>
    </div>
  );
}
```

## `src/components/Legend.tsx`

`@deck.gl/carto` v9 does **not** re-export `CARTOColors`. Pull palette stops from the `cartocolor` package (`npm i cartocolor`). See [`legend.md`](../legend.md) for the full pattern.

```tsx
import * as cartoColors from 'cartocolor';

export default function Legend({
  title, domain, palette,
}: { title: string; domain: number[]; palette: string }) {
  const buckets = domain.length + 1;
  const colors = cartoColors[palette][buckets] as string[];   // hex strings
  const labels = [
    `< ${domain[0].toLocaleString()}`,
    ...domain.slice(0, -1).map((d, i) => `${d.toLocaleString()}–${domain[i + 1].toLocaleString()}`),
    `≥ ${domain.at(-1)!.toLocaleString()}`,
  ];
  return (
    <div className="legend">
      <h4>{title}</h4>
      {labels.map((label, i) => (
        <div key={i} className="legend-row">
          <span className="legend-swatch" style={{ background: colors[i] }} />
          <span>{label}</span>
        </div>
      ))}
    </div>
  );
}
```

`cartocolor` ships without bundled types — add `declare module 'cartocolor';` to a `.d.ts` if TS complains.

## `src/style.css`

```css
* { box-sizing: border-box; }
html, body, #root { margin: 0; height: 100%; font-family: system-ui, sans-serif; }
.app { position: relative; height: 100vh; width: 100vw; }
.kpi-card { position: absolute; top: 16px; left: 16px; background: #fff; padding: 12px 16px;
            border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,.1); }
.kpi-label { font-size: 11px; color: #888; text-transform: uppercase; }
.kpi-value { font-size: 20px; font-weight: 600; }
.legend { position: absolute; right: 16px; bottom: 16px; background: #fff; padding: 12px 16px;
          border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,.1); font-size: 12px; }
.legend h4 { margin: 0 0 8px; font-size: 12px; }
.legend-row { display: flex; align-items: center; gap: 8px; margin: 2px 0; }
.legend-swatch { width: 14px; height: 14px; border-radius: 2px; }
```

## Extending

- **Filter by population threshold** → add a `<input type="range">`, drop `aggregationExp` to a query source with a `WHERE`.
- **Switch to viewport-scoped KPI** → see [`widgets.md`](../widgets.md) for the debounced viewport pattern; pass `spatialFilter` to `getFormula`.
- **Toggle resolution** → add a select for `aggregationResLevel` (3..6), include in the `useMemo` deps. Lower numbers = bigger cells = fewer tiles.
