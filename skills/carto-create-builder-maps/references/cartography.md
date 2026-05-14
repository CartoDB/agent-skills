# Cartography reference — for CARTO maps authored via the `carto-create-builder-maps` skill

> **This is a reference, not a standalone skill.** Read alongside `SKILL.md` in the same directory when composing a CARTO map that needs cartographic decisions. The `carto-create-builder-maps` skill (in `SKILL.md`) is the primary authoring entry point — commands, configuration shape, field reference, validation. This file layers *what to pick* on top (palette family, scale type, basemap pairing) once the agent knows *how to encode* the configuration.

**Audience:** an LLM agent composing or editing a CARTO map configuration (via the CARTO CLI). This reference teaches *what to pick* — layer type, channel, scale, palette, basemap, legend, widget — so the resulting map reads well at a glance and holds up to scrutiny.

**Scope:** maps authored through the CLI configuration — the same object model Builder renders. Layer types: `tileset`, `h3`, `quadbin`, `heatmapTile`, `clusterTile`, `raster`. Prescriptive: each decision names a default and the conditions to deviate.

## Table of contents

- **§0** *Before you pick anything* — read the data, name the hook, set the four downstream constraints.
- **§1** *Pick the layer type* — `tileset` (point / line / polygon), `h3`, `quadbin`, `heatmapTile`, `clusterTile`, `raster`. §1.0 covers point-source aggregation, §1.8 covers stack order, §1.9 covers zoom-aware layering (point-overplotting fix + admin-boundary cascade).
- **§2** *Pick the visual channel* — primary-channel rules (§2.1), combining channels (§2.2).
- **§3** *Classify the data* — scale types (§3.1), the quantize-vs-quantile-vs-custom decision (§3.2), what the runtime doesn't offer (§3.3), class count (§3.4), escape hatches (§3.5).
- **§4** *Pick the palette* — CARTO families (§4.1), measure-character match (§4.2), basemap × narrative decision tree (§4.2a), centring diverging palettes (§4.3), dark-basemap considerations (§4.4), categorical-with-too-many-values (§4.5), numeric-with-too-many-NULLs (§4.5a), naming + borrowing (§4.6), hex-color column mode (§4.7).
- **§5** *Basemap pairing* — light/dark fill picks, contrast.
- **§6** *Legend, popup, label, description* — legend (§6.1), popup defaults (§6.2), label sparseness (§6.3), description / right-rail markdown (§6.4).
- **§7** *Anti-patterns — do not emit these* — rainbow on sequential (§7.1), sequential on signed (§7.2), 3D where it doesn't belong (§7.3), too many classes (§7.4), red/green only (§7.5), quantile on bimodal (§7.6), opacity-as-channel (§7.7), encoding the same column twice (§7.9), palette mono-culture across sessions (§7.10), multi-layer mono-culture within one map (§7.11), point overplotting at low zoom (§7.12), white / contrasting stroke on dense choropleths (§7.13).
- **§8** *Worked recipes* — population density (§8.1), revenue change YoY (§8.2), and others.
- **Authoring checklist** — final per-map gate before emit, at the bottom of the file.

---

## 0. Before you pick anything — read the data and name the hook

Cartographic choices depend on the data and on what story the map is meant to tell. Before any decision below:

**Know the data:**

| Question | Where to get it |
|---|---|
| What geometry does the dataset carry? | `carto connections describe <conn> <table>` — inspect the geometry metadata (the command surfaces the geo column, any spatial index, and the shape type) |
| What columns exist, and what types? | Same `describe` call — note numeric vs. string vs. timestamp vs. boolean |
| Is the measure a count, a rate, a share, a magnitude, a delta, a z-score, a category? | From the user's prompt + column semantics. Ask if genuinely ambiguous |
| What's the cardinality of the coloring column? | For string: how many unique values? For numeric: min/max, skew |
| Is the distribution skewed or heavy-tailed? | Stats API quantiles when available; otherwise assume log-distributed for any count-like measure (population, revenue, incidents) |

**Heuristic for skew without running stats:** anything describing *counts*, *revenue*, *population*, *incidents*, *downloads*, *visits*, *areas in m²* is almost always right-skewed. Anything describing *rates*, *percentages*, *z-scores*, *indices normalised to a population* is usually closer to normal.

**Who's reading this map.** The consumer at the other end is typically a GIS / Data Analyst on the terminal, not a developer — they read maps at a glance and judge by legibility, not by field completeness. Optimise for the glance; don't pile on options just because the schema allows them.

**Name the hook.** Every decision downstream sharpens if you can answer, in one sentence, *what the viewer should take away*. Good hooks: "Revenue per store is concentrated in the northeast." "Most counties improved, but a dozen got worse." "Wind speed spikes at sunset in this quadrant." Bad hooks: "Map of stores" — that's a dataset, not a hook. If the user's prompt doesn't give you one, infer and confirm briefly.

**The hook shapes four things below:**
1. The layer type (§1) — what renders best for the takeaway, given the source's constraints.
2. The classification (§3) — whether to emphasise extremes, the middle, or break at a policy threshold.
3. The palette family (§4) — sequential for magnitude, diverging for signed, qualitative for kinds.
4. The anti-patterns to avoid (§7) — the failure modes that obliterate the hook.

**Legibility, contrast, hierarchy, balance.** These four principles (drawn from the practitioner literature) are the internal check: a map reader's eye should land on the primary layer first, read the encoding from the legend without guesswork, and see the basemap receding into context. Every recipe below is compatible with them; if a choice violates one, the map fails even if every field is technically valid.

If the user's prompt names the measure but not the column (*"map population density by county"*), pick the column that matches semantically and confirm briefly — don't ask them to name it if one is obviously right.

---

## 1. Pick the layer type

**Most of this is not your call.** The layer type is almost entirely determined by the **source** — the dataset's type / indexing / geometry, resolved from the organization's connection metadata. The agent doesn't *decide* that an h3-indexed table renders as an `h3` layer or that a raster band store renders as a `raster` layer. Those are fixed by the data.

**Source → layer type:**

| Source is… | Layer type | Agent choice? |
|---|---|---|
| A raster (quadbin-backed band store — NDVI, elevation, land cover, imagery, etc.) | `raster` | No |
| An h3-indexed table | `h3` | No |
| A quadbin-indexed table | `quadbin` | No |
| A line tileset | `tileset` | No |
| A polygon tileset | `tileset` | No |
| **A point source** (tileset or query over a point table) | `tileset` **or** aggregate | **Yes — only point sources can be re-rendered as a different layer type (§1.0)** |

Trust the source. If `carto connections describe` reports a quadbin index, the layer is `quadbin` — don't second-guess it from column names or user phrasing. If the dataset type is raster, the layer is `raster` — the prompt saying "NDVI" is not what drives the choice, the band-store dataset type is.

**Only points get the aggregation pathway.** Lines and polygons are always `tileset`. Rasters are always `raster`. H3 / quadbin tables always render at their own layer type. Do not attempt to aggregate a line or polygon source into cells — the runtime has no such path.

### 1.0 The one real layer-type decision: what to do with point sources

A point source can be rendered as any of five layer types. Pick one:

| Choice | Reach for it when |
|---|---|
| Keep as `tileset` (individual points) | Each point is meaningful on its own. User wants to see / click / inspect individuals. Cardinality ≤ ~50k at the target zoom |
| Aggregate to `h3` | **Default for density / "where is X concentrated?" questions.** Orientation-neutral phenomena (events, activity, incidents, visits). Cells are quantitative — the legend reads as "events per cell", widgets aggregate to real numbers |
| Aggregate to `quadbin` | Same role as h3, but pick it when rectilinear binning is semantically required — satellite grid alignment, regular sampling grid, integration with a quadbin-indexed reference dataset |
| `heatmapTile` | **Not for density measurement.** Only when the intent is the blurred narrative "glow" at wide zoom and the reader is not expected to quantify anything from the legend |
| `clusterTile` | High-cardinality point datasets where individuals must stay click-revealable at maximum zoom. Clustering is the wide-zoom affordance; individual dots re-emerge on zoom-in |

**Prefer h3 (or quadbin) aggregation over heatmapTile / clusterTile for anything that needs to be read quantitatively.** Aggregated cells carry real numbers — aggregation, legend, widgets, popups all align. Heatmap and cluster compress signal and cost quantitative precision. Use them only when the narrative matters more than the number.

**H3 vs. quadbin for agent-chosen aggregation:** default to `h3`. Pick `quadbin` only when the surrounding data ecosystem is already quadbin-indexed (e.g. the map has a quadbin-indexed reference layer alongside).

**Resolution when aggregating:** match the viewport. Rough guide for h3:

| Target zoom / extent | h3 resolution |
|---|---|
| Country / continent | 3–4 |
| Region / state | 5–6 |
| City / metropolitan | 7–9 |
| Neighbourhood / street | 10–12 |

### 1.1–1.7 Per-layer capability reference

The rest of §1 is **capability reference** — "given the layer type is fixed, here's what you can style and configure on it". **Each geometry has independent attribution** — the fields you can set on a point tileset are not the same as the fields you can set on a line tileset or a polygon tileset, even though all three are `layer.type: "tileset"`.

### 1.1 `tileset` — points

**Source:** point tilejson (or point source rendered as individual points per §1.0).

**Attribution (point-specific fields):**

- `radius` (fixed point diameter, px) or `radiusField` (numeric column → size)
- `radiusRange` — `[min, max]` diameter when `radiusField` is set
- `filled` — almost always `true`; when false the point reduces to a ring
- `stroked` + `strokeColor` + `strokeColorField` + `thickness` — point outline
- `opacity` — drop below 0.7 when points overlap heavily
- `customMarkers: true` + `customMarkersUrl` / `customMarkersField` / `customMarkersRange.markerMap` — swap circles for icons (Maki or SVG)
- `rotationField` — rotate the marker by a numeric column (degrees, identity scale)

**Geometry-aware default** (CLI auto-applies, respects explicit fields): `filled: true, radius: 4`.

**Data-driven point size** goes on `radiusField`. Do not confuse with `sizeField` — on points, `sizeField` drives *stroke width*, not diameter. Rule: **radius = point diameter; size = stroke**.

