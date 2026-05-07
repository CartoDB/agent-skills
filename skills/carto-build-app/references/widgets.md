# Widgets

Charts and stat cards that read from the same `widgetSource` returned by every data source. Server-side aggregation for table/query sources, Web Worker for tileset/raster.

## The seven widget models

| Method | Returns | Typical UI |
|---|---|---|
| `getFormula` | A single number | KPI / stat card |
| `getCategories` | Top-N categories with counts | Bar chart |
| `getHistogram` | `number[]` aligned to `ticks` (length `ticks.length + 1`, with under/overflow at ends) | Histogram |
| `getRange` | `{ min, max }` | Slider bounds |
| `getTimeSeries` | Time-bucketed values | Line / area chart |
| `getScatter` | Sample points | Scatter plot |
| `getTable` | Paginated rows | Data table |

## Pattern (vanilla / Vue / Angular)

```ts
import {
  vectorTableSource,
  createViewportSpatialFilter,
} from '@carto/api-client';

const dataSource = vectorTableSource({ ...cartoConfig, tableName: 'demo.public.stores' });

async function refreshWidgets(viewport) {
  const spatialFilter = createViewportSpatialFilter(viewport.getBounds());
  const { widgetSource } = await dataSource;

  const total = await widgetSource.getFormula({
    column: 'revenue',
    operation: 'sum',
    spatialFilter,
  });

  const byCategory = await widgetSource.getCategories({
    column: 'category',
    operation: 'count',
    spatialFilter,
  });

  const hist = await widgetSource.getHistogram({
    column: 'revenue',
    ticks: [0, 10_000, 50_000, 100_000, 500_000],
    spatialFilter,
  });

  renderKPI(total);
  renderBarChart(byCategory);
  renderHistogram(hist);
}

deck.setProps({
  onViewStateChange: debounce(({ viewState }) => {
    /* sync map */
    refreshWidgets(deck.getViewports()[0]);
  }, 300),
});
```

## Pattern (React)

The cleanest React shape is to lift the **viewport** (not just `viewState`) out of `DeckGL` via `onViewStateChange` and pass it down. `viewport.getBounds()` returns `[west, south, east, north]` — exactly what `createViewportSpatialFilter` wants. No helper needed.

```tsx
import { useEffect, useMemo, useState } from 'react';
import { WebMercatorViewport } from '@deck.gl/core';
import { vectorTableSource, createViewportSpatialFilter } from '@carto/api-client';

function useDebounced<T>(value: T, ms = 300): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return debounced;
}

function Widgets({ accessToken, viewState }: {
  accessToken: string;
  viewState: { longitude: number; latitude: number; zoom: number; pitch: number; bearing: number };
}) {
  const dataSource = useMemo(() => vectorTableSource({
    apiBaseUrl: import.meta.env.VITE_API_BASE_URL,
    accessToken,
    connectionName: import.meta.env.VITE_CONNECTION_NAME,
    tableName: 'demo.public.stores',
  }), [accessToken]);

  const debouncedView = useDebounced(viewState);
  const [stats, setStats] = useState<{ total?: { value: number } } | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const { widgetSource } = await dataSource;
      // Build a viewport from the current view state, then read bounds.
      // WebMercatorViewport(viewState) needs width/height — pass the rendering surface size.
      const viewport = new WebMercatorViewport({
        ...debouncedView,
        width: window.innerWidth,
        height: window.innerHeight,
      });
      const spatialFilter = createViewportSpatialFilter(viewport.getBounds());
      const total = await widgetSource.getFormula({ column: 'revenue', operation: 'sum', spatialFilter });
      if (!cancelled) setStats({ total });
    })();
    return () => { cancelled = true; };
  }, [dataSource, debouncedView]);

  return <KPICard label="Total revenue" value={stats?.total?.value} />;
}
```

