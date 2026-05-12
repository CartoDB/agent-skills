---
name: carto-arcgis-migrate-maps
description: Migrate ArcGIS Web Maps — and simple ArcGIS Dashboards / Web Experiences / Web Mapping Applications flagged with `Routing decision: builder` by discover — into CARTO Builder maps. Walks the manifest's Web Maps section AND the Apps section's simple-app entries; translates drawingInfo (simple / uniqueValue / classBreaks renderers) + popupInfo + supported Arcade subset (attribute references, per-row math, simple aggregations) + basemap into a keplerMapConfig JSON; for app entries, also enables Builder map controls (legend, layer list, search, basemap switcher, measurement) and emits Builder analytical widgets (formula / pie / histogram / range / timeseries / table) to mirror the source app's UI; validates with `carto maps validate`; creates with `carto maps create`; tags every migrated map `From ArcGIS` for organization. Default mode is batch. Triggers on "migrate the maps", "migrate the simple apps", or naming a specific title from the manifest. Always creates maps as private.
license: TBD
---

# carto-arcgis-migrate-maps

Walks the Web Maps section of `MIGRATION_MANIFEST.md` AND the Apps section's simple-app entries (those discover flagged with `Routing decision: builder`), creating a CARTO Builder map per pending entry. **Default mode is batch.** Idempotent: `done` entries skip after a precheck (search CARTO for an existing map with same title + `From ArcGIS` tag); `failed` entries retry. Entries whose layers depend on not-yet-migrated datasets are marked `failed` with a clear reason rather than auto-invoking `migrate-data` — the user wants explicit visibility into the gap.

This skill is a translator from two source shapes — ArcGIS Web Map JSON OR ArcGIS app config (Dashboard / Web Experience / Web Mapping App) — to keplerMapConfig JSON. It delegates Builder authoring conventions, validation, and screenshot mechanics to `carto-create-builder-maps` (in the installed `carto-skills` plugin).

For complex apps (`Routing decision: custom-app`) the user invokes `carto-arcgis-migrate-apps` instead, which generates a Vite + React + deck.gl scaffold. Discover's rubric in [`carto-arcgis-discover/references/app-routing-rubric.md`](../carto-arcgis-discover/references/app-routing-rubric.md) decides per-app which path applies; this skill simply respects the routing decision recorded on each manifest entry.

## Prerequisites

- `MIGRATION_MANIFEST.md` exists in the working directory with at least one `pending` Web Map entry OR a `pending` Apps entry whose `Routing decision:` is `builder`. Datasets referenced by those Web Maps / apps should already be `done` from `carto-arcgis-migrate-data`.
- The `carto-skills` plugin (`/plugin install carto-skills@carto-agent-skills`). This skill defers Builder mechanics to `carto-create-builder-maps` and SQL execution to `carto-query-datawarehouse`.
- `carto auth login` already done. The connection named in the manifest's `target_connection` must be reachable.
- Python with `sqlglot` for Arcade-to-SQL validation (`pip install sqlglot`). Without it, the simple Arcade translator still proceeds but skips client-side SQL validation; `carto maps validate` will catch broken SQL at compose time.

## When to use this skill

- After `carto-arcgis-migrate-data` completes for the underlying datasets. Default: process all pending Web Maps + simple-app entries in batch.
- To migrate a single Web Map or simple app: name its title from the manifest (case-insensitive contains-match).
- To re-run after fixing a `failed` entry — for example, when the user manually migrated a missing dataset and wants the Web Map / app retried.

## Phases

Follow these in order on every invocation.

### Phase 0 — Read prior lessons + carto-skills

Open [`references/lessons.md`](references/lessons.md) for migration-specific patterns. Read `carto-create-builder-maps` (in the installed carto-skills plugin) for Builder authoring conventions — keplerMapConfig schema sections, validation flow, basemap rules, the 5-field hover cap, multi-layer hue separation, "do silently, don't ask" defaults. Initialize an empty `SESSION_LESSONS.md` in the working directory.

### Phase 1 — Plan the batch

