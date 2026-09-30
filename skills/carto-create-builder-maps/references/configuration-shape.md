# Map configuration shape — JSON skeleton + dataset reference

The annotated tree below shows every top-level field the map API accepts, plus per-dataset structure and `mapSettings` rules. For the authoritative field-level reference, run `carto maps schema [section]` (sections: `bundle`, `dataset`, `privacy`, `agent`, `mapstate`, `mapstyle`, `mapsettings`, `layer`, etc. — CLI-only). This config is identical whether you send it via `create_map` / `update_map` (MCP) or `carto maps create` / `update` (CLI); "the CLI" coercion and Tier-1 rules noted below run on both paths (the MCP map tools wrap the same pipeline).

## Top-level structure

```jsonc
{
  // Server-assigned; omit on create, present on update.
  "id": "uuid-from-maps-get",

  // Basic metadata. All optional. POST /maps only accepts title/description/keplerMapConfig;
  // tags/collaborative/agent land via the follow-up PATCH the CLI does for you.
  "title": "My map",
  "description": "Markdown, viewer-facing. See `SKILL.md` *Always-on rules → Do silently, don't ask → Description* for the authoring rule.",
  "collaborative": false,           // update-only. true → org users with Editor role can open in /builder (else /viewer). Orthogonal to privacy: privacy controls who sees the map, collaborative controls who of those can edit.
  "tags": ["demo", "poc"],          // update-only

  // Data sources. One per dataset the map references.
  // Identity: server id on existing datasets; omit id + use "$ref":"<name>" on new
  // datasets the kepler config will reference via "dataId":"$ref:<name>".
  "datasets": [
    {
      "$ref": "collisions",
      "type": "table",               // enum: table | tileset | query | raster
      "source": "carto-demo-data.demo_tables.nyc_collisions",
      "connectionId": "uuid-from-connections-list",
      "geoColumn": "geom",           // or "h3:h3" / "quadbin:quadbin" (pre-indexed) or "h3:geom" / "quadbin:geom" (dynamic binning)
      "columns": ["geom"],           // columns to fetch for rendering
      "format": "tilejson",          // `tilejson` for table/query/tileset, `raster` for raster. Optional — derived from `type` when omitted.
      "label": "NYC Collisions"
    }
  ],

  // Kepler.gl viz config. When present on an UPDATE this field is REPLACED
  // wholesale, not merged — send the full desired state every time.
  "keplerMapConfig": {
    "version": "v1",
    "config": {
      "mapState":     { /* viewport */ },
      "basemapConfig":{ /* basemap (canonical) — see references/basemap.md */ },
      "mapStyle":     { /* basemap (legacy mirror) — must match basemapConfig.styleId */ },
      "visState":     { "layers": [ /* … */ ], "filters": [] },
      "widgets":    [ /* formula, histogram, … */ ],
      "sqlParameters": [ /* parameterized queries */ ],
      "mapSettings": { /* feature settings */ },
      // spatialFilter (optional): clips the rendered extent to a GeoJSON Feature
      // (usually a Polygon). Builder writes this when the viewer draws a lasso or
      // imports a boundary; programmatic authoring is rare. Round-trip-safe — preserve
      // as-is when reading + writing back. Omit on new maps unless clipping is the
      // central interaction. NOTE: `visState.filters[]` is a separate, legacy
      // post-fetch row-filter mechanism — for live filtering use SQL parameters
      // (`references/sql-parameters.md`); they re-run the query rather than filtering
      // already-fetched rows.
      "spatialFilter": null,
      // Split-map mode (optional). See *"Split-map mode"* section below —
      // `visState.splitMaps` is the whole of it: two entries turn the split on.
      // Layer groups (optional). Collapsible folders for the layer panel — a flat,
      // ordered array of {type:"layer",layerId} / {type:"group",…,children} entries.
      // Sibling of visState (NOT inside it); layers join a group via the group's
      // `children`, not a field on the layer. Omit for a flat list. See references/layers.md.
      "layerGrouping": []
    }
  },

  // Optional AI agent config. Full tree — omit the whole field to disable.
  "agent": {
    "enabledForViewer": false,
    "config": { /* see references/agent-config.md for the full tree */ }
  },

  // Privacy — CLI-level; maps to POST /maps/:id/privacy behind the scenes.
  // Two accepted forms; send ONE, not both.
  // Preferred — explicit per-grantee policies:
  "privacy": {
    "policies": [                    // {type:"organization"} | {type:"public"}
      { "type": "user", "id": "<user-id>" },    // {type:"user"|"group"} need an id
      { "type": "group", "id": "<group-id>" }
    ],
    "publicPassword": null           // set a string to password-protect a public map
  }
  // Legacy form, still accepted:
  // "privacy": {
  //   "privacy": "private",         // private | shared | public
  //   "sharingScope": "organization" // organization | specific (with userIds / groupIds)
  // }
}
```

