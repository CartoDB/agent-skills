# Layers — per-layer-type authoring

Every `keplerMapConfig.visState.layers[]` entry has the same top-level shape. The difference between layer types is the `type` field and the defaults Kepler fills in. This file documents each layer type's authoring shape, decision criteria, and the gotchas that aren't visible from `carto maps schema layer.<type>`.

For cartographic decisions (which layer to pick by data character, which palette family, which scale), read `cartography.md` first — that's *what to pick*; this file is *how to encode it*.

### Z-order — stack smallest geometry first

Layer stack order matters as much as palette. `visState.layers[0]` renders **on top**; subsequent indices stack below (this is the opposite of standard deck.gl — see `references/cartography.md` §1.8). Author smallest / most-foreground geometry first — points and lines above polygons, polygons above rasters. Same rule for cell-fill renderers: `h3` / `quadbin` / `heatmapTile` / `clusterTile` cells stack at the polygon rank, so points above cells, cells above raster. **Anti-pattern: the borough-polygon-on-top-of-collision-points trap** — the background fill smothers the foreground feature and the map looks empty even though the data is there. When in doubt set `visState.layerOrder` explicitly so the configuration is self-documenting; the CLI also surfaces a *"⚠ Layer order will hide foreground features"* warning pre-flight when it detects wide-on-top-of-narrow stacking without an explicit `layerOrder`.

### Layer × dataset compatibility

Not every layer type pairs with every dataset shape. Mismatches either silently render blank or crash Builder with *"Failed to migrate document mode"*. The Tier-1 validator rejects layer types that aren't on the authorised list (see §Allowed layer types below); the matrix below shows which dataset shape each allowed type needs.

| Layer `type` | Dataset `type` | Dataset `format` | Dataset `geoColumn` | Notes |
|---|---|---|---|---|
| `tileset` | `table` / `query` / `tileset` | `tilejson` | `"geom"` (or column name) | Workhorse — points, polygons, lines. Any tilejson dataset. |
| `h3` | `table` / `query` / `tileset` | `tilejson` | `"h3:<col>"` | Pre-indexed H3 column OR dynamic binning from `"h3:geom"`. Requires `aggregationExp` + `aggregationResLevel` on the dataset. |
| `quadbin` | `table` / `query` / `tileset` | `tilejson` | `"quadbin:<col>"` | Same shape as h3; cells are squares instead of hexes. |
| `heatmapTile` | `table` / `query` / `tileset` | `tilejson` | `"quadbin:<col>"` | Density heatmap, quadbin-backed under the hood. |
| `clusterTile` | `table` / `query` / `tileset` | `tilejson` | `"quadbin:<col>"` | Adaptive point clustering, quadbin-backed. |
| `raster` | `raster` | `raster` | `"geom"` | Quadbin-addressed raster imagery. Dataset MUST be `type: "raster"`. |

**Layer types that would fail** (rejected by Tier-1): `point`, `geojson`, `line`, `s2`, `hexagonId`, `grid`, `hexagon`, `heatmap`, `cluster`, `trip`, `arc`. These are document-mode layer types that the modern Builder runtime no longer supports — opening a map that carries them throws *"Failed to migrate document mode"*. Legacy maps survive `maps get --json` (the values are migrated to `unknown` on read), but **do not emit them on new maps**.


**Canonical layer shell:**

```jsonc
{
  "id": "any-stable-string",             // not validated; used by visualChannels
  "type": "tileset",                     // see variants below
  "config": {
    "dataId": "$ref:<name>",             // or a real dataset UUID — see "Ref syntax" below
    "label": "Collisions",
    "color": [241, 92, 23],              // RGB triplet, used as legend color
    "isVisible": true,
    "hidden": false,
    "columns": {},
    "textLabel": [                       // required — but can be a single-item default
      { "size": 12, "color": [44,48,50], "field": null, "anchor": "start",
        "offset": [0,0], "alignment": "center", "outlineColor": [255,255,255] }
    ],
    "visConfig": { /* type-specific; defaults come from Kepler */ }
  },
  "visualChannels": {                    // maps dataset columns to visual aesthetics
    "colorField": null, "colorScale": "quantize",        // pick scale by data shape, not reflex — see cartography.md §3.2
    "sizeField":  null, "sizeScale":  "linear",
    "radiusField":null, "radiusScale":"linear",
    "heightField":null, "heightScale":"linear",
    "strokeColorField": null, "strokeColorScale": "quantize"
  }
}
```

> **Important:** Kepler's reducer runs `Object.keys()` on several nested sub-objects during init (textLabel, visualChannels, colorUI). If you omit them, the first open flashes a red *"Cannot convert undefined or null to object"* toast. The minimal shape above avoids this.

### `type: "tileset"` — the workhorse (points, polygons, pre-tiled layers)

Used for 90% of `tileset` / `table` / `query` datasets. Same `type: "tileset"` works for point, line, and polygon datasets — Kepler dispatches by the tileset's actual geometry type. For the full `visConfig` field surface, run `carto maps schema layer.tileset`.

> **Terminology — internal vs. user-facing.** In JSON, `layer.type: "tileset"` is the deck.gl TileLayer name and covers points / lines / polygons / pre-tiled datasets alike. **In user-facing language, say *"point layer"* / *"line layer"* / *"polygon layer"* matching the dataset's geometry** — that's what Builder's UI shows in the layer panel and what users will recognise. Reserve the word *"tileset"* in conversation for the **pre-generated-tileset** case (`dataset.type: "tileset"`) — that matches Builder's connection-picker vocabulary. Same JSON, plainer label.

#### Point tilesets — knobs worth knowing