**No polygon attribution applies to points** — `enable3d`, `heightField`, `wireframe`, `elevationScale`, polygon `filled` vs. `stroked` as fill/outline are all nonsensical or ignored on points.

### 1.2 `tileset` — lines

**Source:** line tilejson (roads, flows, routes, isolines, boundaries-as-lines).

**Attribution (line-specific fields):**

- `thickness` (fixed stroke width, px) or `sizeField` → `sizeRange` (numeric column → width)
- `strokeColor` or `colorField` — line color (there is no "fill" concept on a line; the color *is* the stroke)
- `opacity` — 0.7–1.0; lines need more opacity than polygons to remain legible

**Geometry-aware default:** `stroked: true, filled: false, thickness: 2`.

**No point or polygon attribution applies to lines** — `radius`/`radiusField`/`customMarkers`/`rotation` are point-only; `filled` (as a fill-vs-outline toggle), `heightField`, `enable3d`, `wireframe` are polygon-only.

**Width encodes magnitude.** When a numeric column is present, `sizeField` + `sizeRange` is the right data-to-visual mapping for lines. Color encodes category or magnitude; use both only when the map needs to carry two dimensions (e.g., `colorField` = traffic kind, `sizeField` = traffic volume).

### 1.3 `tileset` — polygons

**Source:** polygon tilejson (administrative boundaries, parcels, service areas).

**Attribution (polygon-specific fields):**

- `filled: true` + `colorField` → choropleth
- `stroked: true` + `strokeColor` + `strokeColorField` + `thickness` → visible borders (keep thin: 0.5–1 px for thematic maps)
- `enable3d: true` + `heightField` + `heightRange` + `elevationScale` → extrusion
- `wireframe: true` — wireframe 3D extrusion instead of solid (only when `enable3d: true`)
- `opacity` — 0.6–0.8 lets the basemap show through without washing out

**Geometry-aware default:** `filled: true, opacity: 0.6`.

**No point or line attribution applies to polygons** — `radius`, `customMarkers`, `rotation`, line-style `sizeField` (stroke width is `thickness`) are not polygon concepts.

**Don't extrude rates** (density, percentage, share). Extrusion reads as *count*, not *intensity*. See §8.3.

#### Stroke styling on dense choropleths — derive the stroke from the fill

When a choropleth has many small polygons in the viewport (admin boundaries below the country level, postcodes, parcels, h3 / quadbin cells), the default stroke is a contrasting colour — typically white-ish at low opacity. At wide zoom every polygon edge is drawn in a hue that is not in the data, and the boundaries become more visually prominent than the fill differences. Polygon shape needs to remain visible, but the stroke colour should not be a separate visual signal.

**Pattern — bind `strokeColorField` to the same column as `colorField`, on a darker variant of the fill palette with the same break points.** Each polygon's stroke ends up in the same data class as its fill, just darker. Edges stay defined; the stroke does not introduce a new colour.

```jsonc
"visConfig": {
  "filled": true,
  "stroked": true,
  "thickness": 0.6,
  "strokeOpacity": 0.9,
  "opacity": 0.9,
  "colorRange": {
    "name": "TealRose", "type": "diverging", "category": "CARTO",
    "colors": ["#009392","#39b185","#9ccb86","#e9e29c","#eeb479","#e88471","#cf597e"],
    "colorMap": [
      [-10, "#009392"], [-5, "#39b185"], [0, "#9ccb86"], [5, "#e9e29c"],
      [10, "#eeb479"], [20, "#e88471"], [null, "#cf597e"]
    ]
  },
  "strokeColorRange": {
    "name": "TealRose (dark)", "type": "diverging", "category": "Custom",
    "colors": ["#00524f","#1d6048","#5a7649","#90875c","#8a6745","#854a3f","#7a3349"],
    "colorMap": [
      [-10, "#00524f"], [-5, "#1d6048"], [0, "#5a7649"], [5, "#90875c"],
      [10, "#8a6745"], [20, "#854a3f"], [null, "#7a3349"]
    ]
  }
},
"visualChannels": {
  "colorField":       { "name": "<your-column>", "type": "real" },
  "colorScale":       "custom",
  "strokeColorField": { "name": "<your-column>", "type": "real" },
  "strokeColorScale": "custom"
}
```

**Break points must match.** The stroke's `colorMap` uses the same break thresholds as the fill. A polygon classified into the third fill bucket should get the third stroke bucket. Mismatched breaks place a polygon's outline in a different data class than its fill, which is semantically wrong.

**Deriving the darker palette.** Multiply each fill colour's RGB by ~0.65–0.75. The goal is "visibly darker, same hue", not a separately curated ramp.

| Fill | Stroke (R×0.7) |
|---|---|
| `#009392` | `#00524f` |
| `#9ccb86` | `#6d8e5e` |
| `#e9e29c` | `#a39e6d` |
| `#cf597e` | `#913e58` |

**Numeric knobs at wide zoom.** Default `thickness: 0.5` + low `strokeOpacity` is too faint to define small polygons but too non-data-coloured to disappear into the fill. Use `thickness: 0.6–0.8` and `strokeOpacity: 0.85–0.95`. Set fill `opacity: 0.85–0.9` so the fill-stroke contrast is consistent across the map.

**When to use a contrasting (non-derived) stroke instead:**

- The stroke encodes a separate measure (a second data axis on the layer — e.g., outline thickness as a confidence indicator, or `strokeColorField` driven by a different column). The stroke serves an independent role; the palettes should also be independent.
- The polygons are large and few (countries on a world map, top-level admin regions on a national map). At that zoom each polygon is a distinct entity rather than one cell in a continuous distribution, and a contrasting stroke (`#444` or `#333` at `strokeOpacity: 0.6`) is appropriate.

The same pattern applies to `h3` / `quadbin` cells (§1.4 / §1.5) at any zoom dense enough that adjacent cells touch. See §7.13 for the failure mode this prevents.

### 1.4 `h3` — hex cell aggregation

**Source:** h3-indexed table, OR a point source the agent chose to aggregate to h3 (§1.0).

**Why hex:** hexagons avoid orientation bias (all neighbours equidistant). Better than quadbin for phenomena that flow in all directions.

**Attribution:**

- `colorField` + `colorAggregation` — *which column* to aggregate and *how*. Aggregation aliases and column-type gating live in [`layers.md`](layers.md) *"h3 / quadbin aggregation restrictions"* — author long-form (`average`, not `avg`); on a numeric column use `count` / `sum` / `average` / `maximum` / `minimum` / `stdev` / `variance`, on a string/boolean/date column use `mode` / `any_value`.
- `filled`, `stroked`, `thickness`, `opacity` — as §1.3 (spatial-index cells are polygons — treat opacity the same as `tileset` polygons)
- `enable3d` + `heightField` + `heightAggregation` → volumetric hex rendering

**Opacity is your friend on spatial-index layers.** h3 / quadbin / heatmapTile / clusterTile all tile the viewport wall-to-wall — every pixel is covered by a cell at some aggregation level. At the default `opacity: 1`, the cells completely hide the basemap (road, label, water context disappear), and the map reads as a sea of colour detached from place. Drop to `0.6–0.8` for most cases; `0.5` when the basemap carries meaningful context the viewer needs to orient (city grid, coastline, major roads). Same range as `tileset` polygons (§1.3), same rationale — let the basemap breathe.

**Aggregation heuristic** (numeric columns): `count` when asking *"how many?"*, `sum` when totalling a quantity, `average` when measuring intensity per event, `maximum` for *"worst case in cell"*. For string columns the only useful aggregations are `mode` (most-common value in cell) and `any_value` (an arbitrary representative).

### 1.5 `quadbin` — square cell aggregation

**Source:** quadbin-indexed table, OR a point source the agent chose to aggregate to quadbin (§1.0).

**Everything in §1.4 applies** — quadbin and h3 share the same `SpatialIndexLayer` family in the runtime. Same attribution, same aggregations, same restrictions, same opacity guidance (`0.6–0.8`; `0.5` when the basemap matters for orientation).

### 1.6 `heatmapTile` and `clusterTile`

**Source:** point source (agent-chosen aggregation, §1.0). Pick them over h3/quadbin only when the narrative reasons in §1.0 outweigh the loss of quantitative precision.

**`heatmapTile`** — continuous density surface. Quadbin-backed under the hood. Reads as a blurred heat surface.

- **Per-record contribution to the surface** — set via `weightField` (identity scale; no aggregation transform) + `weightAggregation` on visConfig.
- **Gradient across the surface** — set via `colorRange`.
- **Legend** — almost always misread on a heatmap; suppress it (§6.1).

**`clusterTile`** — adaptive point clustering.

- `radius`, `radiusRange`, `clusterRadius` on visConfig
- Cluster size and color can encode separate dimensions (e.g., size = count, color = average)

**Between the two:** pick `clusterTile` when individuals must become clickable at high zoom; `heatmapTile` only when the map is a wide-zoom narrative view and no one will zoom in for detail.

**Opacity on both:** same range as h3 / quadbin (`0.6–0.8`) for the same reason — the surface covers the basemap. Heatmap especially benefits from `0.6–0.7` so the underlying roads / labels still carry geographic context; a fully-opaque glow reads as data-floating-in-void.

### 1.7 `raster`

**Source:** quadbin-backed raster band store. Not an agent choice.

**Three modes — pick by band semantics:**

| `rasterStyleType` | When | Extra config |
|---|---|---|
| `Rgb` | True-colour or false-colour composite (Sentinel RGB, NDVI as R/G/B bands) | `colorBands`: three entries, one per red/green/blue channel; each is `{ band, type, value }` — `type: "band"` for a named band, `type: "expression"` for a SQL expression over bands (e.g., `(B04-B03)/(B04+B03)` for NDVI) |
| `ColorRange` | Continuous palette on one band (elevation, temperature) | `colorField` + `colorRange` (sequential palette) |
| `UniqueValues` | Categorical raster (land cover classes, masks) | `colorField` + `uniqueValuesColorRange` + `uniqueValuesColorScale: "ordinal"` + `uniqueValuesColorDomain` |

**Default to `ColorRange`** for any single-band continuous measure. Only reach for `Rgb` when the data is natively multi-band and the composite is the point.

---

