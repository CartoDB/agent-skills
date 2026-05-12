# Cartography reference — for CARTO maps authored via the `carto-create-builder-maps` skill

> **This is a reference, not a standalone skill.** Read alongside `SKILL.md` in the same directory when composing a CARTO map that needs cartographic decisions. `SKILL.md` is the primary authoring entry point — commands, configuration shape, field reference, validation. This file layers *what to pick* on top (palette family, scale type, basemap pairing) once the agent knows *how to encode* the configuration.

**Audience:** an LLM agent composing or editing a CARTO map configuration via the CARTO CLI. This reference teaches *what to pick* — layer type, channel, scale, palette, basemap, legend — so the resulting map reads well at a glance.

**Scope:** maps authored through the CLI configuration — the same object model Builder renders. Layer types: `tileset`, `h3`, `quadbin`, `heatmapTile`, `clusterTile`, `raster`.

## Table of contents

- **§0** *Before you pick anything* — read the data, name the hook.
- **§1** *Pick the layer type* — source-driven; §1.0 covers the one real choice (point aggregation); §1.8 covers stack order; §1.9 covers zoom-aware visibility.
- **§2** *Pick the visual channel* — one measure per channel, max two channels per layer.
- **§3** *Classify the data* — scale types and the quantize/quantile/log/custom decision.
- **§4** *Pick the palette* — the cartographic principle, then families, then specifics.
- **§5** *Basemap pairing*.
- **§6** *Legend, popup, label*.
- **§7** *Anti-patterns — do not emit these*.
- **§8** *Worked recipes*.
- **Authoring checklist** at the bottom.

---

## 0. Before you pick anything — read the data and name the hook

Cartographic choices depend on the data and on what story the map tells. Before any decision below:

**Know the data:**

| Question | Where to get it |
|---|---|
| What geometry does the dataset carry? | `carto connections describe <conn> <table>` — surfaces the geo column, any spatial index, the shape type |
| What columns exist, and what types? | Same `describe` call — note numeric vs. string vs. timestamp vs. boolean |
| Is the measure a count, a rate, a share, a magnitude, a delta, a category? | From the user's prompt + column semantics. Ask if genuinely ambiguous |
| What's the cardinality / shape of the coloring column? | For string: unique-value count. For numeric: min/max, skew |

**Heuristic for skew without running stats:** *counts*, *revenue*, *population*, *incidents*, *visits*, *areas in m²* are almost always right-skewed. *Rates*, *percentages*, *z-scores*, *indices normalised to a population* are usually closer to normal.

**Who's reading this map.** Typically a GIS / Data Analyst at the terminal, not a developer — they read maps at a glance and judge by legibility. Optimise for the glance; don't pile on options just because the schema allows them.

**Name the hook.** Every decision sharpens if you can answer, in one sentence, *what the viewer should take away*. Good: *"Revenue per store is concentrated in the northeast."* Bad: *"Map of stores"* — that's a dataset, not a hook.

**The hook shapes four things:**
1. The layer type (§1) — what renders best for the takeaway.
2. The classification (§3) — emphasise extremes, the middle, or a policy threshold.
3. The palette family (§4) — sequential for magnitude, diverging for signed, qualitative for kinds.
4. The anti-patterns to avoid (§7).

If the user names the measure but not the column (*"map population density by county"*), pick the column that matches semantically and confirm briefly — don't ask them to name it if one is obviously right.

---

## 1. Pick the layer type

**Most of this is not your call.** The layer type is determined by the **source** — the dataset's type / indexing / geometry.

| Source is… | Layer type | Agent choice? |
|---|---|---|
| A raster (quadbin-backed band store) | `raster` | No |
| An h3-indexed table | `h3` | No |
| A quadbin-indexed table | `quadbin` | No |
| A line tileset | `tileset` | No |
| A polygon tileset | `tileset` | No |
| **A point source** | `tileset` **or** aggregate | **Yes — §1.0** |

Trust the source. If `carto connections describe` reports a quadbin index, the layer is `quadbin` — don't second-guess from column names or user phrasing.

**Only points get the aggregation pathway.** Lines and polygons are always `tileset`. Rasters are always `raster`. H3 / quadbin tables always render at their own layer type.

### 1.0 The one real layer-type decision: what to do with point sources

| Choice | Reach for it when |
|---|---|
| Keep as `tileset` (individual points) | Each point is meaningful on its own. Cardinality ≤ ~50k at target zoom |
| Aggregate to `h3` | **Default for density / "where is X concentrated?"** Cells are quantitative — the legend reads as "events per cell" |
| Aggregate to `quadbin` | Same role as h3, but rectilinear binning is semantically required (satellite grid, integration with quadbin reference data) |
| `heatmapTile` | Only when the intent is the blurred narrative "glow" and the reader is not expected to quantify anything |
| `clusterTile` | High-cardinality point datasets where individuals must stay click-revealable on zoom-in |

**Prefer h3 (or quadbin) over heatmapTile / clusterTile for anything quantitative.** Aggregated cells carry real numbers. Heatmap and cluster compress signal and cost quantitative precision.

**H3 vs. quadbin for agent-chosen aggregation:** default to `h3`. Pick `quadbin` only when the surrounding data ecosystem is already quadbin-indexed.

**Resolution when aggregating, rough h3 guide:**

| Target zoom / extent | h3 resolution |
|---|---|
| Country / continent | 3–4 |
| Region / state | 5–6 |
| City / metropolitan | 7–9 |
| Neighbourhood / street | 10–12 |