- **`stroked` defaults to `false`** for Point / MultiPoint geometries. For *line* tilesets `stroked: true` is effectively required (no stroke → nothing renders — lines have no fill body). *Polygon* tilesets render fine with `filled: true` alone; stroke is optional and only needed when you want a visible outline.
- **`customMarkers: true`** swaps the circle for an SVG icon. Pair with `customMarkersUrl` (default icon) and optionally `customMarkersField` + `customMarkersRange.markerMap` (per-category icon mapping — see cookbook below). When on, `radius` range expands to `[0, 200]` and strokes are ignored.
- **`rotationField`** rotates each point/icon by the column's numeric value in degrees. No aggregation (identity scale only); useful for heading/bearing data or custom SVG markers that indicate direction.
- **`_carto_point_density`** is a synthetic column the Maps API injects into **point-tileset schemas only** (point / MultiPoint geometry + `layer.type: "tileset"`). Holds the point count per tile cell — handy as a `colorField` or `sizeField` for density-style rendering without aggregation-SQL gymnastics. **Does NOT exist on aggregated layers (h3 / quadbin / heatmapTile / clusterTile) or on line / polygon tilesets** — those layers use `aggregationExp` aliases (`count`, `casualties_sum`, etc.) for the same role. Not listed in `dataset.columns`; only appears after the first stats fetch.
- **3D extrusion is NOT supported on point tilesets.** `enable3d`, `heightField`, `heightRange`, `elevationScale`, `wireframe` are accepted by the schema but the renderer ignores them — points have no extrudable surface. 3D works only on **polygon tilesets, h3, and quadbin**. If the user wants 3D for point data, aggregate the points to h3 / quadbin first (see §1.0 in `references/cartography.md`) and extrude the cells instead.

#### Per-channel aggregations (tile layers)

Each aggregatable channel has its own `<channel>Aggregation` knob in `visConfig`: `colorAggregation`, `heightAggregation`, `strokeColorAggregation`, `radiusAggregation`, `sizeAggregation`. **Use the long-form aliases**: `count | sum | average | maximum | minimum | median | stdev | variance | mode | count unique | any_value`. Short forms (`avg` / `max` / `min`) cause silent runtime rejection on Builder surfaces — see the *"h3 / quadbin aggregation restrictions"* block below for the full rule. The CLI auto-normalises short→long on emit, but author long-form directly. Spatial-index layers (`h3`/`quadbin`/`heatmapTile`/`clusterTile`) additionally reject `median` and `count unique`.

#### Custom markers (point tilesets)

For icon-per-category rendering on point tilesets, you need **four things**, all required:

1. **`visConfig.customMarkers: true`** — toggle the channel on.
2. **`visConfig.customMarkersUrl`** — fallback icon URL for any feature whose value isn't in the markerMap. Without it, those features render iconless. Use an organization-served Maki URL (`<org>.app.carto.com/markers/maki/<icon>.svg`) or a URL from your own upload (see below).
3. **`visConfig.customMarkersRange.markerMap[]`** — array of `{ value, markerId | markerUrl }` per category. **Each entry sets EITHER `markerId` OR `markerUrl`, never both** — `markerId` references the Maki icon catalogue (`"restaurant"`, `"lodging"`, `"airport"`, etc.); `markerUrl` accepts any custom SVG / PNG URL. Tier-1 rejects entries that set both.
4. **`visualChannels.customMarkersField`** + **`customMarkersScale: "ordinal"`** — the binding that says "use this column to look up which icon goes on each feature". Without the field, the markerMap is dead config and every feature renders the fallback. Tier-1 rejects `customMarkers: true` + populated markerMap with no `customMarkersField`.

**Uploading a custom marker.** When a user wants a custom SVG / PNG that isn't in the Maki catalogue, upload it via the CLI and use the returned URL:

```sh
$ carto maps markers upload restaurant.svg --json | jq -r .url
https://example.carto.com/assets/<asset-id>
```

Constraints (mirrored from Builder): file size ≤ 200 KB, format `.svg` or `.png` only, PNG resolution ≤ 120 × 120 px (SVGs unconstrained). Pass `--public` for markers on `privacy: "public"` maps so viewers without an organization session can load the icon (uses the GCS signed-URL path).

Once uploaded, drop the URL into either `customMarkersUrl` (single-icon use) or `customMarkersRange.markerMap[].markerUrl` (per-category). Run `carto maps schema layer.tileset` for the full visConfig schema.

**Minimal point-tileset example** — colour by a numeric column, default radius:

```jsonc
{
  "type": "tileset",
  "config": {
    "dataId": "$ref:stores",
    "label": "Store revenue",
    "color": [120, 80, 200],
    "visConfig": {
      "filled": true, "stroked": false, "opacity": 0.85, "radius": 4,
      "colorRange": { "name": "Sunset", "type": "sequential", "category": "CARTO",
        "colors": ["#f3e79b","#fac484","#f8a07e","#eb7f86","#ce6693","#a059a0","#5c53a5"] }
    }
  },
  "visualChannels": {
    "colorField": { "name": "revenue", "type": "real" },
    "colorScale": "quantile"
  }
}
```

#### `visibilityByZoom` — limit when the layer renders

Set on `layer.config.visibilityByZoom: { min, max }` (NOT inside `visConfig`) to cap the zoom range. Range limits: `[0, 24]` on CARTO basemaps / `[0, 22]` on Google Maps. Useful for detail layers that only make sense at close zooms; omit the field for always-on.

#### Line tilesets — road networks, cycle routes, rivers

`type: "tileset"` over a dataset whose geometry is `LineString` / `MultiLineString`. Builder auto-detects and routes to a line renderer. Knobs that differ from points:

- **`filled` defaults to `false`.** Lines have no fill; setting `filled: true` is a no-op.
- **`stroked` is effectively required true** — the tile server renders nothing otherwise. Builder's side panel hides the stroke-disable toggle for line geometries.
- **`thickness`** is the fixed line width (px) when `sizeField` is null; defaults to 1.
- **`sizeField`** + **`sizeRange` [min, max]** + **`sizeAggregation`** drive width-by-value. Numeric fields only.
- **`strokeColorField`** + **`strokeColorRange`** + **`strokeColorAggregation`** drive the line colour.
- **`radius`, `radiusField`, `rotation`, `customMarkers` are ignored** for lines.
- **3D extrusion is NOT supported on line tilesets.** `enable3d`, `heightField`, `heightRange`, `elevationScale`, `wireframe` are ignored by the renderer — lines have no extrudable surface. 3D works only on polygon tilesets, h3, and quadbin.

