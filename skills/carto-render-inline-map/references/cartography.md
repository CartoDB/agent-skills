# Cartography reference — for `view_map` deck.gl declarative specs

> **This is a reference, not a standalone skill.** Read alongside the `carto-render-inline-map` `SKILL.md` when composing a `view_map` spec that needs cartographic decisions. The `view_map` tool description carries the *syntax* (layer-source compatibility, `aggregationExp`, `@@function` shapes, expression-eval restrictions). This file layers *what to pick* on top — palette, scale, basemap, stroke, drawing order, hierarchy, picking, anti-patterns — once the agent knows *how to encode*.

> **Different from `carto-create-builder-maps/references/cartography.md`.** That reference is for Builder/kepler-config maps authored via the CLI. The shapes don't transfer to deck.gl declarative — they target a different runtime.

> **Different from `carto-build-app/references/layers.md`.** That skill targets developers writing TypeScript/JavaScript app code with full `@deck.gl/carto` access. This file targets agents emitting the `@deck.gl/json` declarative spec consumed by the `view_map` MCP tool — restricted to CARTO classes registered in the JSONConverter and the `@@=` expression-eval engine.

> The cartographic *principles* are the same across all three contexts; the *encodings* are not.

> **Only CARTO layers and primitives.** `view_map` accepts only the layers/sources/helpers from `@deck.gl/carto`: `VectorTileLayer`, `H3TileLayer`, `QuadbinTileLayer`, `ClusterTileLayer`, `HeatmapTileLayer`, `RasterTileLayer`, `PointLabelLayer`. Generic deck.gl layers are **not accepted**.

**Audience:** an LLM agent composing a `view_map` deck.gl declarative spec.

---

## 0. Before you pick anything

**Know the data.** Use the discovery tools rather than guessing:

| Question | How |
|---|---|
| What columns and types? | `list_resources({ fqn })` — response includes `schema: [{name, type}, …]` and `geomField`. |
| What's the column distribution? | `get_column_stats({ table_fqn / query, column })` — numeric returns `min`, `max`, `quantiles[N]`; string returns categories with frequencies. |
| Is it skewed? | Inspect `quantiles[10]`. If `q[5] - q[0] << q[9] - q[5]`, right-skewed (typical for counts, revenue, population, incidents). |

**Name the hook.** One sentence: *"Population is concentrated in the southeast."* The hook governs four downstream decisions: layer (§1), classification (§5), palette (§6), anti-patterns to avoid (§9).

**The cartographic principle — match palette family to measure character.** Foundational thematic cartography (Brewer / ColorBrewer / MacEachren). Three families, three data shapes:

- **Qualitative** → unordered categories. **Distinct hues**, no implied ordering.
- **Sequential** → ordered magnitude. **One hue family, light→dark or dark→light**, implies *more* in one direction.
- **Diverging** → signed deviation around a midpoint. **Two hue families meeting at a neutral midpoint**, implies *zero matters*.

Crossing families misrepresents the data. Pick the family from the data's character; pick the specific palette (named or custom RGBA) by fit — basemap tone, colorblind safety, hue connotation.

---

## 1. Pick the layer

Each CARTO layer is hardcoded to a tiling scheme — see the `view_map` tool description's compatibility matrix. The cartographic question here is *which one tells the story*:

| Story | Layer | Source |
|---|---|---|
| "Where are these things?" — individual features | `VectorTileLayer` (point/line/polygon) | `vector*Source` or `boundary*Source` |
| "Where is the spatial pattern of magnitude?" — bin counts/sums/averages by area | `H3TileLayer` (isotropic) **or** `QuadbinTileLayer` (faster joins) | `h3*Source` / `quadbin*Source` with `aggregationExp` |
| "Where is the density?" — soft continuous gradient | `HeatmapTileLayer` | `h3*Source` or `quadbin*Source` |
| "Where do points cluster, how many in each?" — discrete clusters | `ClusterTileLayer` | `h3*Source` or `quadbin*Source` |
| "What's the value of this continuous surface?" — elevation, NDVI, land class | `RasterTileLayer` | `rasterSource` |
| Place name labels on top of another layer | `PointLabelLayer` (text-only; pair with `VectorTileLayer`) | Same `vector*Source` (often a filtered query) |

