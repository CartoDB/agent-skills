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

**Z-order is the `layers` array, nothing else.** Layers render bottom-to-top: index 0 is on the bottom, the *last* element is on top. To restack, change array position. Put fills below outlines, outlines below points, points below markers/labels.

```ts
layers: [
  choroplethLayer,   // bottom
  boundaryLayer,
  storesLayer,       // top — drawn last, never occluded
]
```

This is the thing agents get wrong most. Three rules:

- **`z-index` (CSS) does nothing to layer stacking.** All deck.gl layers live on one canvas; CSS `z-index` only orders DOM siblings (HTML panels, the canvas vs. the basemap div). A layer hidden behind another is an *array-order* problem — reorder the array, don't touch CSS.
- **Rebuild the array; don't mutate it.** `layers.push(...)` / reassigning `layers[i]` in place won't re-render reliably. Build a fresh array (`setProps({ layers: [...] })` in vanilla, a new array each render in React) so deck.gl diffs it.
- **A layer that "won't restack" is usually a stale closure, not a z-order bug.** If reordering the array has no visible effect, confirm you're passing the *new* array to `setProps` / the `<DeckGL layers>` prop, and that nothing downstream re-sorts it. (Distinct from "a layer won't *update* when state changes" → that's `updateTriggers`, see above.)

Two refinements for the rare cases array order can't express:

- **Z-fighting between two flat layers at the same elevation** (a fill and a coincident outline flicker): disable depth testing on the one that should win — deck.gl v9 spelling is `parameters: { depthCompare: 'always' }` (the old `depthTest: false` is gone). For fighting *between* layers, `polygonOffset: [factor, units]` (negative pulls toward the camera) is the finer tool.
- **3D / extruded layers depth-test against each other**, so nearer geometry occludes farther regardless of array index. That's correct 3D behavior, not a stacking bug — array order only fully governs flat 2D layers.

> Separate axis: whether deck.gl as a whole sits *above* the basemap (the default — opaque fills then hide basemap labels) or is *interleaved* so labels read over your data. That's a basemap concern, covered in [`basemap-and-view.md`](basemap-and-view.md), not array order.

## Gotchas

- **Don't recreate the source on every render.** In React, wrap the source call in `useMemo`. Without it, you trigger a full re-fetch on every state change.
- **`data: source` not `data: await source`** — the layer awaits the promise itself.
- **Aliased columns in `aggregationExp` are the only properties** that exist on H3/quadbin features. There is no row-level data — you sum it up before rendering.
- **`updateTriggers` is the most-forgotten thing in deck.gl.** If a layer "doesn't update when I change state", check this first.