```jsonc
{
  "type": "tileset",
  "config": {
    "dataId": "$ref:cycle_network",
    "label": "Cycle routes",
    "color": [46, 204, 113],
    "visConfig": {
      "filled": false, "stroked": true, "opacity": 0.9,
      "thickness": 3,                           // base width in px
      "sizeRange": [1, 8],                      // used only if sizeField set
      "strokeColor": [46, 204, 113],
      "strokeColorRange": { "name": "Bold", "type": "qualitative", "category": "CARTO",
        "colors": ["#11A579","#E73F74","#80BA5A"] },
      "strokeColorAggregation": "mode"
    }
  },
  "visualChannels": {
    "strokeColorField": { "name": "route_category", "type": "string" },
    "strokeColorScale": "ordinal",
    "sizeField": { "name": "avg_daily_cyclists", "type": "integer" },
    "sizeScale": "linear"
  }
}
```

#### Polygon tilesets — neighbourhoods, parcels, buildings (2D)

`type: "tileset"` over `Polygon` / `MultiPolygon`. Fill is the primary visual; stroke is optional:

- **`filled` defaults to `true`** and is enough on its own — polygons render cleanly without a stroke (different from lines, which need stroke to show at all). Add `stroked: true` only when you want a visible outline.
- **`colorField` / `colorRange` / `colorAggregation`** drive fill colour — the main visual.
- **`strokeColorField` / `strokeColorAggregation`** drive outline colour, *if* you opt into a stroke.
- **`thickness`** is outline width (px) — only relevant when `stroked: true`. Keep thin (0.5 – 2) to let the fill read.
- **No `radius`, `rotation`, `customMarkers`, `sizeField`** for polygons (size doesn't map to anything useful — use `thickness` for outline width when stroked).

```jsonc
{
  "type": "tileset",
  "config": {
    "dataId": "$ref:neighbourhoods",
    "label": "Median income",
    "color": [150, 150, 200],
    "visConfig": {
      "filled": true, "opacity": 0.6,
      // Optional outline — add only when you want polygon edges visible:
      //   "stroked": true, "thickness": 1, "strokeColor": [50, 50, 50], "strokeOpacity": 0.8
      "colorRange": { "name": "DarkMint", "type": "sequential", "category": "CARTO",
        "colors": ["#d2fbd4","#a5dbc2","#7bbcb0","#559c9e","#3a7c89","#235d72","#123f5a"] }
    }
  },
  "visualChannels": {
    "colorField": { "name": "median_income", "type": "integer" },
    "colorScale": "quantize"     // bounded, comparable across viewports — see cartography.md §3.2
  }
}
```

#### 3D-extruded polygon tilesets — buildings, population pyramids

To extrude polygons, add to the polygon shape above: `visConfig.enable3d: true`, `heightField` (numeric column) + `heightRange: [min_px, max_px]` mapping the column domain to pixel elevation, `elevationScale` as overall multiplier (default `500`; tune to units — metres ≈ 1–10, raw counts much higher), `worldUnitSize: 1` unless the tileset was authored in world units, optionally `wireframe: true` for edges-only. The tile server reads the pre-stored height directly — no `heightAggregation` for polygon tilesets. **Set `mapState.pitch > 0` (e.g. 45°)** to actually see the extrusion.

The CLI auto-fills `enable3d: true` whenever `visualChannels.heightField` is set on a 3D-capable layer. **3D-capable** = **polygon tilesets** (NOT point or line tilesets — point/line have no extrudable surface, and the renderer ignores `enable3d`/`heightField` on those), `h3`, and `quadbin`. `heatmapTile` and `clusterTile` inherit the schema field but the renderer ignores extrusion there too — auto-fill is also skipped. So on a polygon tileset / h3 / quadbin layer you can omit `enable3d` and the coercer will fill it; on point / line tilesets, omit both.

```jsonc
{
  "type": "tileset",
  "config": {
    "dataId": "$ref:buildings",
    "label": "Building heights",
    "visConfig": {
      "filled": true, "opacity": 0.9, "wireframe": false,
      "enable3d": true, "elevationScale": 5, "heightRange": [0, 500], "worldUnitSize": 1,
      "colorRange": { "name": "BluYl", "type": "sequential", "category": "CARTO",
        "colors": ["#f7feae","#b7e6a5","#7ccba2","#46aea0","#089099","#00718b","#045275"] }
    }
  },
  "visualChannels": {
    "colorField":  { "name": "height_m", "type": "real" },
    "colorScale":  "quantile",
    "heightField": { "name": "height_m", "type": "real" },
    "heightScale": "linear"
  }
}
```

#### Aggregate by geometry — when to bin a row-level source on the fly

Keep the dataset's `geoColumn` as a raw geometry (`"geom"`) but add `dataset.aggregationExp` to tell the tile server to bin rows into spatial cells on the fly. Useful when the source is point-shaped and dense and the narrative is pattern-level rather than feature-level.

**When to apply it.** Reach for aggregate-by-geometry on a `table` / `query` dataset when:

- The source is **point-shaped and dense** — typical threshold: a row count high enough that point-by-point rendering smears at common zoom levels (~50k+ rows in the viewport at city-level zoom is the rough trigger; lower for global views).
- The map's **narrative is pattern-level, not feature-level** — *"where do collisions cluster?"*, *"which neighbourhoods generate the most revenue?"*, *"density of trees across the city"* — questions about the aggregate, not the individual.
- The user says it explicitly — *"too dense, let's aggregate"* / *"show this as h3 cells"* / *"density heatmap"*.
- Performance — the source is large enough that a row-level tileset would blow past the warehouse's per-tile row budget.

**When NOT to apply it.** Skip aggregation and stay row-level when:

- The unit of insight IS the individual feature (find a store, click an incident, look up a parcel by address).
- The user wants per-feature popups / labels / icon-by-category.
- The dataset is already polygonal or linear — aggregation is for points-into-cells, not polygons-into-cells.

**Decision: which target layer type?** Once you've decided to aggregate, pick the layer type up front:

| Narrative | Layer type | When |
|---|---|---|
| Quantitative density per cell, hex aesthetic | `h3` | Default for *"density of X by area"*. |
| Quantitative density per cell, square aesthetic, zoom-adaptive cell size | `quadbin` | When cells should shrink as the user zooms in. |
| Smooth continuous density gradient | `heatmapTile` | When the read is *"hotspots"* not *"per-cell value"*. |
| Adaptive point clustering (numbered bubbles) | `clusterTile` | *"This many points clustered here"* — preserves point identity at high zoom. |

Author straight as `h3` / `quadbin` / `heatmapTile` / `clusterTile` with the right `geoColumn` prefix and `aggregationExp`. See `§ "type: h3"`, `§ "type: quadbin"`, `§ "type: heatmapTile"`, `§ "type: clusterTile"` below for the per-type recipes.

**Seeded `aggregationExp` — round-trip preservation.** You'll encounter this minimal shape on round-trips of existing bundles:

```jsonc
"datasets": [{
  "$ref": "events",
  "type": "table",
  "source": "carto-demo-data.demo_tables.events",
  "connectionId": "<conn-id>",
  "geoColumn": "geom",
  "aggregationExp": "1 AS __aggregationValue",
  "format": "tilejson"
}]
```

Preserve it as-is on read + update. Don't author it on new maps — go straight to `h3` / `quadbin` / `heatmapTile` / `clusterTile` and emit a complete `aggregationExp` (the CLI computes it for you when the layer's visualChannels reference aggregatable columns; see *"`aggregationExp` — let the CLI compose it"* below).

