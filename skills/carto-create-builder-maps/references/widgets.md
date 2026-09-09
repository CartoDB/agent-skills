# Widgets — analytical surface

Widgets sit in `keplerMapConfig.config.widgets[]`. Each targets a `dataSource` (dataset id) and (for most kinds) a `column`. Seven widget kinds: `formula`, `category`, `pie`, `histogram`, `range`, `timeseries`, `table`. For the full discriminated field surface per kind, run `carto maps schema widgets`.

> **Nesting gotcha — widgets and sqlParameters live at `config.*`, NOT `config.visState.*`.** Both are peer fields of `visState` directly under `keplerMapConfig.config`. Agents used to Kepler's upstream shape sometimes nest them under `visState` — the CLI + server accept it silently, Builder ignores the mis-nested array, and the widget never appears. Tier-1 rejects non-empty `visState.widgets` / `visState.sqlParameters` with a "move up one level" hint.

### Picking a widget kind

| Kind | When to pick | Required fields beyond `dataSource` |
|---|---|---|
| `formula` | Single headline metric (sum / average / minimum / maximum / count / custom). | `column` (except `operation: "count"`), `operation`. For `operation: "custom"` add `operationExp` (raw SQL, e.g. `"SUM(revenue) / COUNT(*)"`). |
| `histogram` | Distribution of a numeric column. | `column`, `operation`, **`buckets` (REQUIRED — see callout)**. Optional `min`/`max` to pin the domain. |
| `category` | Bar chart by string/categorical value. | `column`, `operation`, **`operationColumn` (REQUIRED at mount — see callout)**. `orderBy`: `frequency_desc` (default) \| `frequency_asc` \| `alphabetical_asc` \| `alphabetical_desc`. |
| `pie` | Same shape as `category`, rendered as pie. | Same as `category`. |
| `range` | Min/max slider filter. | `column`, `operation`. |
| `timeseries` | Line / bar over time. | `column` (date/timestamp), `operation`, **`operationColumn` (REQUIRED at mount — see callout)**, `stepSize` (`second`…`year` — no `quarter`; use `stepSize: "month"` + `stepMultiplier: 3`), `chartType` (`line` \| `area` \| `bar`), **`showControls` (REQUIRED at mount — emit `false` by default; see callout below)**. Optional `series[]` for multi-line, `splitByCategory` for per-category series. |
| `table` | Paginated row browser / feature browser. | `dataSource` + `columns: [{ field, headerName, type, format }]`. No top-level `column` / `operation`. |

> **Histogram requires both `column` AND `buckets`.** Builder's UI silently defaults `buckets` to 30 when authored in-panel, but the runtime does NOT — its tick loop is `for (let i = 1; i < widget.buckets; i++)`. With `buckets: undefined` the widget renders an empty container. Tier-1 rejects pre-create.

> **`operationColumn` is required at mount on `category` / `pie` / `timeseries`, even when `operation: "count"`.** Builder's widgets panel throws when mounting these widgets without it; the React `ErrorBoundary` catches the throw and renders the styled "Error 500" page (which masquerades as a backend failure — see *"`Error 500` page in CARTO Builder is ambiguous"*). For `count`, set `operationColumn` to the same value as `column`; for non-`count` aggregations (`sum` / `average` / etc.), set it to the numeric column being aggregated. Tier-1 rejects empty / missing `operationColumn` pre-create.

> **`showControls` is required at mount on `timeseries`.** Builder reads the field at mount time; absent or `undefined` triggers a render error. **Emit `"showControls": false` by default**; emit `true` ONLY when the user explicitly asks for time-scrubbing animation playback. The animation playback has several non-obvious failure modes: rejected outright on aggregated datasets (h3 / quadbin / heatmapTile / clusterTile — per-row timestamps are gone once binned), disabled when the widget is in `global: true` mode, and disabled when cross-filtering is active.

> **Aggregation aliases for widget `operation`, `series[].operation`, and `spatialIndexAggregation`** — widget operations route through the Model API, which only accepts **short-form** values: `avg`, `min`, `max`, `sum`, `count`. The long-form aliases (`average` / `minimum` / `maximum`) that appear in [`layers.md`](layers.md) are for layer `aggregationExp` (Maps API) only — they are rejected by the Tier-1 validator on widgets with an explicit error. Do not use long-form on any widget field.