Fields that are **server-computed and auto-stripped** by `maps get --json` so the output can be piped straight back into `create` / `update`: `accountId, ownerId, createdAt, thumbnailUrl, token, views, policies, publishedWithPassword, agent.token, agent.issues`, etc.

---

### Split-map mode

Builder's **split-map** view shows the same map in two side-by-side viewports with different per-side layer visibility — useful for before/after comparisons (year vs year, scenario vs scenario) where filtering rebinds the data and you want both states visible simultaneously.

State lives in **one place** under `keplerMapConfig.config` — `visState.splitMaps`:

```jsonc
{
  "visState": {
    "layers": [
      { "id": "L_2020", /* ... */ },
      { "id": "L_2024", /* ... */ }
    ],
    "splitMaps": [
      { "layers": { "L_2020": true,  "L_2024": false } },   // [0] = left  — shows 2020 only
      { "layers": { "L_2020": false, "L_2024": true  } }    // [1] = right — shows 2024 only
    ]
  }
}
```

**Authoring rules:**

1. **`splitMaps.length === 2` ⇒ split active.** Length 0 / 1 / absent ⇒ single-pane. Every reader derives the split from the length alone — there is no companion flag to keep in sync. `mapState.isSplit` rides along in most stored maps, but nothing reads it and a Builder save drops it; don't author it.
2. **At most two panes.** A third and beyond are dropped silently, so a longer array is rejected on the way in. `[0]` = left/top, `[1]` = right/bottom.
3. **Each entry is `{ "layers": { "<layerId>": <value> } }`.** The `layers` map is required — a nullish one throws on load.
4. **Write booleans, and list every layer on both sides.** Neither is enforced: kepler backfills a layer omitted from a side, ignores a key that matches no layer, and reads the values by truthiness. Doing it properly keeps the file readable and states the intent; it is not what stands between you and a broken render.

**Round-trip behaviour.** `carto maps get <id> --json` preserves `splitMaps` faithfully, and `carto maps create` / `update` accept it.

**When NOT to author split-map mode:**
- Single-layer maps (split with one layer is a UI no-op).
- Cases where toggling layers in the legend already does what you want (split is for *side-by-side simultaneous* viewing, not alternating).
- Pre-built tileset maps where left/right layers reference *different* tilesets — Builder's split sub-tree assumes both sides share the same source dataset; mixing sources tends to render only one side.

---


## Datasets — table / query / tileset / raster

Datasets live at `/maps/:id/datasets` — a sub-resource per map. The configuration's `datasets[]` is your declarative view of them.

### Choosing the source shape for H3 / quadbin maps — decision rubric

For aggregated layers (`h3` / `quadbin` / `heatmapTile` / `clusterTile`) there are two valid source shapes. Pick the right one before authoring — they have different gotchas, and it's easy to land on the wrong one.

| Source shape | Use when | Caveat |
|---|---|---|
| **Raw `table` / `query` + spatial-index `geoColumn` + `aggregationExp`** (dynamic binning — the tile server bins on the fly) | The source rows fit in a normal warehouse table and you control the SQL. The default for most CLI-authored maps. | `aggregationExp` MUST produce columns whose names match what `visualChannels.colorField` references via Builder's `<col>_<agg>` aliasing convention (see [`layers.md`](layers.md) *"h3 / quadbin source decision rubric"* and *"`aggregationExp` — let the CLI compose it"*). |
| **Pre-built `tileset`** (binned upstream by CARTO / a tileset-generation pipeline) | Billions of rows where dynamic binning would time out, OR a CARTO-curated tileset (Spatial Features, etc.). | `colorField.name` must match the **post-aggregation column inside the tile**, not the raw source-table column. The bridging convention from dynamic binning does NOT apply here — the rename has already happened upstream. **Always inspect the tilejson first** to learn the actual column names. |