### 1.1–1.7 Per-layer capability reference

Given the layer type is fixed, here's what you can style. **Each geometry has independent attribution.**

### 1.1 `tileset` — points

- `radius` or `radiusField` + `radiusRange`
- `filled` — almost always `true`
- `stroked` + `strokeColor` + `strokeColorField` + `thickness` — point outline
- `opacity` — typical range `0.5–0.9`; drop to `0.4–0.6` when points overlap heavily so density reads through blending (see opacity design note in §1.4)
- `customMarkers: true` + `customMarkersUrl` / `customMarkersField` / `customMarkersRange.markerMap`
- `rotationField` — rotate by a numeric column (degrees)

**Default:** `filled: true, radius: 4`.

**Rule: radius = point diameter; size = stroke.** On points, `sizeField` drives stroke width, not diameter.

**No polygon attribution applies to points** — `enable3d`, `heightField`, `wireframe`, `elevationScale` are ignored.

### 1.2 `tileset` — lines

- `thickness` or `sizeField` + `sizeRange`
- `strokeColor` / `colorField` — the line color *is* the stroke
- `opacity` — 0.7–1.0; lines need more opacity than polygons

**Default:** `stroked: true, filled: false, thickness: 2`.

**Width encodes magnitude.** Use `sizeField` + `sizeRange` for numeric line measures. Color encodes category or magnitude.

### 1.3 `tileset` — polygons

- `filled: true` + `colorField` → choropleth
- `stroked: true` + `strokeColor` + `strokeColorField` + `thickness` → borders (keep thin: 0.5–1 px)
- `enable3d: true` + `heightField` + `heightRange` + `elevationScale` → extrusion
- `wireframe: true` — wireframe 3D (only with `enable3d: true`)
- `opacity` — typical range `0.4–0.8`; lower when the basemap carries orientation context or you want the layer to recede in the design (see §1.4)

**Default:** `filled: true, opacity: 0.6`.

**Don't extrude rates** (density, percentage, share). See §7.3.

**Stroke on dense choropleths — derive from the fill.** When a choropleth has many small polygons (sub-national admin, postcodes, parcels, h3 / quadbin cells), the default contrasting stroke makes boundaries more prominent than the data. **Bind `strokeColorField` to the same column as `colorField`, on a darker variant of the fill palette with the same break points.** Multiply each fill RGB by ~0.7. Use `thickness: 0.6–0.8`, `strokeOpacity: 0.85–0.95`. See §7.13 for the failure mode.

A contrasting stroke is correct when polygons are large and few (countries on a world map) — each is a distinct entity, not one cell in a distribution.

### 1.4 `h3` — hex cell aggregation

**Source:** h3-indexed table, OR a point source aggregated to h3 (§1.0).

**Why hex:** hexagons avoid orientation bias (all neighbours equidistant).

- `colorField` + `colorAggregation` — long-form aggregations (`average`, not `avg`); numeric: `count` / `sum` / `average` / `maximum` / `minimum` / `stdev` / `variance`; string/boolean/date: `mode` / `any_value`. See [`layers.md`](layers.md).
- `filled`, `stroked`, `thickness`, `opacity` — same as polygons (§1.3)
- `enable3d` + `heightField` + `heightAggregation` → volumetric hex

**Opacity is a design lever, not a fixed setting.** It does three jobs on cell and polygon layers (h3, quadbin, polygon tilesets, heatmap, cluster):

1. **Lets the basemap breathe** — at default `opacity: 1` the basemap disappears and the map reads as data floating in void.
2. **Sets visual weight and hierarchy** — a saturated `0.9` layer feels heavy and dominant; a `0.5` layer recedes into the design. In multi-layer maps, use opacity to choose which layer the eye lands on first.
3. **Reveals density through overlap** — where features overlap, lower opacity blends them so the eye reads "more here". Useful on layered choropleths and point clouds.

Typical range `0.4–0.8`. Go to `0.4–0.5` when the basemap carries critical orientation (city grid, coastline, roads), when you want the layer to recede in the design, or when overlap density is itself the signal. Go to `0.7–0.8` when the layer is the hero and the basemap is purely backdrop. Resist defaulting to a single number — fit opacity to the layer's role in the map.

This applies to every fill layer (see also §1.1 points, §1.3 polygons). The numbers in the per-layer sections are starting points, not floors.

**Aggregation heuristic:** `count` for *"how many?"*, `sum` for totalling, `average` for intensity per event, `maximum` for *"worst case in cell"*. String columns: `mode` (most common) or `any_value`.

### 1.5 `quadbin` — square cell aggregation

Everything in §1.4 applies — quadbin and h3 share the same `SpatialIndexLayer` family.

### 1.6 `heatmapTile` and `clusterTile`

Pick over h3 / quadbin only when narrative reasons outweigh the loss of quantitative precision.

**`heatmapTile`** — continuous density surface (quadbin-backed).
- `weightField` (identity scale) + `weightAggregation` set per-record contribution
- `colorRange` sets the gradient
- Suppress the legend — heatmaps are almost always misread quantitatively (§6.1)

**`clusterTile`** — adaptive point clustering.
- `radius`, `radiusRange`, `clusterRadius`
- Cluster size and color can encode separate dimensions (size = count, color = average)

