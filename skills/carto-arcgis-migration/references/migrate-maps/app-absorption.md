# App absorption — simple Dashboard / Web Experience / Web Mapping App → Builder map

When the discover phase flags an app entry with `Routing decision: builder` (per the rubric in [`../discover/app-routing-rubric.md`](../discover/app-routing-rubric.md)), the maps phase **absorbs the app into a single Builder map** rather than scaffolding a custom Vite + React + deck.gl app. The absorbed map gets:

- The embedded Web Map's layers, renderers, popups (translated per the standard Web Map flow).
- Builder map controls (search, basemap switcher, measurement, locate) toggled to mirror the app's UI, as far as `mapSettings` has an equivalent — legend, layer list and bookmarks have none.
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
carto maps schema mapsettings --json
```

Then apply the mapping (control names left as found in source; Builder field names per the live schema):

| ArcGIS control / widget | Builder `mapSettings` flag |
|---|---|
| Layer list (visible / `layerListShown: true`) | no equivalent toggle — the legend panel is always available. `reorderLayers: true` is the closest thing (lets viewers reorder it). Record `Notes: app-control-skipped: layer list` |
| Legend (`legendShown: true`) | no `mapSettings` flag — legend state lives in `keplerMapConfig.config.legendSettings` |
| Basemap gallery / switcher (`basemapTogglerShown: true`) | `basemapsSelector: true` |
| Search bar (`searchEnabled: true`, `Search` widget on canvas) | `addressSearchBar: true` |
| Measurement / Measure widget | `showMeasureDistanceTool: true` (and `measurementUnit`: `"kilometers"` \| `"miles"`) |
| Bookmarks (`bookmarks` populated) | no equivalent — record `Notes: app-control-skipped: bookmarks` |
| Zoom / Home / Compass | Builder shows zoom by default; no explicit setting |
| Locate | `showMyLocationButton: true` |
| Print | `exportPDF: true` is the nearest equivalent (viewer-side PDF export) |

If the live schema doesn't have a flag for one of these controls, record `Notes: app-control-skipped: <name>` and continue. **Don't fabricate field names**: `mapSettings` is an open object, so an invented key passes validation, is stored, and toggles nothing — the control silently never appears. The live schema is the only way to tell a real flag from a plausible-looking one.

## Analytical widgets → Builder `widgets[]`

The rubric guarantees that every analytical widget on a simple app has a Builder equivalent (otherwise the rubric would have routed `custom-app`). So translation is mostly mechanical. Live shape:

```bash
carto maps schema widgets --json
```

`widgets` is one section covering every type; there is no `widgets.formula` / `widgets.pie` section to fetch. The response is large, so descend into the type you need rather than reading it whole.

Per-widget mapping:

**Every widget, whatever its type, requires `id`, `title`, `type` and `dataSource`** — the widget object is closed, so an unknown or missing key is rejected by name. The table below lists only what each type needs *on top of* those four.

| ArcGIS widget | Builder widget | Per-type fields |
|---|---|---|
| `pie-chart` (Dashboard) / pie chart (ExB / Instant App) | `pie` | `column` (the categorical field), `operation` (usually `count`), and `operationColumn` — required for `avg`/`min`/`max`/`sum`, omitted for `count` and `custom` |
| `serial-chart` single-series, temporal axis | `timeseries` | `column` (the date/time field), `operation`, and `operationColumn` on every series — required there even for `count` |
| `serial-chart` single-series, categorical axis | `histogram` | `column` (the numeric field), `buckets` |
| Histogram widget | `histogram` | `column` (numeric), `buckets` |
| Range slider / numeric filter | `range` | `column` (numeric) |
| Time-slider | `timeseries` (with default interval) | `column` (date) |
| `indicator` (Dashboard KPI) | `formula` | `operation` (`sum` / `avg` / `count` / `min` / `max`), `column` — **omitted** when `operation` is `count` |
| `list` (Dashboard) | `table` | `columns: [{"field": "<col>"}, ...]` (object form, not bare strings) |
| `table` (Dashboard / ExB attribute table) | `table` | `columns: [{"field": "<col>"}, ...]` |
| Filter (single-column attribute filter) | SQL parameter (`Category` / `NumericRange` / `DateRange`) on the layer's source query | `column`, type derived from the field — n/a (sqlParameters, not a widget) |

`dataSource` — **not `dataId`**, which belongs to a layer's `config` and is rejected on a widget — references the dataset the widget reads, as `"$ref:<name>"` for a dataset declared in the same bundle. For simple apps, the widget is usually bound to the same data the map renders, so reuse the embedded Web Map's primary layer's dataset ref.

Two more shape rules worth knowing before you compose:

- **`operation` takes the short spelling**: `avg`, not `average`. The long form is the layer/`spatialIndexAggregation` vocabulary and is rejected here.
- **`table.columns` is an array of `{"field": "<col>"}` objects, not bare strings.** Bare strings are rejected with a message naming the object form; they would otherwise round-trip through the API and throw when the table renders.

`isValid` and `buckets` do not need to be written by hand: both are filled when omitted (`isValid` to `true`, histogram `buckets` to `30`). An explicit `isValid` other than `true` is refused — Builder renders such a widget as an inert placeholder and drops it on the next save.

Always re-fetch the live shape with `carto maps schema widgets --json` and run `carto maps validate` after composition — the schema is the source of truth; the table above is a starting-point shortcut.

If a widget specifies a column the migrated DW table doesn't have (e.g. the source ArcGIS layer had a field that didn't survive migration), record `Notes: app-widget-skipped: <type> bound to missing column <name>` and skip.

## Title and tags

- `title` (bundle top level, a sibling of `datasets` and `keplerMapConfig`) = the **app's** title from the manifest entry (NOT the embedded Web Map's title — the user knows the artifact by the app name).
- `tags` = `["From ArcGIS", "From ArcGIS <Type>"]` where `<Type>` is `Dashboard` / `Web Experience` / `Web Mapping App`. The first tag is required for idempotency precheck; the second is informational.
- The app's `description` (when present, plain-text not Arcade) becomes the Builder map's `description` field.

## Bookmarks

There is no bookmarks feature on a Builder map, and no `bookmarks` section in the schema. A source app's `bookmarks[]` cannot be preserved: pick the most representative extent as the map's `mapState` viewport if the source has no other hint, and record `Notes: app-control-skipped: bookmarks (<N> saved extents)` so the user knows what was dropped.

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