**Constraints — refuse to author this when:**

- The dataset's connection is **Oracle** — H3 / quadbin aggregation isn't supported on Oracle. Tier-1 rejects.
- The source is already a **pre-built tileset** (`dataset.type: "tileset"`) — binning is baked at upload time; can't be toggled at render. Inspect tilejson and use the post-aggregation aliases directly.
- Multiple layers need to share the dataset and render together — an aggregated dataset supports a single layer (mixed geometries don't aggregate together). If the user wants two layers, split the dataset into two sources or render row-level on one and aggregated on the other.

**Side effects when the CLI emits this configuration:**

- `visualChannels.<x>Field` references must point to columns that exist in the *post-aggregation* tile output, NOT the raw source — pair `colorField: { name: "revenue" }` with `colorAggregation: "sum"` and the CLI bridges the `<col>_<agg>` rename in `aggregationExp`.
- Popups (`popupSettings.layers[<id>]`) on the aggregated layer should use `spatialIndexAggregation` on each field — aggregated cells have no per-row identity. See [`popups.md`](popups.md).
- Timeseries widgets with `showControls: true` won't animate — per-row timestamps are gone once binned. The CLI strips animation on round-trips of aggregated datasets; see [`widgets.md`](widgets.md).

### `type: "h3"` — hex-cell aggregation for H3 datasets

> **Pre-built H3/quadbin tilesets — `colorField.name` is the upstream alias.** When the dataset is a **pre-built tileset** (`dataset.type: "tileset"`) rather than a dynamically-binned table, `visualChannels.colorField.name` must match the **post-aggregation column inside the tile** — typically `<col>_<agg>` (`population_sum`, `revenue_avg`, etc.) as named by the tileset author. Builder's bridging convention (where the CLI emits `aggregationExp` and Kepler bridges the rename internally — see *"`aggregationExp` — let the CLI compose it"* below) applies **only to dynamic binning**. With a pre-built tileset the rename has already happened upstream — you reference the post-aggregation alias directly. Always inspect the tilejson first (run `carto connections describe <conn> <table>`) to learn what columns exist.

Use with a dataset whose `geoColumn` is `h3:<colname>` and (for non-tileset sources) `aggregationExp` is set. Two shapes work:

- **Pre-indexed h3 table** — the dataset already has an h3 column. `geoColumn: "h3:h3_id"` (or whatever the column is called) + `aggregationExp` summarising non-h3 columns. See [`examples.md`](examples.md) *§B — H3 aggregation* for a working recipe.
- **Raw points, dynamically binned to h3** — the dataset has a raw geometry column and the tile server computes `H3_FROMGEOGPOINT(geom, aggLevel)` on the fly. `geoColumn: "h3:geom"` + `aggregationExp` aggregating row-level fields per cell. Builder's layer-type picker patches the dataset into this shape automatically when the user picks H3 from a point dataset. Tier-1 in the CLI enforces the same shape.

Caveat on dynamic h3 bins: for raw-point datasets, the tilejson reports `maxresolution: 0` — the tile server does **not** subdivide cells at deeper zoom levels; you see the same h3 resolution regardless of how far you zoom in. If you want cells that shrink with zoom, use `type: "quadbin"` (natively tile-z scaled).

#### h3 / quadbin aggregation restrictions

**Use the long-form aliases on every Builder surface** — `colorAggregation` / `strokeColorAggregation` / `sizeAggregation` / `heightAggregation` / `weightAggregation`, plus widget `operation` and `spatialIndexAggregation`, plus popup-field `spatialIndexAggregation`. Authoritative full enum: `count`, `sum`, `average`, `maximum`, `minimum`, `median`, `stdev`, `variance`, `mode`, `count unique`, `any_value`.

> **The short forms (`avg`, `max`, `min`) are NOT production-safe on Builder surfaces.** They cause silent rejection in popup sync and 500s on layer click. Short forms ARE valid only inside `aggregationExp` SQL function calls (e.g. `sum(revenue) as revenue_sum`, `max(severity) as severity_max`) — that's SQL, not the Builder enum. The CLI auto-normalises short→long on emit (`avg → average`, `min → minimum`, `max → maximum`) so a round-tripped legacy bundle still validates, but **author long-form directly** for every new map.

**The available aggregations on spatial-index cells (`h3` / `quadbin` / `heatmapTile` / `clusterTile`) are column-type-gated** — Builder's "Color by …" / "Size by …" picker shows ONLY the subset valid for the chosen column's type, mirroring kepler.gl's `linearFieldAggrScaleFunctions` / `ordinalFieldAggrScaleFunctions`:

| Column type | Valid on spatial-index | Excluded |
|---|---|---|
| Numeric (`integer`, `real`) | `count`, `sum`, `average`, `maximum`, `minimum`, `stdev`, `variance` | `median` (rejected at tile-build); `mode` / `any_value` / `count unique` (ordinal-only) |
| String / boolean / date | `mode`, `any_value` | `count unique` (rejected at tile-build); all numeric aggregations (numeric-only) |

If you author `colorField: { name: "category", type: "string" }` on an h3 layer, `colorAggregation: "average"` is invalid (numeric-only on a string column) — use `mode` or `any_value`. Conversely, `colorAggregation: "mode"` on a numeric column is invalid — use one of the seven numeric aggregations. Tier-1 permits the full enum because gating is column-type-dependent and the CLI doesn't always have the column type at validate time, but the runtime falls back silently if you mismatch them. **Match the aggregation to the column type.**

On non-spatial-index `tileset` polygon layers, `median` and `count unique` are also valid (the `UNSUPPORTED_AGGREGATIONS` list only excludes them on `SpatialIndexLayer`).

#### `aggregationExp` — let the CLI compose it

The tile server only produces columns named in `dataset.aggregationExp` — a mismatch with the layer's `visualChannels` renders blank tiles. **The CLI computes `aggregationExp` for you** on `maps create` / `maps update` when (a) the dataset has a spatial-index `geoColumn`, (b) `aggregationExp` is unset on the dataset, (c) at least one layer references it, and (d) the connection provider is BigQuery / Snowflake / Postgres / Redshift / Databricks SQL Warehouse. It walks the layer's 6 aggregatable visual channels, pairs each `<channel>Field` with its `<channel>Aggregation`, and emits `fn(column) as column_<agg>` per the provider's dialect. Provider quirks: Redshift skips `mode` (Builder hides it there too); Oracle is unsupported (Builder rejects H3/quadbin on Oracle outright). Write `aggregationExp` yourself when you need popup-field or secondary-colour aggregation.

#### h3 / quadbin inherit the full tileset visConfig

Both `type: "h3"` and `type: "quadbin"` extend `TileLayer`, so every field in `layer.tileset`'s visConfig also applies — `thickness`, `sizeRange`, `strokeColorRange`, `worldUnitSize`, etc. The point-only extras (`radius`, `radiusField`, `customMarkers`, `rotationField`) are ignored because cells aren't points. Run `carto maps schema layer.h3` or `layer.quadbin` for the full list.

```jsonc
{
  "type": "h3",
  "config": {
    "dataId": "$ref:infra",
    "label": "Power density (H3)",
    "visConfig": {
      "filled": true, "stroked": true, "opacity": 0.8,
      "colorRange": { "name": "Global Warming", "type": "sequential", "category": "Uber",
        "colors": ["#5A1846","#900C3F","#C70039","#E3611C","#F1920E","#FFC300"] },
      "strokeColor": [0, 0, 0], "strokeOpacity": 0.8,
      "colorAggregation": "average",
      "enable3d": false, "heightRange": [0, 500], "elevationScale": 5
    }
  },
  "visualChannels": {
    "colorField": null,
    "colorScale": "quantile"
  }
}
```

> **How to color a layer — three working shapes:**
>
> - **Uniform** — leave `visualChannels.colorField: null` and let `config.color` (RGB triplet) drive the layer. No /stats call. For a base layer where geometry is the message.
> - **Per-row column** (non-aggregated `tileset` layers) — set `visualChannels.colorField: { name, type }` + `colorScale`. /stats reads the raw source; no `colorAggregation` needed.
> - **Aggregated cell value** (`h3` / `quadbin` / `heatmapTile` / `clusterTile`) — `colorField.name` must point at a **column that exists in the raw source**, NOT the post-aggregation alias (`/stats` reads the raw source, not the tile). Builder's aliasing convention names the aggregated column `<column>_<aggregation>` (e.g. `aggregationExp: "sum(casualties) as casualties_sum"` + `visualChannels.colorField.name: "casualties"` + `visConfig.colorAggregation: "sum"`). Kepler bridges the rename internally. For "just count rows per cell" with no useful numeric column: add a constant column to the source SQL (`SELECT 1 AS incident, geom FROM …`) and use it as the aggregation target — `aggregationExp: "sum(incident) as incident_sum"` + `colorField.name: "incident"` + `colorAggregation: "sum"`.
>
> **Don't emit `1 AS __aggregationValue` in `aggregationExp` on new maps.** The literal is a round-trip shape some legacy bundles carry (see §"Seeded `aggregationExp`" above) — `maps create` accepts it, but the maps-api `/stats` SQL parser rejects the synthetic `__aggregationvalue` identifier with `{"error":"__aggregationvalue at [<col>]","status":400}` when Builder hydrates attribute stats on map open. Validation passes, viewer renders, **Builder 500s on load** with no obvious cause. Use only real raw columns plus their aggregation aliases — the `<column>_<aggregation>` pattern above.

> **Scales are channel-scoped — `linear` / `sqrt` / `log` are size/height/radius scales, NOT color scales.** Builder's picker is per-channel:
>
> | Channel | Picker offers | Notes |
> |---|---|---|
> | `colorScale` / `strokeColorScale` | `quantize` \| `quantile` \| `custom` (+ "Logarithmic" via `custom` + `uiCustomScaleType: "logarithmic"`) — categorical adds `ordinal` | Binned scales only. The runtime won't reject `colorScale: "log"` / `"linear"` / `"sqrt"` but Builder doesn't author those and they render unpredictably — **don't emit them on color**. For log-shaped colour on a skewed distribution, use the Logarithmic form (`colorScale: "custom"` + `uiCustomScaleType: "logarithmic"` + log10-spaced `colorMap`). |
> | `sizeScale` / `heightScale` / `radiusScale` | `linear` \| `sqrt` \| `log` \| `quantize` \| `custom` | Continuous scales — visual size reads better as a smooth function of the data than as bins. |
>
> For long-tail / skewed distributions on color, prefer the Logarithmic form over `quantile` — `quantile` splits the *raw* /stats distribution, which collapses to flat breaks when the aggregated per-cell distribution diverges from the raw one.

### `type: "quadbin"` — square-cell aggregation

Same two-mode setup as h3:

- **Pre-indexed quadbin table** — the dataset already has a quadbin id column. `geoColumn: "quadbin:quadbin"` (or whatever the column is called: `quadbin:cell_id`, `quadbin:q`, etc.) + `aggregationExp` summarising other columns per cell.
- **Raw points, dynamically binned to quadbin** — the dataset has a raw geometry column and the tile server computes the quadbin index from it. `geoColumn: "quadbin:geom"` + `aggregationExp` aggregating row-level fields.

Same `visConfig` shape as h3. Key difference from h3 worth calling out: **quadbin is tile-z native** — the tile server adds `aggregationResLevel` to the requesting tile's z, so cells shrink automatically as the user zooms in. Pick quadbin over h3 if you want zoom-dependent granularity without extra configuration.

> **Also affects `heatmapTile` and `clusterTile`:** both are quadbin-backed under the hood. Their datasets follow the same two-mode pattern — `quadbin:<quadbin_col>` for pre-indexed, `quadbin:<geom_col>` for dynamic.

```jsonc
{
  "type": "quadbin",
  "config": {
    "dataId": "$ref:trips",
    "label": "Trip density (quadbin)",
    "color": [240, 145, 0],
    "visConfig": {
      "filled": true, "stroked": false, "opacity": 0.8,
      "colorRange": { "name": "PinkYl", "type": "sequential", "category": "CARTO",
        "colors": ["#fef6b5","#ffdd9a","#ffc285","#ffa679","#fa8a76","#f16d7a","#e15383"] },
      "colorAggregation": "sum"
    }
  },
  "visualChannels": {
    "colorField": { "name": "trip_count", "type": "integer" },
    "colorScale": "quantize"      // h3/quadbin cell counts: quantize anchors bins; if heavy-tailed, prefer custom + log10 (cartography.md §3.2)
  }
}
```

### `type: "heatmapTile"` — continuous density from any point/quadbin source

Use when you want a smooth density heatmap without discrete cells. Dataset follows the same two-mode pattern as quadbin (pre-indexed `quadbin:<quadbin_col>` or dynamic `quadbin:<geom_col>`) + `aggregationExp`. HeatmapTile extends SpatialIndexLayer, so inherits every knob from `layer.quadbin` — the aggregation restriction (no `median`, no `count unique`) applies too.

```jsonc
{
  "type": "heatmapTile",
  "config": {
    "dataId": "$ref:poi",
    "label": "Luxury POI Density",
    "visConfig": {
      "filled": true,              // REQUIRED — server default is false, heatmap renders blank without it
      "radius": 2, "opacity": 0.8,
      "colorRange": { "name": "Global Warming", "type": "sequential", "category": "Uber",
        "colors": ["#5A1846","#900C3F","#C70039","#E3611C","#F1920E","#FFC300"] },
      "colorAggregation": "sum",
      "weightAggregation": "average"   // REQUIRED — heatmap's weight visual-channel needs an aggregation
    }
  },
  "visualChannels": {
    "weightField": { "name": "intensity", "type": "real" },   // optional — omit for pure density (each point counts as 1)
    "weightScale": "identity",
    "colorField": null
  }
}
```

> **Gotcha — tile-backed layers render blank without `visConfig.filled: true`.** Affects every TileLayer subclass: `tileset` (points / lines / polygons), `h3`, `quadbin`, `heatmapTile`, `clusterTile`. The tile server defaults `filled` to `false` when omitted, producing zero-pixel heatmaps and hollow-outline point layers; Builder writes `filled: true` for every tile layer it authors. `heatmapTile` additionally needs `visConfig.weightAggregation` (defaults to `"average"`) or the weight visual channel has nothing to aggregate. `raster` is exempt (the raster pipeline goes through `colorBands` / `rasterStyleType` and ignores the fill flag). **The CLI auto-fills both pre-validation** on `maps create` / `maps update` (log line: *"→ Filled tile-layer defaults…"*) — emit them explicitly only if you want the configuration to survive being passed through other tooling.

> **Geometry-aware defaults for `tileset` layers.** In addition to the blanket `filled: true`, the CLI picks **point / line / polygon-specific visConfig defaults** by probing the dataset's tilejson:
> - **point** → `filled: true, radius: 4`
> - **line** → `stroked: true, filled: false, thickness: 2`
> - **polygon** → `filled: true, opacity: 0.6`
>
> Pass `dataset.geomType: "point" | "line" | "polygon"` in the configuration to skip the tilejson probe (case-insensitive; accepts GeoJSON names like `MultiPolygon`). Any field you set explicitly overrides the default.

**Weight channel** is the heatmap-specific addition: `weightField` + `weightScale: "identity"` + `visConfig.weightAggregation`. If you leave `weightField` null the heatmap weighs every point as 1 (pure density). Setting it to a numeric column multiplies the contribution — good for "weighted hotspots" (e.g., accidents weighted by casualties).

### `type: "clusterTile"` — adaptive point clustering

Aggregates points into cluster markers whose radius scales with cluster size. Pairs with a **`tileset` dataset backed by a quadbin scheme** (`geoColumn: "quadbin"` on the dataset) — the backend groups points into quadbin cells and the client draws them as circular clusters. Useful for large point datasets (millions of rows) where per-point rendering would flood the viewport.

```jsonc
{
  "type": "clusterTile",
  "config": {
    "dataId": "$ref:events",
    "label": "Incidents (clustered)",
    "visConfig": {
      "filled": true, "stroked": false, "opacity": 1,
      "radiusRange": [12, 64],
      "thickness": 2,
      "isTextVisible": true,
      "colorRange": { "name": "Global Warming", "type": "sequential", "category": "Uber",
        "colors": ["#5A1846","#900C3F","#C70039","#E3611C","#F1920E","#FFC300"] },
      "colorAggregation": "sum"
    }
  },
  "visualChannels": {
    "colorField": null,
    "colorScale": "quantile"
  }
}
```

**Knobs:**
- `radiusRange: [min, max]` (px) — the two endpoints of the cluster-size → marker-radius mapping. `[8, 80]` is the allowed range.
- `thickness` — stroke width (px); only visible when `stroked: true`.
- `isTextVisible` — show the count label inside each marker.
- `clusterLevel` — advanced override for the quadbin aggregation level. Leave unset to let Builder auto-resolve from viewport zoom.
- **Inherited from SpatialIndexLayer**: `strokeColorRange` + `strokeColorAggregation` + `sizeAggregation` + `heightAggregation` + the rest of `layer.quadbin`'s knobs. Same aggregation restriction: no `median`, no `count unique`.

### `type: "raster"` — quadbin-backed raster imagery

Renders a raster dataset (satellite imagery, elevation, demographic grids) whose tilejson serves quadbin cells with per-band values. Requires `dataset.type: "raster"` (not `"tileset"`) — the server returns `raster_metadata` describing the available bands, which Builder uses to populate the field picker.

Three coloring modes, selected via `visConfig.rasterStyleType`:

```jsonc
// Mode 1: ColorRange — continuous palette on one band (the common case)
{
  "type": "raster",
  "config": {
    "dataId": "$ref:dem",
    "label": "Elevation",
    "visConfig": {
      "opacity": 0.9,
      "rasterStyleType": "ColorRange",
      "colorRange": { "name": "Earth", "type": "sequential", "category": "CARTO",
        "colors": ["#a16928","#bd925a","#d6bd8d","#edeac2","#b5c8b8","#79a7ac","#2887a1"] }
    }
  },
  "visualChannels": {
    "colorField": { "name": "elevation", "type": "real" },
    "colorScale": "quantize",                    // raster safe default — always available
    "colorDomain": [0, 8849]
  }
}
```

> **Gotcha — raster `colorScale` set is narrower than tileset/h3/quadbin.** Builder offers only `quantize | custom` + conditionally `quantile` for raster ColorRange mode. The `quantile` option is shown **only** when the raster band has precomputed `quantiles` in its stats — some older rasters don't, so Builder hides it. Other scale types (`linear`, `log`, `sqrt`, `identity`, `ordinal`) are NOT offered for raster ColorRange mode and will render unpredictably if you set them. Safe default: `quantize` for bounded numeric bands; use `custom` with `colorRange.colorMap` when you want explicit thresholds. `ordinal` belongs to the separate `UniqueValues` mode (uses `uniqueValuesColorScale`), not ColorRange.

```jsonc
// Mode 2: UniqueValues — categorical palette (e.g. land-use classes)
{
  "type": "raster",
  "config": {
    "dataId": "$ref:landcover",
    "label": "Land cover",
    "visConfig": {
      "opacity": 1,
      "rasterStyleType": "UniqueValues",
      "uniqueValuesColorRange": { "name": "Bold", "type": "qualitative", "category": "CARTO",
        "colors": ["#7F3C8D","#11A579","#3969AC","#F2B701","#E73F74","#80BA5A","#E68310"] }
    }
  },
  "visualChannels": {
    "colorField": { "name": "class", "type": "integer" },
    "uniqueValuesColorScale": "ordinal",
    "uniqueValuesColorDomain": [11, 21, 31, 41, 51, 71, 81]
  }
}
```

```jsonc
// Mode 3: Rgb — 3-band composite (aerial/satellite imagery)
// Each entry maps a display channel to either a raw band (type: "band") or a
// SQL expression over bands (type: "expression"). `type: "none"` leaves the
// channel unset. The array must contain one entry per channel (red/green/blue).
{
  "type": "raster",
  "config": {
    "dataId": "$ref:aerial",
    "label": "Aerial RGB",
    "visConfig": {
      "opacity": 1,
      "rasterStyleType": "Rgb",
      "colorBands": [
        { "band": "red",   "type": "band",       "value": "B04" },
        { "band": "green", "type": "band",       "value": "B03" },
        { "band": "blue",  "type": "expression", "value": "(B04-B03)/(B04+B03)" }  // NDVI on blue channel, purely illustrative
      ]
    }
  }
}
```

> **Gotcha — `colorField` / `colorScale` / `colorDomain` / `uniqueValuesColorScale` / `uniqueValuesColorDomain` live on `layer.visualChannels` (sibling of `layer.config`), NOT inside `visConfig`.** Only `colorRange`, `uniqueValuesColorRange`, `rasterStyleType`, and `colorBands` live in `visConfig`. Mis-placing them silently fails — the layer renders uniform. Builder rewrites to `visualChannels` on every save, so `get --json` always returns them there.
>
> **Parallel fields for mode switching:** `ColorRange` mode reads `visualChannels.colorField` + `visConfig.colorRange` + `visualChannels.colorScale` + `visualChannels.colorDomain`. `UniqueValues` mode reads `visualChannels.colorField` + `visConfig.uniqueValuesColorRange` + `visualChannels.uniqueValuesColorScale` (always `"ordinal"`) + `visualChannels.uniqueValuesColorDomain`. Both sets coexist on the same layer so switching modes in Builder doesn't clobber the other's palette — emit only the set for your chosen mode, leave the other undefined.

> **Dataset dependency:** `raster` layers can't render until the backend returns `raster_metadata.bands` for the dataset. If you don't know the band names yet, open the map in Builder once to let it populate the metadata; the band list then lives at `dataset.metadata.raster_metadata.bands[].name`.

> **Raster layers don't use `enable3d`, `heightField`, `stroked`, or `radius`.** The raster layer only honours `opacity`, `colorRange`, `rasterStyleType`, `colorBands`, and `uniqueValuesColorRange`. Everything else is ignored.

#### Band expressions — `colorBands[].type: "expression"`

When an entry uses `type: "expression"`, the `value` is a string evaluated **element-wise** per pixel — arithmetic / comparison / logical / bitwise / ternary / unary operators on band identifiers and numeric literals. No functions, no strings, no matrix ops. Common recipes: `"band_1 * 1.5"` (brightness boost), `"(B04 - B03) / (B04 + B03)"` (NDVI), `"(B08 - B11) / (B08 + B11)"` (NDBI), `"band_1 > 100 ? band_1 : 0"` (threshold cut). Per-channel `type: "none"` leaves a channel unset.

### `type: "unknown"` — legacy maps post-migration

Older maps may carry layers that migrated to `unknown` because their original layer type is no longer supported by the runtime. These still survive duplicate-and-tweak (`get | update`). **Do not emit `unknown` from scratch** — it's a fallback for legacy maps, not a target for new authoring.

### Allowed layer types

Authoritative list: `carto maps schema enums`. Current: `tileset`, `quadbin`, `h3`, `heatmapTile`, `clusterTile`, `raster`, plus `unknown` for legacy migrations. The Tier-1 validator rejects everything else.

---


## Color ranges — palettes, scales, /stats

Cartographic decisions (palette family by narrative, basemap pairing, contrast, anti-patterns) live in `references/cartography.md` §3-§7 — read that first when picking colours. This section covers the **CLI-specific** behaviour: how the configuration carries palettes, how the CLI hydrates categorical legends, and how `/stats` powers scale domains.

> **Before binding a `colorField` (or `sizeField` / `radiusField` / `heightField`), validate the data shape can carry the encoding.** Two shapes break the legend the same way (dominant grey "Others"), both fixed in the source SQL not the layer config: (a) numeric column with > 25% NULL rows — the populated rows get binned but most features render grey; (b) categorical column with more unique values than the palette has colours — overflow categories all collapse to grey. See `references/cartography.md` §4.5 (categorical) and §4.5a (numeric / NULL ratio) for the diagnostic SQL probes and the two fixes (filter / pick a different column / collapse to top-N + Other / hexColor mode).

**`colorRange` shape** — `name` + `type` + `category` + `colors[]`. The triple **must be consistent** for the Builder legend to render — don't rename fields or invent categories. Run `carto maps schema palettes` for the 32-entry CARTOColors catalogue (each entry is a ready-to-paste `colorRange` block). Just the names: `carto maps schema enums --json | jq .paletteNames`. Non-CARTO palettes (Uber `Global Warming`, `ColorBrewer Reds-6`, etc.) still work — copy from a real map's configuration if you need them.

### Categorical coloring (`colorScale: "ordinal"`) — CLI auto-hydrates

Author a categorical layer with just `colorField` + `colorScale: "ordinal"` + a palette:

```jsonc
"config": {
  "visConfig": {
    "colorRange": {
      "name": "Bold", "type": "qualitative", "category": "CARTOColors",
      "colors": ["#7F3C8D","#11A579","#3969AC","#F2B701","#E73F74","#80BA5A", /* … */]
    }
  },
  "visualChannels": {
    "colorField": { "name": "species", "type": "string" },
    "colorScale": "ordinal"
  }
}
```

On `maps create` / `maps update`, the CLI calls `/v3/stats/{connection}/{column}` (same endpoint Builder's UI hits) and injects `visualChannels.colorDomain` + `colorRange.colorMap` with the top-N categories ordered by frequency, paired with your palette colors. The map opens with a populated legend on first paint — no user interaction needed.

Rules:

- Only `type: "query"` and `type: "table"` datasets get hydrated. Tilesets have stats baked in.
- The number of categories fetched is **capped at the palette length** — a 6-colour palette gets 6 categories; the rest collapse into Builder's "Others" bucket which renders **grey**. See `references/cartography.md` §4.5 for the full constraint set (palette-length cap + 20-entry legend cap + escape hatches).
- If you pre-seed `colorDomain` or `colorMap` yourself, the CLI respects it and skips hydration for that layer.
- Hydration runs always on create/update; only `--dry-run` on update skips it (no writes happen).
- Stats-fetch failures (timeout, 500) are logged as actions but don't fail the write — the layer saves without the domain and you see a blank legend until Builder fetches stats on interaction.

### Scale types — channel binding

A visual channel binds three things: `<x>Field` (column, on `visualChannels`), `<x>Scale` (mapping shape, on `visualChannels`), `<x>Range` (palette / numeric range, on `config.visConfig`). For when to pick which scale, see `references/cartography.md` §3.1.

#### Authorable `*Scale` fields

Five `<channel>Scale` fields are exposed as user-editable controls in Builder — these are the ones to author on new maps. Anything else (`radiusScale`, `weightScale`, `customMarkersScale`, `rotationScale`) has no UI selector; the runtime default applies, so omit them on new maps and preserve whatever's there on round-trips of legacy bundles.

| `*Scale` field | Where in Builder | Author when |
|---|---|---|
| `colorScale` | "Color scale" in Fill group; also in Raster style group (sequential mode) | Primary cartographic dial — every data-driven colour layer. |
| `strokeColorScale` | "Color scale" inside Stroke group (UI label is just "Color scale" — the underlying field is `strokeColorScale`) | The layer binds `strokeColorField` for stroke colour by data. |
| `sizeScale` | "Weight scale" under Stroke → Weight (drives stroke-width scaling on tile layers) | The layer binds `sizeField` for stroke-width-by-data. |
| `heightScale` | "Height scale" in Height group (3D extrusion) | 3D extrusion layers (polygon tilesets / `h3` / `quadbin`). |
| `uniqueValuesColorScale` | Raster style group, categorical mode only | Raster layer with `rasterStyleType: "UniqueValues"`. |

### `/stats` — what the CLI fetches

For every active visual channel with `Field` + a non-identity `Scale`, the CLI hits `GET /v3/stats/{connection}/{column}` to produce the scale's domain. Numeric columns return `{ min, max, avg, sum, quantiles: { "5": [...], "10": [...] } }` keyed by palette size; string/boolean columns return `{ categories: [{ category, frequency }, ...] }`. `quantize` / `linear` read `min`/`max`; `quantile` reads `quantiles[N]` (palette size); `ordinal` reads `categories[].category` ordered by frequency. `custom` skips stats (breakpoints live on `colorRange.colorMap`). Spatial-index tilesets may nest quantiles under a `global` key. Raster bands get stats from tilejson metadata + `top_values` for `UniqueValues` mode.

---


## Contrast — basemap-aware colour picking

White-on-light or dark-on-dark renders invisible. The CLI does not auto-adjust for basemap tone — agents must pick right the first time. The full basemap × palette × narrative decision tree (light/dark fill picks, sequential ramp ends, qualitative palettes, diverging midpoints, opacity defaults) lives in [`references/cartography.md`](cartography.md) §4.4 (dark-basemap considerations) and §5 (basemap pairing). Default when basemap is ambiguous: `positron` + a light-basemap palette (CARTO default, no organization dependency). See [`references/basemap.md`](basemap.md) for the basemap catalogue (CARTO basemaps, Google Maps, custom).

---