**H3 vs Quadbin:** prefer **H3** when the takeaway is shape/extent (organic, equal-area, no axis bias). Prefer **Quadbin** for joins to other quadbin tilesets or national tile schemes.

**Heatmap vs Cluster vs H3:**
- `HeatmapTileLayer` — smooth, soft. Good for "the broad pattern". No discrete cell value to hover.
- `ClusterTileLayer` — discrete clusters; hover shows aggregated `properties` and a `stats` object with cluster-wide aggregations.
- `H3TileLayer` — discrete cells at fixed resolution; hover shows cell values from `aggregationExp` outputs.

**Point overplotting at low zoom on `VectorTileLayer`** (raw points become a black blob below ~zoom 8 in dense areas):
- Add `pointRadiusUnits: "pixels"` + `pointRadiusMinPixels: 2` + `pointRadiusMaxPixels: 8`.
- Or switch to `H3TileLayer` with `aggregationExp: "COUNT(*) AS n"` and color by `n`.
- Or pair with `HeatmapTileLayer` underneath for density context.

---

## 2. Drawing order — bottom to top

deck.gl renders layers in **array order**: index 0 paints first (deepest), the highest index paints last (on top). There is **no `zIndex` / `renderOrder` prop** — reorder the `layers` array.

The cartographic rule: **layers that cover more pixels go to the bottom; sparse features go on top.** Raster and heatmap surfaces tile the entire viewport. H3 / quadbin cells tile wall-to-wall at their aggregation. Polygons cover their bounds. Lines are thin strokes. Points are sparse dots. Labels go last so collision detection runs against the final scene.

Conventional order, bottom → top:

1. **Continuous surfaces** — `RasterTileLayer`, `HeatmapTileLayer`.
2. **Polygons / cells** — `H3TileLayer`, `QuadbinTileLayer`, polygon-geometry `VectorTileLayer`.
3. **Lines** — line-geometry `VectorTileLayer`.
4. **Points** — point-geometry `VectorTileLayer`, `ClusterTileLayer`.
5. **Labels** — `PointLabelLayer`.

**Violations to avoid:**
- Points beneath a polygon fill — eye reads the polygon as the headline, points are missed.
- Labels mid-stack — subsequent layers paint over them.
- Two `H3TileLayer`s of the same data at different resolutions — the higher one obscures the lower.

---

## 3. Pick the visual channel

CARTO accessors that drive visual channels:

| Channel | Accessor / prop | Helper or expression |
|---|---|---|
| Color (fill) | `getFillColor` | `colorBins` / `colorContinuous` / `colorCategories` helpers, constant `[r,g,b,a]`, or `@@=` ternary |
| Color (stroke) | `getLineColor` | Same as fill |
| Size (point radius) | `getPointRadius` + `pointRadiusUnits` (`'pixels' | 'meters'`) + min/max | `@@=` expression (no `colorBins`-style helper for size) |
| Size (line width) | `getLineWidth` + `lineWidthUnits` + min/max | `@@=` expression |
| 3D extrusion | `getElevation` + `elevationScale` (H3/Quadbin when `extruded: true`) | `@@=` expression |
| Layer opacity | `opacity` (0–1, layer-level) | constant; **don't use opacity to encode values** — reserve for hierarchy/design |

**Primary-channel rule:** color carries the headline. Size carries a secondary supporting measure. Don't double-encode the same column on color and size — wastes a channel.

**Pixel-units idiom:** for any size accessor that should remain visually consistent at every zoom, set units to `"pixels"` and clamp with min/max:

```jsonc
"pointRadiusUnits": "pixels",
"getPointRadius": "@@=properties.weight / 100",
"pointRadiusMinPixels": 2,
"pointRadiusMaxPixels": 12
```

Without min/max, points balloon at high zoom and disappear at low zoom. The default `"meters"` scales with zoom and is rarely what you want for symbology.

### 3.1 Opacity as a design lever

