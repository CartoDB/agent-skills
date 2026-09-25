# Widgets — analytical surface

Widgets sit in `keplerMapConfig.config.widgets[]`. Each targets a `dataSource` (dataset id) and (for most kinds) a `column`. Seven widget kinds: `formula`, `category`, `pie`, `histogram`, `range`, `timeseries`, `table`. For the full discriminated field surface per kind, run `carto maps schema widgets`.

> **Nesting gotcha — widgets and sqlParameters live at `config.*`, NOT `config.visState.*`.** Both are peer fields of `visState` directly under `keplerMapConfig.config`. Agents used to Kepler's upstream shape sometimes nest them under `visState` — the CLI + server accept it silently, Builder ignores the mis-nested array, and the widget never appears. Tier-1 rejects non-empty `visState.widgets` / `visState.sqlParameters` with a "move up one level" hint.

### Picking a widget kind

| Kind | When to pick | Required fields beyond `dataSource` |
|---|---|---|
| `formula` | Single headline metric (sum / avg / min / max / count / custom). | `column` (except `operation: "count"`), `operation`. For `operation: "custom"` add `operationExp` (raw SQL, e.g. `"SUM(revenue) / COUNT(*)"`). |
| `histogram` | Distribution of a numeric column. | `column`, `operation`, **`buckets` (REQUIRED — see callout)**. Optional `min`/`max` to pin the domain. |
| `category` | Bar chart by string/categorical value. | `column`, `operation`, **`operationColumn` (REQUIRED at mount — see callout)**. `orderBy`: `frequency_desc` (default) \| `frequency_asc` \| `alphabetical_asc` \| `alphabetical_desc`. |
| `pie` | Same shape as `category`, rendered as pie. | Same as `category`. |
| `range` | Min/max slider filter. | `column`, `operation`. |
| `timeseries` | Line / bar over time. | `column` (date/timestamp), `operation`, **`operationColumn` (REQUIRED at mount — see callout)**, `stepSize` (`second`…`year` — no `quarter`; use `stepSize: "month"` + `stepMultiplier: 3`), `chartType` (`line` \| `bar`), **`showControls` (REQUIRED at mount — emit `false` by default; see callout below)**. Optional `series[]` for multi-line, `splitByCategory` for per-category series. |
| `table` | Paginated row browser / feature browser. | `dataSource` + `columns: [{ field, headerName, type, format }]`. Only `field` is required per column; `type` (`number` / `string` / `date`) drives sorting and default formatting, and `format` is a d3-format specifier, not a preset id and not a date pattern. |

> **Histogram requires both `column` AND `buckets`.** An omitted `buckets` is filled with Builder's own 30, but author it explicitly: the tick loop is `for (let i = 1; i < widget.buckets; i++)`, so a value that reaches the widget as `undefined` — or the still-accepted `1` — renders an empty container.

> **`operationColumn` is required at mount on `category` / `pie` / `timeseries`, even when `operation: "count"`.** Builder's widgets panel throws when mounting these widgets without it; the React `ErrorBoundary` catches the throw and renders the styled "Error 500" page (which masquerades as a backend failure — see *"`Error 500` page in CARTO Builder is ambiguous"*). For `avg` / `min` / `max` / `sum`, set it to the numeric column being aggregated. For `count` and `custom` the key still has to be there but names nothing — emit `"operationColumn": ""`, which is what Builder writes. The same rule applies to `series[]` entries, where omitting the key is what breaks.

> **`showControls` belongs on every `timeseries`.** An omission is filled with `false`, which is what Builder persists on creation — but the component's own fallback is `true`, so leaving it out is what makes a CLI-authored timeseries diverge from a Builder-authored one. **Emit `"showControls": false` by default**; emit `true` ONLY when the user explicitly asks for time-scrubbing animation playback. The animation playback has several non-obvious failure modes: rejected outright on aggregated datasets (h3 / quadbin / heatmapTile / clusterTile — per-row timestamps are gone once binned), disabled when the widget is in `global: true` mode, and disabled when cross-filtering is active.

> **`operation` takes the SHORT form; `spatialIndexAggregation` on the same widget takes the LONG one.** Widget `operation` and `series[].operation` accept `count` / `avg` / `min` / `max` / `sum` / `custom` only — the layer spellings (`average` / `maximum` / `minimum`) are rejected outright. `spatialIndexAggregation` is the opposite: it takes the long form (`count` / `sum` / `average` / `minimum` / `maximum` / `stdev` / `variance` / `mode` / `any_value` / `custom`), the same renderable set as the layer aggregations — no `median`, no `count unique`. See [`layers.md`](layers.md) *"h3 / quadbin aggregation restrictions"* for the column-type gating that applies to the long-form set.