**Opacity:** same design considerations as h3 / quadbin — typical `0.4–0.8`, fit to the layer's role (see §1.4).

### 1.7 `raster`

**Source:** quadbin-backed raster band store.

| `rasterStyleType` | When | Extra config |
|---|---|---|
| `Rgb` | True/false-colour composite | `colorBands`: three `{ band, type, value }` entries — `type: "band"` or `"expression"` (e.g., `(B04-B03)/(B04+B03)` for NDVI) |
| `ColorRange` | Continuous palette on one band | `colorField` + `colorRange` (sequential) |
| `UniqueValues` | Categorical raster (land cover, masks) | `colorField` + `uniqueValuesColorRange` + `uniqueValuesColorScale: "ordinal"` + `uniqueValuesColorDomain` |

**Default to `ColorRange`** for any single-band continuous measure. Reach for `Rgb` only when the data is natively multi-band and the composite is the point.

---

**Legacy types — do not emit.** `point`, `geojson`, `line`, `hexagonId`, `grid`, `hexagon`, `heatmap`, `cluster`, `trip`. The CLI rejects them on create.

---

### 1.8 Layer order — index 0 renders on top

**The first entry in `keplerMapConfig.config.visState.layers` renders on top.** Builder's legend uses the same convention.

> **Heads-up: opposite of standard deck.gl.** Builder reverses the array internally. From the configuration author's POV, **index 0 = top, last index = bottom**.

The cartographic rule: **layers that cover more pixels go to the bottom; sparse features go on top**. Point tilesets are sparse (a dot per record). Polygon tilesets fill only where polygons exist. h3 / quadbin / heatmap / cluster tile the *entire viewport* wall-to-wall. Raster covers everything.

| Array position | Layer shape | Why this position |
|---|---|---|
| **Index 0** (top) | `tileset` points | Sparse — doesn't occlude |
| Index 1 | `tileset` lines | Thin strokes — minimal occlusion |
| Index 2 | `tileset` polygons (`filled: true`) | Fills where polygons exist; partial coverage |
| Index 3 | `h3`, `quadbin`, `heatmapTile`, `clusterTile` | Tiles viewport wall-to-wall at the aggregation level |
| **Last index** (bottom) | `raster` (basemap-like imagery) | Total coverage |

**`layerOrder` overrides the array order.** When `layerOrder` is missing, Builder uses array-index order. The CLI auto-emits `layerOrder` on create.

**Edge case.** A `tileset` polygon with `filled: false` (outline-only) can sit above fill layers without occluding them.

### 1.9 Zoom-aware visibility — show the right layer at the right zoom

`§1.8` decides which layer is on top *at a single zoom*. `§1.9` decides which layer is *visible at all* by zoom level. Enforced via `layer.config.visibilityByZoom: { min, max }` (range `[0, 24]` on CARTO basemaps / `[0, 22]` on Google Maps).

**The point-overplotting trap.** A point `tileset` at zoom 3–8 (country view) collapses every point into the same pixel cluster. Viewers see "lots of stuff" and learn nothing — the most common low-zoom-unreadable failure for point maps.

**Two fixes — pick by data shape:**

**Fix A — hide below the readable zoom.** `visibilityByZoom: { min: <zoom-where-it-becomes-readable>, max: 24 }`. Use when individual features are the point (find-this-store). Below the threshold the absence is correct, not a UX bug.

**Fix B — multi-layer cascade.** Stack layers over the same data with handoff windows: coarse h3 at zoom 0–7, finer aggregation 7–11, points 11–24. The same source drives multiple layers; the SQL or aggregation differs. Use when the narrative is pattern-level at every zoom.

**Admin-boundary cascade** is the same shape on the polygon side: countries 0–4, states 4–7, counties 7–10, tracts 10–24 — separate boundary tileset per granularity, each with its own `visibilityByZoom` band.

**Defaults to author up front:**
- Point `tileset` over a national / global dataset → `visibilityByZoom: { min: 7, max: 24 }` at minimum, OR pair with a low-zoom aggregation companion.
- Admin-boundary maps spanning >2 levels → always emit a per-level cascade.
- `clusterTile` is the runtime alternative — adapts cluster size to zoom in one layer.

**Anti-pattern (see §7.12):** a single point `tileset` always-visible with no `visibilityByZoom` and no aggregated companion, then expecting the viewer to zoom in.

---

## 2. Pick the visual channel

**One measure per channel. Max two channels per layer.** Three is busy; four is unreadable.

| Channel | Drives | Valid on | Use for |
|---|---|---|---|
| `colorField` | Fill color | All tile layers | The *primary* measure |
| `strokeColorField` | Stroke color | Tileset (lines/polygons), h3, quadbin | Secondary measure — rare |
| `sizeField` | Stroke width | Tileset (points/lines), h3, quadbin | Edge thickness — rare |
| `radiusField` | Point diameter | Tileset (points only) | Magnitude on points |
| `heightField` | 3D extrusion height | Tileset (polygons), h3, quadbin | Magnitude when extrusion is justified |
| `weightField` | Heat density weight | heatmapTile | Per-record contribution |
| `customMarkersField` | Icon selection | Tileset (points only) | Categorical → distinct icons |
| `rotationField` | Point rotation (degrees) | Tileset (points only) | Direction (wind, heading, bearing) |

### 2.1 Primary-channel rules

**Color is almost always the right primary channel.** Humans read color faster than size or height.

