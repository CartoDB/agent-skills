# App routing rubric — Builder vs. custom deck.gl app

ArcGIS Dashboards, Web Experiences (Experience Builder), and Web Mapping Applications (Configurable Apps, Instant Apps, Map Viewer templates, Web AppBuilder) come in two shapes:

- **Simple apps** — the entire interactive surface is a map plus widgets that CARTO Builder offers natively (legend, layer list, basemap switcher, search, measurement, plus a small number of analytical widgets like pie / histogram / range / timeseries / table / formula).
- **Custom apps** — the app uses widgets Builder doesn't cover, OR shows more than 4 widgets simultaneously, OR has a layout that doesn't reduce to a single Builder map.

The `discover` skill applies this rubric to every Dashboard, Web Experience, and Web Mapping Application item it finds, records the decision on the manifest entry, and routes simple apps to `carto-arcgis-migrate-maps` (absorbed into the embedded Web Map's Builder map) and custom apps to `carto-arcgis-migrate-apps`.

## Decision

```
For each Dashboard, Web Experience, or Web Mapping Application:
  fetch the item's `data` payload
    GET /sharing/rest/content/items/<id>/data?f=json
  enumerate detected widgets per item type (see "Where widgets live" below)
  count max widgets visible simultaneously on any single page or layout
    (exclude map controls — see "Map controls" table below)
  for each detected widget: look up its Builder equivalent

  if any detected widget has no Builder equivalent
      → custom app   (Recommended path: carto-arcgis-migrate-apps)
  elif max-visible-widgets > 4
      → custom app   (Recommended path: carto-arcgis-migrate-apps)
  else
      → simple app   (Recommended path: carto-arcgis-migrate-maps)
```

By type:

- **Dashboards** typically fail the rubric (≥ 5 widgets is the design intent).
- **Experience Builder** experiences pass more often, especially when the app's purpose is "show a map with standard controls and one or two analytical widgets."
- **Web Mapping Applications** vary widely. **Instant Apps** and **Map Viewer-based templates** are usually wrappers over a Web Map with map controls and a search bar — they pass the rubric. **Configurable Apps** (older "Basic Viewer", "Public Information", etc.) are similar. **Web AppBuilder (WAB)** apps are heavier — they often include Edit, Geoprocessing, 3D, or custom widgets that have no Builder equivalent and route to `migrate-apps`.

## ArcGIS widget → CARTO Builder equivalent

### Map controls — always available, never counted toward the cap

| ArcGIS widget / control | Builder equivalent |
|---|---|
| Layer list | Builder layer panel |
| Legend | Builder legend |
| Basemap gallery / switcher | Builder basemap selector |
| Search | Builder search bar |
| Measurement | Builder measure tool |
| Zoom / Home / Locate / Compass | Builder map controls |
| Print | Builder export-to-image |
| Bookmarks | Builder bookmarks |
| Header / sidebar / text panel | Builder map title + description (informational only) |

### Analytical widgets — counted toward the cap

| ArcGIS widget | Builder equivalent | Status |
|---|---|---|
| `pie-chart` / Pie chart | `pie` widget | available |
| `serial-chart` (single series) | `timeseries` (if temporal) or `histogram` (if categorical) | available |
| `serial-chart` (multi-series) | — | **not available** |
| Histogram | `histogram` widget | available |
| Range slider / numeric filter | `range` widget | available |
| `timeseries` / temporal slider | `timeseries` widget | available |
| `indicator` / KPI | `formula` widget | available |
| `list` / record list | `table` widget | available |
| `table` / attribute table | `table` widget | available |
| `details` / record detail | popup or info panel | available |
| Filter (attribute filter, single column) | SQL parameter (`Category` / `NumericRange` / `DateRange`) | available |
| `embedded-content` / iframe widget | — | **not available** |
| Custom script widget | — | **not available** |
| Print-report widget | — | **not available** |
| Survey widget (Survey123) | — | **not available** |

When a widget type isn't in this table, treat as **not available** and route to `migrate-apps` — the rubric is conservative on unknowns.

## Where widgets live in the item `data` payload

Different app types store their widget configurations in different shapes. The agent reads the `data` payload once and enumerates widgets per the item's type and `typeKeywords`:

| Item type | `typeKeywords` hint | Where to find widgets |
|---|---|---|
| `Dashboard` | — | `data.widgets[]` (flat list); `data.headerPanel`, `data.sidebar`, `data.leftPanel` for non-counted text/header panels |
| `Web Experience` | — | walk `data.pages[]` → each page's `layouts[]` → `widgets[]` and `widgetIds[]`; `data.widgets` is also a flat dictionary keyed by widget id |
| `Web Mapping Application` | `Configurable` | `data.values` — the configured widget set varies per template; common keys include `legendShown`, `layerListShown`, `searchEnabled`, `bookmarksEnabled`. Treat each true flag as one map-control entry |
| `Web Mapping Application` | `Instant App` | `data.draft` (or `data` if published) — Instant App config schema varies per template (Sidebar, Nearby, Atlas, Insets, Minimalist, etc.). Walk `tools[]` / `widgets[]` / `expressions[]` per template |
| `Web Mapping Application` | `WAB2D` / `WAB3D` | `data.widgetPool.widgets[]` (off-screen catalog) and `data.widgetOnScreen.widgets[]` (visible). Only count `widgetOnScreen` toward the cap |
| `Web Mapping Application` | `Story Map` | Treat as gap (`out-of-scope-v1`) at the item-types level — do not enter the rubric |

When `typeKeywords` is ambiguous or empty, prefer the conservative fallback: enumerate `data.values` and `data.widgetOnScreen.widgets[]` if present; if neither yields a clean widget list, classify as `custom-app` and note `unknown Web Mapping Application subtype` in the manifest entry's `Notes:`.

## What "max visible widgets" means

- **Dashboard**: count widgets on the single dashboard layout. Header / sidebar text panels don't count; map controls don't count.
- **Web Experience**: evaluate each page independently; the max across all pages is the number used. Tabbed views inside a single page count the tab with the most simultaneously-visible widgets (not the sum across tabs). Pop-up dialogs that appear only on user action don't count.
- **Web Mapping Application**: count widgets that are visible on initial load. Map controls don't count. Off-screen widgets in WAB's `widgetPool` don't count (only `widgetOnScreen` does). Pop-up panels that open on user action don't count. For Instant Apps, count any panel/section that's visible alongside the map by default.

## What gets recorded on the manifest entry

After applying the rubric, the discover skill writes the following fields onto the app's manifest entry (see [`manifest-format.md`](manifest-format.md)):

- `App profile:` — one-line summary of detected widgets and which are Builder-available.
- `Max visible widgets:` — the count.
- `Routing decision:` — `builder` or `custom-app`.
- For `builder` decisions: `Source Web Map:` pointing at the embedded Web Map's item ID — the map `migrate-maps` will turn into a Builder map (with the relevant Builder widgets enabled).
- For `custom-app` decisions: a short reason in `Notes:` explaining which rule fired (e.g. `embedded-content widget not available` or `7 widgets visible — > 4 cap`).

## Tuning

The 4-widget cap is a heuristic — Builder's right-hand panel comfortably shows 3 to 4 widgets simultaneously without scrolling on a typical desktop viewport. The cap can be overridden per migration: edit the manifest after `discover` runs and before `migrate-maps` / `migrate-apps` is invoked. Flip `Routing decision:` (and `Recommended path:` accordingly) and the downstream skills honor the override.