**Default recommendation:** dynamic binning (raw table + `h3:` / `quadbin:` `geoColumn`) unless the table is genuinely too big to bin per-request.

> **Inspect tilejson before authoring against any pre-built tileset (raster, h3, quadbin).** The column catalogue isn't in `INFORMATION_SCHEMA` — it's only in tilejson metadata. Run `explore_data describe` / `carto connections describe <conn> <table>` to confirm the dataset is a tileset, then read the tilejson to see what columns exist (and at what aliases). Authoring blind to it produces silent blank renders. Same advice [`layers.md`](layers.md) gives for raster / h3 / quadbin pre-built tilesets — applies equally everywhere a tilejson is the source of truth.

### `type: "table"` — a full warehouse table

Works against any warehouse CARTO connects to — BigQuery, Snowflake, Redshift, Databricks, Postgres, Oracle. The `connectionId` picks the provider; `source` is just the fully-qualified identifier in that provider's syntax (`project.dataset.table` on BigQuery, `database.schema.table` on Snowflake / Redshift / Databricks / Postgres / Oracle).

```jsonc
{
  "$ref": "sources",
  "type": "table",
  "source": "carto-demo-data.demo_tables.nyc_collisions",   // FQN, no backticks
  "connectionId": "<uuid>",                                  // explore_data list_connections / carto connections list
  "geoColumn": "geom",
  "columns": ["geom"],
  "format": "tilejson",
  "label": "NYC Collisions"
}
```

**When to use:** the table exists in the warehouse and is sized reasonably (< a few GB).
**Gotchas:** the column list bounds what the map *can ever show*. If you want tooltips with other columns, include them here too.

### `type: "query"` — a SQL query as the source

```jsonc
{
  "$ref": "top-brands",
  "type": "query",
  "source": "SELECT brand, geom, sales FROM `project.ds.sales_points` WHERE year = 2025",
  "connectionId": "<uuid>",
  "geoColumn": "geom",
  "columns": ["brand", "geom", "sales"],
  "format": "tilejson",
  "label": "Top brands 2025"
}
```

**When to use:** filtering, joining, computing columns, or piping a warehouse view. The most common shape in real maps.
**Gotchas:** the query is re-run on every pan/zoom with a bbox injected. Avoid expensive joins; pre-aggregate where possible.

### `format` values

A *response* can still carry six values — `json | table | geojson | binary | tilejson | raster` — from maps created before the move to dynamic tiling. **Only two of them are authorable**, and each `type` has exactly one:

| dataset.type | `format` | Notes |
|---|---|---|
| `table` | `tilejson` | Dynamic tiling — Builder writes this for every new table dataset. |
| `query` | `tilejson` | Same — tiles are generated from the SQL result. |
| `tileset` | `tilejson` | Pre-built CARTO tileset. |
| `raster` | `raster` | Always. Mismatches (e.g. `raster` + `tilejson`) are tolerated by the API but produce undefined tile-server behaviour. |

Because the mapping is one-to-one, **`format` is optional on the way in: omit it and it's derived from `type`**. Writing it explicitly is fine and the examples do; what you must not do is write a value that disagrees with the table.

**Rule for agents authoring new datasets: `tilejson` or `raster`. Nothing else.** Builder's own frontend enum doesn't even include `table` or `binary`, and it writes only `TILEJSON` / `RASTER` for new datasets. `json` is the backend's document-mode path (loaded via the SQL API for legacy maps) and was migrated out when Builder moved to dynamic tiling. `geojson`, `binary`, and `table` are similarly vestigial.

**Editing legacy maps**: the four legacy formats are **rejected on create and update** — you cannot pass one back through, and rewriting it to `tilejson` yourself doesn't fix the map either. A stored legacy format is not fixable from a bundle: the map's owner has to open it once in Builder's *editor*, which migrates the dataset and saves it (viewer and public mode migrate nothing). When you hit one, report that to the user rather than editing the value.

The legacy *layer* types (`point`, `geojson`, `line`, `s2`, `hexagonId`, `grid`, `hexagon`, `heatmap`, `cluster`, `trip`) are rejected the same way, and for the same reason — opening the map in Builder's editor migrates the layer and its dataset together.

### `type: "tileset"` — a pre-built CARTO tileset

