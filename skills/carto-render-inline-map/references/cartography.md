# Cartography reference — for `view_map` deck.gl declarative specs

> **This is a reference, not a standalone skill.** Read alongside the `carto-render-inline-map` `SKILL.md` when composing a `view_map` spec that needs cartographic decisions. The `view_map` tool description carries the *syntax* (layer-source compatibility, `aggregationExp`, `@@function` shapes, expression-eval restrictions). This file layers *what to pick* on top — palette, scale, basemap, stroke, drawing order, hierarchy, picking, anti-patterns — once the agent knows *how to encode*.

> **Different from `carto-create-builder-maps/references/cartography.md`.** That reference is for Builder/kepler-config maps authored via the CLI. The shapes don't transfer to deck.gl declarative — they target a different runtime.

> **Different from `carto-build-app/references/layers.md`.** That skill targets developers writing TypeScript/JavaScript app code with full `@deck.gl/carto` access (auth, scaffolds, React/Vue, full deck.gl surface including `Math.*` and arbitrary layers). This file targets agents emitting the `@deck.gl/json` declarative spec consumed by the `view_map` MCP tool — restricted to CARTO classes registered in the JSONConverter and the `@@=` expression-eval engine.

> The cartographic *principles* are the same across all three contexts; the *encodings* are not.

> **Only CARTO layers and primitives.** `view_map` accepts only the layers/sources/helpers from `@deck.gl/carto`: `VectorTileLayer`, `H3TileLayer`, `QuadbinTileLayer`, `ClusterTileLayer`, `HeatmapTileLayer`, `RasterTileLayer`, `PointLabelLayer`, paired with the matching CARTO sources. Generic deck.gl layers (`ScatterplotLayer`, `HexagonLayer`, `GeoJsonLayer`, etc.) are **not accepted** — see the `view_map` tool description's NOT ACCEPTED list.

**Audience:** an LLM agent composing a `view_map` deck.gl declarative spec.

---

## 0. Before you pick anything

**Know the data.** Use the discovery tools rather than guessing:

| Question | How |
|---|---|
| What columns and types? | `list_resources({ fqn })` — response includes `schema: [{name, type}, …]` and `geomField`. |
| What's the column distribution? | `get_column_stats({ table_fqn / query, column })` — numeric returns `min`, `max`, `quantiles[N]`; string returns categories with frequencies. |
| Is it skewed? | Inspect `quantiles[10]`. If `q[5] - q[0] << q[9] - q[5]`, it's right-skewed (typical for counts, revenue, population, incidents). |

**Name the hook.** One sentence: *"Population is concentrated in the southeast."* *"Most regions improved, three got worse."* The hook governs four downstream decisions: layer (§1), classification (§4), palette (§5), anti-patterns to avoid (§9).

---

## 1. Pick the layer

Each CARTO layer is hardcoded to a tiling scheme — see the `view_map` tool description's compatibility matrix. The cartographic question here is *which one tells the story*:

| Story | Layer | Source |
|---|---|---|
| "Where are these things?" — show individual features | `VectorTileLayer` (point/line/polygon) | `vector*Source` or `boundary*Source` (boundaries serve admin geographies as MVT) |
| "Where is the spatial pattern of magnitude?" — bin counts/sums/averages by area | `H3TileLayer` (hexagons, isotropic) **or** `QuadbinTileLayer` (squares, faster joins) | `h3*Source` / `quadbin*Source` with `aggregationExp` |
| "Where is the density?" — soft, continuous gradient of point density | `HeatmapTileLayer` | `h3*Source` or `quadbin*Source` (raw points wrapped via `h3QuerySource` + `H3_FROMGEOGPOINT(geom, <res>)`) |
| "Where do points cluster, and how many in each cluster?" — discrete clusters | `ClusterTileLayer` | `h3*Source` or `quadbin*Source` (same wrap pattern) |
| "What's the value of this continuous surface?" — elevation, NDVI, land class | `RasterTileLayer` | `rasterSource` |
| Place name labels on top of another layer | `PointLabelLayer` (text-only, no markers — pair with `VectorTileLayer`) | Same `vector*Source` (often a filtered query) |

**H3 vs Quadbin:** prefer **H3** when the takeaway is shape/extent (organic, equal-area, no axis bias) — typical for "where are accidents", "where's the density of stores". Prefer **Quadbin** for joins to other quadbin tilesets, or grid ergonomics matching national tile schemes.