> **Table widgets are feature-browsers — search-and-click, NOT a filter.** What they CAN do: per-column search filters the *rows shown inside the table view*, and clicking a row zooms the map to that feature's geometry (when the dataset has resolvable geometry — set `uniqueIdProperty` on the dataset for stable cross-tile linkage). Use this for *"find this specific record"* use cases: viewer types into the column search → finds the row → clicks it → map zooms to highlight the feature.
>
> What they **CANNOT** do: **sort columns**, filter the rest of the map, or participate in cross-filtering. The search inside the table affects the table's own row display only — other layers / widgets / popups don't react to it. Don't author a `table` widget expecting it to drive cross-filtering — use a `category` / `pie` / `range` / `histogram` widget for that (those DO cross-filter via `crossFilteringDataSourceIds`).
>
> Pure tabular exploration (table-only "browse the warehouse" maps): set `global: true` so the table queries the whole dataset rather than just the viewport.

**Minimal example per kind** — these are the smallest valid shapes. For the full discriminated schema (every optional field) run `carto maps schema widgets`.

```jsonc
// formula — single headline metric (sum / average / count / minimum / maximum / custom).
// Use as the panel-top "what's the headline?" widget.
{ "id": "w-total", "type": "formula", "title": "Total revenue",
  "column": "revenue", "operation": "sum",
  "formatter": "DECIMAL_CURRENCY",
  "dataSource": "$ref:stores", "global": false }
```

```jsonc
// category — bar chart by string/categorical value.
// `column` groups; `operationColumn` is REQUIRED at mount (mirror `column` for `count`).
{ "id": "w-cat", "type": "category", "title": "Sales by region",
  "column": "region", "operation": "count", "operationColumn": "region",
  "dataSource": "$ref:stores",
  "orderBy": "frequency_desc" }
```

```jsonc
// pie — same shape as category, rendered as pie. Use sparingly (≤ 7 slices).
// `operationColumn` is REQUIRED at mount (mirror `column` for `count`).
{ "id": "w-pie", "type": "pie", "title": "Top contributing factor",
  "column": "factor", "operation": "count", "operationColumn": "factor",
  "dataSource": "$ref:incidents" }
```

```jsonc
// histogram — distribution of a numeric column.
// `buckets` is REQUIRED — without it the widget renders empty.
{ "id": "w-hist", "type": "histogram", "title": "Revenue distribution",
  "column": "revenue", "operation": "count",
  "buckets": 30,
  "formatter": "DECIMAL_SHORT_COMMA",
  "xAxisFormatter": "DECIMAL_CURRENCY",
  "dataSource": "$ref:stores" }
```

```jsonc
// range — min/max slider for filtering on a numeric column.
{ "id": "w-range", "type": "range", "title": "Revenue range",
  "column": "revenue", "operation": "count",
  "dataSource": "$ref:stores", "global": true }
```

```jsonc
// timeseries — line / area / bar over time. `stepSize` accepts second…year (NO quarter — use month + stepMultiplier: 3).
// `operationColumn` and `showControls` are REQUIRED at mount. Bottom of panel; collapsed by default.
{ "id": "w-time", "type": "timeseries", "title": "Sales over time",
  "column": "sale_date", "operation": "sum", "operationColumn": "revenue",
  "stepSize": "month", "chartType": "line",
  "dataSource": "$ref:stores", "global": false,
  "collapsible": true, "autoCollapse": true,
  "showControls": false,
  "isValid": true }
// NB: emit showControls: false by default. Set true ONLY when the user explicitly asks for animation playback —
//     it's rejected on aggregated datasets and disabled when global: true or cross-filtering is active.
```

```jsonc
// table — paginated row browser / feature browser. No top-level `column` / `operation`;
// list the columns to display + their formatting. Bottom of panel; collapsed by default.
// Set `uniqueIdProperty` on the dataset for click-to-zoom row→feature linkage.
{ "id": "w-table", "type": "table", "title": "Raw incidents",
  "dataSource": "$ref:incidents",
  "columns": [
    { "field": "incident_datetime", "headerName": "When",     "type": "date",   "format": "%Y-%m-%d" },
    { "field": "injuries",          "headerName": "Injured",  "type": "number", "format": ",.0f" },
    { "field": "factor",            "headerName": "Cause",    "type": "string" }
  ],
  "dense": true, "pageSize": 20,
  "global": false,
  "collapsible": true, "autoCollapse": true }
```

### Widget rendering surfaces — right-side panel vs. bottom-of-map