Opacity is set via the layer-level `opacity` prop. It does three jobs on fill layers (H3, quadbin, polygon, heatmap, cluster):

1. **Lets the basemap breathe** — at default `opacity: 1` cell layers cover the basemap entirely; the map reads as data floating in void.
2. **Sets visual weight and hierarchy** — a saturated `0.9` layer feels heavy and dominant; a `0.5` layer recedes. In multi-layer maps, use opacity to choose which layer the eye lands on first.
3. **Reveals density through overlap** — where features overlap, lower opacity blends them so the eye reads "more here". Useful on layered choropleths and point clouds.

Typical range `0.4–0.8`. Go to `0.4–0.5` when the basemap carries critical orientation (city grid, coastline, road network), when you want the layer to recede in the design, or when overlap density is itself the signal. Go to `0.7–0.8` when the layer is the hero and the basemap is purely backdrop. Resist defaulting to a single number — fit opacity to the layer's role.

For points, opacity is set via the alpha channel in the color array (`[r, g, b, alpha]`) rather than a layer-level prop. Same principles: lower alpha (~`150`/255) when points overlap heavily so density reads through blending.

---

## 4. Stroke conventions

Default for most CARTO layers is **`stroked: false`, `filled: true`** for polygons/cells. Adding stroke is a deliberate choice:

| Situation | Stroke |
|---|---|
| Light fills on light basemap | **Add stroke** in a darker shade than the fill so cells separate. |
| Dark/saturated fills on dark basemap | **Add a light stroke** to separate adjacent cells. |
| Tiny polygons at low zoom (<10 pixels each) | **Skip stroke** — outlines collapse into noise. |
| `H3TileLayer` / `QuadbinTileLayer` covering most of the viewport | **Skip stroke** — adjacent cells share boundaries; outlines double-paint. |
| Single-feature highlight (focus polygon) | **Add a thicker stroke** in a contrasting hue. |
| Points that should pop against a busy basemap | **Add a halo stroke** (white-ish, `lineWidthMinPixels: 1`). |

**Line widths:** `lineWidthUnits: "pixels"` + `lineWidthMinPixels: 1` + `lineWidthMaxPixels: 4` for context lines, more for headline lines.

**Stroke on dense choropleths — derive from the fill.** When a polygon or cell layer has many small features in the viewport (admin sub-levels, postcodes, parcels, dense h3 / quadbin cells), a contrasting stroke pulls attention away from the data-driven fill. Bind `getLineColor` to the same column as `getFillColor` with a darker variant of the fill colors. Skip stroke entirely when cells are wall-to-wall.

**Stroke as encoding** (rare): drive `getLineColor` from a different column than `getFillColor` for two-axis stories. Use sparingly; second visual channel competes for attention.

---

## 5. Classify the data

Three color helpers map to three scale types:

| Helper | Scale | When |
|---|---|---|
| `colorBins` | Threshold (`d3.scaleThreshold`) — discrete buckets | Most numeric data. Pair with quantile breakpoints from `get_column_stats`. |
| `colorContinuous` | Linear (`d3.scaleLinear`) — smooth gradient | Fine variation where every value should map to a unique color. Multi-stop arrays for diverging around a midpoint. |
| `colorCategories` | Nominal — one color per category | Strings / booleans / ordinal. Cap at 12 distinct values; aggregate the rest into "other". |

**`colorBins` workflow:**
1. `get_column_stats({ table_fqn, column })`.
2. Take `quantiles[N]` for your bucket count (4–5 is the sweet spot).
3. Drop the first and last entries (natural extremes); inner N-1 numbers are the `domain`.
4. Pick a palette by family fit (§6) — by name from the CARTOcolor registry, or a custom RGBA array of N colors.

```jsonc
"getFillColor": {
  "@@function": "colorBins",
  "attr": "population",
  "domain": [1200, 5500, 18000],
  "colors": "<sequential palette name from §6, or custom RGBA array of 4 colors>"
}
```

**Class count:** 4–5 buckets is the legibility sweet spot. 7+ pushes the eye past distinguishability. Fewer than 3 is rarely informative.