**Heatmap vs Cluster vs H3:**
- `HeatmapTileLayer` — smooth, soft. Good for "the broad pattern". No discrete cell value to hover.
- `ClusterTileLayer` — discrete clusters; hover shows the cluster's aggregated `properties` and a `stats` object with cluster-wide aggregations (useful for normalising marker size to "biggest cluster on screen").
- `H3TileLayer` — discrete cells at a fixed resolution; hover shows cell values from `aggregationExp` outputs. Good for "I want a uniform grid".

**Point overplotting at low zoom on `VectorTileLayer`** (raw points become a black blob below ~zoom 8 in dense areas):
- Add `pointRadiusUnits: "pixels"` + `pointRadiusMinPixels: 2` + `pointRadiusMaxPixels: 8`.
- Or switch to `H3TileLayer` with `aggregationExp: "COUNT(*) AS n"` and color by `n`.
- Or pair with `HeatmapTileLayer` underneath for density context.

---

## 2. Drawing order — bottom to top

deck.gl renders layers in **array order**: index 0 paints first (deepest), the highest index paints last (on top). There is **no `zIndex` / `renderOrder` prop** — reorder the `layers` array to change stacking.

Conventional order, bottom → top:

1. **Continuous surfaces** — `RasterTileLayer`, `HeatmapTileLayer`. They cover area; everything else sits on them.
2. **Polygons / cells** — `H3TileLayer`, `QuadbinTileLayer`, polygon-geometry `VectorTileLayer` (e.g., `boundaryTableSource`). Area-based marks; bound to be partly obscured by points/lines on top.
3. **Lines** — line-geometry `VectorTileLayer`. Roads, routes, networks.
4. **Points** — point-geometry `VectorTileLayer`, `ClusterTileLayer`. Eye anchors here; the headline marker.
5. **Labels** — `PointLabelLayer`. Always last, so collision detection runs against the final visible scene.

**Violations to avoid:**
- Putting points beneath a polygon fill (eye reads the polygon as the headline; points are missed).
- Putting labels mid-stack (subsequent layers paint over them).
- Stacking two `H3TileLayer`s of the same data at different resolutions (the higher one obscures the lower; use opacity or pick one).

---

## 3. Pick the visual channel

CARTO accessors that drive visual channels:

| Channel | Accessor / prop | Helper or expression |
|---|---|---|
| Color (fill) | `getFillColor` | `colorBins` / `colorContinuous` / `colorCategories` (helpers), constant `[r,g,b,a]`, or `@@=` ternary |
| Color (stroke) | `getLineColor` | Same as fill |
| Size (point radius) | `getPointRadius` + `pointRadiusUnits` (`'pixels' | 'meters'`) + `pointRadiusMinPixels` / `pointRadiusMaxPixels` | `@@=` expression (no `colorBins`-style helpers exist for size) |
| Size (line width) | `getLineWidth` + `lineWidthUnits` + `lineWidthMinPixels` / `lineWidthMaxPixels` | `@@=` expression |
| 3D extrusion | `getElevation` + `elevationScale` (H3 / Quadbin only, when `extruded: true`) | `@@=` expression |
| Layer opacity | `opacity` (0–1, layer-level) | constant; **don't use opacity to encode values** — reserve for hierarchy/stacking |

**Primary-channel rule:** color carries the headline. Size carries a secondary supporting measure. Don't double-encode the same column on both — it wastes a channel.

**Pixel-units idiom (universal across layers):** for any size accessor that should remain visually consistent at every zoom, set the units to `"pixels"` and clamp with min/max:

```jsonc
"pointRadiusUnits": "pixels",
"getPointRadius": "@@=properties.weight / 100",
"pointRadiusMinPixels": 2,
"pointRadiusMaxPixels": 12
```

Without min/max clamps, points balloon at high zoom (and disappear at low zoom). The default unit is `"meters"`, which scales with zoom and is rarely what you want for symbology.

---

## 4. Stroke conventions

The default for most CARTO layers is **`stroked: false`, `filled: true`** for polygons/cells. Adding stroke is a deliberate choice; here's when:

| Situation | Stroke |
|---|---|
| Light fills on light basemap (low-saturation choropleths on positron) | **Add stroke** in a darker shade than the fill (or constant `[60,60,60,180]`) so cells separate. |
| Dark/saturated fills on dark basemap | **Add white-ish stroke** `[255,255,255,160]` to separate adjacent cells. |
| Tiny polygons at low zoom (<10 pixels each) | **Skip stroke** — outlines collapse into noise. |
| `H3TileLayer` / `QuadbinTileLayer` covering most of the viewport | **Skip stroke** by default — adjacent cells share boundaries; outlines double-paint. |
| Single-feature highlight (e.g., a focus polygon) | **Add a thicker stroke** in a contrasting hue. |
| Points that should pop against a busy basemap | **Add a halo stroke** (white, `getLineColor: [255,255,255,230]`, `lineWidthMinPixels: 1`). |

**Line widths:** scale with `lineWidthUnits: "pixels"` + `lineWidthMinPixels: 1` (minimum visible) + `lineWidthMaxPixels: 4` (typical max for context lines, more for headline lines).

**Stroke as encoding** (rare): you can drive `getLineColor` from a different column than `getFillColor` — useful for two-axis stories ("color = magnitude, stroke = significance"). Use sparingly; second visual channel competes for attention.

---

## 5. Classify the data

Three color helpers map to three scale types:

| Helper | Scale | When |
|---|---|---|
| `colorBins` | Threshold (`d3.scaleThreshold`) — discrete buckets | Most numeric data. Legible buckets, clean grouping. Pair with quantile breakpoints from `get_column_stats`. |
| `colorContinuous` | Linear (`d3.scaleLinear`) — smooth gradient | Fine variation where every value should map to a unique color. Multi-stop arrays for diverging palettes around a midpoint. |
| `colorCategories` | Nominal — one color per category | Strings / booleans / ordinal. Cap at 12 distinct values; aggregate the rest into "other". |

**`colorBins` workflow:**
1. `get_column_stats({ table_fqn, column })`.
2. Take `quantiles[N]` for your bucket count (4-5 is the sweet spot).
3. Drop the first and last entries (natural extremes); inner N-1 numbers are the `domain`.
4. Pick a CARTOcolor palette name (`"Sunset"`, `"Teal"`, etc.) — auto-resolves to N colors.

```jsonc
"getFillColor": {
  "@@function": "colorBins",
  "attr": "population",
  "domain": [1200, 5500, 18000],
  "colors": "Sunset"
}
```

**Class count:** 4-5 buckets is the legibility sweet spot. 7+ pushes the eye past distinguishability. Fewer than 3 is rarely informative.

**Quantile vs custom thresholds:** default to quantile breakpoints. Override with custom thresholds when there's a meaningful policy break (e.g., `[0, 0.5, 1.0]` for shares).

**Heavy-tailed data:** if `q[9] / q[5] > 5`, quantiles compress the tail too aggressively. Either: (a) precompute `LOG10(col + 1)` in `vectorQuerySource` and bin on that, or (b) switch to `colorContinuous` with a multi-stop domain anchored on the median.

**Boolean columns:** `colorCategories` doesn't match raw booleans (it expects numeric or string). Cast in SQL: `SELECT *, CAST(<bool> AS STRING) AS <bool>_s FROM …` and use `domain: ["true", "false"]`.

---

## 6. Pick the palette

CARTO palettes (resolved by name in `colors`):

| Family | Use for | Examples |
|---|---|---|
| **Sequential single-hue** | Magnitude in one direction (counts, sums, populations) | `"Burg"`, `"BluYl"`, `"Teal"`, `"Sunset"`, `"OrYel"`, `"DarkMint"` |
| **Sequential multi-hue** | Same, more contrast across the range | `"PurpOr"`, `"BluGrn"`, `"Magenta"`, `"PinkYl"` |
| **Diverging** | Signed values around a meaningful midpoint (deltas, residuals, z-scores) | `"Geyser"`, `"Tropic"`, `"Earth"`, `"Fall"`, `"TealRose"`, `"Temps"` |
| **Qualitative** | Discrete unordered categories | `"Bold"`, `"Pastel"`, `"Prism"`, `"Vivid"`, `"Antique"`, `"Safe"` |

**Match family to data character.** Sequential for ordered. Diverging for signed (use `colorContinuous` with multi-stop `[min, mid, max]` domain, or `colorBins` with thresholds straddling the midpoint). Categorical for unordered.