```jsonc
{
  "$ref": "buildings",
  "type": "tileset",
  "source": "cartobq.public_tilesets.osm_buildings_v2",
  "connectionId": "<uuid>",
  "geoColumn": null,                                   // tilesets self-describe geometry
  "columns": null,
  "format": "tilejson",
  "label": "Global buildings"
}
```

**When to use:** billions-of-rows datasets (AIS, OSM). Pre-tiled, very fast.

### Spatial indexes (H3, quadbin)

The warehouse column holds an index integer, and `geoColumn` uses a prefix:

```jsonc
// H3 aggregation with per-cell metrics
{
  "$ref": "infra",
  "type": "query",
  "source": "SELECT h3, sum(gens) as gens_sum, max(temp) as temp_max FROM infra GROUP BY h3",
  "connectionId": "<uuid>",
  "geoColumn": "h3:h3",                  // prefix ":colname" marks the spatial index type
  "format": "tilejson",
  "aggregationExp": "sum(gens_sum) as gens_sum,max(temp_max) as temp_max",
  "aggregationResLevel": 4,              // resolution when zooming out
  "label": "Power infra (H3)"
}

// Quadbin raster aggregation
{
  "$ref": "elev",
  "type": "table",
  "source": "raster.dataset.elevation",
  "connectionId": "<uuid>",
  "geoColumn": "quadbin:quadbin",
  "format": "tilejson",
  "aggregationExp": "avg(band_1_int16) as band_1_int16_average",
  "aggregationResLevel": 9,
  "label": "Elevation"
}
```

**Reading the geoColumn prefix:**
- `geom` / `point_geom` / any plain name → regular geometry column
- `h3:<colname>` → H3 cell index in `<colname>`. Canonical pre-indexed form is `h3:h3`; for dynamic binning from a raw geometry column, pass the raw column name (typically `h3:geom`).
- `quadbin:<colname>` → quadbin index in `<colname>`. Canonical pre-indexed form is `quadbin:quadbin`; for dynamic binning, pass the raw column name (typically `quadbin:geom`).

**`aggregationExp`** is required on any dataset an `h3` / `quadbin` / `heatmapTile` / `clusterTile` layer reads, and must be consistent with the layer type below. Two forms count as an answer: an expression, or an explicit `null` to render the raw cell values. **Omitting the key is the failure** — the client then substitutes an aggregation expression nobody asked for. The exemption is the dataset *type*, not whether the column is pre-indexed: only `dataset.type === "tileset"` is excused (the tileset metadata carries the binning). A `table` or `query` dataset still needs `aggregationExp` even when its `geoColumn` points at an already-indexed `h3:h3` / `quadbin:quadbin` column.

**`aggregationResLevel`** is optional — plenty of Builder-authored spatial-index maps carry none and render fine, because the client falls back to its own level. That fallback is not the level Builder starts from, so set it whenever the resolution matters.

> **Dynamic H3 / quadbin binning requires POINT geometries.** The tile server's dynamic-binning path internally calls `H3_FROMGEOGPOINT` / `QUADBIN_FROMGEOGPOINT`, which reject any non-POINT input (polygons, lines). When the source is polygons, Builder rejects the tilejson with a misleading `"Aggregation resolution level can't be greater than the resolution of the spatial indexes in the table"` error that blames the wrong thing — an LLM reading it obediently tries lowering `aggregationResLevel` and the error stays. The real fix is either **(a)** wrap the source SQL with `ST_CENTROID(<col>)` — `SELECT ST_CENTROID(geom) AS geom FROM ...` — or **(b)** pre-compute the spatial index upstream: `SELECT H3_FROMGEOGPOINT(ST_CENTROID(geom), <res>) AS h3, COUNT(*) ... GROUP BY h3` + `geoColumn: "h3:h3"`. Tier-1 catches this when the configuration declares a non-POINT `dataset.geomType`; when the hint is absent, the `verifyRender` step translates the misleading tile-server error into a message that names the POINT constraint and the workarounds.

### Ref syntax — how `dataId` / `dataSource` point at a dataset

These two are the references that decide what renders: `layer.config.dataId` and `widget.dataSource`. Two forms, nothing else:

- `"$ref:<name>"` — declare the name once on the dataset (`"$ref": "<name>"`) and reference it from layers and widgets. **This is the only form that works on create**: the server assigns the real dataset ids, and the `$ref:` reference is what gets substituted for them before the config is sent. A layer whose `dataId` is a bare name the server never assigned ends up pointing at no dataset at all — Kepler drops the layer and the map opens missing it, with no error anywhere.
- A real dataset UUID — only when you're editing a map that already exists and you read the id off it (typically via `maps get --json`).