**Use radius/size when color won't reach:** all points share one category but magnitudes differ; the map already has many coloured layers; the user asked for *"bigger dots where X is higher"*.

**Use height (3D) only when:** the measure is genuinely a volume / stacked quantity (floors, tonnage, count); the camera is tilted; the user explicitly asks. **Never** for rates, percentages, shares, densities, indices, z-scores (§7.3).

### 2.2 Combining channels

| Primary | Secondary | Reads as |
|---|---|---|
| Color | Radius (different column) | Bivariate "what + how much" on points |
| Color | Height (different column) | Volumetric choropleth — only with one being a count |
| Color (category) | Radius (magnitude) | "Kind + size" — strong for business locations |
| Icon (category) | Color (category) | Categorical combined — rare, careful palette |

**Anti-combinations:** color and stroke-color on different columns (visually inseparable); color + height on the same column (redundant); radius + size + color on points (overload).

---

## 3. Classify the data

*"Classification"* = how a continuous numeric column is broken into color bins. The single highest-leverage decision in choropleth / cell cartography.

### 3.1 Scale types

The `colorScale` values to emit — matching what Builder's UI offers:

| Scale | Name | Character |
|---|---|---|
| `quantize` | Equal interval | Equal *value* ranges. Magnitude distance preserved, breaks are round numbers, maps comparable across viewports. **Strong default for bounded data.** |
| `quantile` | Quantile | Equal *count* per class. Rank, not magnitude. Use when the question is *"top-N?"* |
| `custom` + `uiCustomScaleType: "logarithmic"` | Logarithmic | Heavy-tailed across 4+ orders of magnitude |
| `custom` (hand-authored `colorMap`) | Custom thresholds | Domain-specific breakpoints (grades, policy cutoffs, Jenks pre-computed) |
| `ordinal` | Categorical | String fields, or hexColor mode (§4.7) |

If a configuration read back via `get --json` shows `log`, `sqrt`, `linear`, `identity` on a *color* channel, treat it as legacy — Builder's UI doesn't produce those. They're valid for size / height / radius channels.

> **Gotcha: `ordinal` only honours string columns.** If `colorField.type` is `integer` or `real` and `colorScale: "ordinal"`, Builder silently renders `quantize` — the legend shows numeric bins instead of categorical labels. Same for `strokeColorScale` and `sizeScale`. Tier-1 catches this. **Fix:** `CAST(<col> AS STRING)` in source SQL + set `colorField.type: "string"`; or switch to `quantize` with explicit breaks.

### 3.2 Pick `colorScale` by distribution shape AND data meaning

> **`quantile` is NOT the safe default.** Reflexively picking it is the most common scale-choice failure. Pick by data shape AND what you want the viewer to take away.

| Data shape | What viewers should read | `colorScale` | Notes |
|---|---|---|---|
| **Bounded with semantic landmarks** (0–100 scores, 0–1 ratios, percentages, age bands) | Magnitude on a fixed-meaning scale | **`quantize`** + explicit `visualChannels.colorDomain` set to the scale's natural extent (e.g. `[0, 100]`) | Anchored bins, round-number legend, comparable across viewports. Without `colorDomain`, breaks shift as the user pans |
| **Skewed long-tail unbounded** where viewers care about *rank* | Rank | `quantile` | Equal-population bins. Don't pick for bounded scores — breaks become arbitrary |
| **Heavy-tailed across 4+ orders of magnitude** (point density, throughput, financial outliers) | Magnitude on log scale | `custom` + `uiCustomScaleType: "logarithmic"` + log10-spaced `colorMap` | Linear breaks compress the tail; quantile flattens the bulk |
| **Categorical-looking integers** (severity 1/2/3, tier id, status code) | Discrete categories | `CAST(<col> AS STRING)` + `ordinal` | The integers are labels, not magnitudes |

**Default ladder when in doubt:**
1. Bounded / has semantic extent → `quantize` + `colorDomain`.
2. Heavy-tailed across orders of magnitude → `custom` + log10 `colorMap`.
3. Skewed unbounded, viewers want rank → `quantile`.
4. Categorical labels disguised as integers → cast to string + `ordinal`.
5. Stakeholder-agreed breakpoints → `custom` with explicit `colorMap`.
6. String / native categorical → `ordinal`.
7. Hex column → `ordinal` + hexColor mode (§4.7).

**On CARTO-indexed cell datasets (h3, quadbin, pre-aggregated tilesets):** cell counts are frequently log-normal — prefer the logarithmic option before falling back to quantile.

### 3.3 What the runtime does NOT offer as first-class scales

When you need them, pre-compute upstream and emit as `custom` with a `colorMap`:

- **Jenks natural breaks** — minimises within-class variance. Quantile/quantize cover most uses.
- **Standard-deviation classification** — compute the σ-tier column upstream as integer, classify as `ordinal`, or bake into `custom` `colorMap`.

### 3.4 Number of classes

Default to **5**. Drop to 3 for overview / executive maps. Up to 7 for detailed analysis. Past ~7 the ramp blurs in the middle.

### 3.5 Escape hatches

- **Meaningful zero** (change, delta, z-score) → diverging palette (§4.2), optionally centred via `custom` colorMap (§4.3).
- **Categorical but ordered** (low/med/high, A–F) → `ordinal` on the string field, sequential palette so the order reads.
- **One extreme value dominates** → clip the top 1–5% and annotate, or switch to logarithmic.

---

## 4. Pick the palette