**Multi-layer hue separation:**
- One sequential + one categorical → fine.
- Two sequentials → make them different families (`"Teal"` + `"Sunset"`, not two blues).
- Three+ data-driven layers → cap at two; the rest constants or muted boundary context.

---

## 7. Basemap pairing

Set top-level `mapStyle` to a CARTO basemap URL: `https://basemaps.cartocdn.com/gl/{name}-gl-style/style.json`.

| Basemap | Strengths | Default for |
|---|---|---|
| `positron` | Light, low-saturation, neutral. Lets data colors pop. | Most maps. The right default if the user doesn't specify. |
| `voyager` | Light but more colorful — useful labels, OSM-styled context. | When geographic context (roads, names, POIs) carries meaning. |
| `dark-matter` | Dark, high-contrast for bright/saturated data. | Heatmaps, density of bright signals (lights, fires, night population). |
| `*-nolabels` variants | Same color scheme, no place labels. | Dense data layers where labels would clutter, or when adding `PointLabelLayer` with its own labels. |

**Always emit `mapStyle`.** Without it, the renderer falls back to positron, but the spec stops being self-describing/portable.

**Palette × basemap:**
- **Light basemap** — most palettes work. Avoid very pale lower-bound colors (the bottom bucket disappears into the basemap); bump alpha or pick palettes that start mid-saturation.
- **Dark basemap** — light-on-dark reads well; dark colors near `[0,0,0]` disappear. Prefer palettes that span mid-to-light. Diverging palettes need their dark end re-checked: `"Tropic"`, `"Geyser"`, `"Earth"` work; `"Temps"` low-end can vanish.

---

## 8. Picking, highlighting, tooltips

Interactivity is part of cartography — a hover that lights up the right feature with the right info reinforces the hook.

**Pick what to make pickable.**
- **Always pickable:** the headline layer (top of the stack, the one carrying the takeaway). Set `pickable: true`.
- **Optionally pickable:** secondary layers if the user might want to inspect them. Default is `pickable: false` — leave it that way unless there's a reason.
- **Never pickable:** `HeatmapTileLayer` (picking returns cell properties, not density — usually unhelpful), continuous raster surfaces.

**Highlighting** (auto-on when `pickable: true`):
- `autoHighlight: true` — default when pickable. The hovered feature gets `highlightColor`.
- `highlightColor` — default `[0, 0, 0, 128]` (semi-transparent black overlay). Override with a brand color if the dark default fights your palette: `highlightColor: [255, 200, 0, 180]` (gold) reads on most basemaps.

**Multi-layer tooltips** — `getTooltip` is top-level (one expression for the whole spec), but you can branch on `layer.id`:

```
"@@=object && (
  layer.id === 'cycle_network'
    ? '<b>Cycle Route</b><br>' + object.properties.route_name
    : layer.id === 'hotspots'
      ? '<b>Hotspot</b><br>Accidents: ' + object.properties.accident_count
      : '<b>' + object.properties.severity + ' accident</b>'
)"
```

Use `layer.id` (hoisted as a sibling in PickingInfo), NOT `object.layer.id` — `object` is the feature, not the layer context.

**Tooltip content discipline.** Keep tooltips to ≤ 5 fields. Reserve full data inspection for a separate panel/UI. The tooltip's job is "what is this thing?", not "everything about it".

---

## 9. Anti-patterns — do not emit these

- **Hardcoded `colorBins` domain values without `get_column_stats` first.** You can't pick informed breakpoints for an unknown distribution.
- **Sequential palette on signed data, or diverging palette on unsigned data.** Mismatch.
- **Rainbow palette on ordered data.** Hue order doesn't match value order — readers misread.
- **More than 7 `colorBins` buckets, or more than 12 `colorCategories` values.** Eye stops distinguishing.
- **Mixing tile schemes** (`vectorTableSource` → `HeatmapTileLayer`, etc.). Silent empty render. The `view_map` tool description has the matrix.
- **Encoding the same column on color and size.** Wastes a channel.
- **Three+ data-driven layers stacked.** Hierarchy collapses. Cap at two; the rest constants or muted boundary context.
- **Hardcoded raster `getFillColor` ternaries with 10+ branches.** Silently fails to render — collapse into range bins (`band_1 < 60 ? colorA : ...`) instead of exact-value matching.
- **Function calls in `@@=` expressions.** Forbidden — no `Math.sqrt`, `.toFixed()`, `.toLocaleString()`, template literals, optional chaining. Precompute in SQL.
- **Opacity-as-channel.** Reserve `opacity` for layer-stacking (e.g., 0.55 for an underlying density layer, 1.0 for a top categorical layer).
- **`stroked: true` on covering H3/Quadbin layers.** Adjacent cells share boundaries; double-painting.
- **Labels mid-stack** (`PointLabelLayer` not last in the layers array). Subsequent layers paint over them.
- **`getFillColor` / `getLineColor` on `HeatmapTileLayer`.** Silently ignored. Use `colorRange` + `colorDomain`.
- **Generic deck.gl layers** (`ScatterplotLayer`, `HexagonLayer`, `GeoJsonLayer`, etc.). The `view_map` JSON converter only registers CARTO layers — anything else silently produces nothing.