**Legacy types.** Do not emit `point`, `geojson`, `line`, `hexagonId`, `grid`, `hexagon`, `heatmap`, `cluster`, `trip`. The CLI rejects them on create. If you see one in a configuration read back via `get --json`, migrate to a tile-based equivalent.

---

### 1.8 Layer order in the configuration — index 0 renders on top

When a map carries more than one layer, **the first entry in `keplerMapConfig.config.visState.layers` renders on top**. Builder's legend uses the same convention: the layer at the top of the legend list is the one drawn on top of the map. This matches what the user sees and clicks in the UI.

> **Heads-up: opposite of standard deck.gl.** In raw deck.gl, the LAST layer in the array is drawn on top. Builder reverses this internally when handing layers to its render pipeline, so from the configuration author's point of view, **index 0 = top, last index = bottom**. If you've worked with deck.gl directly, remember this is flipped.

The cartographic rule: **bigger features go to the bottom, smaller features go on top**, so points are not eclipsed by polygons and lines are not eclipsed by aggregations. The order from top (array index 0) to bottom (last index) should be:

| Array position | Layer shape |
|---|---|
| **Index 0** (top of legend, rendered on top) | `tileset` points |
| Index 1 | `tileset` lines |
| Index 2 | `tileset` polygons (`filled: true`) |
| Index 3 | `h3`, `quadbin`, `heatmapTile`, `clusterTile` (cell aggregations) |
| **Last index** (bottom of legend, rendered at the bottom) | `raster` (basemap-like imagery) |

So the canonical multi-layer composition reads **point → line → polygon** in the array (not the other way around). For a hex aggregation with point overlays, the points go first (`tileset` point at index 0, `h3` at index 1). For a raster with vector overlays, the vectors go first, raster last.

**`layerOrder` overrides the array order.** If the configuration includes `keplerMapConfig.config.visState.layerOrder` (an array of indices into `layers`), that array dictates the render order — `layerOrder[0]` is rendered on top, regardless of where that layer sits in the `layers` array. When `layerOrder` is missing, Builder uses array-index order (which matches the rule above). The CLI auto-emits `layerOrder` on create when it's absent and there are multiple layers, so the configuration is self-documenting.

**Why this matters for agents.** A viewer who sees nothing where the data clearly has rows blames the data, not the layer order — and the configuration survives `get | update` fine, so there's no Tier-1 error to catch the mistake. The only signal is the rendered map looking wrong, and by then the user has already opened it. Put points at index 0, polygons last; don't rely on the viewer to figure it out.

**Edge case.** If a `tileset` polygon layer has `filled: false` (outline-only), it can sit above fill layers without occluding them. The general rule still applies when any layer has fill — larger filled areas go lower in the stack (higher array index).

### 1.9 Zoom-aware layering — show the right layer at the right zoom

`§1.8` is about which layer is on top of which at a single zoom level. **`§1.9` is about which layer should be visible at all, depending on zoom level.** This is a cartographic decision the agent makes up front; Builder enforces it at render time via `layer.config.visibilityByZoom: { min, max }` (capability reference: [`layers.md`](layers.md) *"`visibilityByZoom`"*; range limits `[0, 24]` on CARTO basemaps / `[0, 22]` on Google Maps).

**The point-overplotting trap at low zoom.** A point `tileset` with the default radius range (`radiusRange: [0, 50]` px or similar) at zoom levels 3–8 (country / continent view) collapses every point into the same on-screen pixel cluster. Three boroughs of New York at zoom 5 read as one giant blob; pan to a small country and the entire dataset is a single dot. Viewers see "lots of stuff" and learn nothing — the radius scales with the data value, not with zoom, so far-out views drown in overlap. **This is the single most common low-zoom-unreadable failure mode for point maps.**

**Two cartographic fixes — pick by data shape:**

#### Fix A: Hide the layer below the zoom where it reads

Set `layer.config.visibilityByZoom: { min: <zoom-where-it-becomes-readable>, max: 24 }` so the point layer simply doesn't render at far-out views. The viewer sees the basemap (and any aggregated overlay you've stacked below it; see Fix B) until they zoom in far enough that the points stop overlapping.

```jsonc
{
  "id": "stores",
  "type": "tileset",
  "config": {
    "dataId": "$ref:stores",
    "label": "Individual stores",
    "visibilityByZoom": { "min": 11, "max": 24 }   // hidden below city-level zoom
  }
}
```

Use this when the dataset only makes sense as individual features (find-this-store use case, click-to-popup). Below the threshold, the layer is hidden — the *absence* is correct, not a UX bug.

#### Fix B: Multi-layer zoom cascade — aggregated at low zoom, granular at high

Stack two (or three) layers over the same data, each with a `visibilityByZoom` window that hands off as the viewer zooms in. The viewer sees a coherent map at every zoom level, but *which* representation they see depends on what reads at that zoom:

| Zoom band | Visible layer | Why |
|---|---|---|
| 0 – 7 | `h3` aggregation at coarse resolution (e.g. h3 res 4) | Continent view; cells are visible, points would be invisible |
| 7 – 11 | `quadbin` aggregation, OR finer h3 (res 6–7), OR a polygon choropleth at admin level | Region / state view; cell density still legible |
| 11 – 24 | `tileset` points (the original individual features) | City / neighbourhood view; points read as distinct, popups become useful |

Each layer carries its own `visibilityByZoom: { min, max }` matching its band. The bands can overlap by ±1 zoom for a smooth handoff. The same dataset (`$ref` to one source table) can drive multiple layers — the source SQL or aggregation differs, but the data is consistent.

#### Administrative-boundary cascade — the other common pattern

Same shape, different geometry:

| Zoom band | Visible layer | Why |
|---|---|---|
| 0 – 4 | Country boundaries (polygon tileset, low-detail) | World view; only countries read |
| 4 – 7 | State / province boundaries | Regional view; states fit the eye |
| 7 – 10 | County / postcode polygons | Sub-regional; counties / ZIPs read |
| 10 – 24 | Tract / block / parcel polygons (high-detail) | Neighbourhood; the most granular shapes are readable |

Each level uses its own dataset (a separate boundary tileset per granularity) and its own `visibilityByZoom` band. Showing all four at all zooms produces the same overplotting failure on the polygon side — overlapping outlines so dense the underlying basemap disappears.

#### When to apply which

| Situation | Fix |
|---|---|
| Dataset is points, narrative is feature-level (*"find your nearest store"*) | **Fix A** — hide below the readable zoom; tell viewers to zoom in. |
| Dataset is points, narrative is pattern-level at any zoom (*"density of incidents"*) | **Fix B** — pre-aggregate to h3/quadbin once, render aggregation low + points high. |
| Multi-granularity polygon data (admin boundaries, postcodes, parcels) | **Fix B (admin cascade)** — separate layer per granularity, zoom-band per layer. |
| Public-share / dashboard map with a fixed zoom | Neither — set the viewport's `mapState.zoom` to where the map reads, and don't rely on the viewer changing it. |

**Defaults to author up front** (so low-zoom overplotting never lands):

- Point `tileset` over a national / global dataset → `visibilityByZoom: { min: 7, max: 24 }` at minimum, OR pair with a low-zoom h3 layer that takes over below 7.
- `clusterTile` is the runtime alternative to a manual cascade — it adapts cluster size to zoom in one layer, no `visibilityByZoom` needed. Pick it when the user wants the numbered-bubble UX; pick the manual h3+points cascade when they want quantitative cell colour at low zoom.
- Admin-boundary maps spanning >2 levels of administrative geography → always emit a per-level cascade. One global tileset rendered at every zoom is the wrong default.

**Anti-pattern (see also §7.12):** authoring a single point `tileset` layer with no `visibilityByZoom` AND no aggregated companion layer, then expecting the viewer to zoom in until it reads. Most viewers don't — they open the map at the default zoom, see overlap, and conclude the map is broken.

---

## 2. Pick the visual channel

Every layer has a set of channels that map dataset columns onto visual aesthetics. **One measure per channel. Max two channels per layer.** Three loaded channels is busy; four is unreadable.

| Channel | Drives | Valid on | Use for |
|---|---|---|---|
| `colorField` | Fill color | All tile layers | The *primary* measure |
| `strokeColorField` | Stroke color | Tileset (lines/polygons), h3, quadbin | Secondary measure that shares the polygon — rare |
| `sizeField` | Stroke width | Tileset (points/lines), h3, quadbin | Edge thickness data-driven — rare |
| `radiusField` | Point diameter | Tileset (points only) | Magnitude on points |
| `heightField` | 3D extrusion height | Tileset (polygons only — not points or lines), h3, quadbin | Magnitude when extrusion is justified |
| `weightField` | Heat density weight | heatmapTile | Each record's contribution to the density surface |
| `customMarkersField` | Icon selection | Tileset (points only) | Categorical variable → distinct icons |
| `rotationField` | Point rotation (degrees) | Tileset (points only) | Direction (wind, heading, flow bearing) |

### 2.1 Primary-channel rules

**Color is almost always the right primary channel.** Humans read color faster than size or height. Use color for the measure the user most wants to see.

**Use radius/size when color won't reach:**
- Every feature has the same fill color (e.g., all points are one category) but magnitudes differ → radius.
- Map has many layers; coloring another adds clutter → radius for the new one.
- The user asked for *"bigger dots where X is higher"* — they want radius.

**Use height (3D) only when:**
- The measure is genuinely a *volume* or *stacked quantity* (building floors, tonnage, revenue in $, population count).
- The map is being viewed on a tilted camera at close-to-medium zoom.
- The user explicitly asks for 3D.

**Never use height for:** rates, percentages, shares, densities, indices, z-scores. See §8.3.

### 2.2 Combining channels

The only combinations worth the complexity:

| Primary | Secondary | Reads as |
|---|---|---|
| Color | Radius (different column) | Bivariate "what + how much" on points |
| Color | Height (different column) | Volumetric choropleth — only with one of the two being a count |
| Color (category) | Radius (magnitude) | Classic "kind + size" — best-in-class for business locations |
| Icon (category) | Color (category) | Categorical combined read — rare, needs careful palette |

**Anti-combinations:**
- Color *and* stroke color driven by different columns — the user cannot separate them visually.
- Color (continuous) + height (same column) — redundant; pick one.
- Radius + size + color on points — three channels, four minutes to decode.