Widget kinds DON'T all render in the same place in Builder. Two distinct surfaces:

- **Right-side panel** (the standard widget rail): `formula`, `category`, `pie`, `histogram`, `range`. Stacked vertically in `widgets[]` array order — top of the array = top of the panel. These are the small, glanceable kinds that answer *"what's the headline?"* / *"how does this break down?"* / *"how is this distributed?"*. Author them in this rough order: headline metrics first (`formula`), categorical breakdowns next (`category` / `pie`), distribution / filter last (`histogram` / `range`).
- **Bottom-of-map** (a separate horizontal surface below the map view, NOT in the right panel): `table` and `timeseries`. They're space-hungry — table rows need horizontal width, time-axis charts need a long X axis — so Builder renders them across the full width below the map instead of cramping them into the right rail. Their position in `widgets[]` doesn't affect their on-screen position the way it does for panel widgets; they just appear at the bottom regardless.

### Collapsibility defaults

**Default `collapsible: true` + `autoCollapse: true` on `table` and `timeseries`.** They take more vertical space than other kinds, so collapsing them by default keeps the bottom-of-map surface scannable at first open — the viewer expands the one they need. Other kinds (formula / category / pie / histogram / range) read fine expanded; `collapsible` is optional on them.

```jsonc
// Table — bottom-of-map surface, collapsed by default
{ "id":"w-table","type":"table","title":"Raw incidents",
  "dataSource":"$ref:col", "columns":[ /* ... */ ],
  "collapsible": true, "autoCollapse": true }
```

> **`wrapperProps.expanded: false` and `autoCollapse: true` do the same thing — pick one.** Builder writes `wrapperProps.expanded: false` from its UI; CLI authoring more naturally uses `collapsible: true` + `autoCollapse: true`. Both are accepted by the CLI Tier-1 schema and survive round-trips. The examples here use `autoCollapse` for legibility; if you're round-tripping a Builder-authored bundle that carries `wrapperProps`, leave it.

### Knobs that apply across kinds

- **`global` mode** — `false` (default) queries only the layer-rendered data (filtered by viewport / bounds); `true` queries the entire dataset via the Model API (whole-dataset stats). **Forced true** when the dataset is tileset/raster without an attached layer, or a dynamic spatial-index dataset — Builder disables the toggle, but the CLI doesn't enforce: a tileset-backed widget with no layer needs `global: true` or it renders empty.
- **`spatialIndexAggregation`** — required on widget fields when the underlying dataset is h3/quadbin/heatmapTile/clusterTile. Accepts the standard aggregation set MINUS `median` and `count unique` (same restriction as layer aggregations).
- **`collapsible` / `autoCollapse` / `wrapperProps.expanded`** — collapse the widget panel entry. **Default `collapsible: true` for `table` and `timeseries`** (large footprint); optional on smaller kinds. `autoCollapse: true` opens the map with the widget collapsed; Builder writes the equivalent `wrapperProps: { expanded: false }`. Either form is accepted.
- **`note` / `noteFormat` / `noteExpanded`** — optional freeform documentation shown alongside the widget. `noteFormat: "markdown"` renders Markdown; `plainText` (default) renders literal.
- **`operationExp`** — raw SQL for `operation: "custom"` (formula / category / pie / timeseries only). NOT supported when `dataSource` is a tileset or raster.

> **Widget ↔ dataset gotcha.** A widget whose `dataSource` is a `tileset` or `raster` dataset *with no layer in the map referencing it* renders empty (Builder marks it incompatible: `TILESET_OR_RASTER_WITHOUT_LAYER`). Always include the layer in the same configuration as the widget.

### Cross-filtering — propagating a widget's filter to other datasets

By default a widget filters only its own `dataSource`. To filter other datasets that share the same column (e.g., click a severity slice and shrink both the accidents and the accident-buffers datasets), set `crossFilteringDataSourceIds: [<own-dataSource-id>, <other-id>, ...]` on the widget.

**Authoring rule:**
1. The widget's own `dataSource` id MUST be included in the array — omitting it is the most common CLI authoring bug (the widget then doesn't even filter its own source).
2. Include every other dataset id whose schema has the same column with a compatible type. Mismatched types or column-not-in-SELECT → cross-filter silently no-ops.
3. Aggregated targets (h3/quadbin) work as long as the column is in the source SELECT before binning — the WHERE pushes down pre-aggregation.

Empty array or `undefined` ⇒ single-source filter only.

---