---

## 10. Worked recipes

### 10.1 Population density (single sequential)

```
get_column_stats({
  connection_name: "carto_dw",
  table_fqn: "carto-demo-data.demo_tables.populated_places",
  column: "pop_max"
})
// → quantiles[5] returns [0, 1500, 5000, 25000, 200000, 30000000]
// Drop first/last; inner 4 are the domain.
```

```json
{
  "initialViewState": { "latitude": 20, "longitude": 0, "zoom": 2 },
  "mapStyle": "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
  "layers": [{
    "@@type": "VectorTileLayer",
    "id": "places",
    "pickable": true,
    "data": { "@@function": "vectorTableSource", "connectionName": "carto_dw", "tableName": "carto-demo-data.demo_tables.populated_places" },
    "getFillColor": {
      "@@function": "colorBins",
      "attr": "pop_max",
      "domain": [1500, 5000, 25000, 200000],
      "colors": "Sunset"
    },
    "pointRadiusUnits": "pixels",
    "getPointRadius": 4,
    "pointRadiusMinPixels": 3,
    "pointRadiusMaxPixels": 10
  }]
}
```

### 10.2 Revenue YoY change (diverging around 0)

`get_column_stats` returns `min: -0.45, max: +0.90, avg: +0.05`. Signed → diverging.

```jsonc
"getFillColor": {
  "@@function": "colorContinuous",
  "attr": "yoy_change",
  "domain": [-0.5, 0, 1.0],
  "colors": "Geyser"
}
```

Multi-stop `domain` anchors the midpoint at 0 even though `min` and `max` are asymmetric.

### 10.3 Heatmap of accidents on dark basemap

```json
{
  "mapStyle": "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
  "layers": [{
    "@@type": "HeatmapTileLayer",
    "id": "accidents-density",
    "data": {
      "@@function": "h3QuerySource",
      "connectionName": "carto_dw",
      "sqlQuery": "SELECT `carto-un`.carto.H3_FROMGEOGPOINT(geom, 9) AS h3, COUNT(*) AS n FROM `<dataset>.accidents` WHERE geom IS NOT NULL GROUP BY 1",
      "aggregationExp": "SUM(n) AS n"
    },
    "getWeight": "@@=properties.n",
    "radiusPixels": 25,
    "intensity": 1,
    "colorRange": [
      [255, 255, 178, 0],
      [254, 217, 118, 160],
      [254, 178, 76, 200],
      [253, 141, 60, 220],
      [240, 59, 32, 240],
      [189, 0, 38, 255]
    ]
  }]
}
```

`HeatmapTileLayer` styling is exclusively via `colorRange` + `colorDomain` — `getFillColor` is silently ignored. Note `colorRange[0]`'s alpha = 0: low-density cells fade to transparent, not white.

### 10.4 Two-layer composition: H3 population + categorical points

Bottom layer (H3 population, sequential, 0.55 opacity, no stroke). Top layer (accident points, categorical, 1.0 opacity, white halo for legibility).