---

## 3. Classify the data

*"Classification"* = how a continuous numeric column is broken into color bins. This is the single highest-leverage decision in choropleth / cell cartography.

### 3.1 Scale types

The `colorScale` values to emit — matching what Builder's UI actually offers:

| Scale | Name | Character |
|---|---|---|
| `quantize` | Equal interval | Classes span equal *value* ranges. Magnitude distance is preserved, legend breaks are round numbers, and two maps of similar data are visually comparable. **Strong default for most numeric data.** |
| `quantile` | Quantile | Each class holds equal count of records. Magnitude distance is *not* preserved — it's a rank map. Use when the question is "which cells are in the top-N?" rather than "how much bigger is this than that?" |
| `custom` + `uiCustomScaleType: "logarithmic"` | Logarithmic (log10 bins) | Heavy-tailed data spanning orders of magnitude (population, revenue spanning 4+ decades). |
| `custom` (with hand-authored `colorMap`) | Custom thresholds | Domain-specific breakpoints (exam grades, policy thresholds, client-agreed cutoffs, pre-computed Jenks / σ-bucketed). |
| `ordinal` | Categorical | String fields — discrete categories. Also the scale used with the hexColor palette mode (§4.7): colours come from a column rather than a classification. |

If you see `log`, `sqrt`, `linear`, or `identity` on a *color* channel in a configuration read back via `get --json`, treat it as legacy — Builder's UI doesn't produce those values. Keep the configuration working on edit; don't author them fresh on color. **Those scales are valid for size / height / radius channels** (where the picker actually offers `linear` | `sqrt` | `log` | `quantize` | `custom`); they're a continuous-magnitude mapping that suits visual size, not colour bins.

