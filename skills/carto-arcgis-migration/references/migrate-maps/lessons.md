# Lessons from the field — maps migration phase

Patterns discovered during real Web Map → Builder map migrations. The agent **reads this file before writing any translation code** and follows the documented patterns. New lessons surface via `SESSION_LESSONS.md` at end-of-batch and merge here when the user confirms (maintainer-only step — see [`../migrate-data/lessons.md`](../migrate-data/lessons.md) for the merge protocol).

The point: every renderer corner case, popup-shape surprise, and Arcade quirk that bit a previous run — captured once, never re-discovered. Where a fix has a canonical code helper, it lives in the topic file (`renderer-mapping.md`, `marker-upload.md`, `dataset-config.md`, `mapconfig-defaults.md`); this file records the incident, the symptom, and the pointer.

---

## Auth handling

### CARTO session expired during a long batch

Same as [`../migrate-data/lessons.md`](../migrate-data/lessons.md) "CARTO session expired": `carto maps create` / `validate` / `carto sql query` returning 401/403 in `--json` stops the **entire batch** (not just the current item). Leave the in-progress Web Map `in-progress`; resumption after `carto auth login` + re-invocation is handled by the manifest precheck. Parse `payload["error"]["code"] in (401, 403)` from stdout — don't rely on exit code alone.

---

## Schema fetching

### Never hardcode kepler schema — the validator is the gate

The keplerMapConfig schema evolves. Always fetch live with `carto maps schema [section]` before composing (`layer.tileset`, `visualChannels`, `visConfig`, `popupSettings`, `widgets.formula`, `basemap`, `dataset`). If a reference in this skill disagrees with the live schema, **the schema wins**, and `carto maps validate` is the authoritative gate. Run `validate` after every meaningful edit, not just before `create` — it's a fast Tier-1 offline check and most renderer-translation bugs surface there.

### `validate` accepts shapes that `create` quietly rejects

`carto maps validate` is a Tier-1 offline structural check; it does NOT enforce every constraint the create-time tilejson generator does. Any time `create` returns a `warnings[]` entry (especially `DATASET_WONT_RENDER`), treat it as a schema-shape mismatch the validator missed — fetch the live schema for the offending section and check what the compose script emits against it. Real case: **`dataset.columns` shape changed in CLI v0.7.0** — items are plain strings (column names), not `{name, type}` objects. Both pass `validate`; only strings produce a valid tilejson (the object form yields `DATASET_WONT_RENDER` with `detail: "Invalid columns parameter"` and the layer renders zero features). Caught on the TfL Bus Route Overlap Map re-migration after a v0.6.3 → v0.7.0 upgrade.

```python
# v0.7.0+
dataset["columns"] = ["direction", "rte_run", "route", "status", "objectid", "shape__length"]
# Old (now broken): [{"name": "direction", "type": "string"}, …]
```

### Inspect `warnings[]` from `carto maps create` before declaring done

`carto maps create --json` returns a `warnings[]` array. Parse it on every create: any code mentioning rendering / dataset / columns (`DATASET_WONT_RENDER`, `INVALID_COLUMNS`) → the entry is `failed`, not `done`. A `--render-engine light` screenshot success is NOT a quality gate — it's too forgiving. Note: `warnings[]` is a create-time response field, NOT stored on the map (`carto maps get` doesn't surface it) — capture at create-time or lose it.

---

## Builder runtime requires kepler boilerplate the schema marks optional

Builder's loader iterates many `keplerMapConfig.config` / `visState` fields during initial load and crashes (full-page 500) when they're `null` / `{}` / absent, even though the schema marks them optional. `validate`, `create`, and the `light`-engine screenshot all pass; only Builder breaks, only at view time. **Never compose `keplerMapConfig` from scratch using only the schema's `required` fields — start from a manually-created Builder map's known-good structure.** The canonical Python helper is in [`mapconfig-defaults.md`](mapconfig-defaults.md); the fields it guards (all verified missing-field crashes on MCIL2 / TfL Bus Routes):