1. Read `MIGRATION_MANIFEST.md`. Collect TWO sets of entries:
   - **Web Map entries**: under `## Web Maps` with `State: pending` or `State: failed`.
   - **Simple-app entries**: under `## Apps` with `Routing decision: builder` AND `State: pending` or `State: failed`. These have a `Source Web Map: <item-id>` field naming the embedded Web Map that will be migrated.

   If the user named a single title, filter to that entry (search both sections).
2. Print a one-line plan: N Web Maps + M simple apps to migrate, target connection.
3. **Idempotency precheck** per entry: `carto maps list --mine --search "<title>" --tag "From ArcGIS" --json` (or filter response by tag client-side). A title match WITH the `From ArcGIS` tag → entry already migrated; transition to `done` with `Target URL` and `Notes: pre-existing migrated map matched title+tag`. Title match WITHOUT the tag is *not* deduped.
4. For each in-scope entry, transition `State: pending → in-progress` and write the manifest immediately.

### Phase 2 — Read source

For each in-scope entry:

- **Web Map entries**: fetch `<portal>/sharing/rest/content/items/<id>/data?f=json`. The Web Map JSON shape: `operationalLayers[]`, `baseMap`, `bookmarks`, `applicationProperties`, `version`, `spatialReference`, plus per-layer `popupInfo`, `layerDefinition.drawingInfo`, `labelingInfo`.
- **Simple-app entries**: fetch BOTH the app's data payload (`/sharing/rest/content/items/<app-item-id>/data?f=json` — Dashboard / ExB / WMA shape varies per type, see [`references/app-absorption.md`](references/app-absorption.md)) AND the embedded Web Map (`/sharing/rest/content/items/<source-web-map-id>/data?f=json` — the ID comes from the manifest entry's `Source Web Map:` field). The embedded Web Map drives the layer/renderer/popup translation in Phase 4; the app data drives the widget + map-control overlay.

Cache responses to `MIGRATION_INVENTORY.json` if discover hasn't already cached them.

### Phase 3 — Resolve layers

For each `operationalLayer`:

1. Match the layer's `url` against the manifest's Datasets entries — including `Source aliases:` (a Map Service URL may have collapsed into a Feature Service entry during discover's Phase 4 dedup). The migrated `Target FQN` belongs to the canonical entry.
2. If no Datasets entry matches → mark the Web Map `State: failed`, `Failure: depends-on-unmigrated-data: <layer-name>`, continue to the next entry. **Do not auto-invoke `migrate-data`.**
3. If the matched entry's `State` is not `done` (e.g. `skipped` because > 1 GB) → `Failure: depends-on-skipped-data: <layer-name> (<reason>)`. Same continue-the-batch behavior.

### Phase 4 — Translate each layer (and, for app entries, the app overlay)

For each operationalLayer (from the embedded Web Map, whether the entry is a Web Map or a simple-app) that resolves to a `done` Datasets entry:

1. **`drawingInfo` → kepler `visState.layers[]`** per [`references/renderer-mapping.md`](references/renderer-mapping.md): `simple` → single-color; `uniqueValue` → ordinal categorical; `classBreaks` → quantize with explicit `colorDomain`. Heatmap / dotDensity / temporal / predominance fall back to simple-color with `Notes: renderer-fallback: <type>`. **Picture marker symbols (`esriPMS`)** on point layers — including per-category icons in `uniqueValue` renderers — are preserved via a multipart `POST /assets` (`type=MapMarker`) to the workspace API (there is no `carto maps markers` CLI subcommand): acquire from `imageData` or `url`, dedup by content hash, upload once, reference the returned asset `id` in `visConfig`. See [`references/marker-upload.md`](references/marker-upload.md). **CIM symbols (`CIMSymbolReference` from ArcGIS Pro 2.0+)** are walked per [`references/cim-symbols.md`](references/cim-symbols.md): `CIMPictureMarker` flows through the same marker-upload pipeline (the URL is typically a `data:` URI — decoded directly); `CIMVectorMarker` / `CIMCharacterMarker` collapse to a colored circle using the extracted dominant fill color; multi-layer symbols pick the topmost marker. Non-circle `esriSMS` styles collapse to circle (color preserved); `esriPFS` and CIM picture / hatch / gradient fills (polygons) collapse to solid fill.
2. **`popupInfo` → `popupSettings.layers`** per [`references/popup-mapping.md`](references/popup-mapping.md): translate `fieldInfos` to the live layer-id-keyed `{ enabled, hover, click }` shape with d3-format strings; **emit click-only popups** — ArcGIS Web Maps are click-only by default and migration faithfully reproduces this; route Arcade through the next step; skip chart `mediaInfos` with a Note. **Layers without `popupInfo` in the source get no popup in the target** — don't apply Builder's default-popup rule during migration.
3. **Arcade expressions** (in `popupInfo.expressionInfos`, `labelingInfo[].labelExpressionInfo`, `drawingInfo.visualVariables[].valueExpression`) per [`references/arcade-translation.md`](references/arcade-translation.md):
   - Single attribute (`$feature.X`) → bind directly.
   - Per-row math (`$feature.A / $feature.B * 1000`) → SQL derived field in the layer's source query, validated with `sqlglot`.
   - Simple aggregations (`Count`, `Max`, `Min`, `Sum`, `Average`/`Mean` of one `$feature.X`) → Builder `formula` widget added to the map.
   - Anything else → `Notes: arcade-skipped: <truncated-fragment>` and fall back to a plain field reference where possible.
4. **`labelingInfo` → kepler `config.textLabel[]`** per [`references/renderer-mapping.md`](references/renderer-mapping.md) "Labels with halo": the source's label config lives at **`layerDefinition.drawingInfo.labelingInfo[]`** (NOT at `layerDefinition.labelingInfo` directly — that path is almost always empty even when CIM-symbol layers have populated labels). Each entry maps to `{size, color, field:{name,type}, anchor, offset, alignment, outlineColor}` where `outlineColor` is the **halo** color from `symbol.haloColor`. Extract the field via `re.match(r'^\$feature\["?(\w+)"?\]$', expr) or re.match(r"^\[(\w+)\]$", expr)`, lower-case it (BQ-side), then build the entry. Accept a `font_size_override` per layer when the source's tuned-for-print font (typically 9 px) doesn't render at city zoom — common pattern: TfL stations 9 → 12, dense point-codes 6 → 8. Leave `offset: [0, 0]` for above/below placements; `alignment` alone positions the label flush to the icon and any extra offset visibly detaches it.
5. **Visibility by zoom** per [`references/renderer-mapping.md`](references/renderer-mapping.md) "Visibility by zoom": convert source `minScale`/`maxScale` (ArcGIS scale denominators) to kepler `visibilityByZoom.{min,max}` via `zoom = log2(559082264 / scale)`. Read BOTH the WebMap's `layerDefinition.minScale` (override, wins when present) AND the FeatureServer layer's own `minScale` (server default, fetch the layer JSON per URL). Without this, every point layer renders at every zoom and the city-wide view becomes a sea of dots (TfL stations needed `minScale 300000 → zmin 11`, Bus Stops `25000 → 15`).
6. **Basemap** per [`references/basemap-mapping.md`](references/basemap-mapping.md): map the source `baseMap.title` (or `baseMapLayers[].url` pattern) to a CARTO basemap; write **both** `basemapConfig` (`{ type, styleId }`) and `mapStyle.styleType` with the matching provider. Honor an explicit `Basemap override:` field on the manifest entry if present.

**For simple-app entries only**, after the layer loop completes, walk the source app's config and overlay the app's UI onto the Builder map per [`references/app-absorption.md`](references/app-absorption.md):

7. **App map controls → Builder `mapSettings`**: each ArcGIS app control (Layer list, Legend, Basemap switcher, Search, Measurement, Bookmarks) toggles a corresponding Builder mapSettings flag. Read the live shape with `carto maps schema mapSettings`; apply the per-control mapping table from `app-absorption.md`.
8. **App analytical widgets → Builder `widgets[]`**: walk the app's widgets per the per-subtype "Where widgets live" map (`data.widgets[]` for Dashboards, `data.pages[].layouts[].widgets[]` for ExB, `data.values` / `data.draft` / `data.widgetOnScreen.widgets[]` for Web Mapping Apps). Translate each per the widget-mapping table — `pie-chart` → `pie`; `serial-chart` (single-series) → `timeseries` / `histogram`; `indicator` → `formula`; `list`/`table` → `table`; `range slider` → `range`; numeric/category filter → SQL parameter. Skip widgets the rubric flagged as not-available (these shouldn't appear if discover routed correctly; if one slips through, treat it as `arcade-skipped:`-style: record `Notes: app-widget-skipped: <type>` and continue).