> **Gotcha: `ordinal` only honours string columns.** Builder's scale picker treats integer / real column types as continuous regardless of `colorScale`. If your `colorField.type` is `integer` or `real` and you write `colorScale: "ordinal"`, Builder silently renders `quantize` and the legend shows numeric bins (`0.00–0.89`, `0.89–1.78`, …) instead of the categorical labels you intended. The configuration is preserved with `"ordinal"` on read+write — it just isn't applied at render time. The same rule holds for `strokeColorScale` and `sizeScale` (the user-editable scales in Builder's Stroke group). Tier-1 catches the mismatch with an actionable error message on those three channels. **Fix one of:** (1) `CAST(<column> AS STRING)` in the dataset source SQL and update `colorField.type` to `"string"`; or (2) switch to `colorScale: "quantize"` with explicit break points in `colorRange.colorMap` for each class.

### 3.2 Pick `colorScale` by distribution shape AND data meaning, not reflex

> **`quantile` is NOT the safe default.** Reflexively picking `quantile` on every numeric column is the single most common scale-choice failure mode for agent-authored maps. Quantile makes sense for a narrow case (skewed unbounded distributions where the question is rank, not magnitude); for everything else, one of the three alternatives below produces a more honest map. **Pick by distribution shape AND what you want the viewer to take away.**

The four-bucket rubric — match the data to the scale, not the other way:

| Data shape | What viewers should read | `colorScale` | Notes |
|---|---|---|---|
| **Bounded with semantic landmarks** (0–100 scores, 0–1 ratios, percentages, age bands, ENERGY STAR ratings, grade percentiles, %-of-target) | Magnitude on a fixed-meaning scale — *"a 65 means the same thing in every viewport"* | **`quantize`** + explicit `visualChannels.colorDomain` set to the scale's natural extent (e.g. `[0, 100]`) | Anchored bins; legend reads round numbers (`0–14, 14–29, …`); two maps comparable. Without `colorDomain`, breaks shift as the user pans — same building scoring 65 colours differently in different viewports. |
| **Skewed long-tail unbounded** (population, revenue, area, sales, foot-traffic) where viewers care about *rank* not magnitude | Rank — *"these cells are in the top 20%"* | `quantile` | Equal-population bins keep colour classes visible. Don't pick this for bounded scores — the bin breaks become arbitrary numbers (e.g. `4.2–18.7, 18.7–43.1, …`) instead of meaningful landmarks. |
| **Heavy-tailed across 4+ orders of magnitude** (point density per cell, network throughput, financial outliers) | Magnitude on log scale | `custom` + `uiCustomScaleType: "logarithmic"` + log10-spaced `colorMap` | Linear breaks compress the tail into one colour band; quantile flattens the bulk. Log10 keeps both ends readable. |
| **Categorical-looking integers** (severity 1/2/3, class 1–10, tier id, status code) | Discrete categories | `CAST(<col> AS STRING)` upstream + `ordinal` | The integers aren't a magnitude scale — they're labels that happen to be numeric. `ordinal` on a string column renders categorical legend; `quantize` on the integer renders "1.00–1.50, 1.50–2.00…" which reads as nonsense. |

#### Worked example — ENERGY STAR scores (0–100)

A building-energy map coloured by `energy_star_score` (0–100, 100 = best). With `colorScale: "quantile"`, the legend reads `12–34, 34–47, 47–58, 58–71, 71–86` — bin breaks are wherever the *current viewport's* records happen to fall, so a building scoring 65 changes colour as the user pans into a different city. With **`colorScale: "quantize"` + `colorDomain: [0, 100]`**, the legend reads `0–14, 14–29, 29–43, 43–57, 57–71, 71–86, 86–100` — anchored to the scale's actual semantic extent. A 65 reads consistently as "57–71" everywhere; the map is comparable across viewports and across other 0–100-scaled maps. Same data, different read, because the scale matches the data's meaning.

#### Default ladder when in doubt

1. **Bounded / has a semantic extent** → `quantize` + `colorDomain` (start here for any 0–100, 0–1, 0–N% measure).
2. **Heavy-tailed across orders of magnitude** → `custom` + log10 `colorMap`.
3. **Skewed unbounded, viewers want rank** → `quantile` (the genuine use case).
4. **Categorical labels disguised as integers** → cast to string + `ordinal`.
5. **Stakeholder-agreed breakpoints** (Jenks, σ-tiers, policy thresholds) → `custom` with explicit `colorMap`.
6. **String / native categorical** → `ordinal`.
7. **Colour comes from a hex column** → `ordinal` + hexColor palette mode (§4.7).

#### Why agents over-use `quantile` (and how to break the reflex)

Quantile *always renders something*: every bin gets the same number of records, so the map is never blank, even when the column is wrong / sparse / mis-typed. That makes it the lowest-friction wrong answer. The fix is upstream — pick the scale that matches what the data MEANS, not what looks visually populated. **A quantile-on-bounded-score map LOOKS fine and IS wrong** — the breakpoints are random, comparability is broken, and viewers reading the legend take away the wrong thresholds.

In Builder practice, **`quantize` often produces better-looking maps than `quantile` on CARTO-indexed cell datasets** (h3, quadbin, pre-aggregated tilesets), because cell counts are frequently log-normal and quantile flattens the mid-range. For those, prefer the logarithmic option (`custom` + `uiCustomScaleType: "logarithmic"`) before falling back to quantile.

### 3.3 What the runtime does NOT offer

Two classical methods are not first-class scales in Builder; when the analysis needs them, pre-compute upstream and emit as `custom` with a `colorMap`:

- **Jenks natural breaks** — optimises class boundaries to minimise within-class variance; suited to data that's unevenly distributed but not directionally skewed. Quantile / quantize will do the job for most use cases.
- **Standard-deviation classification** — classes at ±1σ, ±2σ, etc. Compute the σ-tier column upstream as an integer and classify as `ordinal`, or bake the thresholds into a `custom` `colorMap`.

### 3.4 Number of classes

Default to **5**. Drop to 3 for overview / executive-summary maps where simplicity beats nuance; go up to 7 for detailed analysis where the viewer will spend time on the map. Past ~7 classes a sequential ramp becomes a gradient the eye cannot parse into discrete buckets — top and bottom read, middle blurs.

### 3.5 Escape hatches

- **Data has a meaningful zero** (change, delta, z-score) → diverging palette (§4.2), optionally centred via `custom` colorMap (§4.3).
- **Data is categorical but ordered** (sentiment low/med/high, grades A–F) → `ordinal` on the string field, with a sequential palette so the order reads.
- **One extreme value dominates** — consider clipping the top 1–5% and annotating, or switch to logarithmic. Don't let a single outlier flatten the entire ramp.

---

## 4. Pick the palette

Palette choice follows the measure's character — *kind*, *amount*, or *signed deviation* — not the agent's aesthetic preference. The three-family split below (qualitative / sequential / diverging) is not arbitrary; it reflects that perceptual distinction, and mixing the families misrepresents the data. The CARTO palette set shares its intellectual roots with ColorBrewer — both trace back to Cynthia Brewer's work on perceptually-ordered thematic-map palettes.

**Emit exactly as named.** Every palette below is what the runtime's registry knows; set `colorRange.name` to the verbatim string and `colorRange.category: "CARTO"`. If the name drifts, the legend breaks silently.

### 4.1 CARTO palette families

**Qualitative (categories — unordered):** `Antique`, `Bold`, `Pastel`, `Prism`, `Safe`, `Vivid`

**Sequential (magnitude — ordered low→high):** `Burg`, `BurgYl`, `RedOr`, `OrYel`, `Peach`, `PinkYl`, `Mint`, `BluGrn`, `DarkMint`, `Emrld`, `BluYl`, `Teal`, `TealGrn`, `Purp`, `PurpOr`, `Sunset`, `Magenta`, `SunsetDark`, `BrwnYl`, `Gray`

**Diverging (signed — low ← zero → high):** `ArmyRose`, `Fall`, `Geyser`, `Temps`, `TealRose`, `Tropic`, `Earth`

**Colorblind-safe subset** (recommended when the map will be public or the audience is unknown — safe under deuteranopia, protanopia, tritanopia):
- Qualitative: `Safe`, `Vivid`
- Sequential: `Teal`, `Purp`, `Mint`, `Emrld`, `BluYl`, `DarkMint`
- Diverging: `Temps`, `Geyser`, `Tropic`

### 4.2 Match palette to data character

**Sequential — use when the measure has a clear low→high:**

| Measure family | Default palette | Why |
|---|---|---|
| Population, count, revenue, volume | `Teal` | Calm, reads as magnitude, not alarm |
| Density, intensity, concentration | `Emrld` or `DarkMint` | Dark endpoints carry weight |
| Age, duration, tenure | `Purp` | Neutral non-thermal, avoids false urgency |
| Risk, incidents, rate of undesirable outcome | `BurgYl` or `RedOr` | Warm ramp implies severity |
| Temperature, heat, energy | `Sunset` or `SunsetDark` | Reads as thermal |
| Luminance-only print / simple contexts | `Gray` | No hue bias |

**Diverging — use when zero (or a meaningful midpoint) matters:**

| Measure family | Default palette |
|---|---|
| Year-on-year change, delta, growth | `TealRose` or `Tropic` |
| Z-score, standardised deviation | `Geyser` or `Temps` |
| Political / opinion, two-sided | `Earth` or `ArmyRose` |
| Performance vs. target (over/under) | `Temps` |

**Qualitative — use for unordered categories:**

| Category count | Default palette |
|---|---|
| 2–6 unique values | `Bold` or `Safe` |
| 7–12 unique values | `Pastel` or `Prism` |
| \>12 unique values | Collapse to top-N + "Other". See §4.5 |

### 4.2a Palette decision tree — basemap × narrative

The §4.2 tables tell you "sequential vs. diverging vs. qualitative". This sub-tree goes one step further: once you've picked a family, the basemap tone AND the domain narrative together point at a *specific* palette. Agents defaulting to `SunsetDark` on every map is the failure mode this section exists to prevent.

```
sequential + basemap dark
├── density / mobility / activity           → Mint, BluYl, Emrld (cool, lit endpoints)
├── heat / energy / severity                → Magenta, PinkYl, SunsetDark (warm, emissive)
├── healthcare / environment / vegetation   → Teal, DarkMint (calm green, safe)
└── risk / incidents / "bad thing"          → BurgYl, RedOr (warm, alarming)

sequential + basemap light
├── population / count / volume             → Teal (neutral, reads as magnitude)
├── density / concentration                 → Emrld, DarkMint (dark endpoints weight)
├── age / duration / tenure                 → Purp (neutral non-thermal)
├── risk / incidents                        → BurgYl, RedOr (warm → severity)
└── temperature / heat / energy             → Sunset, SunsetDark

diverging + basemap light
├── year-on-year change / growth            → TealRose, Tropic
├── z-score / normalised deviation          → Geyser, Temps
├── political / two-sided opinion           → Earth, ArmyRose
└── performance vs. target                  → Temps

diverging + basemap dark
├── any of the above                        → Tropic, Temps, Geyser work on both tones

qualitative + basemap light
├── 2–6 categories                          → Bold, Safe (colorblind-safe)
└── 7–12 categories                         → Pastel, Prism

qualitative + basemap dark
├── 2–6 categories                          → Vivid, Bold (higher saturation cuts through)
└── 7–12 categories                         → Prism (pastels vanish on dark)
```

For **bivariate** maps (two measures, one 3×3 palette), the palette family is domain-specific:
- **economic × socioeconomic** (growth vs. risk, revenue vs. cost) → `BiPurpleOrange`, `Stevens Purple-Orange`
- **demographic × density** (age vs. income, population vs. area) → `Stevens Pink-Blue`, `Stevens Green-Blue`
- **environmental × land-use** (rainfall vs. vegetation, NDVI vs. temp) → `Stevens Green-Red`

If the narrative doesn't match any row above, back up to §4.2 and pick by measure character alone — don't force a match.

### 4.3 Centring a diverging palette on zero — when to bother

A diverging palette's midpoint carries the meaning "this is at the baseline" (typically zero). If the distribution is roughly symmetric around zero, `quantize` on the numeric column + a diverging palette produces the right reading without extra work — the middle class sits near zero by construction.

**Explicit centring is worth it when:**

- The distribution is *asymmetric* around zero (e.g., mostly positive change with a few severe negatives) — without explicit breakpoints, one side gets washed out.
- The zero class is meaningful enough that viewers should be able to pick it out exactly ("which cells didn't change at all?"). `quantile` / `quantize` both smear zero across a class; a `custom` colorMap can put zero at a boundary.
- The map is being compared side-by-side with another map (regional / temporal) and the midpoint anchor should match.

Otherwise, `quantize` (or `quantile` if rank is the story) on a diverging palette is fine. Don't reach for `custom` as a reflex.

**If you do centre explicitly:** use `custom` scale with an explicit `colorMap` that pins zero at the palette centre.

```jsonc
"colorScale": "custom",
"colorRange": {
  "name": "TealRose",
  "category": "CARTO",
  "type": "diverging",
  "colors": ["#009392","#39b185","#9ccb86","#e9e29c","#eeb479","#e88471","#cf597e"],
  "colorMap": [
    [-0.5, "#009392"],
    [-0.25, "#39b185"],
    [-0.1, "#9ccb86"],
    [0.1, "#e9e29c"],
    [0.25, "#eeb479"],
    [0.5, "#e88471"],
    [null, "#cf597e"]
  ]
}
```

The last entry with `null` is the catch-all upper bucket — required.

### 4.4 Dark basemap considerations

**Reality check before anything else.** CARTOColors sequential palettes are designed light → dark by default (`Teal` runs from `#d1eeea` → `#2a5674`, `Sunset` from `#f3e79b` → `#5c53a5`, etc.). That ordering is correct on *light* basemaps — the pale low-value class disappears into the positron/voyager background, the dark high-value class stands out, value reads as "more = darker". On `dark-matter` the rule **inverts**: you want the bright end at the high values (so they pop), the dark end at the low values (where they merge with the basemap — which is fine because "empty" or "low" should recede). Without inverting, a default-order palette on dark-matter produces a map where high-value cells vanish into the basemap — the exact opposite of what the author wants.

**Two ways to handle dark:**

1. **Pick a palette whose default order already works on dark.** Some CARTO palettes have a dark low-value end that reads as "background" and a bright high-value end that stands out on dark:
   - Good on dark (default order): `Sunset`, `SunsetDark`, `Magenta`, `Purp`, `BurgYl`
   - OK on dark (default order, but check the low end): `Teal` if the lowest class is semantically "absent"

2. **Reverse the palette.** For the majority of CARTOColors that go light → dark, either:
   - Flip `colors[]` in the configuration so the bright color sits at the high-value end, OR
   - Keep the array as-is but treat the high-value end as "low intensity" in the legend (only correct if the semantic direction is flipped too — rare).

   The simpler pattern is to flip the array:
   ```jsonc
   "colorRange": {
     "name": "Teal",
     "category": "CARTO",
     "colors": ["#2a5674","#3b738f","#4f90a6","#68abb8","#85c4c9","#a8dbd9","#d1eeea"],
     "reversed": true
   }
   ```

**On `positron`** the opposite: pale starts are fine, dark ends give contrast. Most palettes work in their default order.

**On `voyager`** treat like positron but with slightly less headroom for pale starts (the roads/labels on voyager compete with light colors more than on positron).

**Never pair `dark-matter` with a palette that has a light low-value end UNLESS the "low" class is semantically "absent"** — pale blobs disappearing into dark is only OK if disappearing is what you want (masking no-data as background). Otherwise, invert.

### 4.5 Categorical — too many values

More than 12 categories is unreadable with any palette. **Collapse to top-N by frequency and bucket the rest as `Other`.** If the data already encodes its own per-category colors in a column, use hexColor mode (§4.7) instead — each category gets its own colour from the row itself.

> **Two stacking constraints to know about** when `colorScale: "ordinal"` or `"custom"` runs against a high-cardinality string column:
>
> - **Palette length caps the distinct-hue count → overflow renders grey.** When the column has more unique values than the palette has colours, the extra values fall into Builder's "Others" bucket which renders as grey (`#A9A9A9`-ish). A 6-colour palette over 25 unique values means 5 categories get distinct colours and 20 collapse to a single grey blob — the map looks broken even though the data is intact. CARTO's qualitative palettes scale up to 12 colours (`Bold`, `Vivid`, `Prism`, `Antique`, `Safe`, `Pastel`); pick one long enough for the unique-value count, OR specify an explicit `colorRange.colorMap` to control which values get which colour.
>
> - **Legend caps at 20 entries — but the visualisation renders all of them.** Builder's `MAX_LEGEND_ENTRIES = 20` slices the side-panel and map-overlay legends to the first 20; past that, a *"+N more"* style message appears. **The map itself colours every feature correctly** — this is purely a legend-display limit, not a rendering limit. So a 25-colour custom palette over 25 categories paints the map fine but leaves 5 entries unlabelled in the legend. When the user needs every category labelled, collapse to top-19 + `Other` so the legend stays under the cap.
>
> Three escape hatches:
> 1. **Pick a palette long enough** for the unique-value count (CARTO qualitative ≤ 12, custom up to 20 if labels matter).
> 2. **Filter the source SQL to top-N upstream** — e.g. `WITH top_n AS (SELECT col FROM t GROUP BY col ORDER BY COUNT(*) DESC LIMIT 19) SELECT t.* FROM t INNER JOIN top_n USING (col)` keeps the legend complete.
> 3. **Use hexColor mode** (§4.7) when the data carries its own per-row colour — palette-free, no bucketing, no cap interaction.

### 4.5a Numeric — sparse columns / NULL ratio

**The same dominant-grey-Others trap as §4.5, but inverted.** §4.5 is about a *categorical* column that's *too cardinal* for the palette. This one is about a *numeric* column that's *too sparse* — too many NULLs — to bind as `colorField`. Same visible failure (the map looks broken, dominated by grey), different root cause, same fix family (in the source SQL).

**Why it produces grey.** Builder's quantile / quantize binning ignores NULL rows. If 91% of the column is NULL, the 9% non-null rows get spread across N colour buckets, and every NULL row falls into Builder's residual "Others" bucket which renders grey (`#A9A9A9`-ish — same colour as the high-cardinality overflow case). A 6-bucket quantile over a 9%-populated column means 6 thin coloured bands lost in a sea of grey.

**Live failure example.** Map of 265k rooftop-PV installations coloured by `num_modules` (a column populated on only 9% of rows). Result: ~242k of 265k features rendered grey — the visible map looked empty even though the data was intact. Fix was two-part in the source SQL:

```
-- Filter out the NULL-rendered-grey rows AND switch to a populated column
WHERE area_sqm IS NOT NULL AND area_sqm > 0
-- and then bind colorField: { name: "area_sqm" } instead of "num_modules"
```

After: 15.4k installations visible — the ones with actual measurable PV infrastructure.

**The authoring rule.** Before binding any numeric column as `colorField` (or `sizeField` / `radiusField` / `heightField`), check the NULL ratio in the source SQL. If `WHERE col IS NULL` returns more than ~25% of rows, you have a problem at render time. Two fixes (pick whichever fits the narrative):

1. **Filter** — add `WHERE col IS NOT NULL` (or a domain-specific filter like `WHERE area_sqm > 0`) to the dataset's `source` SQL. The map then represents only the rows where the measurement exists; the legend reads correctly. Best when NULLs are noise (missing measurements, partial data quality).
2. **Pick a different column** with better coverage. Best when NULLs are signal (the column doesn't apply to those rows — e.g., `num_modules` is null on rooftops without solar; `area_sqm` is on virtually every row regardless).

**Check it cheaply before binding.** A one-line SQL probe via `carto sql query`:

```sql
SELECT
  COUNT(*) AS total_rows,
  COUNT(col) AS populated_rows,
  COUNT(col) / COUNT(*) AS populated_ratio
FROM your_table
```

`populated_ratio < 0.75` means the column is a poor `colorField` candidate as-is — apply one of the two fixes above before authoring.

**This is the same family as §4.5 (cardinality cap on categorical columns).** Both produce the dominant-grey-Others trap, both are fixed upstream in the source SQL rather than at the layer-config level. Whenever you author a `colorField` (numeric or categorical), the question is *"does the data shape match what the colour ramp can communicate?"* — too many distinct categorical values OR too many NULL numerics break the answer in the same way.

### 4.6 Don't invent palettes, but borrow well-studied ones

`colorRange.name` and `category` must match the runtime's registry or the legend breaks. If you want a one-off palette:

- Keep `name` pointing to a real CARTO palette (e.g., `Teal`)
- Replace `colors` with your custom array
- Optionally set `colorMap` for exact thresholds
- The runtime will render the colors you provided; the legend will still find the entry by name

Never set `category` to anything other than `CARTO`, `ColorBrewer`, `Uber`, or an account-palette category you've confirmed exists.

**When to reach for a non-CARTO palette — and which one:**

- **You need a perceptually-uniform ramp and none of the CARTO sequential palettes satisfy that** (rare — `Teal` / `Emrld` / `BluYl` are close, but not strictly perceptually-uniform). Use **Viridis** or its follow-on **Cividis** (colorblind-safe, print-safe, perceptually-uniform by construction). Paste the hex values into `colors[]`, keep `name: "Teal"` (or the nearest CARTO entry) so the legend still resolves.
- **The stakeholder already agreed on a ColorBrewer palette** (many analyst teams standardise on ColorBrewer for publication consistency). CARTO's palette family shares the same intellectual lineage — both come from Cynthia Brewer — but the names may differ. Paste the ColorBrewer hex values into `colors[]`; keep `name` on a real CARTO entry.

These two escapes cover ~99% of "the default CARTO palettes aren't quite right" cases. Do not invent palettes ad-hoc — a palette that hasn't been checked for luminance ordering, colorblind safety, and print legibility will fail one of the three.

### 4.7 Hex-color columns — palette-free coloring from the data

When the dataset carries its own hex-color column (or a custom SQL query projects one), the runtime can colour features directly from that column — no palette, no classification, no CARTO-provided ramp. This is the right tool when the data already encodes its own visual semantics: brand colors per product, team colors per sport, regulatory traffic-light indicators, UI-theme alignment, any case where the color *is* part of the dataset's meaning.

**Requirements:**

- A column containing valid CSS-style hex strings — `"#FF5733"`, `"#00A86B"`, etc. The runtime reads these verbatim; malformed or null values fall back to the unknown color (light gray).
- The column must be present either in the source table or projected by a custom SQL query (`carto maps schema dataset` — `customSql` / `querySource` patterns). No column, no hexColor mode.
- Works on the **color channels only** — `colorField` and `strokeColorField`. Not available for size, radius, height, weight, or rotation.

**Configuration shape:**

The colorField carries both a **label column** (what the legend reads) and the **color column** (what the runtime draws). The colorRange marks itself as hex-sourced with `hexColor: true`.

```jsonc
"visualChannels": {
  "colorField": {
    "name": "product_category",     // label column — legend shows these strings
    "type": "string",
    "colorColumn": "brand_hex"      // hex-value column — actual fill color
  },
  "colorScale": "ordinal"
},
"visConfig": {
  "colorRange": {
    "hexColor": true,
    "name": "Custom",
    "category": "Custom",
    "type": "custom",
    "colors": []                    // runtime fills these from the query
  }
}
```

`colorScale` stays `ordinal` — hexColor is a categorical-coloring mode. The legend pairs each unique `name` value with its corresponding `colorColumn` value (the runtime issues a `GROUP BY name, colorColumn` query to the dataset to build the legend).

**When to reach for hexColor mode:**

- Domain-required colors — brand guidelines, legal / regulatory colour conventions (hazard tiers, compliance statuses), industry-standard class colours (land-use codes with official colours, team jerseys).
- The dataset author has *already* done the cartographic work upstream and the CLI should honour it.
- Many categories (> 12) where a single palette would cycle through colors in a way that loses meaning — let each row declare its own colour.

**When NOT to reach for hexColor mode:**

- The column name suggests colours but doesn't actually contain hex strings (often a mistake — verify with a quick `connections describe` or query sample before committing).
- The user wants cartographic control — colorblind safety, luminance matching to basemap, palette rotation. hexColor gives up that control by design; it's the data's decision, not the agent's.
- Continuous numeric measures — hexColor is categorical. For a numeric column, classify and pick a palette (§3, §4).

**Integrity check:** if the source contains the hex column but the query / view the map reads does not project it, the runtime can't find it. When authoring a configuration against a `customSql` / `querySource` dataset, include the color column in the `SELECT` list.

**Legend:** hexColor mode produces a categorical legend where each row is a unique label → hex pair. Don't suppress it — the legend is how viewers read the encoding. Label-column semantics still apply: if the label column has > 12 distinct values, collapse upstream (§4.5).

**Layer-type caveat:** hexColor is reliable today on `tileset` (points, lines, polygons) where every row reaches the renderer unchanged. On `h3` / `quadbin` layers the color column must be carried through the spatial-index aggregation expression, which the CLI does not yet propagate automatically — prefer tileset or pre-compute the aggregation manually for now.

---

## 5. Basemap pairing

> **Where to set the basemap in the configuration:** write BOTH `keplerMapConfig.config.basemapConfig.styleId` AND `keplerMapConfig.config.mapStyle.styleType` to the same value. See [`references/basemap.md`](basemap.md) for the dual-write rule (Tier-1 rejects desync; the screenshot engine and viewer SSR still read `mapStyle`) and the full id catalogue — this section is the cartographic decision tree for *which* id to pick.

```
Data is primarily thematic (choropleth, cells, density)
└── Use `positron` (light) or `dark-matter` (dark) — minimal basemap, maximum data prominence

Data is primarily reference (points on top of city context)
└── Use `voyager` — keeps road, label, POI context without overwhelming

Data is a photo-real raster (satellite imagery, NDVI composite)
└── Use `positron` under it (reference grid) or no basemap at all

Data is about real-world features that need high-zoom context
(delivery routes, indoor plans, detailed ops)
└── Use Google `satellite` or `hybrid`
```

**Default, when in doubt: `positron`.** It's neutral, doesn't fight the data, and works with every palette family.

**Never pair `dark-matter` with a palette that has a light start** unless the lowest class is semantically *absent* (it'll vanish and that's the point).

**Layer-group toggles** (`basemapConfig.visibleLayerGroups`, mirror in `mapStyle.visibleLayerGroups`): for a clean thematic view, turn off `road`, `border`, `label` and keep `land`, `water`, `building`. For a reference map, keep everything on. For print, turn off `building` at low zoom and `label` when your thematic layer already carries text.

---

## 6. Legend, popup, label

### 6.1 Legend

The runtime auto-generates a legend per layer unless the layer suppresses it. The legend type is inferred from `colorScale`:

- `quantile` / `quantize` / `custom` → binned legend with range labels
- `ordinal` → categorical legend
- `custom` + `logarithmic` → binned with exponential labels

**When to suppress** the legend (`config.legend.isHidden: true`, or via `legendSettings`):
- The layer is a reference backdrop (e.g., light gray admin polygons under a point layer).
- Two layers encode the same measure (one for overview, one for detail) — suppress the second to avoid duplicate legends.
- The map is paired with an external panel (widget, sidebar chart) that already shows the distribution. Widget design is out of scope for this skill — see the maps agent skill for widget composition.

**Never suppress** the primary layer's legend on a choropleth — the map is illegible without it.

**Legend entry order — bake it into the configuration, don't rely on Builder's drag-reorder.**

For CLI-authored maps, the legend's visible order is dictated by the configuration, not the UI:

| `colorScale` | Source of truth for legend order |
|---|---|
| `custom` (categorical with `colorRange.colorMap: [[key, hex], …]`) | The order of entries in `colorMap` IS the legend order. Author it in the order the viewer should read. |
| `custom` (numeric break-points) | Ascending key order of `colorMap` entries — emit them sorted. |
| `ordinal` (categorical) | Set `visualChannels.colorDomain: ["catA", "catB", …]` explicitly. If absent, Builder derives order from the data — for CLI maps that means whatever the warehouse returns first, which is non-deterministic. |
| `quantize` / `quantile` | Always low → high derived from the scale; not author-controllable except via class count. |

Builder's legend panel shows a drag-reorder handle, but for CLI-created maps it may silently fail to persist on next open (the *"sort by value"* path needs per-category tilestats CLI-created datasets don't ship). Encode the order in the configuration per the table above so the UI never has to compute it.

### 6.2 Popup (hover + click)

> **Popups are load-bearing whenever the unit of insight is the individual feature, not the aggregate pattern.** A choropleth without popups answers *"where is it more concentrated?"* and stops there. Add popups and the same map answers *"what is this specific store's revenue?"*, *"who manages this parcel?"*, *"when was this incident reported?"*. The map shifts from a presentation to an exploration tool. Default to **emitting popups whenever the dataset has feature-identifying columns** (name, id, address, owner, timestamp) — even on aggregation maps if the cells point at named places. Skip popups only on pure pattern maps (heatmap, density quadbin) where features are anonymous, or presentation-only public maps where the viewer won't hover.

Popups expose columns on hover or click. `popupStyle` options: `light`, `lightWithHiFirst`, `dark`, `darkWithHiFirst`, `panel`, `none`.

**Rules:**
- **Hover popup:** capped at 5 columns by the CLI. Within that cap, prefer fewer — 2–4 columns keep the popup compact enough not to obscure the map under the cursor.
- **Click popup:** no hard cap. Scope by relevance: the primary measure, its unit, the identifier, and whatever the user asked about. If the dataset has 30 columns and all of them are genuinely useful, include them — the click popup is a detail view, not a glance view.
- **Style:** `light` on positron/voyager, `dark` on dark-matter. `WithHiFirst` variants promote the hovered field to the top — useful when one column is the "hero".
- **`panel`** style docks the popup to a side panel — choose for dense detail or when the map is mobile-portrait and the popup would cover the map.
- **`none`** — use only for pure presentation maps where the user won't interact.

**Do not put every column into the click popup.** Users read the first 3–5; the rest is scroll noise.

### 6.3 Labels (textLabel)

All tile layer types support `config.textLabel` — an array of label configurations. Each needs a field (string column), color (RGB), outlineColor (RGB), size, anchor, alignment, offset.

Labels render with their parent layer across all zoom levels where the layer is visible. There is no per-label zoom gate — if a layer renders labels, every labelled feature in the viewport gets a label. The implication: **control label density upstream** by choosing a label field that's only populated for features worth naming (major cities, HQ locations, flagship sites), not a dense column (every store, every point).

**Use labels for:**
- Named features the viewer won't recognise from position alone (facilities, small localities).
- Polygons where the name at a glance is meaningful (counties, neighbourhoods) and the dataset isn't so dense that labels collide.
- Reference / annotation layers ("HQ", "Flagship store") — usually a small, hand-curated dataset.

**Don't use labels for:**
- Dense point datasets — every point gets a label, every label overlaps.
- Cell layers (h3, quadbin) — no natural anchor, cells aren't named.
- Raster — the raster has no text semantics.

**Label legibility — non-negotiable defaults:**
- `outlineColor`: the inverse of the basemap background (white on dark, near-black on light). Outlines are what keep labels legible at any zoom.
- `size`: 12–14 at most; 16+ becomes shouting.
- `offset`: `[0, -8]` for points (label above), `[0, 0]` for polygons (centroid).

### 6.4 Description (right-rail markdown)

The map's `description` field is **optional**. When empty, the right-rail info button is hidden entirely (the viewer sees nothing) — so don't emit a description just to fill the slot. When emitted, it renders as viewer-facing markdown (short headings, bullets, ` code spans ` for technical terms) in Builder's right-side info panel. Treat it as **analyst commentary**, not a spec sheet of the layers.

> **The legend, layer panel, and viewport already tell the viewer *what's on the map*. The description's job is *what to take away from it* — the takeaway, the caveats, the interaction hints. If the description would only restate layer names, palette stops, or zoom thresholds, emit no description at all — empty is better than noise.**

**Template — fill the slots in this order:**

| Slot | Content | Length |
|---|---|---|
| Lead paragraph | The takeaway — the question the map answers, or the pattern the viewer is meant to notice | 1–2 sentences |
| `## What you're seeing` *(only if non-obvious)* | One bullet per layer ONLY when composition isn't already obvious from the legend (zoom-staggered visibility, masked layers, time-dependent behaviour, reference backdrops) | ≤ 3 bullets |
| `## How to read it` *(only if interactive)* | Click / hover / zoom hints when the viewer has to *do* something to get value | ≤ 2 bullets |

The `*(only if…)*` gates are the discipline — they keep the description from filling with content the legend already shows. Don't include a "Source" section — connection / table identifiers are author-side plumbing, not analyst commentary, and viewers don't care which warehouse the data sits in.

**Length cap:** ~5 lines of body. The right rail is tall, but more than that becomes a wall the viewer skips.

**No tables.** Builder's description renderer supports markdown headings, paragraphs, lists, and embedded images — but not table syntax. For data callouts (top-N, before/after, comparisons) embed a small image, or fold the data into prose. Never bullet-pad in lieu of a table.

**Worked example — analytical map (choropleth + point overlay):**

```markdown
US retail density tracks coastal metros, not state population. Inland states cover most of the area but hold a fraction of the stores.

## How to read it
- Click any state for total store count.
- Zoom past 8 to see census-tract detail.
```

**Worked example — pure cartography reference map (lead-only is enough):**

```markdown
World admin boundaries (level 1) for use as a reference backdrop in dashboards.
```

Note what's *not* in either: layer names, palette stops, zoom thresholds, classification method, connection IDs. The legend and layer panel carry the first four; the last is author plumbing.

**Anti-pattern — the spec-sheet description (do not emit):**

```markdown
This map shows three layers:
- Retail stores coloured by storetype (point layer)
- States — population (zoom 0–5)
- Counties — population (zoom 5–8)
- Census tracts — population (zoom 8+)

All zooms: Retail stores (~12K points) coloured by store type.
```

Every line restates content already visible in the legend and layer panel. The viewer learns nothing they couldn't read off the right side of the map. The fix: lead with the takeaway (*"Retail density tracks coastal metros, not state population"*) and let the legend explain the layers.

---

## 7. Anti-patterns — do not emit these

### 7.1 Rainbow ramps

**Don't use** `Prism` or `Vivid` for a sequential measure. They lack luminance ordering — the eye cannot tell which value is higher. Keep rainbow palettes for categorical data only.

### 7.2 Sequential palette on signed data

A measure that crosses zero (change, delta, over/under target) mapped with a sequential palette loses the sign. Always use diverging for signed data. See §4.3 for centring.

### 7.3 3D extrusion where it doesn't belong

**3D extrusion (`enable3d: true` + `heightField`) is only supported on polygon tilesets, h3 layers, and quadbin layers.** Point tilesets and raster layers don't have an extrudable surface.

**When to pause before extruding:** extrusion reads as *magnitude* — "this is taller, so it's more." That reading is honest for counts, totals, population, tonnage, revenue in currency units. It's less honest for rates, percentages, densities, and shares, because those are ratios — a 10% rate isn't "bigger" than a 5% rate the way 10M residents are bigger than 5M. Extruding a ratio can mislead a fast-scanning viewer into a quantity reading the data doesn't support.

Not an absolute prohibition — extruding a rate is fine when the map is interactive (viewers will read the legend), when the legend is clearly labelled as a rate, or when the whole point is to compare relative tiers visually. The failure mode to avoid is extrusion presented *as if* it were a count when the column is actually a rate.

**Rule of thumb:** extrude *counts* by default. If extruding a rate, label the legend unambiguously (include the `%` or the unit), and consider colouring the same layer by a different column to carry the second dimension.

### 7.4 Too many classes

Past ~7 classes on a sequential ramp, viewers can no longer reliably pair a ramp position with a legend bin. Cap at 7; default to 5.

### 7.5 Red/green as the only encoding

The three common forms of color vision deficiency — deuteranopia, protanopia, tritanopia — collectively affect ~8% of men and ~0.5% of women of Northern European descent (and meaningful minorities elsewhere). Deuteranopia and protanopia both collapse red and green toward the same yellow-brown; a red/green over-vs-under map becomes uniform to those viewers.

**Fix:** use blue-red diverging palettes (`Temps`, `Tropic`) — blue and red remain distinct across all three CVD types. `TealRose` is also safe. Never rely on red/green as the *only* channel carrying the sign; if the design requires red/green, pair it with shape/icon/label as a redundant encoding.

### 7.6 Quantile on bimodal distributions

Quantile classification assumes the data is roughly unimodal. Bimodal data (two populations with a valley between) gets chopped into classes that don't correspond to either mode.

**Detection:** pull the stats histogram before committing to quantile. If bimodal, consider `custom` with breakpoints at each mode's peak, or `quantize` to keep the two modes separated cleanly.

### 7.7 Opacity as a data channel

Opacity *can* encode a measure via `opacity` on `visConfig`, but the measure becomes entangled with overlap density — two faint points look the same as one solid point. Reserve opacity as a global dimmer (0.6–0.9) for layer-stack readability, not for per-feature encoding.

### 7.9 Encoding the same column twice

Color + height driven by the same column is redundant. The user sees twice the visual weight for no extra information and loses a channel that could carry a second dimension. One column per channel.

### 7.10 Palette mono-culture across sessions

Specific to agents (and a known failure mode in practice): if your previous session ended on `SunsetDark` / `Teal` / whatever, **don't reach for it again on the next map**. The palette fit that worked once is rarely the optimal fit for a different narrative on different data. A human cartographer intuitively varies; an agent that just picks "the palette I used last time" produces maps that feel samey and miss the narrative specificity §4.2a asks you to pick by.

**The correct prompt each time is:** what's the measure character (sequential / diverging / qualitative), what's the basemap tone (light / dark), what's the narrative (healthcare → cool greens, risk → warm reds, mobility → lit cool, change → diverging). §4.2a walks that tree — follow it from the top even if the answer the last time was also `Teal`, because *the answer might still legitimately be Teal* but it should be a fresh decision, not a reach.

**Escape hatch:** if the user explicitly asks for a series of maps with a consistent palette (dashboards, multi-panel reports, before/after comparisons), fixed palette is correct — consistency is the point. The anti-pattern is unconscious repetition across unrelated maps.

### 7.11 Multi-layer mono-culture within one map

> **Stack order: see §1.8 above — `visState.layers[0]` renders on top; canonical stacking is point → line → polygon → aggregation → raster (smallest geometry first).** [`references/layers.md`](layers.md) opens with the same rule for the structural reference. This section covers visual distinguishability between layers; the z-order rule is the structural sibling.

Sibling failure mode to §7.10, but inside a single configuration: when a map has multiple layers, each layer must be **visually distinguishable from every other layer at a glance**. Distinct hues do that. Opacity steps on a single hue do *not* — three rings at alpha 0.2 / 0.35 / 0.5 in the same colour read as "darker shade where layers overlap", not as discrete layers. Same trap with stacked thematic layers (choropleth + overlay + reference) and multi-source overlays (own stores + competitor stores).

**The rule is palette-family-per-layer, not shades-of-one.** Layer 1 picks its palette from §4.2a (e.g. `RedOr` for warm intensity), layer 2 picks an *independent* family (e.g. `Teal` for cool reference), layer 3 another (`Purp`). The ramp inside each family encodes that layer's data; the family itself encodes which layer you're looking at. Picking three shades from the same `RedOr` ramp for three different layers is exactly the blob this rule warns against — that's how a single-hue sequential palette is meant to work *within* one layer.

**Disambiguate nested-with-shared-encoding from independent overlays.** Drive-time isochrones at 5 / 10 / 15 min are *one logical layer* (one encoding, one ramp) — single sequential palette, outer ring lightest, inner darkest is correct. Three independent catchment polygons from three different sources are *three layers* — distinct palette families. Ask which one you're holding before reaching for a colour.

**Point / branch / accent layers want a contrasting hue, not yet another family.** A point layer of "own stores" sitting on top of warm-toned isochrone rings should be dark charcoal or near-black, so it reads as a different *visual category* (the thing you locate) rather than another ring. §4.4 has the dark-basemap variant.

**Sanity check before `maps create` / `maps update`:** if two layers in the configuration share the same `visConfig.colorRange.colors[]` (data-driven layers) *or* the same `config.color` (solid-fill layers), refit before submitting. Same palette across layers in one map is almost always a bug.

### 7.12 Point overplotting at low zoom — point layers always-visible without a fallback

A single always-visible point `tileset` with no `visibilityByZoom` window and no aggregated companion collapses every point into the same on-screen pixel cluster at country / continent zoom — the most common low-zoom-unreadable failure for point maps, and the silent kind (configuration validates, create succeeds, the failure surfaces only when the user opens the map). Author the fix up front per §1.9 (Fix A: hide below readable zoom; Fix B: zoom cascade with an aggregated companion).

### 7.13 Contrasting stroke on dense choropleths

A polygon `tileset` (or `h3` / `quadbin`) choropleth with many small polygons in the viewport, rendered with the default contrasting stroke, makes every administrative boundary more visually prominent than the data-driven fill differences. The stroke colour is not in the data, so the boundaries pull attention away from the measure being mapped. Failure mode applies to any dense small-polygon choropleth — sub-national admin levels, postal areas, parcels, hex / quadbin grids.

**Fix:** drive `strokeColorField` from the same column as the fill, with the same `colorMap` break points, on a darker variant of the fill palette (~70% RGB). Recipe in §1.3 *"Stroke styling on dense choropleths — derive the stroke from the fill"*.

**When a contrasting stroke is correct** — large, few polygons (countries on a world map, top-level admin regions on a national map). Each polygon is a distinct entity rather than one cell in a continuous distribution. See §1.3 for the cutover.

---

## 8. Worked recipes

End-to-end decision-tree applications. Every field name is real. Widget composition is out of scope — recipes cover the map itself.

### 8.1 Population density by US county

- Data: polygon tileset, numeric column `pop_density` (right-skewed).
- Layer: `tileset` (polygon — source-fixed).
- Classification: `quantile` (skewed distribution).
- Channel: `colorField: "pop_density"`.
- Classes: 5.
- Palette: `Teal` (magnitude, calm).
- Basemap: `positron`.
- Legend: on.
- Popup: hover shows `name` + `pop_density`; click shows `name`, `pop_density`, `total_pop`, `area_sq_mi`.

### 8.2 Store revenue change YoY by postcode

- Data: polygon tileset, numeric column `revenue_change_pct` (signed, centred ≈0).
- Layer: `tileset` (polygon — source-fixed).
- Classification: `custom` with colorMap pinning 0 at palette centre.
- Channel: `colorField: "revenue_change_pct"`.
- Classes: 7 (to show nuance both sides of zero).
- Palette: `TealRose` (diverging, colorblind-safe).
- Basemap: `positron`.
- Legend: on, with percentage format.
- Popup: hover shows `postcode` + `revenue_change_pct`; click shows full breakdown.

### 8.3 Bike-share trip density in a city

- Data: point source, ~2M rows, no pre-aggregation.
- Layer: **agent choice** (§1.0) — aggregate to `h3` (density question, quantitative reading wanted).
- Aggregation: `colorAggregation: "count"` over the point set.
- Resolution: h3 res 8 (city scale).
- Classification: `quantile` (right-skewed counts across cells).
- Channel: `colorField` on the cell count.
- Classes: 5.
- Palette: `Emrld` (sequential, dark-end-up).
- Basemap: `positron`.
- Legend: on — cells are quantitative, legend carries real numbers.
- Popup: hover shows cell total; click shows top start-stations in the cell.

*When to pick `heatmapTile` instead:* only if the deliverable is explicitly a wide-zoom narrative glow and no one reads the legend. For analysis / product use, h3 wins.

### 8.4 Land-cover classification from a raster

- Data: quadbin-backed raster, band `land_cover` with 10 discrete class values.
- Layer: `raster` (source-fixed).
- Mode: `rasterStyleType: "UniqueValues"`.
- Channel: `colorField: "land_cover"`.
- Palette: `Bold` (6 values) or a custom palette — land cover has conventional colors (forest green, water blue, built gray). Override `colors[]` while keeping `name: "Bold"`, `category: "CARTO"`.
- Basemap: `positron`.
- Legend: on, with class labels (forest, water, urban, …).

### 8.5 H3-aggregated telemetry

- Data: already h3-indexed telemetry pings, `count_events` column.
- Layer: `h3` (source-fixed).
- Aggregation: `colorAggregation: "sum"` over `count_events`.
- Classification: `custom` + `uiCustomScaleType: "logarithmic"` (event counts span orders of magnitude).
- Channel: `colorField: "count_events"`.
- Classes: 5.
- Palette: `Emrld` (sequential, dark-end-up, works on any basemap).
- Basemap: `positron`.
- Popup: hover shows cell-level total; click shows breakdown.

### 8.6 Product catalog — brand-coloured stores

- Data: point tileset, each row has `brand_name` (string) and `brand_hex` (string, valid hex).
- Layer: `tileset` (point, source-fixed).
- Mode: **hexColor** — data carries its own colors (§4.7).
- Channel: `colorField: { name: "brand_name", colorColumn: "brand_hex" }`, `colorScale: "ordinal"`.
- Palette: `{ hexColor: true, name: "Custom", category: "Custom", type: "custom", colors: [] }` — runtime fills colors from the column.
- Basemap: `positron`.
- Legend: on — one row per unique brand, coloured with that brand's hex.
- Popup: hover shows `brand_name`; click adds store-specific fields.

*Why this over a `Bold` palette:* the brand colours are contractual, not aesthetic. A CARTO palette would violate brand guidelines.

---

## 9. Checklist before handing off

Before you emit the configuration, walk this list. If any answer is "no" or "unsure", fix it or note it to the user.

- [ ] Layer type respects the source — only point sources can be re-rendered as a different layer type (§1, §1.0).
- [ ] For point sources, aggregation defaults to `h3` over `heatmapTile` / `clusterTile` when quantitative reading matters (§1.0).
- [ ] Primary channel is color unless there's a specific reason otherwise (§2.1).
- [ ] Attribution matches the geometry — point fields on points, line fields on lines, polygon fields on polygons (§1.1–§1.3).
- [ ] Scale type matches data shape AND meaning: `quantize` + explicit `colorDomain` for bounded with semantic landmarks (0–100 scores, %, age bands), `custom` + log10 for heavy-tailed across orders of magnitude, `quantile` only for skewed-unbounded where viewers want rank not magnitude, cast-to-STRING + `ordinal` for categorical-looking integers, `custom` colorMap for stakeholder-agreed breakpoints (§3.2). **`quantile` is NOT the safe default** — reflex-picking it on bounded scales is the most common scale-choice failure.
- [ ] Palette family matches the measure character: sequential (magnitude), diverging (signed), qualitative (categorical) (§4.2).
- [ ] **`colorField` data shape can carry the encoding.** Numeric: column populated > 75% of rows (NULL ratio < 25%) — otherwise the map renders dominantly grey (§4.5a). Categorical: unique-value count fits the palette length (≤ palette colours; CARTO qualitative cap = 12) — otherwise overflow renders grey (§4.5).
- [ ] Palette is colorblind-safe if the audience is public or unknown (§4.1).
- [ ] Palette is named exactly as the runtime knows it (§4.6).
- [ ] Basemap pairs with palette luminance (§4.4, §5).
- [ ] Class count is 3–7, default 5 (§3.4).
- [ ] 3D extrusion only used where supported (polygon tilesets, h3, quadbin) and the measure is a count/total, not a misleading ratio (§7.3).
- [ ] **Zoom strategy** for point and multi-granularity layers — point `tileset` over a wide area: either `visibilityByZoom: { min: ≥7, max: 24 }` (hide at low zoom) OR pair with a low-zoom aggregation layer (h3 / quadbin) for a zoom cascade. Multi-granularity polygon data (admin boundaries, postcodes): per-level `visibilityByZoom` cascade. Don't ship a single always-visible point tileset over a national/global dataset — overplotting at low zoom makes it unreadable (§1.9, §7.12).
- [ ] No rainbow palette on a sequential measure (§7.1).
- [ ] Hover popup 2–4 columns (cap is 5); click popup has no cap, scope by relevance (§6.2).
- [ ] Label field is sparse enough that labels don't collide — Builder has no per-label zoom gate (§6.3).
- [ ] **Description is optional** — only emit when it adds value (takeaway, caveat, or interaction hint); empty is better than a layer recap. When emitted, lead with the takeaway; skip `## What you're seeing` unless composition is non-obvious; no `## Source` section; no tables (§6.4).
- [ ] One column per channel (§7.9).