- `config.uiState` — `{commentsVisible, controlsPaneOpen, descriptionOpen, descriptionPreview}`. Empty `{}` crashes panel init.
- `config.filters` — **object keyed by dataset `$ref`** with `{}` values (`{ds["$ref"]: {} for ds in datasets}`), NOT the kepler-legacy array `[]`. Builder iterates `Object.keys(...)`; the array form crashes the loader. Tolerated by `validate` + `fetchMap`.
- `config.spatialFilter` — explicit `null`, **never `{}`**. See dedicated lesson below.
- `visState.animationConfig` — `{currentTime: null, speed: 1}`.
- `visState.filters` — `[]` (legacy array form inside visState — **different** from `config.filters`; both must exist).
- `visState.interactionConfig` — `{brush, coordinate, geocoder, tooltip}` with default sub-objects.
- `visState.layerBlending` — `"normal"`. `visState.splitMaps` — `[]`.
- `basemapConfig` — see [`basemap-mapping.md`](basemap-mapping.md) and [`mapconfig-defaults.md`](mapconfig-defaults.md) for the current `type`/`styleId` shape.

### Layer `visConfig` has its own non-null requirements

Same "schema-optional, runtime-required" pattern inside `visState.layers[].config.visConfig`: `initialStrokeColor` / `initialFillColor` must be RGB int arrays (default to `strokeColor` / `fillColor`); `opacity` / `radius` / `thickness` must be numbers, not `null`. Verified: a uniqueValue-rendered map screenshotted correctly but Builder 500'd — only `initialStrokeColor: null` differed from a manual map. Canonical `normalize_layer_defaults` helper in [`renderer-mapping.md`](renderer-mapping.md) "Required non-null layer-config fields".

### `spatialFilter: {}` crashes Builder even with zero datasets

`config.spatialFilter` is schema-typed `anyOf [object, null]`. Builder UI writes `null`; the agent often defaults to `{}`. **These are NOT equivalent.** With `{}`, Builder's runtime accesses `.geometry.type` on undefined inside an `Array.map`, throws `TypeError: Cannot read properties of undefined (reading 'type')`, and the `ErrorBoundary` shows the inline 500 page. The most pernicious "validator passes, runtime crashes" trap caught so far:

- ✅ `validate`, `create` (empty `warnings[]`), and `--render-engine light` screenshot all pass; tilejson fetches succeed.
- ❌ Builder shows inline 500 at `/builder/<id>` (URL unchanged). **No** failed XHR, **no** console error (workspace-www's TrackJS silences `componentDidCatch`'s log with `console: { display: false }`).

Bug is independent of layers/datasets/popups — an empty map still crashes if `spatialFilter: {}`. Prevention: `apply_mapconfig_defaults` always emits `spatialFilter: null` ([`mapconfig-defaults.md`](mapconfig-defaults.md)). Hotfix an already-migrated map by patching `.keplerMapConfig.config.spatialFilter = null` and `carto maps update <id> --file /tmp/fix.json --allow-kepler-replace --json`.

**Capturing a swallowed exception** when this kind of silent crash happens — wrap `console.error` before navigating to the map, then read `window.__caught` after the 500:

```js
const __orig = console.error;
window.__caught = [];
console.error = function (...a) {
  window.__caught.push({ t: new Date().toISOString(), args: a, stack: new Error().stack });
  return __orig.apply(console, a);
};
```

**Bisection** when symptoms are opaque: strip config fields one at a time via `carto maps update --allow-kepler-replace` until the 500 disappears; start by setting `visState.layers = []` to localise shell-vs-layer. The MCIL2 Rates incident (May 2026) isolated `spatialFilter: {} → null` after seven refreshes.

### Diff against a manually-created Builder map to find Builder-only shape bugs

When `fetchMap` (screenshot light engine) works but Builder crashes, the bug is in a field Builder reads that `fetchMap` doesn't: `filters`, `popupSettings`, `widgets`, `sqlParameters`, `mapSettings`, `interactionConfig`, `agent`, `description`. The source of truth is what Builder UI writes:

1. Builder UI: New map → add the same dataset(s) → save with no customization.
2. `carto maps get <good-id> --json > /tmp/good.json`; same for the bad map.
3. `diff <(jq -S '.keplerMapConfig.config' /tmp/good.json) <(jq -S '.keplerMapConfig.config' /tmp/bad.json) | head -120`.
4. Every differing line (excluding ids, timestamps, lat/lon precision, source FQN) is a shape candidate — fix structural mismatches (object-vs-array, present-vs-absent, populated-vs-empty) first.

Found 3 distinct bugs in one session (filters shape, color shape, presence of `popupSettings` when source had none). Faster than reasoning from the validator's silence.

---

## Datasets

### `dataset.columns: null` 500s Builder even though everything else passes