**Quantile vs custom thresholds:** default to quantile breakpoints. Override with custom thresholds when there's a meaningful policy break (e.g., `[0, 0.5, 1.0]` for shares).

**Heavy-tailed data:** if `q[9] / q[5] > 5`, quantiles compress the tail too aggressively. Either (a) precompute `LOG10(col + 1)` in `vectorQuerySource` and bin on that, or (b) switch to `colorContinuous` with a multi-stop domain anchored on the median.

**Boolean columns:** `colorCategories` doesn't match raw booleans. Cast in SQL: `SELECT *, CAST(<bool> AS STRING) AS <bool>_s FROM …` and use `domain: ["true", "false"]`.

---

## 6. Pick the palette

CARTO palettes (resolved by name in `colors`):

| Family | Use for | Available names |
|---|---|---|
| **Sequential single-hue** | Magnitude in one direction (counts, sums, populations, intensities) | `Burg`, `BurgYl`, `RedOr`, `OrYel`, `Peach`, `PinkYl`, `Mint`, `BluGrn`, `DarkMint`, `Emrld`, `BluYl`, `Teal`, `TealGrn`, `Purp`, `BrwnYl`, `Gray` |
| **Sequential multi-hue** | Same, more contrast across the range | `PurpOr`, `Sunset`, `SunsetDark`, `Magenta` |
| **Diverging** | Signed values around a meaningful midpoint (deltas, residuals, z-scores) | `ArmyRose`, `Fall`, `Geyser`, `Temps`, `TealRose`, `Tropic`, `Earth` |
| **Qualitative** | Discrete unordered categories | `Antique`, `Bold`, `Pastel`, `Prism`, `Safe`, `Vivid` |

**Colorblind-safe subset** (recommended when audience is public or unknown):
- Sequential: `Teal`, `Purp`, `Mint`, `Emrld`, `BluYl`, `DarkMint`
- Diverging: `Temps`, `Geyser`, `Tropic`
- Qualitative: `Safe`, `Vivid`

**Pick by character, not by reflex.** Once the family is right (per the §0 principle), the specific palette is a fit decision:

- **Hue connotation.** Warm hues carry *severity / heat / alarm*; cool hues carry *calm / magnitude / safe*; purple is neutral. Reach for connotation only when the measure actually supports it — *"risk of flood"* is warm-appropriate, *"population count"* is not.
- **Basemap tone.** Light basemap → palettes with a dark high-end stand out. Dark basemap → palettes with a bright high-end stand out (see §7).
- **Colorblind safety.** Use the subset above when audience is public or unknown.
- **Within-map distinguishability.** Multiple layers in one map need different *families*, not different shades of one (§9).

**Custom palettes are valid.** Any RGBA array of the right length works — `"colors": [[60, 80, 200, 220], [120, 140, 230, 220], …]`. Use when CARTO palettes don't fit the brand / domain / luminance constraint, or when the dataset carries its own colour semantics. The named palettes are tuned for luminance ordering and colorblind safety; a custom palette needs to be checked for the same properties.

**Don't reflex on a palette name.** *"What did I pick last time?"* is the wrong prompt — re-derive each map from the family principle (§0) and the data character.

**Multi-layer hue separation:**
- One sequential + one categorical → fine.
- Two sequentials → make them different hue families (one warm, one cool — not two blues).
- Three+ data-driven layers → cap at two; the rest constants or muted boundary context.

---

## 7. Basemap pairing

Set top-level `mapStyle` to a CARTO basemap URL: `https://basemaps.cartocdn.com/gl/{name}-gl-style/style.json`.

| Basemap | Strengths | Default for |
|---|---|---|
| `positron` | Light, low-saturation, neutral. Lets data colors pop. | Most maps. The right default if the user doesn't specify. |
| `voyager` | Light but more colorful — useful labels, OSM-styled context. | When geographic context (roads, names, POIs) carries meaning. |
| `dark-matter` | Dark, high-contrast for bright/saturated data. | Heatmaps, density of bright signals (lights, fires, night population). |
| `*-nolabels` variants | Same color scheme, no place labels. | Dense data layers where labels would clutter. |