**The cartographic principle — match the family to the measure character.** This is foundational thematic cartography (Cynthia Brewer / ColorBrewer / MacEachren). Three families, three data shapes:

- **Qualitative** → unordered categories (kinds, types, names). **Distinct hues.** No implied ordering.
- **Sequential** → ordered magnitude (counts, intensities, scores). **One hue family, light→dark or dark→light.** Implies *more* in one direction.
- **Diverging** → signed deviation around a midpoint (change, z-score, over/under target). **Two hue families meeting at a neutral midpoint.** Implies *zero matters*.

**Crossing families misrepresents the data.** A sequential palette on a string column implies an ordering the data doesn't have. A qualitative palette on a magnitude column loses the *more/less* read. A sequential palette on signed data hides the sign. Pick the family from the data's character; pick the specific palette by fit (basemap tone, colorblind safety, hue connotation).

### 4.1 CARTO palette families

**Qualitative (unordered categories — distinct hues):** `Antique`, `Bold`, `Pastel`, `Prism`, `Safe`, `Vivid`

**Sequential (magnitude — ordered):** `Burg`, `BurgYl`, `RedOr`, `OrYel`, `Peach`, `PinkYl`, `Mint`, `BluGrn`, `DarkMint`, `Emrld`, `BluYl`, `Teal`, `TealGrn`, `Purp`, `PurpOr`, `Sunset`, `Magenta`, `SunsetDark`, `BrwnYl`, `Gray`

**Diverging (signed):** `ArmyRose`, `Fall`, `Geyser`, `Temps`, `TealRose`, `Tropic`, `Earth`

**Colorblind-safe subset** (recommended when audience is public or unknown):
- Qualitative: `Safe`, `Vivid`
- Sequential: `Teal`, `Purp`, `Mint`, `Emrld`, `BluYl`, `DarkMint`
- Diverging: `Temps`, `Geyser`, `Tropic`

### 4.2 Fit the palette to the measure

Once the family is right (§4 principle), the specific palette is a fit decision — not a reflex. Consider:

- **Hue connotation.** Warm hues (red, orange) carry *severity / heat / alarm*; cool hues (blue, green) carry *calm / magnitude / safe*; purple is neutral. Reach for the connotation only when the measure actually supports it — *"risk of flood"* is warm-appropriate, *"population count"* is not.
- **Basemap tone.** Light basemap (positron, voyager) → palettes with a dark high-end stand out. Dark basemap (dark-matter) → palettes with a bright high-end stand out (see §4.4).
- **Colorblind safety.** Use the subset above when audience is public or unknown.
- **Within-map distinguishability.** Multiple layers in one map need different *families*, not different shades of one (§7.11).

**Don't reach for a named palette by reflex.** "What did I use last time?" is the wrong prompt — the answer should be a fresh fit-by-character each map (§7.10).

For categorical data, the goal is **distinct hues**. CARTO qualitative palettes are tuned for that. A custom palette is fine as long as adjacent categories are visually separable; shades of one hue are not (that's a sequential palette, and using it for categories implies an order that isn't there).

### 4.3 Centring a diverging palette on zero

If the distribution is roughly symmetric around zero, `quantize` + diverging palette places the middle class near zero by construction — no extra work.

**Explicit centring is worth it when:**

- Distribution is *asymmetric* around zero (mostly positive with a few severe negatives) — one side gets washed out without explicit breakpoints.
- Viewers should pick out the zero class exactly (*"which cells didn't change?"*).
- Side-by-side comparison with another map needs the midpoint anchored.

**If you centre explicitly:** `custom` scale with a `colorMap` pinning zero at the centre. Last entry uses `null` as the catch-all upper bucket — required.

```jsonc
"colorScale": "custom",
"colorRange": {
  "name": "TealRose",
  "category": "CARTO",
  "type": "diverging",
  "colors": ["#009392","#39b185","#9ccb86","#e9e29c","#eeb479","#e88471","#cf597e"],
  "colorMap": [
    [-0.5, "#009392"], [-0.25, "#39b185"], [-0.1, "#9ccb86"],
    [0.1, "#e9e29c"], [0.25, "#eeb479"], [0.5, "#e88471"], [null, "#cf597e"]
  ]
}
```

### 4.4 Dark basemap considerations

CARTOColors sequential palettes are designed light → dark by default. That's correct on *light* basemaps — the pale low-value class disappears into the background, the dark high-value class stands out. On `dark-matter` the rule **inverts**: bright at the high-value end (so they pop), dark at low (recede into basemap).

**Two ways to handle dark:**

1. **Pick a palette whose default order already works on dark** — sequential palettes with a dark low-value end that reads as "background" and a bright high-value end. Several CARTO palettes qualify; check the low end against `#1a1a1a`-ish basemap.
2. **Reverse the palette** — flip `colors[]` so bright sits at the high-value end, OR set `"reversed": true` on `colorRange`.

**On `positron` / `voyager`:** default light→dark order is fine.

**Never pair `dark-matter` with a palette that has a light low-value end UNLESS the "low" class is semantically "absent"** — pale blobs disappearing into dark is only OK if disappearing is intended.

### 4.5 Categorical — too many values

More than 12 categories is unreadable with any palette. **Collapse to top-N by frequency, bucket the rest as `Other`.** If the dataset encodes its own per-category colors in a column, use hexColor mode (§4.7).