`dataset.columns: null` (or missing) is **the** silent map killer. `validate` accepts it; `create` may or may not emit `DATASET_WONT_RENDER` depending on CLI version; the `light` screenshot succeeds (deck.gl `fetchMap` infers columns from `/stats`). Builder 500s on view — the tilejson generator can't build a tile request without an explicit column list. **Always populate `dataset.columns` explicitly**, including `geoColumn`, via `carto connections describe <conn> <fqn> --json | jq -r '[.columns[].name]'`. Full shape + post-create repair recipe in [`dataset-config.md`](dataset-config.md). Real incident: an MCIL2 / TfL Bus Routes map migrated cleanly, screenshotted fine, every layer 500'd — every dataset had `columns: null`.

### `uniqueIdProperty` must reference a column that exists

`dataset.uniqueIdProperty` pointing to a column not in `columns[]` makes the tilejson SQL throw server-side (maps-api 500 on that tile fetch) — usually a stuck layer rather than a full-page 500, but still a broken map. Resolve per-dataset against the actual `columns[]`; **never hardcode `"objectid"`** — File Geodatabase / Shapefile / GeoPackage extracts frequently land with `fid` after the ArcGIS → GeoParquet → warehouse round-trip (the MCIL2 Isle of Dogs dataset was a real example). Full resolution order in [`dataset-config.md`](dataset-config.md). Diagnose an existing map via `/maps/<id>/datasets` and check `hasUid: (.columns | index(.uniqueIdProperty) != null)`; hotfix with `carto maps datasets update <map-id> <dataset-id> --unique-id-property <real-column> --json`.

### ArcGIS field names don't survive the warehouse import verbatim

The "never hardcode" rule extends to **every** column reference the composer emits: `visualChannels.*Field.name`, `popupSettings.layers.<id>.click.fields[].name`, `textLabel[].field.name`, Arcade-derived SQL. `carto import` normalizes ArcGIS field names, so mirroring `drawingInfo.renderer.field` directly can bind to a non-existent column — the layer then renders in its fallback color with no visible error (`validate` passes, `create` returns empty `warnings[]`, screenshot looks right except the binding is missing).

Two normalizations seen on real migrations:

- **Lowercasing**: `OBJECTID` → `objectid`, `Shape__Length` → `shape__length`.
- **SQL-keyword-suffix stripping**: ArcGIS Pro appends `_` to fields colliding with reserved words (`COUNT` → `COUNT_`); the import normalizer strips the trailing underscore, so `COUNT_` lands as `count`. Verified on the TfL Bus Route Overlap Map — both layers' classBreaks renderer used `field: "Count_"`; a `colorField.name: "count_"` binding would silently render all 46K polygons in the fallback fill.

