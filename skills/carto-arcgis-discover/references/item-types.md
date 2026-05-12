# ArcGIS item types → CARTO migration target

Authoritative mapping from ArcGIS Portal / AGOL `type` field (sometimes refined by `typeKeywords`) to the migration path the discover skill records in `MIGRATION_MANIFEST.md`.

When the source portal returns a `type` not in this table, classify the entry as a gap with reason `unknown type: <type>` and surface it to the user in the Phase 5 summary.

## Datasets → `carto-arcgis-migrate-data`

| ArcGIS `type` | Notes |
|---|---|
| `Feature Service` | Hosted feature layers and tables. The most common source. Each layer in the service becomes one DW table. |
| `Feature Collection` | In-memory features stored on the item. Migrate as a one-shot table. |
| `CSV Collection` / `CSV` | Tabular data; no geometry. Migrate as a table. |
| `Microsoft Excel` | Tabular; sheet 0 by default. Confirm with user if multi-sheet. |
| `Shapefile` | Already a file; download and feed to `carto imports create`. |
| `File Geodatabase` | Multi-layer; expand into one DW table per feature class. |
| `GeoPackage` | OGC GeoPackage file. Download via the item's attachment URL → `carto imports create --file <path>`. Multi-layer `.gpkg` files: expand into one DW table per layer (mirror the File Geodatabase flow), or pick the primary layer if the user prefers. |
| `GeoJson` | Single-table source. Stream straight to import. |
| `KML Collection` / `KML` | Convert to GeoJSON before import. |
| `Service Definition` | Underlying source data only — usually paired with a Feature Service item; classify the SD as a gap (the Feature Service is what gets migrated). |

## Tile sources → `carto-arcgis-migrate-data` (table; dynamic-tiled)

| ArcGIS `type` | Notes |
|---|---|
| `Vector Tile Service` | Underlying source data is usually a Feature Service. Migrate the source data and target dynamic tiling first. Pre-generate tiles only if perf is insufficient (see `carto-import-export-data` tileset prep flow). |
| `Vector Tile Package` | Local `.vtpk` file; tiles are pre-baked. If source data isn't downloadable, classify as `manual-only` gap. |
| `Tile Layer` (raster) | Raster cache. Source data may not be downloadable; treat as gap unless a Map Service item points at the underlying source. |

## Web maps → `carto-arcgis-migrate-maps`

| ArcGIS `type` | Notes |
|---|---|
| `Web Map` | The standard map item type. Operational layers reference Feature Services; record those as dependencies. |

## Services → `carto-arcgis-migrate-services`

> **Dedup before classifying as Services.** Map Service / WFS items that are alternate endpoints over the same underlying data as a Feature Service should be **collapsed into the Feature Service's Datasets entry as `Source aliases`**, not duplicated as Service entries. See [`manifest-format.md`](manifest-format.md) for the alias field; see Phase 4 of `SKILL.md` for the dedup logic. Only items that genuinely expose data the migrated table doesn't already serve land under Services.

| ArcGIS `type` | Notes |
|---|---|
| `Geoprocessing Service` | Migrate to a CARTO Workflow bundle (native components first; `native.customsql` fallback). The Geoprocessing Service item describes a *server*; each task on the server may map to one workflow. |
| `Geoprocessing Package` | Local `.gpk` — no live service. Classify as `manual-only` gap. |
| `Map Service` | **Dedup first**: if the same data has a Feature Service item in the org, collapse this MS into the Feature Service's Datasets entry as a `Source aliases` row — do not create a separate entry. If standalone (no FS counterpart), and the underlying data is downloadable: classify as a Datasets entry under `migrate-data`. If not downloadable: gap with reason `no-source-data`. |
| `Image Service` | Out of scope v1 — gap with reason `out-of-scope-v1`. |
| `Geocoding Service` | Out of scope v1; M5+ candidate for `carto-pattern-geocoding`. Gap reason: `out-of-scope-v1`. |
| `Network Analysis Service` / `Routing Service` | Out of scope v1; M5+ candidate for `carto-pattern-routing-od-analysis`. Gap reason: `out-of-scope-v1`. |
| `WFS` / `OGC Web Service` (WFS) | **Dedup first**: WFS items often shadow a Feature Service. If both are in the org, collapse the WFS into the Feature Service's Datasets entry as a `Source aliases` row. Standalone WFS with downloadable data → classify under `migrate-data` (use `ogr2ogr`-friendly extraction). Standalone WFS that's read-only with no downloadable source → gap. |
| `WMS` / `OGC Web Service` (WMS) | Treat WMS like a Map Service (raster gap unless source data is available). Same dedup rule applies. |