A dataset's `$ref` and its `id` are mutually exclusive: `$ref` says "create this one", `id` says "update that one". There is **no `@name` or `#name` shorthand**. Tier-1 validation rejects unresolved refs, bare-name `dataId`s on create, and dangling ids loudly — if you see `UNRESOLVED_REF` or `Dangling data reference`, the typo is your cue.

**SQL parameters are not in this list.** A `sqlParameters[]` entry holds no reference to a dataset that you author: the binding is the `{{placeholder}}` in `dataset.source`, matched by `sqlName` (see [`sql-parameters.md`](sql-parameters.md)). You will still see a `dataSources[]` array on parameters read back from an existing map — it is a cache of "which datasets use this parameter" that Builder rebuilds from the live datasets on every read, matching on the query template rather than on the stored ids. Preserve it on a round-trip if it is there, don't write it on a new map, and don't read it as the thing that wires the parameter up: a stale entry decides nothing.

---


## Source capabilities — columns, cache, mapSettings

Every dataset sits at the intersection of three things: the **warehouse** (via `connectionId`), the **data** (via `source` + optional SQL parameter binding), and the **rendering pipeline** (via `format`, `geoColumn`, `aggregationExp`, etc). This section maps every useful field on a dataset, grouped by what it controls.

### What's on a dataset

Full per-field reference: `carto maps schema dataset`. Key ones:

- `connectionId`, `source` and `type` are required on every NEW dataset (one carrying `$ref` rather than a server-assigned `id`). `format` is optional — derived from `type`.
- `geoColumn` uses the `h3:<col>` / `quadbin:<col>` prefix pattern to mark spatial indexes.
- `aggregationExp` is required for h3/quadbin datasets **when the dataset is `table` or `query`** (dynamic binning) — see the rule above for the `null` form. `aggregationResLevel` is optional, but set it when the resolution matters. For pre-indexed tilesets (`dataset.type: "tileset"`), the binning is baked into the tileset metadata — don't set these fields, and the tile server ignores anything you pass.
- `queryTemplate` + `queryParameters` turn on the SQL-parameters flow (see [`sql-parameters.md`](sql-parameters.md)).
- `uniqueIdProperty` enables cross-tile feature highlighting.

### Dataset type × layer type matrix