### Phase 5 — Compose + validate

1. **Resolve dataset metadata for every layer** per [`references/dataset-config.md`](references/dataset-config.md). For each unique source FQN referenced by the map's layers:
   - `carto connections list --json` → resolve `connectionName` → `connectionId` UUID (cache per batch — same connection across the whole migration).
   - `carto connections describe <connection-name> <fqn> --json` → extract the **full column list** (`columns[].name`) and the **geometry column name**. Cache per FQN — if multiple layers reference the same source, describe once.
   - Build each `dataset` entry with:
     - `$ref` (UUID), `type: "table"` (or `"query"` if Arcade derived fields are needed)
     - `source` (FQN), `connectionId` (UUID), `connectionName` (string)
     - `geoColumn`, `columns` (**non-null string array including `geoColumn`**)
     - `format: "tilejson"`, `label`
     - **`color`: a hex string** like `"#7F3C8D"` (Builder's default purple). **NOT** an int array `[r, g, b]` and **NOT** a Postgres array literal — the column is `text`; int arrays get coerced to `text[]` form that Builder can't parse on read. Cycle through a small palette across datasets if there are several (e.g. `#7F3C8D` / `#11A579` / `#3969AC` / `#F2B701` / `#E73F74` / `#80BA5A` / `#E68310` / `#008695` by index mod 8).
     - **`queryParameters: null`** (NOT `[]`)
     - `aggregationExp: null`, `aggregationResLevel: null`, `spatialIndex: null`, `queryTemplate: null`, `sourceWorkflowNodeId: null`
     - `uniqueIdProperty`: **MUST be a column present in `columns[]`** — resolve from the source layer's `objectIdField`, normalize casing to match `columns[]`, fall back to `objectid`/`fid`/`id`/`oid` (whichever exists), else `null` with `Notes: no-unique-id-resolved`. **Never hardcode `"objectid"`** — stale value referencing a non-existent column makes that layer's tilejson SQL fail. See [`references/dataset-config.md`](references/dataset-config.md) `uniqueIdProperty` row and [`references/lessons.md`](references/lessons.md) "`uniqueIdProperty` must reference a column that exists"
   - **Never emit `dataset.columns: null`** — Builder 500s on view (verified failure; see `references/lessons.md`).
2. **Initialize top-level filter state**: set `keplerMapConfig.config.filters` to an **object keyed by dataset `$ref`**, with empty `{}` values per dataset: `{"<ds-1-ref>": {}, "<ds-2-ref>": {}, ...}`. **NOT** `[]` (the legacy kepler array shape — Builder's loader crashes on it; verified). See `references/dataset-config.md` "Top-level filter state".
3. **Popup settings — omit when source has no popups**: if `popupInfo` is null/absent on every source layer, **do not emit `keplerMapConfig.config.visState.popupSettings` at all** (not even `{layers: {}}` or `{layers: []}`). Migration faithfully reproduces source behavior. Only emit `popupSettings` when at least one source layer has a populated `popupInfo`, then follow [`references/popup-mapping.md`](references/popup-mapping.md).
4. **Normalize per-layer `visConfig` defaults** per [`references/renderer-mapping.md`](references/renderer-mapping.md) "Required non-null layer-config fields". After translating each layer's renderer, ensure these fields are non-null: `initialStrokeColor` (mirror `strokeColor`), `initialFillColor` (mirror `fillColor`), `opacity`, `radius`, `thickness`. Builder's layer init reads them and crashes on null even though the schema marks them optional. Verified failure mode.

5. **Apply kepler boilerplate defaults** per [`references/mapconfig-defaults.md`](references/mapconfig-defaults.md). Builder's loader requires the following to be present with specific shapes even on minimal maps:
   - **`keplerMapConfig.config.uiState`**: `{commentsVisible: true, controlsPaneOpen: false, descriptionOpen: false, descriptionPreview: false}`. Empty `{}` crashes Builder.
   - **`visState.animationConfig`**: `{currentTime: null, speed: 1}`. Not `null`.
   - **`visState.filters`**: `[]` (legacy array form inside visState — **different** from `config.filters` at the top level, which is the object form keyed by dataset id; both must be present).
   - **`visState.interactionConfig`**: `{brush: {enabled: false, size: 0.5}, coordinate: {enabled: false}, geocoder: {enabled: false}, tooltip: {compareMode: false, compareType: "absolute", enabled: true}}`. Not `null`, not `{}`.
   - **`visState.layerBlending`**: `"normal"`.
   - **`visState.splitMaps`**: `[]`. Not `null`.
   - **`basemapConfig`**: `{"styleId": "<id>"}` — **no `type` field for any basemap source**. `styleId` alone is sufficient for CARTO defaults, Google variants, and custom basemaps; Builder routes by id. Verified against manual Builder maps for each provider.
   - **`config.spatialFilter`**: `null` (or omit). **NEVER `{}`** — empty object crashes Builder with `TypeError: Cannot read properties of undefined (reading 'type')` inside an `Array.map`, rendered as an inline 500 page with no visible XHR error and no console output (TrackJS suppresses the throw). Validator and `create` both pass with `{}`. The MCIL2 Rates incident was traced to this one field. See `references/lessons.md` "`spatialFilter: {}` crashes Builder even with zero datasets".

6. Compose the full `keplerMapConfig` JSON. **Always fetch live schema** with `carto maps schema [section]` and validate fragment shapes inline; never hardcode kepler shapes (the schema is the source of truth — see `references/lessons.md` "Never hardcode kepler schema"). For everything the schema marks optional but Builder runtime requires, see `references/mapconfig-defaults.md` (config-level) and `references/renderer-mapping.md` (layer-level) — start from those defaults and modify.
7. **Title**:
   - Web Map entries: top-level `title` = source Web Map's title.
   - Simple-app entries: top-level `title` = the **app's** title (not the embedded Web Map's title) — that's the name the user knows the migrated artifact by.
8. **Tags**: `["From ArcGIS"]` on every migrated map. For simple-app entries, optionally append the app subtype as a second tag (`"From ArcGIS Dashboard"`, `"From ArcGIS Web Experience"`, `"From ArcGIS Web Mapping App"`) so the user can filter by source type in CARTO Workspace; this is informational and doesn't affect idempotency (the precheck still uses `From ArcGIS` only).
9. **Privacy**: leave `privacy` unset (Builder default = private). Record the source's `access` field as `Notes: source-access: <value>` so the user can re-share manually after review.
10. `carto maps validate /tmp/<slug>.json --json`. Iterate the translation until clean. If after 3 iterations the JSON still fails, mark `State: failed`, `Failure: <validation-error-summary>`.

### Phase 6 — Create + verify + record

1. `carto maps create < /tmp/<slug>.json --json` → capture the new map id AND the `warnings[]` array from the response.
2. **Inspect `warnings[]` before celebrating.** Any entry with a `code` mentioning rendering / dataset / columns (e.g. `DATASET_WONT_RENDER`, `INVALID_COLUMNS`) means the map was created but **won't render in Builder**. Mark `State: failed`, `Failure: <warning-code>: <warning-detail>`, log the full warning, continue to the next entry. **Do not proceed to screenshot or `done` state.** The screenshot's `light` engine (deck.gl `fetchMap`) is more forgiving than Builder's view path; a successful screenshot does NOT mean Builder will load the map. See `references/lessons.md` "`validate` accepts shapes that `create` quietly rejects" and "`dataset.columns: null` 500s Builder" for the historical incidents that led to this rule.
3. `carto maps screenshot <id> --render-engine light --json` → embed the resulting PNG path inline in chat per `carto-create-builder-maps`'s "Visual verification" rules. (Only reached when step 2 found no rendering warnings.)
4. Update manifest entry — same fields whether it lives under `## Web Maps` or `## Apps`: `State: done`, `Target URL: https://<tenant>/builder/<id>`, `Migrated at:` (UTC ISO 8601), plus all `Notes:` accumulated during translation. For simple-app entries, the entry stays under the Apps section (don't move it to Web Maps); the `Routing decision: builder` field tracks where it was routed.

### Phase 7 — Final summary + capture lessons

Print a structured chat summary, distinguishing the two source shapes:

- **Migrated — Web Maps** (count + URLs).
- **Migrated — simple apps** (count + URLs, with the app's source-type per entry: Dashboard / Web Experience / Web Mapping App).
- **Skipped** (per-entry reason — pre-existing migrated maps detected by idempotency precheck).
- **Failed** (per-entry `Failure:` line — `depends-on-unmigrated-data`, validation error, etc.).

If `SESSION_LESSONS.md` is non-empty, surface it with the maintainer / end-user follow-up paths (per `carto-arcgis-migrate-data/SKILL.md` Phase 5 protocol). If both Web Maps and simple-app sections are fully resolved, suggest invoking `carto-arcgis-migrate-services` next (or `carto-arcgis-migrate-apps` if any complex-app entries remain).

## Always-on rules

- **Consult `references/lessons.md` before writing any translation code.**
- **Consult `carto-agent-skills` (especially `carto-create-builder-maps`) before writing any `carto maps` invocation.** Don't trial-and-error flags. Don't hardcode kepler schema; fetch with `carto maps schema [section]`.
- **Every dataset gets `columns` populated explicitly** from `carto connections describe`. Never `null`, never empty. See [`references/dataset-config.md`](references/dataset-config.md) for the full shape. Missing `columns` produces a map that validates cleanly, screenshots cleanly, and 500s in Builder.
- **`carto maps create --json` warnings are not cosmetic.** Inspect `warnings[]` after every `create`; any rendering-related warning (`DATASET_WONT_RENDER` / `INVALID_COLUMNS` / similar) means the map is broken and the entry must be marked `failed`. A successful screenshot is necessary but not sufficient.
- **Simple-app entries follow the same translation pipeline as Web Maps**, with one extra step (Phase 4 #5–6): the app overlay (map controls + analytical widgets). See [`references/app-absorption.md`](references/app-absorption.md). Trust the `Routing decision:` field on each manifest entry — don't second-guess discover's rubric.
- **Every migrated map gets `tags: ["From ArcGIS"]`.** Sole signal for the idempotency precheck and customer-side filtering.
- **Every migrated map is private.** The source ArcGIS access level is recorded in `Notes:` for manual re-sharing review. Never set `privacy: shared` or `privacy: public` automatically.
- **Pass `--json`** on every `carto` invocation; pass `&f=json` on every ArcGIS REST call.
- **Idempotency**: `done` entries skipped silently. `failed` entries retried. Title-and-tag precheck — never title alone.
- **Capture new lessons as you go.** Append to `SESSION_LESSONS.md` whenever a non-obvious pattern surfaces (renderer corner case, schema drift, basemap mismatch, Arcade construct that should be supported but isn't yet).
- **Never abort the batch on per-item failures**, except CARTO auth expiry (parse `--json` 401/403, leave the in-progress item alone, stop the batch, tell the user to `carto auth login` and re-invoke).
- **One file per item**: `/tmp/<webmap-slug>.json`. Don't share intermediate files between Web Maps.
- **Update the manifest on every state transition.** A crash mid-batch must leave the manifest reflecting reality.

## When in doubt

- Layer with an unsupported renderer (heatmap, dotDensity, temporal, predominance)? Apply simple-color fallback per the renderer-mapping reference; record `Notes: renderer-fallback: <type>`.
- Web Map references a Feature Service in a different ArcGIS org (external dependency not in the manifest)? Mark `failed` with `Failure: external-dependency: <layer-url>`.
- Source basemap is a custom tile service not in [`references/basemap-mapping.md`](references/basemap-mapping.md)? Use `voyager` as fallback and record `Notes: basemap-fallback: <source-name>`.
- `carto maps validate` returns a Tier-1 error after 3 iterations? Mark `failed` with the error summary and continue to the next Web Map. Don't loop indefinitely.
- Auth expires mid-batch? Stop the batch (per the lessons file); user runs `carto auth login` then re-invokes the skill.