**Always emit `mapStyle`.** Without it, the renderer falls back to positron, but the spec stops being self-describing/portable.

**Palette × basemap:**
- **Light basemap** — most palettes work. Avoid very pale lower-bound colors (bottom bucket disappears into the basemap); bump alpha or pick palettes that start mid-saturation.
- **Dark basemap** — light-on-dark reads well; dark colors near `[0,0,0]` disappear. Prefer palettes that span mid-to-light, OR reverse the palette so its bright end sits at the high-value class. Diverging palettes need the dark end re-checked against the basemap.

---

## 8. Picking, highlighting, tooltips

Interactivity is part of cartography — a hover that lights up the right feature with the right info reinforces the hook.

**Pick what to make pickable:**
- **Always pickable:** the headline layer (top of stack). Set `pickable: true`.
- **Optionally pickable:** secondary layers if the user might want to inspect them. Default `pickable: false`.
- **Never pickable:** `HeatmapTileLayer` (picking returns cell properties, not density), continuous raster surfaces.

**Highlighting** (auto-on when `pickable: true`):
- `autoHighlight: true` — default when pickable.
- `highlightColor` — default `[0, 0, 0, 128]`. Override with a contrasting colour if the dark default fights your palette.

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

Use `layer.id` (hoisted as a sibling in PickingInfo), NOT `object.layer.id`.

**Tooltip content discipline.** Keep tooltips to ≤ 5 fields. The tooltip's job is "what is this thing?", not "everything about it".

---

## 9. Anti-patterns — do not emit these

- **Hardcoded `colorBins` domain values without `get_column_stats` first.** You can't pick informed breakpoints for an unknown distribution.
- **Palette family mismatched to data character.** Sequential on signed data hides the sign; diverging on unsigned implies a midpoint that doesn't exist; sequential on an unordered string column implies an ordering. Default unordered string columns to qualitative; deviate only when the strings carry inherent order (sentiment low/med/high, grades A–F).
- **Rainbow palette (`Prism`, `Vivid`) on ordered data.** Hue order doesn't match value order — readers misread.
- **More than 7 `colorBins` buckets, or more than 12 `colorCategories` values.** Eye stops distinguishing.
- **Palette reflex across sessions.** If your previous spec ended on a given palette, re-derive from the family principle this time. The answer may legitimately be the same palette, but should be a fresh fit — not a reach.
- **Multi-layer mono-culture.** Multiple layers in one map sharing the same hue family → ambiguous which is which. Distinct families per layer.
- **Mixing tile schemes** (`vectorTableSource` → `HeatmapTileLayer`, etc.). Silent empty render.
- **Encoding the same column on color and size.** Wastes a channel.
- **Three+ data-driven layers stacked.** Hierarchy collapses. Cap at two.
- **Hardcoded raster `getFillColor` ternaries with 10+ branches.** Silently fails — use range bins.
- **Function calls in `@@=` expressions.** Forbidden — no `Math.sqrt`, `.toFixed()`, template literals, optional chaining. Precompute in SQL.
- **Opacity-as-channel.** Reserve `opacity` for layer-stacking and design hierarchy (§3.1), not per-feature encoding.
- **`stroked: true` on covering H3/Quadbin layers.** Adjacent cells share boundaries; double-painting.
- **Contrasting stroke on dense small-polygon choropleths.** Edges become more prominent than the data. Derive stroke from fill or skip stroke entirely (§4).
- **Labels mid-stack** (`PointLabelLayer` not last in the layers array). Subsequent layers paint over them.
- **`getFillColor` / `getLineColor` on `HeatmapTileLayer`.** Silently ignored. Use `colorRange` + `colorDomain`.
- **Generic deck.gl layers** (`ScatterplotLayer`, `HexagonLayer`, `GeoJsonLayer`). Silently produces nothing.

---

## 10. Worked recipes