> **Two stacking constraints** when `colorScale: "ordinal"` or `"custom"` runs against a high-cardinality string column:
>
> - **Palette length caps distinct-hue count.** When the column has more unique values than the palette has colours, extras fall into Builder's "Others" bucket which renders grey. A 6-colour palette over 25 unique values means 5 distinct + 20 grey — the map looks broken. CARTO qualitative palettes scale up to 12 colours; pick one long enough, or specify `colorRange.colorMap` to control mappings.
>
> - **Legend caps at 20 entries — the map still renders all.** `MAX_LEGEND_ENTRIES = 20` slices the legend; past that, a *"+N more"* message appears. The map colours every feature correctly. When every category must be labelled, collapse to top-19 + `Other`.
>
> Three escape hatches: (1) pick a palette long enough; (2) filter source SQL to top-N upstream; (3) use hexColor mode (§4.7) when the data carries its own colour.

### 4.6 Custom palettes and borrowing

`colorRange.name` and `category` must match the runtime's registry or the legend breaks. For a one-off palette:

- Keep `name` pointing to a real CARTO palette (e.g., `Teal`)
- Replace `colors` with your custom array
- Optionally set `colorMap` for exact thresholds
- The runtime renders the colors provided; the legend resolves by name

Set `category` only to `CARTO`, `ColorBrewer`, `Uber`, or an account-palette category confirmed to exist.

**When to reach for a non-CARTO ramp:**

- Need a **perceptually-uniform** ramp — paste **Viridis** or **Cividis** hex into `colors[]` and keep `name` on a nearest CARTO entry.
- Stakeholder agreed on a **ColorBrewer** palette — same lineage as CARTO (both from Brewer). Paste hex into `colors[]`; keep `name` on a real CARTO entry.

Don't invent palettes ad-hoc — luminance ordering, colorblind safety, and print legibility all need checking.

### 4.7 Hex-color columns — palette-free coloring from the data

When the dataset carries its own hex column (or a SQL query projects one), the runtime can colour features directly. Right tool when colour *is* part of the data's meaning: brand colours, regulatory traffic-light indicators, team colours.

**Requirements:**
- A column with valid CSS hex strings (`"#FF5733"`); malformed/null falls back to grey.
- Column present in the source or projected by `customSql` / `querySource`.
- **Color channels only** (`colorField` / `strokeColorField`) — not size / radius / height / weight / rotation.

**Configuration shape:**

```jsonc
"visualChannels": {
  "colorField": {
    "name": "product_category",     // label column — legend shows these
    "type": "string",
    "colorColumn": "brand_hex"      // hex-value column — actual fill
  },
  "colorScale": "ordinal"
},
"visConfig": {
  "colorRange": {
    "hexColor": true,
    "name": "Custom", "category": "Custom", "type": "custom",
    "colors": []                    // runtime fills from the query
  }
}
```

`colorScale` stays `ordinal`. The legend pairs each unique `name` with its `colorColumn` value via `GROUP BY name, colorColumn`.

**Use when:** domain-required colors (brand, regulatory), dataset author has already done the cartography upstream, many categories (>12) where a palette would cycle meaninglessly.

**Don't use when:** column name suggests colours but doesn't contain hex strings (verify first), user wants cartographic control (colorblind / luminance / palette rotation), continuous numeric measures.

**Layer-type caveat:** reliable on `tileset` (every row reaches the renderer unchanged). On `h3` / `quadbin` the color column must propagate through the spatial-index aggregation expression, which the CLI doesn't auto-handle — prefer tileset or pre-aggregate manually.

---

## 5. Basemap pairing

> **Set basemap in BOTH** `keplerMapConfig.config.basemapConfig.styleId` AND `keplerMapConfig.config.mapStyle.styleType` to the same value. See [`basemap.md`](basemap.md) for the dual-write rule and id catalogue.

```
Thematic data (choropleth, cells, density)
└── positron (light) or dark-matter (dark) — minimal basemap, max data prominence

Reference data (points on top of city context)
└── voyager — keeps road/label/POI context without overwhelming

Photo-real raster (satellite, NDVI composite)
└── positron under it (reference grid) or no basemap

Real-world high-zoom context (delivery, indoor, ops)
└── Google satellite or hybrid
```

**Default when in doubt: `positron`.** Neutral, doesn't fight the data, works with every palette family.

**Layer-group toggles** (`basemapConfig.visibleLayerGroups`, mirror in `mapStyle.visibleLayerGroups`): clean thematic view → off: `road`, `border`, `label`; on: `land`, `water`, `building`. Reference map → keep everything on. Print → off `building` at low zoom, off `label` when the thematic layer carries text.

---

## 6. Legend, popup, label

### 6.1 Legend

Auto-generated per layer unless suppressed. Type inferred from `colorScale`:

- `quantile` / `quantize` / `custom` → binned with range labels
- `ordinal` → categorical
- `custom` + `logarithmic` → binned with exponential labels

**When to suppress** (`config.legend.isHidden: true`):
- Reference backdrop layer (light gray admin polygons under points).
- Two layers encode the same measure (suppress the duplicate).
- An external widget already shows the distribution.

**Never suppress** the primary choropleth legend — the map is illegible without it.

**Legend entry order — bake into the configuration.** For CLI-authored maps, the legend's visible order is dictated by config, not the UI:

| `colorScale` | Source of truth |
|---|---|
| `custom` (categorical `colorMap`) | The order of entries IS the legend order — author intentionally |
| `custom` (numeric breaks) | Ascending key order — emit sorted |
| `ordinal` | Set `visualChannels.colorDomain: [...]` explicitly. If absent, Builder derives from data (non-deterministic for CLI maps) |
| `quantize` / `quantile` | Always low→high; not author-controllable except via class count |

### 6.2 Popup (hover + click)

> **Popups are load-bearing whenever the unit of insight is the individual feature, not the aggregate pattern.** A choropleth without popups answers *"where is it concentrated?"* and stops. Add popups and the same map answers *"what is this store's revenue?"*. Default to emitting popups whenever the dataset has feature-identifying columns (name, id, address, owner, timestamp). Skip on pure pattern maps (heatmap, density) or public presentation-only maps.

`popupStyle`: `light`, `lightWithHiFirst`, `dark`, `darkWithHiFirst`, `panel`, `none`.

**Rules:**
- **Hover popup:** capped at 5 columns by the CLI. Prefer 2–4.
- **Click popup:** no hard cap. Scope by relevance — don't dump 30 columns.
- **Style:** `light` on positron/voyager, `dark` on dark-matter. `WithHiFirst` promotes the hovered field to the top.
- **`panel`** docks the popup to a side panel — choose for dense detail or mobile-portrait.
- **`none`** — pure presentation maps only.

### 6.3 Labels (textLabel)

All tile layer types support `config.textLabel` — an array of label configs (field, color, outlineColor, size, anchor, alignment, offset).

Labels render at every zoom the layer is visible. There is no per-label zoom gate — **control label density upstream** by choosing a sparse field (major cities, HQ locations), not a dense one (every store).

**Use for:** named features the viewer won't recognise from position; polygons where the name is meaningful (counties, neighbourhoods) and density is OK; small hand-curated reference layers.

**Don't use for:** dense point datasets, cell layers (no natural anchor), rasters.

**Legibility defaults:**
- `outlineColor`: inverse of basemap background (white on dark, near-black on light).
- `size`: 12–14 max; 16+ shouts.
- `offset`: `[0, -8]` for points (above), `[0, 0]` for polygons (centroid).

---

## 7. Anti-patterns — do not emit these

### 7.1 Rainbow ramps on sequential data
`Prism`, `Vivid` lack luminance ordering — the eye can't tell which value is higher. Keep them for categorical only.

### 7.2 Sequential palette on signed data
A measure that crosses zero (change, delta, over/under target) on a sequential palette loses the sign. Always diverging for signed (§4.3 for centring).

### 7.3 3D extrusion where it doesn't belong
Supported only on polygon tilesets, h3, quadbin. Points and rasters have no extrudable surface. Extrusion reads as *magnitude* — honest for counts/totals/population; misleading for rates/percentages/shares/densities. Extrude counts by default; if extruding a rate, label the legend unambiguously.

### 7.4 Too many classes
Past ~7 classes on a sequential ramp the eye can't pair ramp position with legend bin. Cap at 7; default 5.

### 7.5 Red/green as the only encoding
~8% of men have deuteranopia / protanopia — red and green collapse to the same yellow-brown. **Fix:** blue-red diverging (`Temps`, `Tropic`) or `TealRose`. If the design requires red/green, pair with shape/icon as redundant encoding.

### 7.6 Quantile on bimodal distributions
Quantile assumes unimodal. Bimodal data gets chopped into classes that match neither mode. Pull a histogram before committing; if bimodal, switch to `custom` with breakpoints at the modes, or `quantize` to keep modes separated.

### 7.7 Opacity as a data channel
Opacity entangles with overlap — two faint points look like one solid. Reserve `opacity` as a global dimmer (0.6–0.9), not per-feature encoding.

### 7.8 Sequential / diverging on an unordered string column
Most string columns have no inherent order — brand names, product types, country codes. A sequential ramp on those implies *more in one direction* the data doesn't carry; a diverging ramp implies a midpoint that doesn't exist. **Default to qualitative (distinct hues) for string columns.** Exception: when the strings ARE ordered (sentiment low/med/high, grades A–F, severity levels) sequential is correct — lock the order via `visualChannels.colorDomain`. The principle is about matching the family to the data's actual shape, not the column's type.

### 7.9 Encoding the same column twice
Color + height driven by the same column is redundant. One column per channel.

### 7.10 Palette reflex across sessions
If the previous session ended on a given palette, **don't reach for it again**. The fit that worked once is rarely the fit for a different narrative. Re-derive each map from the family principle (§4) — the answer may legitimately be the same palette, but it should be a fresh fit, not a reach. Common reflex traps: defaulting to thermal-warm palettes on non-thermal data, or to a single sequential ramp regardless of basemap tone.

**Escape hatch:** if the user explicitly asks for a consistent palette across a series (dashboards, before/after), fixed palette is correct.

### 7.11 Multi-layer mono-culture within one map
Each layer must be visually distinguishable from every other at a glance. **Palette-family-per-layer, not shades-of-one.** Three rings at alpha 0.2 / 0.35 / 0.5 in the same colour read as overlap shading, not discrete layers. Pick independent families per layer (one warm, one cool, one neutral).

**Disambiguate nested-with-shared-encoding from independent overlays.** Drive-time isochrones at 5/10/15 min are *one logical layer* (one ramp) — single sequential, lightest outside, correct. Three independent catchments are *three layers* — distinct families.