| Dataset `type` | Compatible layer types |
|---|---|
| `table` | `tileset` (any geom), plus `h3` / `quadbin` / `heatmapTile` / `clusterTile` when `geoColumn` carries the matching prefix |
| `query` | same as `table` |
| `tileset` | `tileset` only (it's pre-tiled by the provider) |
| `raster` | `raster`, or `quadbin` when the source is binned into quadbin cells |

What actually gates the aggregating layer types is the `geoColumn` prefix, not the dataset `type`: `h3` needs an `h3:` column, and `quadbin` / `heatmapTile` / `clusterTile` all need a `quadbin:` one (the last two use quadbin under the hood). `format` follows `type`, per the table above — it is `tilejson` everywhere except `raster`.

### `columns` — what to ask the warehouse for

The `columns` array controls which fields the backend fetches per tile. Include only what you'll use — popups, visualChannels, widgets, filters. Fewer columns = smaller payload = faster tiles.

Three traps to avoid:
1. **Widgets referencing columns not in `columns`** render blank. Include the column on the dataset even if no layer uses it.
2. **SQL parameters that reference columns** must still be in `columns`.
3. **The geometry column** must be included (and also named in `geoColumn`).

For `tileset`-type datasets, `columns: null` means "let the tileset's own schema dictate". Once the active normalisation bug is fixed this is the safe default; **until then, prefer an explicit `columns: [...]` even on tilesets** — list every column referenced by `visualChannels` (colorField, heightField, sizeField, etc.), `popupSettings.layers[*].fields[]`, widgets, and the geometry column. Small upfront cost, eliminates the silent-strip class of failures (3D enabled with nothing extruded, popups enabled with no fields).

> **`columns: []` edge case on PATCH.** Sending an empty array is not the same as `null`: Builder's dataset PATCH handler gates the update with `if (columns)`, which treats `[]` as falsy in some backend paths. To clear the column list, **omit the field**; to set a subset, send the explicit array.

### Workflow-sourced datasets

Datasets produced by the "Create map from workflow node" command carry two provenance fields: `sourceWorkflowId` and `sourceWorkflowNodeId`. Both are **server-assigned and not writable** — `sourceWorkflowId` is stripped from your payload, and `sourceWorkflowNodeId` is accepted by neither the create nor the patch route. There is no way to set or clear them from a bundle, so leave them undefined; a map cannot be disconnected from its workflow this way.

### Spatial index datasets (`h3` / `quadbin`)

When a dataset holds a spatial index column (H3 cell id or quadbin id), Builder streams aggregated cells instead of raw rows. You configure this with:

```jsonc
{
  "type": "query",
  "source": "SELECT h3_id as h3, SUM(events) as events FROM `proj.ds.agg` GROUP BY h3_id",
  "geoColumn": "h3:h3",
  "aggregationExp": "sum(events) as events_sum",
  "aggregationResLevel": 4,
  "format": "tilejson",
  "connectionId": "<id>"
}
```

**`aggregationExp` combines cells when zooming out**: the server aggregates adjacent cells into a lower-resolution cell using the expression. If your source table is already at resolution 9 but the user zooms out, the server uses `aggregationExp` to compute a single value for each parent cell.

**`aggregationResLevel`** is the *target* resolution Builder shows when fully zoomed out. Too low = coarse, too high = slow. **Stay within Builder's UI selector range** — H3: `[1, 6]`; quadbin: `[1, 9]`. Tier-1 rejects values outside the range; configurations outside it would render but the user couldn't subsequently adjust the resolution from the Builder UI (the slider is bounded). The H3 cap is *visual-design*, not a warehouse limit — the H3 system supports up to res 15, but cells smaller than ~0.1 km² stop being useful for thematic maps. Pre-indexed tilesets are exempt (the binning is baked at upload time).

Key pattern: the columns produced by `aggregationExp` (aliased with `as …_sum`, `as …_max`) are what layers reference via `visualChannels.colorField` — they don't exist in the raw table.

### Cache / refresh — the only knobs that exist

On `keplerMapConfig.config.mapSettings`:

```jsonc
"mapSettings": {
  "cacheTime": 5,            // minutes (integer). default 0. Ignored unless controlCacheTime=true.
  "controlCacheTime": true   // boolean. Enables the cacheTime behavior.
}
```

**Semantics** (mirrored from Builder's layer-type picker):
- When `controlCacheTime: true` and `cacheTime > 0`, Builder sends `Cache-Control: max-age=<cacheTime*60>` on the maps-api source-instantiation and attribute-stats requests — **not** on the tile fetches themselves. That tells the CDN/service layer "don't hand me anything older than this."
- When `controlCacheTime: false`, service defaults apply (whatever the CDN set).
- The unit is **minutes**.
- There is **no polling**, **no auto-refresh**, **no TTL on the dataset itself** — these are the only cache/refresh primitives.

Typical values: `5` for "pretty fresh" dashboards, `60` for "hourly snapshots", `1440` (1 day) for "archives".

### `uniqueIdProperty` — for linking widgets/filters/popups

If your dataset has a column that uniquely identifies each feature (e.g. `collision_id`), set `uniqueIdProperty: "collision_id"`. Builder uses this to link clicks/hovers to the right row across widgets and tooltips. Without it, Builder falls back to generating synthetic ids per tile, which breaks cross-tile feature highlighting.

### Other mapSettings worth knowing

19 feature settings on `keplerMapConfig.config.mapSettings` — 16 boolean flags plus `cacheTime` (integer minutes), `measurementUnit` (`kilometers`|`miles`), and `exportDataSettings` (per-dataset export allowlist). Cosmetic / behavioural, not data-affecting, generally safe to copy wholesale. For the authoritative list with defaults, run `carto maps schema mapsettings`.

Two more flags, neither of them in the table below. `exportMap` lets viewers export the current map view as a high-resolution PNG — propose it alongside `exportPDF` for stakeholder-facing maps. `showDateControl` is **deprecated**: Builder migrates its value to `sqlParameterControls` on load, so set `sqlParameterControls` directly on new maps and only pass `showDateControl` through on a round-trip.

**Defaults**: almost everything is `false` by default. Only `scrollWheelZoom` defaults to `true` and `measurementUnit` defaults to `'kilometers'`. Set the rest explicitly if you want them on in a public viewer (`exportPDF`, `basemapsSelector`, `showMeasureDistanceTool`, `showMyLocationButton`, etc.). `cacheTime` is in **minutes** and only kicks in when `controlCacheTime: true`.

**Authoring rule — propose the END-USER features that match the map's purpose, in plain language.** These flags are NOT authoring config. They're what the viewer (the *end user* of the map — analyst, exec, or public-link reader) gets in their toolbar and right-side panel when they open the link. The Builder UI calls them *"Map options"* and presents them as a creator's choice of what to expose. CLI-authored maps that skip this whole block ship a stripped-down public map by default — fewer tools than the equivalent Builder-authored map.

**Don't ask the user a generic *"which of these?"* checklist.** They don't know what each flag does for their viewers. Instead: explain in plain language what each feature gives the END USER, propose a sensible set based on the map's purpose (collaborative review map, analytical exploration map, executive presentation, public publish), and let the user accept or refine. One short prompt, framed in viewer-experience terms, not flag names.

| `mapSettings` flag | What you tell the user (plain language) | Propose ON when |
|---|---|---|
| `comments` | *"Lets viewers and guests leave threaded comments on the map — useful for collaborative review. Limited to viewer/guest accounts only (not all roles); pair with sharing if you want a wider audience to comment."* | Map is collaborative-looking — team review, iterative feedback, *"what do you think?"* reviews. |
| `exportPDF` | *"Adds an Export to PDF button so viewers can grab a snapshot for slides or a report."* | Map is going to a stakeholder who needs a deliverable. |
| `exportViewportData` | *"Adds an Export data button so analysts can download the rows currently visible (CSV / GeoJSON / Shapefile / Parquet)."* Refine per-dataset with `exportDataSettings.datasets[<id>]` (allowlist columns/formats; omit to allow all). | Analytical map where the audience will want to take rows out for further work. |
| `showMeasureDistanceTool` | *"Ruler tool for measuring distance / area on the map."* `measurementUnit` picks km vs miles. | Field-operations / planning maps where viewers measure on-the-fly. |
| `featureSelectionTool` | *"Lasso tool — viewers draw a polygon and the map filters to features inside it. Lets the audience drill into a region without writing SQL."* | Exploratory analytical maps where viewers will want to slice by area. |
| `addressSearchBar` | *"Search bar in the toolbar that jumps the map to a place — accepts addresses (`'1600 Pennsylvania Ave'`) AND raw coordinates (`'40.71, -74.00'` or `'40.71°N, 74.00°W'`)."* Geocoding for addresses; coordinate-parse for lat/lng inputs. | Any map where viewers might navigate to a known place rather than pan/zoom — defaults to ON for most public/operational maps. |
| `basemapsSelector` | *"Lets viewers swap the basemap (light ↔ dark ↔ satellite) from the toolbar."* | Mixed-audience maps (some viewers prefer dark, some need satellite for context). |
| `reorderLayers` | *"Lets viewers re-stack the legend layers (drag-reorder) to see what's underneath."* | **MUST be ON whenever the map carries an `agent` block** — the Agent can add datasets / layers on the user's behalf but can't control z-order, so viewers need the freedom to restack themselves. Otherwise, propose ON for any multi-layer map (≥ 2 layers); skip on single-layer maps where there's nothing to reorder. |
| `showMyLocationButton` | *"Toolbar button that uses the browser's location service to centre the map on the viewer's current location."* | Field / mobile audiences. |
| `showTitlePublicMap` | *"Renders the map title in the public-viewer toolbar."* Without it the public link opens with a blank header. | **Default ON whenever `privacy: "public"`** — anonymous viewers need to see what they're looking at. |
| `showPerformanceWarnings` | *"Toast banners that warn viewers when a dataset is slow to load or render."* | Internal / dev / debug only — strip for stakeholder-facing maps; the warnings read as bugs to non-technical audiences. |

**Defaults that don't need a prompt** — apply silently:

- `reorderLayers: true` whenever the bundle has `agent` set (locked-in requirement, not negotiable).
- `showTitlePublicMap: true` whenever the bundle's `privacy: "public"`.
- `showPerformanceWarnings: false` on every public / shared map (only internal / dev maps want them).

**Round-trip preservation.** Maps read out via `get --json` already carry the creator's choices. **Don't strip them on `update`** — preserve the existing `mapSettings` object as-is unless the user explicitly asked to change it.

