# App absorption — simple Dashboard / Web Experience / Web Mapping App → Builder map

When the discover phase flags an app entry with `Routing decision: builder` (per the rubric in [`../discover/app-routing-rubric.md`](../discover/app-routing-rubric.md)), the maps phase **absorbs the app into a single Builder map** rather than scaffolding a custom Vite + React + deck.gl app. The absorbed map gets:

- The embedded Web Map's layers, renderers, popups (translated per the standard Web Map flow).
- Builder map controls (legend, layer list, search, basemap switcher, measurement, bookmarks) toggled to mirror the app's UI.
- Builder analytical widgets (`formula`, `pie`, `histogram`, `range`, `timeseries`, `table`) for each app analytical widget that has a Builder equivalent.
- The app's title and (optionally) source-type tag.

Complex apps (`Routing decision: custom-app`) take a different path — a future app-migration phase will generate a standalone Vite + React + deck.gl scaffold. The maps phase only handles the `builder` branch.

## Detection

A manifest entry is a simple-app entry when ALL of:

- It lives under `## Apps`.
- It has `Routing decision: builder`.
- It has a `Source Web Map: <item-id>` field naming the embedded Web Map.
- Its `Type:` is one of `Dashboard`, `Web Experience`, `Web Mapping Application`.

## Reading the source

Two REST calls per simple-app entry:

```bash
# 1) The app's own data payload — drives widget + map-control overlay.
curl -s "$PORTAL/sharing/rest/content/items/$APP_ID/data?f=json" -o app.json

# 2) The embedded Web Map — drives the layer/renderer/popup translation
#    (same flow as a regular Web Map entry).
curl -s "$PORTAL/sharing/rest/content/items/$WEB_MAP_ID/data?f=json" -o webmap.json
```

`$WEB_MAP_ID` comes from the manifest entry's `Source Web Map:` field. Both responses go into `MIGRATION_INVENTORY.json` for cache + post-mortem.

### Per-subtype: where the widgets live

The same table as `app-routing-rubric.md`'s "Where widgets live in the item `data` payload" — repeat here for self-containment:

| Item type | `typeKeywords` hint | Widgets at |
|---|---|---|
| `Dashboard` | — | `data.widgets[]` (flat). `data.headerPanel`, `data.sidebar`, `data.leftPanel` are non-counted text/header panels |
| `Web Experience` | — | walk `data.pages[]` → each page's `layouts[]` → `widgets[]` and `widgetIds[]`; `data.widgets` is also a flat dictionary keyed by widget id |
| `Web Mapping Application` | `Configurable` | `data.values` — true flags become map-control entries (`legendShown`, `layerListShown`, `searchEnabled`, `bookmarksEnabled`) |
| `Web Mapping Application` | `Instant App` | `data.draft` (or `data` if published) — schema varies per template (Sidebar, Nearby, Atlas, Insets, Minimalist, etc.); walk `tools[]` / `widgets[]` / `expressions[]` |
| `Web Mapping Application` | `WAB2D` / `WAB3D` | `data.widgetPool.widgets[]` (catalog) and `data.widgetOnScreen.widgets[]` (visible). Only `widgetOnScreen` is in scope for absorption |

If `typeKeywords` is ambiguous or empty for a Web Mapping Application, fall back conservatively: enumerate `data.values` AND `data.widgetOnScreen.widgets[]`, deduplicating. If neither yields a clean widget list, mark the entry `failed` with `Failure: app-shape-unrecognized: <typeKeywords>`. Don't guess.

## Map controls → Builder `mapSettings`

ArcGIS apps expose map controls via flags / widget entries. Builder has corresponding `mapSettings` toggles. Always fetch the live shape:

```bash
carto maps schema mapSettings --json
```

Then apply the mapping (control names left as found in source; Builder field names per the live schema):

| ArcGIS control / widget | Builder `mapSettings` flag (typical name) |
|---|---|
| Layer list (visible / `layerListShown: true`) | `layerSelectorEnabled: true` |
| Legend (`legendShown: true`) | `showLegend: true` |
| Basemap gallery / switcher (`basemapTogglerShown: true`) | `basemapToggle: true` |
| Search bar (`searchEnabled: true`, `Search` widget on canvas) | `searchEnabled: true` |
| Measurement / Measure widget | `measureEnabled: true` |
| Bookmarks (`bookmarks` populated) | preserve `bookmarks` array on the map config; flag `bookmarksEnabled: true` if Builder has one |
| Zoom / Home / Locate / Compass | Builder shows zoom + locate by default; usually no explicit setting |
| Print | `printEnabled: true` (if Builder supports it; otherwise no-op + `Notes: app-control-skipped: print`) |

If the live schema doesn't have a flag for one of these controls, record `Notes: app-control-skipped: <name>` and continue. Don't fabricate field names — `carto maps validate` rejects unknown keys.

## Analytical widgets → Builder `widgets[]`

The rubric guarantees that every analytical widget on a simple app has a Builder equivalent (otherwise the rubric would have routed `custom-app`). So translation is mostly mechanical. Live shape:

```bash
carto maps schema widgets --json
carto maps schema widgets.formula --json
carto maps schema widgets.pie --json
# ...etc.
```

Per-widget mapping:

| ArcGIS widget | Builder widget | Required fields | Required boilerplate |
|---|---|---|---|
| `pie-chart` (Dashboard) / pie chart (ExB / Instant App) | `pie` | `dataId`, `column` (the categorical field), `operation` (usually `count`) | `isValid: true` |
| `serial-chart` single-series, temporal axis | `timeseries` | `dataId`, `column` (the date/time field), aggregation `column` + `operation` | `isValid: true` |
| `serial-chart` single-series, categorical axis | `histogram` | `dataId`, `column` (the numeric field) | `isValid: true`, `buckets: 30` |
| Histogram widget | `histogram` | `dataId`, `column` (numeric) | `isValid: true`, `buckets: 30` |
| Range slider / numeric filter | `range` | `dataId`, `column` (numeric) | `isValid: true` |
| Time-slider | `timeseries` (with default interval) | `dataId`, `column` (date) | `isValid: true` |
| `indicator` (Dashboard KPI) | `formula` | `dataId`, `column` (or `null` for count), `operation` (`sum` / `avg` / `count` / etc.) | `isValid: true` |
| `list` (Dashboard) | `table` | `dataId`, columns subset | `isValid: true`, `columns: [{"field": "<col>"}, ...]` (object form, not bare strings) |
| `table` (Dashboard / ExB attribute table) | `table` | `dataId`, full visible columns | `isValid: true`, `columns: [{"field": "<col>"}, ...]` |
| Filter (single-column attribute filter) | SQL parameter (`Category` / `NumericRange` / `DateRange`) on the layer's source query | `column`, type derived from the field | n/a (sqlParameters, not a widget) |

`dataId` references the kepler dataset id of the layer the widget is bound to. For simple apps, the widget is usually bound to the same data the map renders — use the embedded Web Map's primary layer's dataId.

The **Required boilerplate** column captures Tier-1 cross-field rules that the live `widgets` schema doesn't surface as required but `carto maps validate` enforces:

- **`isValid: true` on every widget.** Without it, Builder hides the widget — the panel renders as *"select a field"* and viewers can't reconfigure it.
- **`buckets: <int>` on histograms** (default `30`). The component's render loop is `for (let i = 1; i < widget.buckets; i++)` — undefined → empty render.
- **`table.columns` is an array of `{"field": "<col>"}` objects, not bare strings.** The schema describes `columns: array` (no item shape); bare strings round-trip through the API but the table renderer throws on mount.

Always re-fetch the live shape with `carto maps schema widgets --json` and run `carto maps validate` after composition — the schema is the source of truth; the table above is a starting-point shortcut.

If a widget specifies a column the migrated DW table doesn't have (e.g. the source ArcGIS layer had a field that didn't survive migration), record `Notes: app-widget-skipped: <type> bound to missing column <name>` and skip.

## Title and tags

- `keplerMapConfig.title` = the **app's** title from the manifest entry (NOT the embedded Web Map's title — the user knows the artifact by the app name).
- `tags` = `["From ArcGIS", "From ArcGIS <Type>"]` where `<Type>` is `Dashboard` / `Web Experience` / `Web Mapping App`. The first tag is required for idempotency precheck; the second is informational.
- The app's `description` (when present, plain-text not Arcade) becomes the Builder map's `description` field.

## Bookmarks

If the source app or Web Map has `bookmarks[]`, preserve them on the Builder map. Bookmarks are saved-extents — same shape across both products. Per-bookmark fields: `name`, `extent` (xmin/ymin/xmax/ymax + spatialReference). Translate `extent` to kepler's bookmark format if needed; `carto maps schema bookmarks --json` is authoritative.

## Edge cases

- **App's embedded Web Map is itself a manifest Web Map entry** (the same Web Map is used by both an app AND directly). Handle independently: the app entry produces one Builder map (with widgets); the standalone Web Map entry produces another (without widgets). They share a title prefix only by coincidence; the idempotency precheck uses both title AND `From ArcGIS` tag, and titles will differ enough.
- **Multi-page Web Experience routed `builder`** (rare per the rubric, but possible if pages are simple). Builder is single-page. Migrate the FIRST page's widgets only; record `Notes: web-experience-collapsed-pages: <N>` so the user knows the additional pages weren't preserved. The user can manually add pages worth of widgets later.
- **App config has > 4 widgets visible but rubric still routed `builder`**: trust the manifest. The rubric's `> 4 visible` cap is approximate; if discover decided `builder` despite the count, it had a reason (e.g. some widgets are conditional / hidden by default). Translate all widgets the source actually has and let `carto maps validate` flag any density issue.
- **App-control flag names that don't match Builder's exact mapSettings keys**: skip with `Notes: app-control-skipped: <name>` rather than guessing. Builder's mapSettings is small; uncovered controls aren't worth fabricating field names for.

## When in doubt

- App data payload has no widgets at all (just a wrapper around a Web Map)? Translate as a regular Web Map (skip Phase 4 steps 5 & 6); the app overlay is a no-op, the Builder map ends up with map controls + the embedded Web Map's content.
- The `Source Web Map:` field on the manifest entry is missing or empty? `failed`, `Failure: app-missing-source-web-map: <app-id>`. Re-running discover should populate it; surface to the user.
- Two different app subtypes (e.g. one Dashboard + one ExB) that both reference the same embedded Web Map? Each produces its own Builder map. The `From ArcGIS` tag means they don't dedup with each other (different titles).
- Widget translation produces something `carto maps validate` rejects after 3 iterations? Skip that widget with `Notes: app-widget-validation-failed: <type>`; don't fail the whole map. The map still renders correctly without the widget.