> **Table widgets are feature-browsers — search-and-click, NOT a filter.** What they CAN do: per-column search filters the *rows shown inside the table view*, and clicking a row zooms the map to that feature's geometry (when the dataset has resolvable geometry — set `uniqueIdProperty` on the dataset for stable cross-tile linkage). Use this for *"find this specific record"* use cases: viewer types into the column search → finds the row → clicks it → map zooms to highlight the feature.
>
> What they **CANNOT** do: filter the rest of the map, or participate in cross-filtering. The search inside the table affects the table's own row display only — other layers / widgets / popups don't react to it. Don't author a `table` widget expecting it to drive cross-filtering — use a `category` / `pie` / `range` / `histogram` widget for that (those DO cross-filter via `crossFilteringDataSourceIds`).
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
// timeseries — line / bar over time. `stepSize` accepts second…year (NO quarter — use month + stepMultiplier: 3).
// `operationColumn` and `showControls` are REQUIRED at mount. Bottom-of-map surface.
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
// list the columns to display + their formatting. Bottom-of-map surface.
// Set `uniqueIdProperty` on the dataset for click-to-zoom row→feature linkage.
{ "id": "w-table", "type": "table", "title": "Raw incidents",
  "dataSource": "$ref:incidents",
  "columns": [
    { "field": "incident_datetime", "headerName": "When",     "type": "date" },
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

### Widgets panel layout — `widgetsPanelLayout`

`keplerMapConfig.config.widgetsPanelLayout` (a peer of `widgets[]`, not a field on a widget) sets how Builder lays the panel out. Both members are required when the object is present:

```jsonc
"widgetsPanelLayout": { "columns": 2, "placement": "floating" }
```

- **`columns`** — `1` or `2` widgets per row. Nothing else: `3` is rejected at `keplerMapConfig.config.widgetsPanelLayout.columns`. With `2`, a widget carrying `fullWidth: true` takes a row of its own. Builder can still fall back to a single column on a narrow screen.
- **`placement`** — `docked` keeps the panel beside the map, `floating` draws it as a card over the map. Builder still docks a floating panel on a narrow screen and in the dual map view.

Omitting the object means the default, `{ "columns": 1, "placement": "docked" }` — the default is part of the format, not Builder state. **Round-trip trap:** because `keplerMapConfig` is replaced wholesale (see [`updates.md`](updates.md)), dropping `widgetsPanelLayout` from an update silently resets a two-column or floating panel back to that default. No warning is emitted. Carry the object through on every update of a map that has one.

### Collapsibility

**`collapsible: true` lets the viewer collapse the widget; `autoCollapse: true` collapses it while no layer bound to its `dataSource` is visible** — one hidden from the layer panel, or one whose `visibilityByZoom` range excludes the current zoom. It is NOT an initial state: with such a layer visible the widget renders expanded, so `autoCollapse` is not the way to open a map with a widget already collapsed. `autoCollapse` needs `collapsible: true` — the control is disabled without it. A `table` widget collapses as a tabbed group instead: tabs with no visible layer are skipped, and the group collapses when none is left. `collapsible` is optional on every kind.

```jsonc
// Table — bottom-of-map surface, collapsible, auto-collapsing when its layer is hidden
{ "id":"w-table","type":"table","title":"Raw incidents",
  "dataSource":"$ref:col", "columns":[ /* ... */ ],
  "collapsible": true, "autoCollapse": true }
```

> **`wrapperProps.expanded: false` is not the same thing as `autoCollapse: true`.** `wrapperProps` is per-viewer presentation state Builder persists with the widget — whether it is currently expanded; `autoCollapse` is the layer-visibility rule above. Both are accepted and survive round-trips. If you're round-tripping a Builder-authored bundle that carries `wrapperProps`, leave it.

### Knobs that apply across kinds

- **`global` mode** — `false` (default) queries only the layer-rendered data (filtered by viewport / bounds); `true` queries the entire dataset via the Model API (whole-dataset stats). **Forced true** when the dataset is tileset/raster without an attached layer, or a dynamic spatial-index dataset — Builder disables the toggle, but the CLI doesn't enforce: a tileset-backed widget with no layer needs `global: true` or it renders empty.
- **`spatialIndexAggregation`** — optional, and worth setting when the underlying dataset is h3/quadbin/heatmapTile/clusterTile: the tile server has already binned rows into cells, so this is how the widget aggregates them. Accepts the standard aggregation set MINUS `median` and `count unique` (same restriction as layer aggregations).
- **`collapsible` / `autoCollapse` / `wrapperProps.expanded`** — see *"Collapsibility"* above. `collapsible` lets the viewer collapse the entry; `autoCollapse` collapses it while no layer bound to its `dataSource` is visible (not an initial state) and needs `collapsible: true`; `wrapperProps.expanded` is the per-viewer state Builder persists.
- **`note` / `noteFormat` / `noteExpanded`** — optional freeform documentation shown alongside the widget. `noteFormat: "markdown"` renders Markdown; `plainText` (default) renders literal.
- **`fullWidth`** — gives the widget a row of its own when the panel shows two columns (`widgetsPanelLayout.columns: 2`); no effect with one column. Omit it for a normal-width widget. See *"Widgets panel layout"* above.
- **`operationExp`** — raw SQL for `operation: "custom"` (formula / category / pie / timeseries only). NOT supported when `dataSource` is a tileset or raster.

> **Widget ↔ dataset gotcha.** A widget whose `dataSource` is a `tileset` or `raster` dataset *with no layer in the map referencing it* renders empty (Builder marks it incompatible: `TILESET_OR_RASTER_WITHOUT_LAYER`). Always include the layer in the same configuration as the widget.

### Cross-filtering — propagating a widget's filter to other datasets

By default a widget filters only its own `dataSource`. To filter other datasets that share the same column (e.g., click a severity slice and shrink both the accidents and the accident-buffers datasets), set `crossFilteringDataSourceIds: [<own-dataSource-id>, <other-id>, ...]` on the widget.

**Authoring rule:**
1. The widget's own `dataSource` id MUST be included in the array — omitting it is the most common CLI authoring bug (the widget then doesn't even filter its own source).
2. Include every other dataset id whose schema has the same column with a compatible type. Mismatched types or column-not-in-SELECT → cross-filter silently no-ops.
3. Aggregated targets (h3/quadbin) work as long as the column is in the source SELECT before binning — the WHERE pushes down pre-aggregation.

Empty array or `undefined` ⇒ single-source filter only. To switch cross-filtering off for a widget entirely, set `disableFiltering: true` — it is carried by the filterable kinds (`category` / `pie` / `histogram` / `range` / `timeseries`) and clears `crossFilteringDataSourceIds` when toggled.

---

