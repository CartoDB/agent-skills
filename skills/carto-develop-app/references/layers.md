# Layers

CARTO-specific deck.gl layers from `@deck.gl/carto`. Each pairs with a source family from [`data-sources.md`](data-sources.md).

| Layer | Source pair | Geometry |
|---|---|---|
| `VectorTileLayer` | `vector*Source` | Points, lines, polygons, MultiPolygon |
| `H3TileLayer` | `h3*Source` | H3 cells |
| `QuadbinTileLayer` | `quadbin*Source` | Quadbin cells |
| `RasterTileLayer` | `rasterSource` | Raster pixels |

## VectorTileLayer

```ts
import { VectorTileLayer } from '@deck.gl/carto';

new VectorTileLayer({
  id: 'stores',
  data: dataSource,                          // promise from vectorTableSource(...)
  pickable: true,
  pointRadiusMinPixels: 3,
  getFillColor: [200, 0, 80],
  getLineColor: [255, 255, 255],
  lineWidthMinPixels: 1,
});
```

Polygons:

```ts
new VectorTileLayer({
  id: 'parcels',
  data: dataSource,
  pickable: true,
  filled: true,
  getFillColor: [80, 120, 200, 180],
  getLineColor: [40, 60, 100],
  getLineWidth: 1,
  lineWidthUnits: 'pixels',
});
```

3D extrusions:

```ts
new VectorTileLayer({
  id: 'buildings',
  data: dataSource,
  extruded: true,
  getElevation: (f) => f.properties.height,
  getFillColor: [200, 200, 200],
});
```

## H3TileLayer

```ts
import { H3TileLayer } from '@deck.gl/carto';

new H3TileLayer({
  id: 'h3-pop',
  data: dataSource,                          // h3TableSource(...) with aggregationExp
  pickable: true,
  filled: true,
  extruded: true,
  getFillColor: (d) => colorBins({
    attr: 'population',
    domain: [0, 100, 1000, 10000],
    colors: 'Sunset',
  })(d),
  getElevation: (d) => d.properties.population / 10,
  elevationScale: 1,
});
```

The feature object has `.properties.<aliased aggregation column>` — match the alias used in `aggregationExp`.

## QuadbinTileLayer

```ts
import { QuadbinTileLayer } from '@deck.gl/carto';

new QuadbinTileLayer({
  id: 'qb-density',
  data: dataSource,                          // quadbinTableSource(...)
  pickable: true,
  filled: true,
  getFillColor: colorBins({
    attr: 'count',
    domain: [10, 100, 1000, 10000],
    colors: 'Magenta',
  }),
});
```

## RasterTileLayer

```ts
import { RasterTileLayer } from '@deck.gl/carto';

new RasterTileLayer({
  id: 'temperature',
  data: dataSource,                          // rasterSource(...)
  opacity: 0.7,
  // For continuous data, supply a custom colormap via getFillColor or built-ins
});
```

Raster styling has its own dance — see the `raster-temperature` example in [deck.gl-examples](https://github.com/CartoDB/deck.gl-examples) for a working colormap pipeline.

## Color helpers

Both `colorBins` (continuous → categorical) and `colorCategories` (discrete) come from `@deck.gl/carto`:

```ts
import { colorBins, colorCategories } from '@deck.gl/carto';

const fill = colorBins({
  attr: 'revenue',
  domain: [10_000, 50_000, 100_000, 500_000],
  colors: 'Sunset',                          // or 'Mint', 'Magenta', any CartoColors palette name
});

const fillByCategory = colorCategories({
  attr: 'category',
  domain: ['retail', 'wholesale', 'online'],
  colors: 'Bold',
});

new VectorTileLayer({ /* ... */ getFillColor: fill });
```

Domain is **bin edges** for `colorBins` and **discrete values** for `colorCategories`. Pair the same domain + palette with the legend in [`legend.md`](legend.md).

## Common props worth knowing

- `pickable: true` — required for tooltips, hover, and clicks.
- `pointRadiusMinPixels` / `lineWidthMinPixels` / `radiusMinPixels` — guarantee visibility at low zoom.
- `updateTriggers` — when a `getX` accessor depends on app state, list the state in `updateTriggers` so deck.gl re-evaluates:
  ```ts
  new VectorTileLayer({
    /* ... */
    getFillColor: (f) => f.properties.id === selectedId ? [255, 0, 0] : [80, 80, 80],
    updateTriggers: { getFillColor: [selectedId] },
  });
  ```
- `onClick` / `onHover` — feature picking. The handler receives `{ object, x, y }`.
- `visible: boolean` — toggle from a control without recreating the layer.

## Layer order

Layers in the `layers` array render bottom-to-top — last in the array is on top. Put boundaries below points, points above heatmaps.

## Gotchas

- **Don't recreate the source on every render.** In React, wrap the source call in `useMemo`. Without it, you trigger a full re-fetch on every state change.
- **`data: source` not `data: await source`** — the layer awaits the promise itself.
- **Aliased columns in `aggregationExp` are the only properties** that exist on H3/quadbin features. There is no row-level data — you sum it up before rendering.
- **`updateTriggers` is the most-forgotten thing in deck.gl.** If a layer "doesn't update when I change state", check this first.