**Prevention** — build a resolver early in Phase 4/5 and pass every column reference through it. `connections describe` (already mandatory in C.5 #1 for `dataset.columns`) is the source of truth for every downstream column reference too:

```python
def resolve_column(source_field, warehouse_cols):
    s = source_field.lower()
    by_lower = {c.lower(): c for c in warehouse_cols}
    if s in by_lower:
        return by_lower[s]
    if s.endswith("_") and s.rstrip("_") in by_lower:   # SQL-keyword suffix
        return by_lower[s.rstrip("_")]
    return None
```

If it returns `None`, record `Notes: column-not-resolved: <source-field>` and drop that field or fall back — **don't** silently emit the lowercased source name and hope.

### `dataset.color` is a hex string — the `text` column type matters

The `datasets.color` Postgres column is **`text`** with `NOT NULL`. So it **cannot** be `null` and **cannot** be a JSON int array like `[128, 128, 128]` (the API coerces int arrays to a `text[]` literal-as-string that Builder's read deserializer can't parse). Correct shape: a hex string like `"#7F3C8D"`, cycling a small palette across datasets so multi-dataset maps don't all look identical:

```python
PALETTE = ["#7F3C8D", "#11A579", "#3969AC", "#F2B701",
           "#E73F74", "#80BA5A", "#E68310", "#008695"]
dataset["color"] = PALETTE[i % len(PALETTE)]
```

Verified against the MCIL2 / TfL Bus Routes manual map — Builder's "New map" picks `#7F3C8D` by default and stores it cleanly. (Older lessons that said `dataset.color` is an int array `[128,128,128]` were wrong for the migration path — the `text` column is the constraint.)

### Trust the warehouse for geometry type, not the source

ArcGIS Feature Services don't always report geometry type at the layer level, and `esriGeometryType` may not survive extraction. Use the migrated DW table's actual type via `carto connections describe <conn> <fqn> --json`: `point`/`line`/`polygon` → `tileset` of that geometry; `h3`/`quadbin` (pre-aggregated) → `h3`/`quadbin` layer. If it returns generic `geometry` or no type, run `SELECT ST_GeometryType(geom) FROM <fqn> LIMIT 1`. Don't guess.

---

## Color scales — numeric categoricals need `custom` colorMap, not `ordinal`

When the source renderer is `uniqueValue` on a column the warehouse types as numeric (`integer`/`real`), **do not use `colorScale: "ordinal"`.** The schema accepts ordinal (so `validate` passes and the map renders at create-time), BUT Builder's Style panel exposes only continuous scales for numeric color fields (`quantile`/`quantize`/`logarithmic`/`custom`). The instant a user opens the Style panel, Builder silently re-fits the binding — the pinned value→color mapping is gone. `custom` is the only scale Builder's numeric-UI offers with per-bin pinning.

**Correct shape** — thresholds live in `colorRange.colorMap` (a list of `[upper_threshold, color]` pairs, **N entries**, last threshold `null` = "no upper bound"). `colorDomain` is **omitted entirely** — Builder doesn't read it for custom scale. For integer values `1..N`, thresholds at `[1.5, 2.5, …]`:

```python
values = [1, 2, 3, 4, 5, 6, 7, 8]
colors_hex = ["#9a9cce", "#bccff5", "#8ff5f5", "#94fa64",
              "#fafa94", "#f5bca8", "#f58f8f", "#c79494"]
color_map = [[v + 0.5, c] for v, c in zip(values[:-1], colors_hex[:-1])] + [[None, colors_hex[-1]]]

layer["config"]["visConfig"]["colorRange"] = {
    "name": "PTAL bands (ArcGIS)",
    "type": "qualitative",   # colorRange.type enum is sequential/qualitative/diverging — NOT "custom"
    "category": "Custom", "colors": colors_hex,
    "colorMap": color_map,
}
layer["visualChannels"] = {
    "colorField": {"name": "average_ptal_2023_num", "type": "integer"},
    "colorScale": "custom",  # signals to read colorRange.colorMap thresholds; NO colorDomain
}
```

Each entry reads "if `value < upper_threshold`, render `color`"; the `null` entry catches everything else. **Non-integer discrete numerics**: thresholds at midpoints between sorted unique values.

Established on the TfL Average PTAL LSOA migration (`average_ptal_2023_num`, integer 1..8): (1) `colorField` typed `"string"` → all polygons grey; (2) `"integer"` + `ordinal` + `colorMap` → rendered correctly until the user opened Style panel, binding gone; (3) `custom` + `colorDomain` (N+1) → Builder crashed; (4) `custom` + `colorRange.colorMap`, no `colorDomain` → working. Detect via `renderer.type == "uniqueValue"` AND warehouse col type numeric.

**Anti-patterns**: `ordinal` on a numeric field (breaks on first edit); `colorDomain` populated under `custom` (crashes or ignored); `colorRange.type: "custom"` (not in the enum — use `qualitative`); swapping to a string sibling column (doesn't generalize). **String columns are safe with `ordinal`** — Builder's UI for string color fields exposes ordinal as primary; use `colorRange.colorMap` of `[value, color]` pairs, all values present, no `null` sentinel. The trap is exclusively numeric columns.

**Caveat** — Builder's legend shows the threshold ranges (`< 1.5`, `1.5 – 2.5`, …) not the source `uniqueValueInfos[].label` strings. No JSON-level fix ships both correct binning AND source labels on a numeric color field; binding is the correctness gate, labels are a manual follow-up.

---

## Layer order — ArcGIS and kepler use OPPOSITE array conventions

**Same array shape, opposite semantics.** ArcGIS `operationalLayers[]`: `[0]` is the **bottom** of the visual stack (last element = top). kepler `visState.layers[]`: `[0]` is the **top** (last element = bottom). A composer that copies `operationalLayers[]` into `visState.layers[]` in source order inverts every layer's z-position — translucent choropleths end up on top of point layers, reference outlines end up buried.

**Hard to catch from screenshots**: with translucent layers (opacity 0.5–0.85, common for choropleths) the blend is roughly commutative, so an inverted screenshot looks similar to the source. The reliable diagnostic is **comparing the layer-panel order in Builder against the AGOL map's panel** (AGOL panel top-down = Builder panel bottom-up; if both show the same top-down sequence, the migration is flipped).

**Fix**: emit `visState.layers` as the **reverse** of the flattened source `operationalLayers`. GroupLayers expand into sublayers in source order, then the whole flat list reverses:

```python
def flatten_operational_layers(ops):
    flat = []
    for l in ops:
        if l.get("layerType") == "GroupLayer" and l.get("layers"):
            flat.extend(flatten_operational_layers(l["layers"]))
        else:
            flat.append(l)
    return flat

source_flat = flatten_operational_layers(webmap_json["operationalLayers"])
kepler_layers = [translate_layer(l) for l in reversed(source_flat)]  # reverse for kepler's convention
```

The reversal is the only structural transformation for ordering; per-layer rendering/popups/labels are unchanged, and it fixes popupSettings naturally (keys are `layer.id`s, not positions). Caught on the TfL Average PTAL LSOA migration — PTAL polygons at source index 0 (bottom in AGOL) landed at Builder index 0 (top), sitting over the bus stops and stations. Don't preserve source array order "for traceability" — nothing downstream reads it as an identifier.

---

## Marker icons

The full detect → acquire → dedup → upload → reference → fallback flow, with all code helpers, lives in [`marker-upload.md`](marker-upload.md). Key facts that bit real migrations:

- **There is no `carto maps markers` CLI subcommand.** Marker assets upload via a multipart `POST /assets` to the workspace API — `type=mapMarker` (**camelCase** — `MapMarker` is 400-rejected), `file=<binary>`, returns `{id, url}`. Permission: `write:maps`. Accepted extensions: `png`, `svg` only (convert JPEG/GIF via PIL). Persist the asset **`id`**, not the presigned `url` — Builder's serializer hydrates a fresh 7-day `customMarkersUrl` from the id on every map read.
- **Prefer `imageData` over `url`** on `esriPMS` — always reachable, no auth/network dependency. `CIMPictureMarker` URLs are usually `data:` URIs — decode the base64 directly (no HTTP fetch).
- **Content-hash dedup** (`out/markers/.cache.json`, sha256 16-char prefix) uploads each unique icon once across layers and survives re-runs. CIM- and `esriPMS`-extracted icons with the same bytes → same hash → same single upload.
- **Header-sniff before trusting `contentType`** — ArcGIS sometimes mislabels (National Rail's PNG was declared `image/jpeg`; the workspace-api 400s on the mismatch). Sniff `\x89PNG` / `<svg` / `\xff\xd8\xff`.
- **`radius` is the rendered icon-size knob when `customMarkers: true`**, NOT `customMarkerSize` (a legacy mirror current Builder ignores). Set both, `radius` as source of truth. Symptom: `customMarkerSize: 24` renders at ~12 px (the leftover `radius` default). Verified on TfL PTAL LSOA.
- **Multi-color icons need BOTH `customMarkersId` (uploaded asset) AND `visConfig.filled: false`.** Kepler's TileLayer applies its `getFillColor` tint only when `filled` is truthy; with `filled: true` every non-transparent pixel is replaced by `layer.config.color` and the icon collapses to one shade. Either fix alone still renders monochromatic. Brand color goes in `strokeColor` (Builder's sidebar chip uses it when fill is off). TfL PTAL LSOA rounds 5–7 established this (round 6 proved it's a color REPLACE, not a multiplicative tint).
- **Pad non-square PNGs to square at acquisition time** (transparent fill, `max(w,h)`) — kepler's icon layer has a single size knob, so deck.gl squashes a 2560×1611 PNG into a 24×24 box. Compute the content-hash AFTER padding. PIL helper in [`marker-upload.md`](marker-upload.md); fall back to raw bytes + a `Notes:` if PIL is missing.
- **Categorical icon binding isn't universal** — fetch `carto maps schema layer.tileset --json` and check for `customMarkersField` + `customMarkersRange.markerMap[]` before emitting. When absent, collapse to a single icon and record `Notes: uniqueValue-icons-collapsed-to-single (<N> distinct)`.
- **CARTO auth expiry applies to marker uploads** — a 401/403 on `POST /assets` stops the batch (same as `carto maps create`); leave the Web Map `in-progress`.

---

## Labels

### `labelingInfo` lives at `layerDefinition.drawingInfo.labelingInfo`, not `layerDefinition.labelingInfo`

Two paths look like they could hold label config: `layerDefinition.labelingInfo` (usually empty `[]` on WebMap overrides) and `layerDefinition.drawingInfo.labelingInfo` (**where halo'd labels actually live** in modern WebMaps and CIM-symbol layers). A composer reading only the first silently skips all labels — `validate`/`create`/screenshot pass, but Builder shows icons without station names. Always read `(ld.get("drawingInfo") or {}).get("labelingInfo")` first, then `ld.get("labelingInfo")`, then the FeatureServer's own `drawingInfo.labelingInfo`. Caught on the TfL PTAL LSOA re-migration.

### Label vertical placement: `alignment` drives it, NOT `offset`

For `AboveCenter`, the naive `alignment: "center"` + `offset: [0, -(size+6)]` **doesn't work** — Builder anchors text at its center on the data point regardless of offset, so the label sits on top of the icon. **The fix is `alignment`** (Builder/kepler reads it as "where the label sits relative to the point", NOT the deck.gl `getAlignmentBaseline` "which edge anchors" semantic):

| `alignment` | Where label appears |
|---|---|
| `"top"` | ABOVE the data point |
| `"center"` | ON the data point (overlay) |
| `"bottom"` | BELOW the data point |

So `AboveCenter → "top"`, `BelowCenter → "bottom"`, `CenterCenter → "center"`. **Leave `offset: [0, 0]`** — even ±4 px visibly detaches the label. Easy to get backwards (the first TfL PTAL LSOA round-4 fix had `AboveCenter → "bottom"`); always verify in Builder, not the light-engine screenshot (text doesn't render there).

### Source label font sizes don't always render well at city zoom

ArcGIS publishers tune fonts for print; deck.gl renders them smaller. Accept a per-layer `font_size_override` and bump layers where the source's 9-px label disappears (TfL stations 9 → 12, retail "site name" 7 → 10; dense single-glyph labels like Bus Stops' `POINT_LETTER` can go to 8). Extract the field via `re.match(r'^\$feature\["?(\w+)"?\]$', expr) or re.match(r"^\[(\w+)\]$", expr)`, lower-case it, then build the entry. Skip non-bare-field expressions with `Notes: label-skipped: <expr>` (they'd need Arcade-to-SQL per [`arcade-translation.md`](arcade-translation.md)).

### Plain-circle marker with a centered label needs floors: `radius >= 10`, label `size >= 10`

When a point layer renders as a plain circle (no `customMarkers`) AND has a `textLabel[]` with `alignment: "center"` (label **inside** the circle), Builder needs the circle big enough to contain the label and the label big enough to read. Source print-tuned sizes (4–6 px radius, 6–7 pt font) clip the label or leave it illegible. Floors when **both** hold — point tileset with default circle, and ≥1 `textLabel` with `alignment: "center"` + a resolved `field`:

```python
def normalize_circle_with_centered_label(layer):
    cfg = layer["config"]; vc = cfg.get("visConfig", {})
    if vc.get("customMarkers"):
        return layer
    tls = cfg.get("textLabel", [])
    if not any(t.get("alignment") == "center" and t.get("field") for t in tls):
        return layer
    if (vc.get("radius") or 0) < 10:
        vc["radius"] = 10
    for t in tls:
        if t.get("alignment") == "center" and (t.get("size") or 0) < 10:
            t["size"] = 10
    return layer
```

Caught on TfL Bus Stops (source font 6, composer emitted radius 4 / size 8). **Don't apply universally** — pair with the `visibilityByZoom` rule (Bus Stops zmin 15) so labelled circles only appear when few enough are on screen. `alignment: "top"`/`"bottom"` labels sit outside the marker — no clipping; the font-size-override rule covers their legibility.

### Visibility by zoom — translate `minScale`/`maxScale`

Without it, every point layer renders at every zoom and the city view becomes a sea of dots. Convert scale denominators to kepler zoom via `zoom = log2(559082264 / scale)`; read BOTH the WebMap's `layerDefinition.minScale` (override, wins) AND the FeatureServer layer's own `minScale`. Full helper in [`renderer-mapping.md`](renderer-mapping.md) "Visibility by zoom". TfL needed it: stations `300000 → zmin 11`, National Rail `55667 → 14`, Bus Stops `25000 → 15`.

---

## Renderer fallbacks

- **Heatmap** is not Builder-native at render time (Builder's `heatmapTile` needs pre-generated tilesets). Fall back to simple-color; `Notes: renderer-fallback: heatmap (use h3/quadbin layer manually for parity)`.
- **dotDensity** has no clean analogue (needs per-dot rows the source doesn't provide). Fall back + note.
- **Multi-field `uniqueValue`** (`field1`+`field2`+…): Builder binds one field. Fall back to `field1`; `Notes: renderer-fallback: uniqueValue multi-field collapsed to <field1>`.
- **Empty WebMap renderer + FeatureServer-side `esriPMS`/`CIMPictureMarker` icon**: instead of a generic grey circle, sample the icon's dominant opaque color for the fallback circle fill (or map to a known brand color — TfL bus red `#dc241f`, Underground red `#e4001b`). Document the choice in `Notes:`. Caught on TfL Bus Stops (empty WebMap renderer, red FeatureServer icon, migration emitted grey).

```python
from PIL import Image
from collections import Counter
import io, base64

def dominant_color(b64_image):
    img = Image.open(io.BytesIO(base64.b64decode(b64_image))).convert("RGBA")
    pixels = [img.getpixel((x, y))
              for x in range(0, img.size[0], max(1, img.size[0] // 10))
              for y in range(0, img.size[1], max(1, img.size[1] // 10))]
    opaque = [p[:3] for p in pixels if p[3] > 200]
    return list(Counter(opaque).most_common(1)[0][0]) if opaque else None
```

---

## Popups

### Live `popupSettings.layers` is a layer-id-keyed map, not a `properties[]` array

The live schema (`carto maps schema popupsettings --json`) keys `layers` by **layer id** with `{ enabled, hover: {style, fields, templateMode}, click: {style, fields, templateMode} }`; each `fields[]` entry is `{ name, customName?, format, … }` where `format` is a **d3-format string** (`",.2f"`, `"$,.2f"`, `"%Y-%m-%d"`), NOT a typed object. Translations:

- ArcGIS `{digitSeparator: true, places: 2}` → `",.2f"`; `{digitSeparator: false, places: N}` → `".Nf"`.
- `dateFormat: "shortDate"` → `"%-m/%-d/%Y"`; `"longMonthDayYear"` → `"%B %-d, %Y"`.
- `stringFieldOption: "richtext"` → `templateMode: true` with a `template` HTML string.

The keyed `layers.<id>` is the **layer's own id**, not the dataset `$ref`. `carto maps schema popupsettings --json` is the final tiebreaker.

### Click-only by default; source with no `popupInfo` → no popup

ArcGIS Web Maps are click-only (no hover-popup concept) — emit click config only, leave hover empty (`hover.enabled: false`). If a source layer has no `popupInfo`, **emit no popup** (leave it out of `popupSettings.layers.<id>` entirely — not an `enabled: false` entry, which still registers a click handler). Migration reproduces source behavior; the absence of `popupInfo` IS the prior config.

This **deliberately overrides** `carto-create-builder-maps`'s "emit popups by default" and its "5-field hover cap" — those are fresh-authoring rules. Adding hover behavior the user didn't configure changes the interaction model and backfires. Both were real v0.1.7 bugs (a one-layer Web Map got a hover popup); fixed v0.1.8. Rare exception: source `popupInfo` with explicit `popupShowsAt: "hover"` — detect that signal explicitly, else default click-only.

### Template braces and hidden fields

ArcGIS single-brace `{name}` → kepler double-brace `{{name}}`: run `re.sub(r"\{(\w+)\}", r"{{\1}}", s)` unconditionally on `popupInfo.title` / `description`. `fieldInfos[].visible: false` → exclude the field entirely from `fields[]` (don't emit it and rely on a UI toggle).

---

## Arcade

Supported subset and full translation flow in [`arcade-translation.md`](arcade-translation.md). Lessons:

- **`sqlglot` validation** catches most per-row-math translation bugs cheaply (`sqlglot.parse_one(sql, dialect=...)`). If not installed, continue and rely on `carto maps validate` — flag a one-line warning at start.
- **`Count($feature)`** is the only aggregation with no field argument (counts rows) → Builder `formula` widget with `column: null` (verify via `carto maps schema widgets.formula`). Don't translate as `Count($feature.OBJECTID)`.

---

## Basemaps

Full mapping in [`basemap-mapping.md`](basemap-mapping.md). Note the ongoing `type`-discriminator question: earlier `basemap-mapping.md` revisions recommended `google-satellite` (non-canonical) and omitted the provider `type`; the canonical Google styleIds are 1-word (`roadmap`, `satellite`, `hybrid`, `terrain`) plus the `google-positron`/`google-dark-matter`/`google-voyager` CARTO-on-Google blends. **Neither `validate` nor `create` catches a wrong basemap shape** — they render as a blank/fallback canvas at view time. `--render-engine light` is MapLibre-only and shows a CARTO fallback for ANY Google config; verify with `--render-engine full` and look for the Google logo + "Imagery © …" attribution. Google basemaps work without an org-level API key in current orgs — don't preemptively swap to `voyager`. Reconcile the `type` field against [`mapconfig-defaults.md`](mapconfig-defaults.md) and treat `carto-create-builder-maps/references/basemap.md` as the final source of truth.

---

## CIM symbols (ArcGIS Pro)

Full handling in [`cim-symbols.md`](cim-symbols.md). Lessons:

- **CIM colors use 0-100 alpha, not 0-255.** Forgetting this makes every map "fully transparent" — and `validate`/`create` accept it (alpha stays in-range). Build one `cim_color_to_rgb` + `cim_color_to_opacity` extractor ([`cim-symbols.md`](cim-symbols.md)); don't sprinkle raw `/255` math.
- **`CIMPictureMarker` URLs are usually `data:` URIs** (no separate `imageData` field) — decode the base64 directly. Rare external URLs fall back to the `esriPMS` fetch flow.
- **`CIMVectorMarker` / `CIMCharacterMarker` are out of scope to render faithfully** — collapse to a colored circle using the dominant fill color (note the loss: `cim-vector-marker-collapsed-to-circle` / `cim-character-marker-collapsed-to-circle`).
- **Multi-layer CIM symbols are common** (3–6 layers: halo + outline + main + secondary + shadow). Collapse: markers first (topmost wins), fills next, strokes last; `Notes: cim-multi-layer-collapsed (<N> → 1)`.
- CIM and `esriPMS` icons cache to the same `out/markers/.cache.json` store — same bytes, single upload.

---

## Screenshot mechanics

`carto maps screenshot <id> --render-engine light --json` is documented as Playwright-free (`fetchMap`, ~3–8 s), but on some CLI builds (e.g. `@carto/carto-cli` v0.6.3) the `light` path isn't wired up: the first call fails with `Executable doesn't exist at .../ms-playwright/...`, and a retry after `npx playwright install chromium` succeeds with `engine: "full"` despite `engineRequested: "light"`. During a batch: if `engineRequested !== engine`, treat it as a successful screenshot (don't loop); if the first call errors on the missing executable, run `npx playwright install chromium` (~92 MB, one-time) after warning the user, then retry. Detect via the error string or the `engine !== engineRequested` field.

---

## Widget composition

`carto maps schema widgets --json` returns each type's properties but **doesn't mark `isValid`, `buckets`, or the column-entry shape as required** — they're cross-field rules `carto maps validate` enforces separately, and they bite on first authoring of any histogram/table widget (caught on the first TfL Dashboard migration):

1. **Every widget needs `"isValid": true`** — without it Builder hides the widget and the panel shows *"select a field"*.
2. **`histogram` needs `"buckets": <int>`** (default `30`) — the tick loop `for (let i = 1; i < widget.buckets; i++)` renders empty when undefined.
3. **`table.columns` is `[{"field": "<col>"}, …]` objects, not bare strings** — bare strings round-trip through the API but the renderer throws on mount.

The [`app-absorption.md`](app-absorption.md) widget table carries these as a "Required boilerplate" column. Always run `carto maps validate` after composition — the validator is the source of truth. Detection: `issues[]` paths like `…widgets[<i>].isValid` / `.buckets` / `.columns[<j>]`.

---

## Process patterns

- **Consult `carto-create-builder-maps` first** — its `SKILL.md` documents the 6-phase authoring flow, "do silently, don't ask" defaults, the `keplerMapConfig` partial-vs-wholesale rule, and the screenshot rubric. Read it before writing translation logic. Don't `--help` to find flags — the carto-skills bundle has tested recipes for every `carto maps` invocation.
- **Reload Builder after a write** — Builder loads a map into client state once and doesn't subscribe to server events; tell the user to reload (`Cmd/Ctrl+R`) to see the migrated result.

---

## How to add a lesson

When the agent hits a non-obvious pattern during a run, append to `SESSION_LESSONS.md` using the template at the bottom of [`../migrate-data/lessons.md`](../migrate-data/lessons.md). At end of phase C.7 the same maintainer / end-user merge paths apply: maintainer appends here + bumps `version` in `skills/catalog.json` + `make sync && make validate` + commits; end-user keeps `SESSION_LESSONS.md` for the engagement and shares widely-useful patterns with the skill maintainer. **The agent never edits this cached file at runtime.**