```jsonc
"layers": [
  {
    "@@type": "H3TileLayer",
    "data": {
      "@@function": "h3TableSource",
      "connectionName": "carto_dw",
      "tableName": "carto-demo-data.demo_tables.derived_spatialfeatures_<region>_h3res8_v1_yearly_v2",
      "aggregationExp": "SUM(population) AS population"
    },
    "getFillColor": {
      "@@function": "colorBins",
      "attr": "population",
      "domain": [100, 500, 2000, 10000],
      "colors": "Teal"
    },
    "stroked": false,
    "opacity": 0.55
  },
  {
    "@@type": "VectorTileLayer",
    "data": { "@@function": "vectorTableSource", "connectionName": "carto_dw", "tableName": "<dataset>.accidents" },
    "pickable": true,
    "getFillColor": {
      "@@function": "colorCategories",
      "attr": "severity",
      "domain": ["Slight", "Serious", "Fatal"],
      "colors": [[253, 174, 97, 200], [240, 59, 32, 230], [128, 0, 38, 255]]
    },
    "stroked": true,
    "getLineColor": [255, 255, 255, 230],
    "lineWidthMinPixels": 0.5,
    "pointRadiusUnits": "pixels",
    "getPointRadius": 4,
    "pointRadiusMinPixels": 2,
    "pointRadiusMaxPixels": 10
  }
]
```

Different palette families (`"Teal"` sequential vs custom warm categorical) keep the layers visually separable. Bottom layer at 0.55 opacity recedes. Top layer's white halo separates points from the H3 fills behind them.

### 10.5 Marker + label stack (`PointLabelLayer`)

`PointLabelLayer` renders text only, no marker — always pair with a `VectorTileLayer`. Use a filtered query for the label layer to avoid clutter at low zoom.

```jsonc
"layers": [
  {
    "@@type": "VectorTileLayer",
    "data": { "@@function": "vectorTableSource", "connectionName": "carto_dw", "tableName": "carto-demo-data.demo_tables.populated_places" },
    "getFillColor": [40, 80, 200, 220],
    "pointRadiusUnits": "pixels",
    "getPointRadius": 4,
    "pointRadiusMinPixels": 3
  },
  {
    "@@type": "PointLabelLayer",
    "data": { "@@function": "vectorQuerySource", "connectionName": "carto_dw", "sqlQuery": "SELECT * FROM `carto-demo-data.demo_tables.populated_places` WHERE pop_max > 100000" },
    "getText": "@@=properties.name",
    "getColor": [40, 40, 40, 255],
    "outlineColor": [255, 255, 255, 230],
    "outlineWidth": 3,
    "sizeScale": 14
  }
]
```

`PointLabelLayer` last in the array (drawing-order rule). Filter SQL keeps only large places labeled; smaller markers stay unlabeled until zoomed in (or via a separate larger-zoom label layer in a more complex spec).

---

## Authoring checklist

Before emitting a `view_map` spec where styling is in scope:

- [ ] Did I call `get_column_stats` for any unfamiliar numeric column I'm binning on?
- [ ] Does the palette family match the data character (sequential ↔ ordered, diverging ↔ signed, categorical ↔ unordered)?
- [ ] Does the basemap pair well with the palette (no light colors lost on light basemap, no dark colors lost on dark)?
- [ ] Are layer-source schemes compatible (per the `view_map` tool description's matrix)?
- [ ] If H3/quadbin source: did I include `aggregationExp`?
- [ ] Are layers ordered bottom-to-top: surface → polygons → lines → points → labels?
- [ ] Multi-layer: ≤ 2 data-driven, distinct hue families, opacity-stacked, headline layer pickable?
- [ ] Stroke: `stroked: false` for covering tile layers; on points, white halo if needed for legibility?
- [ ] Pixel-units idiom: `pointRadiusUnits` / `lineWidthUnits` set to `"pixels"` with min/max clamps?
- [ ] If `HeatmapTileLayer`: `getWeight` set, `colorRange` + `colorDomain` set (not `getFillColor`)?
- [ ] If `RasterTileLayer`: `getFillColor` ternary handles the nodata sentinel for the band's dtype?
- [ ] If `PointLabelLayer`: paired with a `VectorTileLayer` for the marker, filtered to relevant features, last in the layers array?
- [ ] `mapStyle` set explicitly to a CARTO basemap URL?
- [ ] `getTooltip` uses `layer.id` for multi-layer dispatch (not `object.layer.id`)?
- [ ] Bucket / category count within legibility limits (≤ 7 numeric buckets, ≤ 12 categories — eye distinguishability cap)?
- [ ] Did I plan to describe the encoding (layer, column, palette, thresholds/categories) in my chat reply, since the renderer doesn't show an inline legend?