**Sanity check before emit:** if two layers share `visConfig.colorRange.colors[]` (data-driven) or `config.color` (solid-fill), refit.

### 7.12 Point overplotting at low zoom
Always-visible point `tileset` with no `visibilityByZoom` and no aggregated companion → silent failure (validates, creates, only fails on open). Author the fix up front per §1.9.

### 7.13 Contrasting stroke on dense choropleths
Dense small-polygon choropleths (sub-national admin, postcodes, parcels, h3 / quadbin cells) with default contrasting stroke make boundaries more prominent than the data. **Fix:** derive `strokeColorField` from the same column as the fill, darker variant of fill palette, same break points. Recipe in §1.3. Contrasting stroke is correct only on *large few* polygons (countries on a world map).

---

## 8. Worked recipes

Three archetypal recipes. Every field name is real. Widget composition is out of scope.

### 8.1 Store revenue change YoY by postcode (signed diverging)

- Data: polygon tileset, numeric `revenue_change_pct` (signed, centred ≈0).
- Layer: `tileset` (polygon — source-fixed).
- Classification: `custom` with colorMap pinning 0 at palette centre.
- Channel: `colorField: "revenue_change_pct"`.
- Classes: 7 (nuance both sides of zero).
- Palette: diverging from the colorblind-safe subset (e.g. `TealRose` or `Temps`) — re-fit each time per §4.
- Basemap: `positron`.
- Legend: on, percentage format.
- Popup: hover `postcode` + `revenue_change_pct`; click full breakdown.

### 8.2 Bike-share trip density (point aggregation)

- Data: point source, ~2M rows, no pre-aggregation.
- Layer: **agent choice** (§1.0) — aggregate to `h3` (density question, quantitative reading wanted).
- Aggregation: `colorAggregation: "count"`.
- Resolution: h3 res 8 (city scale).
- Classification: `custom` + log10 if counts span 4+ orders, else `quantile`.
- Channel: `colorField` on cell count.
- Classes: 5.
- Palette: sequential cool from §4.1, fit to basemap tone.
- Basemap: `positron`.
- Legend: on — cells carry real numbers.
- Popup: hover cell total; click top start-stations in the cell.

*When to pick `heatmapTile` instead:* only if the deliverable is explicitly a wide-zoom narrative glow and no one reads the legend.

### 8.3 Brand-coloured stores (hex column)

- Data: point tileset, each row has `brand_name` (string) + `brand_hex` (hex string).
- Layer: `tileset` (point, source-fixed).
- Mode: **hexColor** — data carries its own colors (§4.7).
- Channel: `colorField: { name: "brand_name", colorColumn: "brand_hex" }`, `colorScale: "ordinal"`.
- Palette: `{ hexColor: true, name: "Custom", category: "Custom", type: "custom", colors: [] }` — runtime fills from the column.
- Basemap: `positron`.
- Legend: on — one row per brand, coloured by hex.
- Popup: hover `brand_name`; click adds store-specific fields.

*Why this over a `Bold` palette:* brand colours are contractual, not aesthetic.

---

## 9. Checklist before handing off

Walk this list before emit. If any answer is *"no"* or *"unsure"*, fix it or note it to the user.

- [ ] Layer type respects the source — only point sources are agent-choice (§1, §1.0).
- [ ] For point sources, aggregation defaults to `h3` over `heatmapTile` / `clusterTile` when quantitative reading matters (§1.0).
- [ ] Primary channel is color unless there's a specific reason otherwise (§2.1).
- [ ] Attribution matches the geometry — point fields on points, line on lines, polygon on polygons (§1.1–§1.3).
- [ ] Scale type matches data shape AND meaning: `quantize` + `colorDomain` for bounded with semantic landmarks; `custom` + log10 for heavy-tailed; `quantile` only for skewed-unbounded where viewers want rank; cast-to-STRING + `ordinal` for categorical-looking integers; `custom` colorMap for stakeholder-agreed breaks (§3.2). **`quantile` is NOT the safe default.**
- [ ] **Palette family matches measure character.** Sequential for magnitude, diverging for signed, qualitative for categorical (§4). For unordered string columns, default to qualitative — only use sequential when the strings carry an inherent order (§7.8).
- [ ] Palette is a fresh fit per map — not a reflex from the prior session (§7.10).
- [ ] Palette is colorblind-safe if audience is public or unknown (§4.1).
- [ ] Palette is named exactly as the runtime knows it, or built via the borrow pattern (§4.6).
- [ ] Basemap pairs with palette luminance (§4.4, §5).
- [ ] Class count is 3–7, default 5 (§3.4).
- [ ] 3D extrusion only on supported layers (polygon, h3, quadbin); default to counts/totals; if extruding a rate, label the legend unambiguously so the height isn't read as quantity (§7.3).
- [ ] **Zoom strategy** for point and multi-granularity layers — `visibilityByZoom: { min: ≥7, max: 24 }` or a low-zoom aggregation companion. Multi-granularity polygon data: per-level cascade. Don't ship an always-visible point tileset over a national/global dataset (§1.9, §7.12).
- [ ] No rainbow palette on a sequential measure (§7.1).
- [ ] Hover popup 2–4 columns (cap 5); click popup scoped by relevance (§6.2).
- [ ] Label field is sparse enough that labels don't collide — no per-label zoom gate (§6.3).
- [ ] One column per channel (§7.9).
- [ ] Multi-layer maps use distinct palette families, not shades of one (§7.11).