If you already hold a `Deck` ref (e.g. via `<DeckGL ref={deckRef} ...>`), prefer `deckRef.current?.deck?.getViewports()[0]?.getBounds()` — it gives you the viewport deck.gl is actually rendering, including any non-WebMercator views. `WebMercatorViewport` is the simplest fallback when you only have view state.

For multiple widgets in a panel, run them in parallel with `Promise.all`.

## Per-method options

### `getFormula`
```ts
widgetSource.getFormula({
  column: 'revenue',
  operation: 'sum',          // sum | avg | min | max | count | count_distinct
  spatialFilter,
  filters,                   // optional column filters
});
```

### `getCategories`
```ts
widgetSource.getCategories({
  column: 'category',
  operation: 'count',        // or sum/avg of operationColumn
  operationColumn: 'revenue',
  spatialFilter,
});
```

### `getHistogram`
```ts
const hist = await widgetSource.getHistogram({
  column: 'revenue',
  ticks: [0, 10_000, 50_000, 100_000, 500_000],   // bin edges, ascending
  operation: 'count',
  spatialFilter,
});
// hist is number[] of length ticks.length + 1 — NOT an array of {tick, value}.
// hist[0]      = rows where revenue < ticks[0]                (underflow)
// hist[i]      = rows where ticks[i-1] <= revenue < ticks[i]  (1 ≤ i ≤ N-1)
// hist[N]      = rows where revenue >= ticks[N-1]             (overflow)
```

### `getRange`
```ts
const { min, max } = await widgetSource.getRange({
  column: 'revenue',
  spatialFilter,
});
```

Use this once at startup to seed slider bounds.

### `getTimeSeries`
```ts
widgetSource.getTimeSeries({
  column: 'event_ts',
  operation: 'count',
  stepSize: 'day',           // hour | day | week | month | quarter | year
  spatialFilter,
});
```

### `getScatter`
```ts
widgetSource.getScatter({
  xAxisColumn: 'population',
  yAxisColumn: 'income',
  xAxisJoinOperation: 'avg',
  yAxisJoinOperation: 'avg',
  spatialFilter,
});
```

### `getTable`
```ts
widgetSource.getTable({
  columns: ['id', 'name', 'revenue'],
  sortBy: 'revenue',
  sortDirection: 'desc',
  limit: 50,
  offset: 0,
  spatialFilter,
});
```

## Rendering with echarts

`hist` is `number[]` aligned to your `ticks` (length = `ticks.length + 1`). Build the category labels yourself:

```ts
import * as echarts from 'echarts';

const ticks = [0, 10_000, 50_000, 100_000, 500_000];
const labels = [
  `< ${ticks[0]}`,
  ...ticks.slice(0, -1).map((t, i) => `${t}–${ticks[i + 1]}`),
  `≥ ${ticks.at(-1)}`,
];

const chart = echarts.init(document.getElementById('hist'));
chart.setOption({
  xAxis: { type: 'category', data: labels },
  yAxis: { type: 'value' },
  series: [{ type: 'bar', data: hist }],   // hist[i] is already the count
});
```

In React, use `echarts-for-react` so option diffs trigger re-renders without manual `setOption` calls.

## Gotchas

- **`spatialFilter` from a stale viewport** is the most common widget bug. Always recompute from the *current* viewport at fire time, not from a closure-captured value.
- **Don't pass widget source's own filter as a column filter.** The `owner` field exists so a histogram can apply all *other* filters but not its own — the helpers in [`filters.md`](filters.md) thread this for you.
- **Tileset / raster widgets run client-side in a Worker.** First call is slow (worker boot + tile load); subsequent calls are fast. Don't show a spinner per call — show one once.
- **Cancel in-flight calls** — pass an `AbortSignal`:
  ```ts
  const controller = new AbortController();
  await widgetSource.getFormula({ /* ... */, signal: controller.signal });
  // cleanup: controller.abort();
  ```
- **`getTable` is paginated.** For large tables, pair `limit` + `offset` with a "load more" button or a virtualized list.