Three archetypal patterns. Palette choices are written as placeholders — the agent picks the specific palette by family fit per §6 (named from the registry or custom RGBA array).

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
      "colors": "<sequential palette, picked per §6 — basemap is light, so any sequential with a dark high-end fits>"
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
  "colors": "<diverging palette, picked per §6 — for a colorblind-safe public audience prefer Temps / Geyser / Tropic>"
}
```

Multi-stop `domain` anchors the midpoint at 0 even though `min` and `max` are asymmetric.

### 10.3 Two-layer composition — H3 magnitude + categorical points

Bottom layer (H3 population, sequential, 0.55 opacity, no stroke — recedes into context). Top layer (events, categorical, white halo for legibility — the headline).

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
      "colors": "<sequential palette per §6 — pick a cool family so the warm categorical points on top read as the headline>"
    },
    "stroked": false,
    "opacity": 0.55
  },
  {
    "@@type": "VectorTileLayer",
    "data": { "@@function": "vectorTableSource", "connectionName": "carto_dw", "tableName": "<dataset>.events" },
    "pickable": true,
    "getFillColor": {
      "@@function": "colorCategories",
      "attr": "severity",
      "domain": ["Slight", "Serious", "Fatal"],
      "colors": "<qualitative palette per §6, OR a custom RGBA array — warm hues fit a severity axis>"
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

Different palette families per layer (sequential cool vs. categorical warm) keep them visually separable. Bottom layer at `0.55` opacity recedes (§3.1). Top layer's white halo separates points from the H3 fills.

### 10.4 Marker + label stack (`PointLabelLayer`)

`PointLabelLayer` renders text only — always pair with a `VectorTileLayer`. Use a filtered query for the label layer to avoid clutter at low zoom.

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

`PointLabelLayer` last in the array (drawing-order rule). Filter SQL keeps only large places labeled.

---

## Authoring checklist

Before emitting a `view_map` spec where styling is in scope:

- [ ] Did I call `get_column_stats` for any unfamiliar numeric column I'm binning on?
- [ ] **Does the palette family match the data character?** Sequential ↔ ordered magnitude, diverging ↔ signed, qualitative ↔ unordered. For string columns: default qualitative; only sequential when strings carry inherent order (§6, §9).
- [ ] Is the specific palette a fresh fit per map — not a reflex from the previous spec? Named from the registry OR custom RGBA — both valid (§6).
- [ ] Colorblind-safe palette if audience is public or unknown (§6 subset)?
- [ ] Does the basemap pair well with the palette (no light colors lost on light basemap, no dark colors lost on dark) (§7)?
- [ ] Are layer-source schemes compatible (per the `view_map` tool description's matrix)?
- [ ] If H3/quadbin source: did I include `aggregationExp`?
- [ ] Layers ordered bottom-to-top: surface → polygons → lines → points → labels (§2)?
- [ ] Multi-layer: ≤ 2 data-driven, distinct hue families, opacity-stacked, headline layer pickable (§6, §3.1)?
- [ ] Stroke: `stroked: false` for covering tile layers; on points, white halo if needed; on dense small-polygon choropleths, derive stroke from fill (§4)?
- [ ] Pixel-units idiom: `pointRadiusUnits` / `lineWidthUnits` set to `"pixels"` with min/max clamps (§3)?
- [ ] Opacity fits the layer's role (§3.1) — `0.4–0.5` for recede / basemap-context, `0.7–0.8` for hero, not a fixed default?
- [ ] If `HeatmapTileLayer`: `getWeight` set, `colorRange` + `colorDomain` set (not `getFillColor`)?
- [ ] If `RasterTileLayer`: `getFillColor` ternary handles the nodata sentinel for the band's dtype?
- [ ] If `PointLabelLayer`: paired with a `VectorTileLayer`, filtered, last in the layers array?
- [ ] `mapStyle` set explicitly to a CARTO basemap URL?
- [ ] `getTooltip` uses `layer.id` for multi-layer dispatch (not `object.layer.id`)?
- [ ] Bucket / category count within legibility limits (≤ 7 numeric buckets, ≤ 12 categories)?
- [ ] Plan to emit an HTML legend after the render — via a widget tool if available, else inline HTML — per the `view_map` tool description's LEGEND section?