## Apps → `carto-arcgis-migrate-apps` or `carto-arcgis-migrate-maps` (conditional)

Apps route **conditionally**. The `discover` skill fetches the item's `data` payload and applies the rubric in [`app-routing-rubric.md`](app-routing-rubric.md):

- **Simple apps** — all detected widgets available in Builder, ≤ 4 visible simultaneously → `carto-arcgis-migrate-maps`. The embedded Web Map becomes a Builder map; standard map controls and analytical widgets are enabled on the resulting map. No custom app code is generated.
- **Custom apps** — any non-Builder widget OR > 4 visible widgets → `carto-arcgis-migrate-apps`. Becomes a Vite + React + deck.gl + ECharts app.

| ArcGIS `type` | Notes |
|---|---|
| `Dashboard` | Apply the rubric. Most ArcGIS Dashboards fail (≥ 5 widgets visible by design) and route to `migrate-apps`; small ones (one map + one or two charts already covered by Builder) can fit a Builder map. |
| `Web Experience` | Experience Builder. Apply the rubric. ExB experiences whose surface is a map plus standard controls and a couple of analytical widgets often fit Builder; rich multi-page experiences with custom widgets route to `migrate-apps`. |
| `Web Mapping Application` | Configurable Apps, Instant Apps, Map Viewer-based templates, Web AppBuilder. Apply the rubric. Identify the subtype via `typeKeywords` (`Configurable`, `Instant App`, `WAB2D`, `WAB3D`) before inspecting the data payload — each subtype stores its widgets in a different shape. Most Instant Apps and Map Viewer-based templates pass the rubric (just a map + map controls + a search bar) and route to `migrate-maps`; Web AppBuilder apps with custom or proprietary widgets (Edit, Geoprocessing, 3D) typically fail and route to `migrate-apps`. |
| `StoryMap` | Out of scope v1 — gap with reason `out-of-scope-v1` (different rendering model; potential M5+ enhancement). |
| `Insights Workbook` | Out of scope v1 — gap. |
| `Form` (`Survey123`) | Out of scope v1 — gap (different domain; CARTO has no direct survey-form equivalent). |

## Other / not directly migratable → gap

| ArcGIS `type` | Reason |
|---|---|
| `OGCFeatureServer` | OGC API Features endpoint. CARTO does not currently support OGC API Features as a data source — gap with reason `no-CARTO-equivalent`. Note this is distinct from older `WFS` items (listed under Services). |
| `Web Scene` | 3D scene item (scene layers, slides, terrain). CARTO Builder is 2D-first — gap with reason `no-CARTO-equivalent`. Note: simple 3D extrusion within an otherwise 2D map can be expressed in Builder; the gap applies to the full 3D scene container. |
| `Notebook` | Python/Jupyter content. `manual-only` — review separately. |
| `Code Sample` / `Code Attachment` | `manual-only`. |
| `Symbol Set` / `Color Set` | Styling assets used by maps. Auto-applied via the renderer translator in `migrate-maps`; the items themselves are `manual-only` if standalone. |
| `Style` (`web-style`) | Same as above. |
| `Workforce Project` / `QuickCapture Project` / `AppBuilder Extension` | `out-of-scope-v1`. |
| `Document Link` / `Hub Site Application` / `Hub Page` | `manual-only` — link to external content. |
| `Image` / `Document` / `PDF` | `manual-only` — generic file attachments. |

## How to use this table at runtime

1. Find the item's `type` in the table.
2. The "Notes" column tells you both the migration target (a `carto-arcgis-migrate-*` skill or a gap reason) and any per-type subtleties.
3. Refine using `typeKeywords` only when noted (e.g. `Web Mapping Application` has many flavors). For most types, `type` alone is sufficient.
4. If the `type` is missing or contains a value not in this table, emit a gap with reason `unknown type: <type>` — never guess.
