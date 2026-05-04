# Filters

Two kinds of filters, one shared object:

1. **Column filters** — predicates on attributes (`category IN ('retail')`, `revenue BETWEEN 1000 AND 50000`).
2. **Spatial filter** — viewport-bound or polygon-bound geometry filter, recomputed as the user pans/zooms.

Both flow into source helpers (so the map respects them) and widget calls (so charts respect them) through the same `filters` object + `spatialFilter` argument.

## The `filters` object

```ts
import { addFilter, removeFilter, clearFilters, FilterType } from '@carto/api-client';

let filters = {};

// IN — categorical
addFilter(filters, {
  column: 'category',
  type: FilterType.IN,
  values: ['retail', 'wholesale'],
  owner: 'category-widget',     // identifies the source of this filter
});

// BETWEEN — numeric range
addFilter(filters, {
  column: 'revenue',
  type: FilterType.BETWEEN,
  values: [[10_000, 100_000]],   // array of [min, max] pairs
  owner: 'revenue-histogram',
});

// CLOSED_OPEN — half-open range (good for bins)
addFilter(filters, {
  column: 'revenue',
  type: FilterType.CLOSED_OPEN,
  values: [[10_000, 50_000]],
  owner: 'histogram',
});

// TIME — date / timestamp range
addFilter(filters, {
  column: 'created_at',
  type: FilterType.TIME,
  values: [['2025-01-01', '2025-12-31']],
  owner: 'time-series',
});

// STRING_SEARCH — substring match
addFilter(filters, {
  column: 'name',
  type: FilterType.STRING_SEARCH,
  values: ['acme'],
  owner: 'search-input',
});

removeFilter(filters, { column: 'category', owner: 'category-widget' });
clearFilters(filters);
```

Pass the same `filters` object to:

- The source helper: `vectorTableSource({ ..., filters })` — so the map respects the predicate.
- Each widget call: `widgetSource.getFormula({ ..., filters })` — so the chart respects them.

Mutating `filters` triggers a re-fetch on next pass.

## Why `owner` matters

When a widget reads its *own* filter back, the chart would self-filter — a histogram showing only the bar the user clicked. That's wrong. The widget passes its own `owner` and `getApplicableFilters` excludes it:

```ts
import { getApplicableFilters } from '@carto/api-client';

const histFilters = getApplicableFilters(filters, 'revenue-histogram');
const hist = await widgetSource.getHistogram({
  column: 'revenue',
  ticks: [/* ... */],
  filters: histFilters,
  spatialFilter,
});
```

The map and other widgets get the full `filters` object; only the histogram gets the filtered-out version.

## Spatial filter

```ts
import { createViewportSpatialFilter, createPolygonSpatialFilter } from '@carto/api-client';

const spatialFilter = createViewportSpatialFilter(viewport.getBounds());
// or for a drawn polygon:
const spatialFilter = createPolygonSpatialFilter(polygonGeoJSON);
```

`createViewportSpatialFilter` takes `[west, south, east, north]` (deck.gl `viewport.getBounds()` returns this directly).

Pass `spatialFilter` to widget calls. **It's not part of `filters`** — separate argument.

For the source: vector/H3/quadbin tile layers fetch only intersecting tiles automatically, so most apps don't pass `spatialFilter` to the source itself, only to widgets.

## Debouncing

```ts
import { debounce } from 'lodash-es';   // or write a 5-line debounce

const onMove = debounce((viewport) => {
  const spatialFilter = createViewportSpatialFilter(viewport.getBounds());
  refreshWidgets(spatialFilter);
}, 300);

deck.setProps({ onViewStateChange: ({ viewState }) => onMove(deck.getViewports()[0]) });
```

300 ms is the upstream-examples default. Lower feels janky; higher feels laggy.

## Wiring widget interactions back into filters

A histogram bar click → add a `BETWEEN` filter for that bin:

```ts
chart.on('click', (params) => {
  const [min, max] = bins[params.dataIndex].range;
  addFilter(filters, {
    column: 'revenue',
    type: FilterType.BETWEEN,
    values: [[min, max]],
    owner: 'revenue-histogram',
  });
  rebuildLayers();
  refreshAllWidgets();
});
```

A category bar click → toggle an `IN` filter. A slider drag → update a `BETWEEN` filter (debounce the drag).

## React state

Keep `filters` in `useState` *as a fresh object on each change* (not mutated in place) so React notices:

```tsx
const [filters, setFilters] = useState({});

const onPickCategory = (cat: string) => {
  const next = { ...filters };
  addFilter(next, { column: 'category', type: FilterType.IN, values: [cat], owner: 'cat-bar' });
  setFilters(next);
};
```

## Gotchas

- **Tileset / raster sources apply filters client-side** — there's no SQL `WHERE` push-down. For huge tilesets, this can be slow; consider `vectorQuerySource` with the filter inlined into SQL when latency matters more than tile reuse.
- **Spatial filter ≠ `filters`.** Two separate arguments; don't put `spatialFilter` inside `filters`.
- **Filters mutate by default** — `addFilter`/`removeFilter` return the same object. For React, copy first (`{ ...filters }`) to break referential equality.
- **Time filters need ISO 8601 strings**, not `Date` objects. `'2025-01-01'` or `'2025-01-01T00:00:00Z'`.
