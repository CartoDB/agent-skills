# Lessons from the field — maps migration phase

Patterns discovered during real Web Map → Builder map migrations. The agent **reads this file before writing any translation code** and follows the documented patterns. New lessons surface via `SESSION_LESSONS.md` at end-of-batch and merge here when the user confirms (maintainer-only step — see `CLAUDE.md` and [`../migrate-data/lessons.md`](../migrate-data/lessons.md) for the merge protocol).

The point: every renderer corner case, every popup-shape surprise, every Arcade quirk that bit a previous run — captured once, never re-discovered.

---

## Auth handling

### CARTO session expired during a long batch

Same pattern as [`../migrate-data/lessons.md`](../migrate-data/lessons.md) "CARTO session expired" — `carto maps create`, `carto maps validate`, or `carto sql query` returning a 401/403 in `--json` output stops the entire batch (not just the current item). Leave the in-progress Web Map as `in-progress`; resumption after `carto auth login` and a re-invocation handles it cleanly via the manifest precheck.

**Detection in script** — same pattern as migrate-data:

```python
import json, subprocess, sys

result = subprocess.run(
    ["carto", "maps", "create", *flags, "--json"],
    capture_output=True, text=True
)
try:
    payload = json.loads(result.stdout)
    if payload.get("error", {}).get("code") in (401, 403):
        sys.exit("CARTO auth expired — stop batch")
except json.JSONDecodeError:
    pass
```

---

## Schema fetching

### Never hardcode kepler schema

The keplerMapConfig schema evolves. Always fetch live with `carto maps schema [section]` before composing JSON:

```bash
carto maps schema layer.tileset --json
carto maps schema visualChannels --json
carto maps schema visConfig --json
carto maps schema popupSettings --json
carto maps schema widgets.formula --json
carto maps schema basemap --json
```

If the references in this skill (`renderer-mapping.md`, `popup-mapping.md`, `basemap-mapping.md`) disagree with the live schema, **the schema wins**. `carto maps validate` is the authoritative gate.

### Validate iteratively, not just at the end

Run `carto maps validate <map.json> --json` after every meaningful edit during composition — not just before `create`. Validation is fast (Tier-1 offline checks) and catches structural issues immediately. Most renderer-translation bugs surface here.

### Layer `visConfig` has its own non-null requirements (`initialStrokeColor` etc.)

The same "schema-says-optional, runtime-says-required" pattern applies inside `visState.layers[].config.visConfig`. Specifically:

- `initialStrokeColor` must be an RGB int array (default to `strokeColor`'s value when the agent doesn't set it explicitly). `null` crashes layer init.
- `initialFillColor` — same pattern.
- `opacity`, `radius`, `thickness` — numbers, not `null`.

When generating a layer from an ArcGIS renderer translation, normalize the `visConfig` block by mirroring `initialStrokeColor` from `strokeColor` and `initialFillColor` from `fillColor` if they aren't already set. See [`renderer-mapping.md`](renderer-mapping.md) "Required non-null layer-config fields" for the canonical Python helper.

Verified failure mode: a uniqueValue-rendered Web Map migrated cleanly, screenshot rendered correctly, Builder crashed with full-page 500. Only `initialStrokeColor: null` in the layer config differed from a manually-created map. Same v0.1.18 fix as the config-level boilerplate.

### Builder requires kepler boilerplate even when the schema says optional

Builder's loader iterates a bunch of `keplerMapConfig.config` and `visState` fields during initial load. The schema marks many of them optional; the **runtime treats them as required** and crashes (full-page 500 error) when they're `null` / `{}` / absent. Verified missing-field crashes during MCIL2 / TfL Bus Routes migration:

- `keplerMapConfig.config.uiState` — must have `{commentsVisible, controlsPaneOpen, descriptionOpen, descriptionPreview}`. Empty `{}` crashes panel init.
- `visState.animationConfig` — must be `{currentTime: null, speed: 1}`. Time-slider widget reads it even when no temporal data.
- `visState.filters` — must be `[]` (legacy array form, inside visState — **different from `config.filters` at the top level**, which is the object form keyed by dataset id; both must exist).
- `visState.interactionConfig` — must have `{brush, coordinate, geocoder, tooltip}` with default sub-objects.
- `visState.layerBlending` — must be `"normal"`.
- `visState.splitMaps` — must be `[]`.
- `basemapConfig.type` — must be **omitted for ANY basemap source**, including Google and custom. `{"styleId": "<id>"}` alone is sufficient; Builder routes by id. Verified across CARTO defaults, Google variants, and custom MapLibre styles.

`carto maps validate` passes when these are missing. `carto maps create` passes. The `light`-engine screenshot renders correctly. Only Builder breaks, and only at view time.

**Lesson**: never compose `keplerMapConfig` from scratch using only the schema's `required` fields. Always start from a manually-created Builder map's known-good structure and modify only the layer/dataset specifics. See [`mapconfig-defaults.md`](mapconfig-defaults.md) for the canonical Python helper that applies these defaults.

### `keplerMapConfig.config.filters` must be an object keyed by dataset id, not an array

Builder's loader iterates `Object.keys(keplerMapConfig.config.filters)` to set up per-dataset filter state during initial load. If `filters` is an empty array `[]`, the loader can't iterate as an object and Builder shows its full-page 500 error.

**Required shape**: `{"<dataset-$ref>": {}, "<dataset-$ref>": {}, ...}` — one entry per dataset with an empty filter-state object.

```python
keplerMapConfig["config"]["filters"] = {ds["$ref"]: {} for ds in datasets}
```

**Wrong shape**: `[]` (kepler legacy array form). Tolerated by `carto maps validate` and `fetchMap` (deck.gl doesn't read filters), but crashes Builder's loader.

Verified by diffing a manually-created Builder map against the agent's migration on the MCIL2 / TfL Bus Routes engagement. Same v0.1.15 fix as the column-shape lessons. See [`dataset-config.md`](dataset-config.md) "Top-level filter state".

### `dataset.color` is a hex string — the `text` column type matters

The `datasets.color` Postgres column is **`text`** with a `NOT NULL` constraint. Two implications:

1. **Cannot be `null`** — the constraint rejects it. The earlier "omit or null" guidance was wrong.
2. **Cannot be a JSON int array** like `[128, 128, 128]`. The API write accepts the array (the column type coercion produces `{"128","128","128"}`, a Postgres `text[]` literal-as-string), but Builder's read deserializer can't parse it as a color — choking on shape.

**Correct shape**: a hex string like `"#7F3C8D"`. Cycle a small palette across datasets so multi-dataset maps don't all look identical in Builder's side panel:

```python
PALETTE = ["#7F3C8D", "#11A579", "#3969AC", "#F2B701",
           "#E73F74", "#80BA5A", "#E68310", "#008695"]
dataset["color"] = PALETTE[i % len(PALETTE)]
```

Verified against the MCIL2 / TfL Bus Routes manual map — Builder UI's "New map" picks `#7F3C8D` by default and stores it cleanly.

### Diff against a manually-created Builder map to find Builder-only shape bugs

When `fetchMap` (screenshot light engine) works but Builder crashes, the bug is in a field Builder reads that `fetchMap` doesn't: `filters`, `popupSettings`, `widgets`, `sqlParameters`, `mapSettings`, `interactionConfig`, `agent`, `description`. Static lessons aren't enough — the source of truth is what Builder UI writes when you build a similar map manually.

**Methodology**:

1. In Builder UI: New map → add the same dataset(s) the agent migrated → save with no customization.
2. `carto maps get <good-id> --json > /tmp/good.json`.
3. `carto maps get <bad-id> --json > /tmp/bad.json`.
4. `diff <(jq -S '.keplerMapConfig.config' /tmp/good.json) <(jq -S '.keplerMapConfig.config' /tmp/bad.json) | head -120`.
5. Every line that differs (excluding ids, timestamps, lat/lon precision, source FQN) is a shape candidate. Fix the most likely structural mismatches first (object-vs-array, present-vs-absent, populated-vs-empty).

This methodology found 3 distinct bugs in one diffing session: filters shape, color shape, presence of `popupSettings` when source had none. Faster than reasoning from the validator's silence.

### `dataset.columns: null` 500s Builder even though everything else passes

`dataset.columns: null` (or missing) is **the** silent map killer. Validator accepts it, `carto maps create` may or may not emit a `warnings[]` entry depending on CLI version, the `--render-engine light` screenshot succeeds because deck.gl `fetchMap` infers columns from `/stats`. Builder 500s on view because the tilejson generator can't construct a tile request without an explicit column list.

**Always populate `dataset.columns` explicitly** from the warehouse — see [`dataset-config.md`](dataset-config.md):

```bash
carto connections describe <conn-name> <fqn> --json | jq -r '[.columns[].name]'
```

Include `geoColumn` in the array. Don't trim; the cost of a few extra columns in tile payloads is negligible compared to a missing one breaking a popup or filter.

Real-world incident: an MCIL2-rates / TfL Bus Routes map migrated cleanly, screenshot looked right, every layer 500'd in Builder. Inspection revealed every dataset had `columns: null`. Manual patch via `carto maps update --datasets-mode replace` cleared it. The skill v0.1.14 fix is a Phase 5 step that runs `carto connections describe` per FQN before composing the dataset block.

### `spatialFilter: {}` crashes Builder even with zero datasets

`keplerMapConfig.config.spatialFilter` is schema-typed as `anyOf [object, null]`. **Builder UI writes `null`. The agent often defaults to `{}`. These are NOT equivalent.** With `{}`, Builder's runtime iterates the (presumed) GeoJSON Feature shape, accesses `.geometry.type` (or similar) on undefined, throws `TypeError: Cannot read properties of undefined (reading 'type')` inside an `Array.map`, and the React `ErrorBoundary` shows the inline 500 page.

This is the most pernicious "validator passes, runtime crashes" trap caught so far. Symptoms:

- ✅ `carto maps validate` returns `success: true`
- ✅ `carto maps create` returns `success: true` with empty `warnings[]`
- ✅ `carto maps screenshot --render-engine light` produces a correct screenshot (deck.gl `fetchMap` doesn't process `spatialFilter`)
- ✅ tilejson fetches succeed for every attached dataset
- ❌ Builder shows **inline 500 page** at `/builder/<map-id>` — URL doesn't change
- ❌ No failed network request visible (the throw is client-side, in the kepler reconciliation pass)
- ❌ No console error (workspace-www installs TrackJS with `console: { display: false }`, which monkey-patches `console.error` and silences `ErrorBoundary.componentDidCatch`'s log)
- ❌ No `stats` or `tile` requests in Network — the crash fires **between** tilejson response and the first downstream call

The bug is **independent of layers, datasets, popups, filters, color encodings**: an empty map (zero layers, zero datasets, no popupSettings) still crashes if `spatialFilter: {}` is set. Conversely, a fully-populated map with `spatialFilter: null` loads cleanly.

**Prevention** (the fix the skill ships in v0.1.20): the `apply_mapconfig_defaults` step always emits `spatialFilter: null`. See [`mapconfig-defaults.md`](mapconfig-defaults.md).

**Hotfix** for already-migrated maps:

```bash
TOKEN=$(jq -r ".profiles.\"$(jq -r .current_profile ~/.carto_credentials.json)\".token" ~/.carto_credentials.json)
TENANT_ID=$(carto auth status --json | jq -r .tenant_id)
API="https://workspace-${TENANT_ID}.app.carto.com"
curl -sS -H "Authorization: Bearer $TOKEN" "$API/maps/<map-id>" \
  | jq '.keplerMapConfig.config.spatialFilter = null | { keplerMapConfig }' > /tmp/fix.json
carto maps update <map-id> --file /tmp/fix.json --allow-kepler-replace --json
```

**Capturing the real exception** when this kind of swallowed crash happens — wrap `console.error` **before** navigating to the map:

```js
const __orig = console.error;
window.__caught = [];
console.error = function (...a) {
  window.__caught.push({ t: new Date().toISOString(), args: a, stack: new Error().stack });
  return __orig.apply(console, a);
};
```

After the 500 page appears, `window.__caught` holds the real `Error` with stack trace.

**Bisection methodology** when symptoms are this opaque: strip the kepler config field-by-field via `carto maps update --allow-kepler-replace` (one mutation per refresh) until the 500 disappears. The shell-vs-layer split (start by setting `visState.layers = []`) localises whether the bug is in a layer or in the config shell — for spatialFilter it's the shell, so layers can be ignored entirely. Then `diff` the broken shell against the working manual map's shell (`jq '.keplerMapConfig.config' | jq 'to_entries | map({k:.key, kind:(.value|type)})'`) to find the structural mismatch. Real-world incident: MCIL2 Rates map, May 2026 — this bisection isolated `spatialFilter: {} → null` after seven refreshes.

### `uniqueIdProperty` must reference a column that exists

A separate latent bug worth hardening against (NOT the cause of the spatialFilter incident above, despite a plausible initial misdiagnosis): `dataset.uniqueIdProperty` pointing to a column that isn't in `columns[]` causes the **tilejson SQL to throw server-side**. The maps-api returns 500 for that one tile fetch. The downstream effect on Builder is less catastrophic than the `spatialFilter` case — usually a stuck layer rather than a full-page 500 — but it still produces a broken map.

**Diagnostic** — verify every dataset's `uniqueIdProperty` is in its `columns[]`:

```bash
TOKEN=$(jq -r ".profiles.\"$(jq -r .current_profile ~/.carto_credentials.json)\".token" ~/.carto_credentials.json)
TENANT_ID=$(carto auth status --json | jq -r .tenant_id)
API="https://workspace-${TENANT_ID}.app.carto.com"
curl -sS -H "Authorization: Bearer $TOKEN" "$API/maps/<map-id>/datasets" \
  | jq '.[] | { id, source, uniqueIdProperty, hasUid: (.columns | index(.uniqueIdProperty) != null) }'
```

Any entry where `hasUid: false` is broken.

**Hotfix** — `carto maps datasets update` patches a single dataset:

```bash
carto maps datasets update <map-id> <dataset-id> --unique-id-property <real-column> --json
```

**Prevention at compose time** — resolve per-dataset against the actual `columns[]`; never hardcode `"objectid"` (see `dataset-config.md` `uniqueIdProperty` row for the full rule + worked example). File Geodatabase / Shapefile / GeoPackage extracts frequently land with `fid` instead of `objectid` after the ArcGIS → GeoParquet → warehouse round-trip — the MCIL2 Rates migration's Isle of Dogs dataset was a real example.

### ArcGIS field names don't survive the warehouse import verbatim — resolve every renderer / popup column reference via `connections describe`

The same "never hardcode" rule that applies to `uniqueIdProperty` extends to **every** column reference the composer emits: `visualChannels.colorField.name`, `visualChannels.strokeColorField.name`, `popupSettings.layers.<id>.click.fields[].name`, `textLabel[].field.name`, and any Arcade-derived SQL. ArcGIS field names are normalized during `carto import` and may not match the source verbatim, so a translation that mirrors ArcGIS's `drawingInfo.renderer.field` directly binds to a column that doesn't exist — the layer then renders in its fallback color with no visible error.

Two normalizations seen on real migrations:

- **Lowercasing**: every column lowercases. `OBJECTID` → `objectid`, `NAME` → `name`, `Shape__Length` → `shape__length`.
- **SQL-keyword-suffix stripping**: ArcGIS Pro appends `_` to fields whose names collide with SQL reserved words (`COUNT` → `COUNT_`, `ROW` → `ROW_`). The CARTO import normalizer strips the trailing underscore, so `COUNT_` lands in BigQuery as `count`. Verified on the TfL `Bus Route Overlap Map` migration — both layers' classBreaks renderer used `field: "Count_"` / `"COUNT_"` server-side; the warehouse columns were `count`, and a `colorField.name: "count_"` binding would silently render all 46K polygons in the fallback fill.

**Symptom**: `carto maps validate` passes, `carto maps create` returns empty `warnings[]`, `--render-engine light` screenshot looks right except the data binding is missing — every feature draws in the layer's default `fillColor` / `strokeColor`. No console error, no failed XHR. The bug is silent because the renderer falls back to constant color when the field can't be resolved.

**Detection** — after import, diff source field names against warehouse columns:

```python
import subprocess, json

service_fields = [f["name"] for f in arcgis_service_meta["fields"]]
desc = json.loads(subprocess.check_output(
    ["carto", "connections", "describe", connection_name, fqn, "--json"]))
warehouse_cols = [c["name"] for c in desc["schema"]]

# Any source field whose lowercase form isn't in warehouse_cols was renamed.
for f in service_fields:
    if f.lower() not in {c.lower() for c in warehouse_cols}:
        # f was renamed in the warehouse — resolve to actual name before using it.
        ...
```

**Prevention** — build a `source_field → warehouse_column` resolver early in Phase 4 / 5 and pass every column reference through it:

```python
def resolve_column(source_field: str, warehouse_cols: list[str]) -> str | None:
    """Map an ArcGIS field name to its warehouse column. Returns None if no match."""
    s = source_field.lower()
    by_lower = {c.lower(): c for c in warehouse_cols}
    if s in by_lower:
        return by_lower[s]
    # Try stripping trailing underscore (SQL-keyword suffix)
    if s.endswith("_") and s.rstrip("_") in by_lower:
        return by_lower[s.rstrip("_")]
    return None
```

Apply this everywhere the composer references a column by name. If `resolve_column` returns `None`, record `Notes: column-not-resolved: <source-field>` on the manifest entry and either drop that styling/popup field or fall back to a sensible default. **Don't** silently emit the lowercased source name and hope — that's the bug.

The `connections describe` call is already mandatory in Phase 5 #1 (for `dataset.columns`); this lesson extends its scope: the column list it returns is also the source of truth for every downstream column reference, not just the dataset block.

### Discrete numeric categorical columns need `colorScale: "custom"` + `colorRange.colorMap` with thresholds — `colorDomain` is NOT used

When the source ArcGIS renderer is `uniqueValue` on a column that the warehouse types as numeric (`integer` / `real`), the composer cannot use `colorScale: "ordinal"` to pin each value to a color. **The kepler schema accepts ordinal as a string enum value, so `validate` passes and the map renders correctly at create-time, BUT Builder's Style panel exposes only the four continuous scales for numeric color fields: `quantile` / `quantize` / `logarithmic` / `custom`.** The instant a user opens the Style panel, Builder silently re-fits the binding to one of those four — most commonly `quantize` — and the carefully-pinned value→color mapping is gone. There is no UI-level path to "set color X for value Y" on a numeric color field. `custom` is the only scale Builder's numeric-UI offers that supports per-bin pinning.

**Symptom progression on the TfL Average PTAL LSOA migration** (`average_ptal_2023_num`, integer 1..8 pinned to PTAL bands "1a","1b","2","3","4","5","6a","6b"):

1. First pass: composer typed `colorField` as `"string"` → silent binding failure, all polygons rendered in the fallback fill color (grey).
2. After retyping to `"integer"` with `colorScale: "ordinal"` + `colorMap`: binding worked, polygons rendered with PTAL colors at create-time and in `--render-engine light` screenshots. The map looked correct **until** the user opened Style panel in Builder — picker showed quantile/quantize/log/custom only, the ordinal binding was gone.
3. Switched to `colorScale: "custom"` with `colorDomain: [0.5, 1.5, …, 8.5]` (N+1 breakpoints): Builder crashed. The N+1 shape and the d3.scaleThreshold-style N-1 shape are both wrong — Builder doesn't read `colorDomain` for custom scale at all.
4. Correct shape (diffed against a manually-built custom-scale map in Builder): the thresholds live in `colorRange.colorMap`, not `colorDomain`. `colorDomain` is omitted entirely. **Working state.**

**Correct shape** — `colorMap` is a list of `[upper_threshold, color]` pairs with **N entries** (one per color). The final entry's threshold is `null`, the sentinel for "no upper bound" — it catches every value above the previous threshold. For integer values `1..N`, thresholds at `[1.5, 2.5, …, (N-1)+0.5]` followed by a `null` isolate each integer into its own bin:

```python
values = [1, 2, 3, 4, 5, 6, 7, 8]
colors_hex = ["#9a9cce", "#bccff5", "#8ff5f5", "#94fa64",
              "#fafa94", "#f5bca8", "#f58f8f", "#c79494"]

# N entries — each [upper_threshold, color]. Last threshold is null.
color_map = [
    [v + 0.5, c] for v, c in zip(values[:-1], colors_hex[:-1])
] + [[None, colors_hex[-1]]]

layer["config"]["visConfig"]["colorRange"] = {
    "name": "PTAL bands (ArcGIS)",
    "type": "qualitative",   # NOT "custom" — the colorRange.type enum is sequential/qualitative/diverging
    "category": "Custom",
    "colors": colors_hex,
    "colorMap": color_map,   # the threshold→color pinning lives here
}
layer["visualChannels"] = {
    "colorField": {"name": "average_ptal_2023_num", "type": "integer"},
    "colorScale": "custom",  # signals to read colorRange.colorMap thresholds
    # NO colorDomain — Builder reads thresholds from colorRange.colorMap only
}
```

Each colorMap entry semantically reads as: "if `value < upper_threshold`, render with `color`". For the last entry (threshold `null`), the rule is "everything else gets this color." Concretely for PTAL:

| colorMap entry | Catches values | Renders as |
|---|---|---|
| `[1.5,  "#9a9cce"]` | `value < 1.5` | PTAL 1 (1a) |
| `[2.5,  "#bccff5"]` | `1.5 ≤ value < 2.5` | PTAL 2 (1b) |
| `[3.5,  "#8ff5f5"]` | `2.5 ≤ value < 3.5` | PTAL 3 (2) |
| ... | ... | ... |
| `[7.5,  "#f58f8f"]` | `6.5 ≤ value < 7.5` | PTAL 7 (6a) |
| `[null, "#c79494"]` | `value ≥ 7.5` | PTAL 8 (6b) |

Builder's Style panel shows `Color scale: Custom` with the thresholds visible and editable. The user sees fractional break edges (1.5, 2.5, …) — slightly unusual but legible and clearly the right semantics. Each integer category gets exactly one color; the binding survives every UI round-trip.

**Why this works where ordinal doesn't**: Builder's scale-picker for numeric color fields is hard-gated to the four continuous scales — internally `numeric_field → continuous_only`. The schema-level `ordinal` value isn't reachable from the UI, so any map that ships with ordinal on a numeric field is in a state Builder can't restore after edit. `custom` is the ONLY scale Builder's numeric-UI offers that supports an explicit per-value pinning (via `colorRange.colorMap` thresholds).

**Why `colorDomain` is not used**: the kepler schema documents `colorDomain` for `quantize` / `custom` as "length is usually N+1 where N is the number of color classes" — but Builder's custom-scale renderer ignores it. The thresholds are sourced exclusively from `colorRange.colorMap`. Setting `colorDomain` with N-1 OR N+1 entries either crashes Builder or is silently ignored depending on shape; either way, the data shape Builder writes when a user manually builds a custom-scale map is `colorDomain` absent + `colorMap` populated. Diff a hand-built custom-scale map against the migrator's output as the canonical check.

**Detection**:

```python
def needs_custom_color_map(renderer, warehouse_col_type):
    if renderer.get("type") != "uniqueValue":
        return False
    return warehouse_col_type in (
        "number", "integer", "real",
        "INT64", "INTEGER", "FLOAT64", "NUMERIC",
    )
```

When this returns True, emit `colorScale: "custom"` + `colorMap` with N entries (last threshold `null`) + N colors in source order. **Do not emit `colorDomain`**.

**Non-integer discrete numerics** (e.g. categories at `1.5`, `3.0`, `4.5`): same approach, but compute thresholds as the midpoints between sorted unique values. `thresholds[i] = (values[i] + values[i+1]) / 2` for `i = 0..N-2`; last entry stays `[null, last_color]`.

**Caveat — legend chip labels**: Builder's default legend shows the threshold ranges (`< 1.5`, `1.5 – 2.5`, …, `≥ 7.5`) rather than the source `uniqueValueInfos[].label` strings ("1a", "1b", …). For migrations where the source labels matter, leave the threshold labels to manual relabeling in Builder. There's no JSON-level fix that ships both correct binning AND correct legend labels in one pass on a numeric color field. The binding is the data-correctness gate; legend labels are a follow-up.

**Anti-patterns**:

- **`colorScale: "ordinal"` on a numeric color field.** Passes validate, renders correctly at create-time, breaks on first user edit. The most common misdiagnosis: "but the schema accepts ordinal!" — yes, but Builder's UI doesn't.
- **`colorDomain` populated with thresholds under `colorScale: "custom"`.** Builder doesn't read it for the custom scale; either crashes or is silently ignored depending on length. Emit `colorMap` only.
- **`colorRange.type: "custom"`.** Not in the colorRange.type enum (`sequential` / `qualitative` / `diverging`). Validate may pass via `additionalProperties: true` but Builder's palette renderer doesn't recognize it. Use `qualitative` for categorical-ramp custom scales; `sequential` is for continuous ramps and pre-selects the `quantize` picker.
- **Swapping the binding to a string sibling column** (e.g. `<X>_cat` next to `<X>_num`). Works cosmetically when a friendly string sibling exists, but doesn't generalize — not every dataset has one, and the lesson the migrator needs is a rule that works on every uniqueValue+numeric pair. Use the custom-scale colorMap approach as the default; the string-sibling path is a hand-tuned post-migration cleanup the user can do in Builder if they prefer.

**Boundary case — string columns are safe by default.** Builder's UI for string color fields exposes `ordinal` as the primary scale; `colorScale: "ordinal"` + `colorDomain` works there as expected. The trap is exclusively on numeric columns. If the source renderer is `uniqueValue` on a column that the warehouse types as `string`, the natural ordinal path is correct (with `colorRange.colorMap` of `[value, color]` pairs, all values present — no `null` sentinel for strings).

### `dataset.color` is an int array, not a stringified curly-brace form

`dataset.color` should be `[128, 128, 128]` (RGB ints 0-255) or `null`. The legacy / wrong form emitted by some translations — `"{\"128\",\"128\",\"128\"}"` (curly-brace-wrapped strings) — is accepted cosmetically by Builder (the data-panel chip still renders grey) but is wrong per the kepler schema. Easiest correct behavior: omit the field, or set explicitly to `null`. If you want a specific chip color, use the int-array form.

### Inspect `warnings[]` from `carto maps create` before declaring done

`carto maps create --json` returns a response with a `warnings[]` array. Most teams discover this AFTER they've shipped a batch of broken maps and watched them 500 in Builder. The screenshot success isn't a quality gate — `--render-engine light` is too forgiving.

Rule: parse `warnings[]` on every create. Any code mentioning rendering / dataset / columns (`DATASET_WONT_RENDER`, `INVALID_COLUMNS`, etc.) → the entry is `failed`, not `done`. The user gets to see exactly why.

Note: `warnings[]` is a create-time response field, NOT stored on the map. `carto maps get` doesn't surface it. Capture at create-time or you don't capture it.

### `validate` accepts shapes that `create` quietly rejects — verify with the live schema, not the validator

`carto maps validate` is a Tier-1 offline structural check; it does NOT enforce every constraint the create-time tilejson generator enforces. Two real cases caught so far where validate returned `success: true, issues: []` while create silently degraded the map:

- **`dataset.columns` shape change in CLI v0.7.0** — items are plain strings (column names), not `{name, type}` objects. Both shapes pass `validate`; only strings produce a valid tilejson. The object form on v0.7.0 yields a `DATASET_WONT_RENDER` warning on `create` with `detail: "Invalid columns parameter"`, the map is created, but the affected layer renders zero features at view time. Caught on the TfL Bus Route Overlap Map re-migration after a v0.6.3 → v0.7.0 CLI upgrade. Worked correct shape:

  ```python
  # v0.7.0+
  dataset["columns"] = ["direction", "rte_run", "route", "status", "run_no",
                        "run_type", "run_length", "date_updated",
                        "authorities", "objectid", "shape__length"]
  # Old (now broken):
  # dataset["columns"] = [{"name": "direction", "type": "string"}, …]
  ```

- (Reserve space for future Tier-2 gaps as they surface.)

**Rule**: any time `carto maps create` returns a `warnings[]` entry (especially `DATASET_WONT_RENDER`), don't treat it as cosmetic — it's almost always a schema-shape mismatch the validator missed. Fetch the live schema for the offending section (`carto maps schema dataset --json` in this case) and check `properties.<field>.anyOf[*].items` against what the compose script emits. The earlier reference docs (e.g. `renderer-mapping.md`) may describe a stale shape if the CLI has been bumped since they were written.

**Detection in script**:

```python
import json, subprocess

resp = json.loads(subprocess.check_output(
    ["carto", "maps", "create", "--from-json", path, "--json"]))
for w in resp.get("warnings", []):
    if w["code"] == "DATASET_WONT_RENDER":
        # Treat as a hard failure for this dataset. Re-fetch schema, fix shape, retry.
        ...
```

---

## Manifest dependency lookup

### Resolve through `Source aliases`

A Web Map's `operationalLayers[].url` may point to a Map Service or WFS that was **collapsed into a Feature Service Datasets entry** during discover's Phase 4 dedup. Don't search by URL alone — check each Datasets entry's `Source aliases:` and match against the layer URL:

```python
def find_dataset_for_layer(layer_url, manifest):
    for entry in manifest.datasets:
        if entry.source == layer_url:
            return entry
        for alias in entry.source_aliases:
            if alias.url == layer_url:
                return entry
    return None
```

If no match, mark the Web Map `failed` with `Failure: depends-on-unmigrated-data: <layer-name>`. Don't auto-invoke `migrate-data` — the user wants the gap surfaced explicitly.

### Skipped data (oversized) is also a blocker

A Datasets entry with `State: skipped` (e.g. `Reason: exceeds-1gb-staging-not-implemented`) can't be a target for a Web Map either. Treat the same way as unmigrated:

```
Failure: depends-on-skipped-data: <layer-name> (exceeds-1gb-staging-not-implemented)
```

Once the staging-fallback feature ships and the dataset transitions to `done`, re-running the Web Map's batch will pick it up.

---

## Layer order

### ArcGIS `operationalLayers` and kepler `visState.layers` use OPPOSITE array conventions — reverse on emission

**Same array shape, opposite semantics.** Easy to miss because both formats put layers in an array and both render bottom-up — but the array end that's "the bottom" differs.

- **ArcGIS Web Map JSON** (`operationalLayers[]`): `[0]` is the **bottom** of the visual stack (drawn first, painted over by subsequent layers). The last element is the **top**. The AGOL Map Viewer layer-list panel displays the array in **reverse**: top of the panel = top of the map = last array element.
- **kepler.gl / Builder** (`visState.layers[]`): `[0]` is the **top** of the visual stack (drawn last, on top of previous layers). The last element is the **bottom**. Builder's layer-list panel displays the array in array order: top of the panel = top of the map = `[0]`.

**Result if you forget**: the composer that just copies `operationalLayers[]` into `visState.layers[]` in source order produces a map where **every layer's z-position is inverted** from the source — choropleth polygons that were the source's basemap-style background end up on top of point layers (obscuring them with their fill, however translucent), and reference outlines (boroughs, GLA) that were the topmost framing in the source end up underneath the choropleth at the bottom.

**Caught on the TfL `Average PTAL LSOA Web Map` migration**: source `operationalLayers` was `[PTAL polygons, Bus Stops, National Rail, TfL stations group, London Boroughs, GLA]` — PTAL at index 0 = **bottom** in AGOL, GLA at index 5 = **top**. Composer emitted them in the same order into `visState.layers`, putting PTAL at index 0 = **top** in Builder. The user noticed: the translucent PTAL choropleth (opacity 0.85) sat on top of the bus stops and station icons in the migrated map, while in the source AGOL map the points and boundary outlines sat on top of the polygons as a sensible cartographic stack.

**Hard to detect from screenshots alone.** With translucent layers (opacity 0.5–0.85, the common case for choropleths), the visual blend is roughly commutative — a screenshot rendered with the layer order inverted looks similar enough to the source that a human reviewer doesn't immediately register the bug. The light-engine screenshot in particular doesn't reliably show the difference. The reliable diagnostic is **comparing the layer-panel order in Builder against the AGOL map's layer-panel order**: AGOL panel top-down = Builder panel bottom-up; if both panels show the same top-down sequence, the migration is flipped.

**Fix**: emit `visState.layers` as the **reverse** of the flattened source `operationalLayers` sequence. GroupLayers expand into their sublayers in source order (sublayers within a group stack the same way as top-level layers — `layers[0]` of a group is the bottom of the group), then the whole flattened list reverses:

```python
def flatten_operational_layers(ops):
    """Walk operationalLayers including GroupLayer sublayers; preserve source order."""
    flat = []
    for l in ops:
        if l.get("layerType") == "GroupLayer" and l.get("layers"):
            flat.extend(flatten_operational_layers(l["layers"]))
        else:
            flat.append(l)
    return flat

source_flat = flatten_operational_layers(webmap_json["operationalLayers"])
# Reverse for kepler's opposite array convention:
kepler_layers = [translate_layer(l) for l in reversed(source_flat)]
keplerMapConfig["config"]["visState"]["layers"] = kepler_layers
```

The reversal is the **only** structural transformation needed for ordering; per-layer rendering, popups, labels, etc. are unchanged. The reversal also fixes the popupSettings mapping naturally because the popup-keys are `layer.id`s, not array positions.

**Detection in script** when reviewing an existing migrated map (no source available): cross-reference the `visState.layers[]` order against any AGOL screenshot or the public Map Viewer URL. If the topmost layer in Builder's panel is what was the bottommost in AGOL, the order is flipped.

**Anti-pattern**: don't try to "preserve source array order for traceability" — the array is internal; nothing downstream reads it as a stable identifier. The visible stack order is what matters, and that requires the reverse.

---

## Geometry-type → kepler layer-type

### Trust the warehouse, not the source

ArcGIS Feature Services don't always tell you the geometry type at the layer level — and the source's `esriGeometryType` may not survive the migration cleanly (e.g. multi-part geometries simplified during extraction). Use the **migrated DW table's actual geometry type** via `carto connections describe <conn> <fqn> --json`:

| `geomType` from `connections describe` | kepler layer subtype |
|---|---|
| `point` | `tileset` (point) |
| `line` / `linestring` / `multilinestring` | `tileset` (line) |
| `polygon` / `multipolygon` | `tileset` (polygon) |
| `h3` (pre-aggregated) | `h3` |
| `quadbin` (pre-aggregated) | `quadbin` |

If `connections describe` returns `geometry` (generic) or no type, run a quick `SELECT ST_GeometryType(geom) FROM <fqn> LIMIT 1` to introspect. Don't guess.

---

## Marker icons

### Prefer `imageData` over `url` on `esriPMS` symbols

Picture marker symbols come with either an external `url`, embedded `imageData` (base64), or both. **Always prefer `imageData`** when present: it's reachable without auth, doesn't require a network call, and works even when the renderer's URL is behind portal auth the agent's token can't pass. The renderer's `url` is a fallback for the few cases where `imageData` is absent.

### Content-hash dedup avoids re-upload churn

A single Web Map often references the same icon across 5+ layers (e.g. a "store" icon used by every regional Feature Service). Hash the bytes (sha256 → 16-char prefix is fine), key the upload cache on the hash, and the `POST /assets` call runs **exactly once per unique icon** regardless of how many layers reference it. The cache lives in `out/markers/.cache.json` and survives across runs — re-running a failed migration won't re-upload icons that already succeeded. Cache the returned `{id, url}`; `id` is the durable kepler reference, `url` is a 7-day presigned GET that Builder re-issues on every map read.

**There is no `carto maps markers` CLI subcommand.** The skill's marker step is a multipart `POST /assets` to the workspace API (`type=MapMarker`, `file=<binary>`, returns `{id, url}`). Accepted extensions: `png`, `svg` only — convert JPEG / GIF to PNG via Pillow before uploading. Permission: `write:maps`. See [`marker-upload.md`](marker-upload.md) for the full helper.

### Categorical icon binding isn't universal in kepler

`uniqueValue` renderers often have per-category picture markers (different icon per `storeType` value). Kepler tileset layers don't always expose `iconField` + `iconRange` for categorical icon binding — it depends on the subtype and version. **Always fetch the live schema** with `carto maps schema layer.tileset --json` and check for the icon-binding fields before emitting them. When absent, collapse to a single icon (most common or first in source order) and record `Notes: uniqueValue-icons-collapsed-to-single (<N> distinct icons)`. Users can rebuild categorical icons manually in Builder if needed.

### CARTO auth expiry applies to marker uploads too

The marker upload `POST /assets` uses the same bearer token as every other workspace-api call. If it returns 401 (expired) or 403 `Not authorized`, stop the batch (don't mark the in-progress Web Map `failed`; leave it `in-progress` for clean resumption after `carto auth login`). Same pattern as `carto maps create`.

### Header-sniff before trusting `contentType`

Some ArcGIS exports mislabel the `contentType` field (e.g. PNG bytes claimed as `image/jpeg`). Sniff the first few bytes:

```python
if data.startswith(b"<svg") or data.startswith(b"<?xml"): ext = "svg"
elif data.startswith(b"\x89PNG"):                          ext = "png"
elif data.startswith(b"\xff\xd8\xff"):                     ext = "jpg"
```

Use the sniff result over `contentType` when they disagree. Saves debug time on uploads that fail with cryptic format errors.

### `radius` is the rendered icon-size knob, NOT `customMarkerSize`

When `visConfig.customMarkers: true`, Builder uses **`visConfig.radius`** as the on-screen pixel size of the icon. The live schema documents this: `radius` has `[0, 200]` range "when `customMarkers: true`" vs the plain-circle `[0, 100]`. `customMarkerSize` is a legacy knob that's mostly cosmetic now — older Builder builds read it, current builds don't.

**Symptom**: you set `customMarkerSize: 24`, validate clean, screenshot looks fine (the light engine doesn't render icons), Builder loads — and renders the icon at ~12 px. The `radius` you left at the default 6 (or 12 from a circle-fallback path) is what Builder picked up.

**Fix**: set both, with `radius` as the source of truth.

```python
if vc.get("customMarkers"):
    target_size = 24
    vc["radius"] = target_size             # Builder reads this
    vc["customMarkerSize"] = target_size   # legacy mirror
```

Verified on the TfL PTAL LSOA migration — icons displayed at ~12 px (the `radius` value) until we promoted `radius` to 24, after which they rendered correctly.

### Multi-color icons: upload via `POST /assets` AND set `visConfig.filled: false`

Two independent changes must be made together to preserve a multi-color source PNG (Underground roundel = red outline + white interior + blue line; Elizabeth Line = purple outline + dark-blue line):

1. **Upload the PNG** to `${workspaceApiUrl}/assets` (the workspace-api endpoint Builder UI itself uses) and store the returned asset id in `visConfig.customMarkersId`. The server-side map serializer hydrates `customMarkersUrl` from the asset id on every map read (7-day presigned GET) — see `workspace-api/src/serializers/kepler-map-config-serializer.ts`. Persist only the id, not the URL.
2. **Set `visConfig.filled: false`** on every icon layer. Kepler's `TileLayer` applies its `getFillColor` accessor only when `visConfig.filled` is truthy (see `workspace-www/src/features/builder/ui/KeplerGl/layers/TileLayer.ts`, the color channel `condition`). With `filled: true`, every non-transparent icon pixel is replaced by `getFillColor` (derived from `layer.config.color`) and the icon collapses into a single shade. With `filled: false`, the tint is skipped and the icon renders with its source colors.

**Both are required.** A data URI in `customMarkersUrl` with `filled: false` still renders monochromatic (deck.gl handles data URIs differently from /assets-hosted URLs). An uploaded asset id with `filled: true` (the default) also renders monochromatic because the tint accessor still fires. Apply both fixes to the same layer.

Test progression on TfL PTAL LSOA (rounds 5–7):

| round | change | result |
|---|---|---|
| 5 | `visConfig.fillColor = white` | server zeroed `fillColor`, no change — uniformly red |
| 6 | `layer.config.color = white` | icons rendered uniformly **white** — proves color is a REPLACE, not a multiplicative tint |
| 7 | `customMarkersId` (uploaded) + `filled: false` | source PNG colors render correctly |

Endpoint: `POST {workspaceApiUrl}/assets`, multipart with `type=mapMarker` (camelCase — `MapMarker` is rejected) and `file=<binary>`. Accepted extensions: `png`, `svg`. Returns `{id, url}`.

Worked composer pattern: see [`marker-upload.md`](marker-upload.md) "Multi-color icons" — full helper with content-hash dedup, byte-header sniffing (source PNG bytes are sometimes declared `image/jpeg` — the workspace-api validates mimetype against the accepted-extensions list and 400s on a mismatch), and JPEG→PNG conversion via PIL.

```python
if vc.get("customMarkers"):
    vc["filled"] = False                                       # disable tint accessor
    if vc.get("customMarkersUrl", "").startswith("data:"):
        raw = base64.b64decode(vc["customMarkersUrl"].split(",", 1)[1])
        asset = upload_marker_asset(raw, layer_label)           # POST /assets
        if asset:
            vc["customMarkersId"]  = asset["id"]                # the durable reference
            vc["customMarkersUrl"] = asset["url"]               # nice-to-have; server overwrites
```

Brand color goes in `visConfig.strokeColor` / `initialStrokeColor` — with `filled: false` the fill never renders, but Builder's sidebar chip uses strokeColor for icon layers, so brand identity is preserved there.

This rule applies ONLY when `customMarkers: true`. Plain circle layers (no icon) follow the normal pattern: `layer.config.color` and `visConfig.fillColor` both = brand color, `filled: true`.

### Aspect-ratio preservation requires padding the source PNG to square

Kepler tileset's icon layer has a **single** size knob (`radius` / `customMarkerSize`), no per-axis width/height. deck.gl scales the source PNG into a square box, so a 2560×1611 PNG (1.59 ratio) renders as a stretched 24×24 box — same visual mass on screen but the icon's shape gets distorted.

**Fix at acquisition time**: pad the PNG to `max(w, h)` on both axes with transparent fill BEFORE encoding the data URI. The original content keeps its aspect ratio inside the transparent canvas; Builder renders the padded square at `radius` px and the icon looks correct.

```python
import io, base64
from PIL import Image

def pad_png_to_square(raw):
    img = Image.open(io.BytesIO(raw)).convert("RGBA")
    w, h = img.size
    if w == h:
        return raw
    side = max(w, h)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(img, ((side - w) // 2, (side - h) // 2))
    out = io.BytesIO()
    canvas.save(out, format="PNG", optimize=True)
    return out.getvalue()
```

Apply to both `esriPMS.imageData` and `CIMPictureMarker.url` (after base64-decode). Compute the content-hash AFTER padding so layers sharing the same source dedupe to a single padded version. PIL is the cleanest dependency; fall back to the raw PNG with a `Notes:` entry if it's not installed.

Verified on TfL PTAL LSOA — pre-fix National Rail (PNG 2560×1611, ratio 1.59) rendered visibly squashed; post-fix the padded version is 2560×2560 and the icon's correct proportions are preserved.

### `labelingInfo` lives at `layerDefinition.drawingInfo.labelingInfo`, not `layerDefinition.labelingInfo`

Two paths in the WebMap JSON look like they could hold label config:

- `operationalLayer.layerDefinition.labelingInfo` — usually empty `[]` on WebMap-overrides.
- `operationalLayer.layerDefinition.drawingInfo.labelingInfo` — **this is where halo'd labels actually live** in modern WebMaps (and CIM-symbol-source layers in particular).

A composer that reads only the first path silently skips all labels on every map that uses CIM symbols. The bug looks like "labels weren't translated" rather than a hard error — `validate` passes, `create` passes, the map looks fine in the screenshot light engine — but in Builder you see icons without their station names.

**Always read `(ld.get("drawingInfo") or {}).get("labelingInfo")` first**, then fall back to `ld.get("labelingInfo")`. The FeatureServer's own `drawingInfo.labelingInfo` is a third fallback (use only when the WebMap doesn't specify either).

Caught on the TfL PTAL LSOA re-migration — every TfL station sublayer plus National Rail had populated `layerDefinition.drawingInfo.labelingInfo` (NAME, halo'd) that the original composer missed entirely.

### Source label font sizes don't always render well at city zoom — accept an override

ArcGIS publishers tune label font sizes for ArcGIS Pro's print-quality renderer. deck.gl text rendering looks smaller for the same `size` value. For a faithful migration, accept a `font_size_override` per layer in the label translator and bump it for layers where the source's 9-px label disappears at the target zoom. Common bumps: TfL stations 9 → 12, retail "site name" labels 7 → 10. Smaller font (8 px) is appropriate for dense, single-glyph point labels like Bus Stops' `POINT_LETTER`.

### Label vertical placement: `alignment` drives it, NOT `offset`

ArcGIS's `labelPlacement: esriServerPointLabelPlacementAboveCenter` means "label sits above the icon, horizontally centered on it." The naive translation is `anchor: "middle"` (horizontal center) + `alignment: "center"` (vertical center) + `offset: [0, -(size + 6)]` (nudge up by font height + clearance).

**That doesn't work.** Builder anchors the text *center* at the data point when `alignment: "center"`, regardless of the offset. The offset is effectively ignored at the alignment level — the label ends up sitting on top of (centered on) the icon. Verified failure on TfL PTAL LSOA round 4.

**The fix is `alignment`, not `offset`.** In Builder/kepler `alignment` describes WHERE the label sits relative to the data point — NOT which edge of the text-box anchors at the point (the latter is the deck.gl `getAlignmentBaseline` semantic; Builder/kepler uses the simpler "label position" reading):

| `alignment` | Where label appears |
|---|---|
| `"top"` | ABOVE the data point (above the icon) |
| `"center"` | ON the data point (overlay) |
| `"bottom"` | BELOW the data point |

So `AboveCenter → alignment: "top"`, `BelowCenter → alignment: "bottom"`, `CenterCenter → alignment: "center"`. **Leave `offset: [0, 0]`** — alignment alone positions the label flush to the icon, and even a small offset (±4 px) visibly detaches the label. Don't try to use offset alone with `alignment: "center"` either.

**Easy to get backwards.** The semantic looks like deck.gl's `getAlignmentBaseline` (which is "which edge anchors at the point") but it's the inverted reading. First implementation on the TfL PTAL LSOA round-4 fix had it flipped (`AboveCenter → "bottom"`) — labels still rendered visually wrong, indistinguishable from the alignment-ignored bug. Always verify the result in Builder (not the light-engine screenshot — text doesn't render there) before declaring labels done.

Same `anchor: "middle"` (horizontal middle) applies to all three vertical placements unless the source uses a left/right placement variant.

### Plain-circle marker with a centered label needs floors: `radius >= 10`, label `size >= 10`

When a point layer renders as a **plain circle** (no `customMarkers`) AND the same layer's `textLabel[]` has `alignment: "center"` (label sits **inside** the circle, not above/below), Builder needs the circle big enough to contain the label and the label big enough to be legible. Source ArcGIS sizes are often print-tuned (4-6 px radius, 6-7 pt label font) and produce a circle that clips the label, or a label too small to read.

**Floors** to apply at composition time when this combination is detected:

- `visConfig.radius` ≥ **10 px** (overrides any smaller value from the source — a 4-6 px circle can't contain even a 1-character label)
- `textLabel[i].size` ≥ **10 px** (overrides any smaller font from the source — 6-8 px loses anti-aliasing on most displays and the label becomes a grey smudge; 10 px is the legibility floor for in-circle text on a typical web viewport)

Detection — applies only when **both** conditions hold:

1. The layer is a point tileset whose marker is the default circle (`visConfig.customMarkers` is unset or `false`). Custom picture-marker layers don't get this floor — the marker is whatever the source PNG dictates.
2. The layer has at least one `textLabel[i]` entry with `alignment: "center"` AND a `field` resolving to a column. (`alignment: "top"` / `"bottom"` labels sit outside the marker — no clipping concern; the existing font-size override rule covers their legibility.)

Worked example — Bus Stops layer (source font 6 px, label `POINT_LETTER` rendered centered inside the marker; default circle):

```python
def normalize_circle_with_centered_label(layer):
    cfg = layer["config"]
    vc = cfg.get("visConfig", {})
    if vc.get("customMarkers"):
        return layer
    tls = cfg.get("textLabel", [])
    has_centered = any(t.get("alignment") == "center" and t.get("field") for t in tls)
    if not has_centered:
        return layer
    if (vc.get("radius") or 0) < 10:
        vc["radius"] = 10
    for t in tls:
        if t.get("alignment") == "center" and (t.get("size") or 0) < 10:
            t["size"] = 10
    return layer
```

Caught on TfL `Average PTAL LSOA Web Map` (Bus Stops layer): source `font.size = 6`, composer emitted `radius = 4`, `label.size = 8`. The 4-px circle was visibly smaller than the label glyph; even after flooring radius to 10, the 8 px label was still hard to read against the red fill. Final floors are `radius = 10` / `label.size = 10`.

**Don't apply the floor universally.** A heatmap-style scatter of 21K bus stops at city zoom would be unreadable at 10 px per dot — but it's also unreadable at 4 px with text inside; the bug is symptom of "trying to label every dot at city zoom" rather than the floor itself. The right pattern is: floors here + the existing `visibilityByZoom` rule (zmin 15 for Bus Stops) so the labelled circles only appear when there are few enough on screen to actually read. The two rules are complementary.

Generalization: the floor specifically defends the **`alignment: "center"`** case (label inside marker). For `alignment: "top"` / `"bottom"` (label outside), the marker radius can stay small — the existing "Source label font sizes don't always render well at city zoom — accept an override" rule covers the font-size half independently.

---

## CIM symbols (ArcGIS Pro)

### CIM colors use 0-100 alpha, not 0-255

CIM color values use percent for alpha (`[r, g, b, 100]` is fully opaque). Easy to miss when porting from legacy `esri*` color handling (which uses 0-255). Forgetting this turns every map into "fully transparent" — and worse, validate/create accept it silently because alpha is always in-range. Build a single `cim_color_to_rgb` + `cim_color_to_opacity` extractor (see [`cim-symbols.md`](cim-symbols.md)) and use it everywhere; don't sprinkle raw `c["values"][3] / 255` math around.

### CIMPictureMarker URLs are usually `data:` URIs, not external URLs

Unlike `esriPMS` (which often has both `url` AND `imageData`), `CIMPictureMarker` typically embeds the image as a `data:image/png;base64,...` URI in the `url` field — there's no separate `imageData` field on CIM picture markers. Decode the base64 part directly; no HTTP fetch needed.

When the `url` is an external URL instead (rare but possible), fall back to the standard `http_get_with_token` flow.

### CIMVectorMarker rendering is out of scope

CIM vector markers can be arbitrarily complex: multiple `markerGraphics[]`, layered fills/strokes, geometric effects, gradients. Rendering them faithfully requires a CIM-to-raster engine that's not in this toolchain. Collapse to a colored circle using the dominant fill color from the first `markerGraphics[0].symbol.symbolLayers[]` `CIMSolidFill`. Note the loss explicitly (`cim-vector-marker-collapsed-to-circle`) so the user knows what to recreate manually if it matters.

The same applies to `CIMCharacterMarker` (glyph from a font) — collapse to colored circle, note the font + character index for traceability.

### Multi-layer CIM symbols are common in real Pro maps

Real-world ArcGIS Pro layers often stack 3-6 symbol layers (halo + outline + main marker + secondary marker + drop shadow). Apply the collapse heuristic from `cim-symbols.md`: markers first (topmost wins), fills next, strokes last. Record `Notes: cim-multi-layer-collapsed (<N> source layers → 1)` so the loss is visible.

### CIM and `esriPMS` cache to the same marker store

The content-hash dedup in `out/markers/.cache.json` doesn't distinguish CIM-extracted icons from `esriPMS`-extracted icons — same bytes → same hash → same single upload. A portal that has both legacy ArcMap-published and Pro-published layers sharing the same icon will upload it exactly once.

---

## Renderer fallbacks

### Heatmap is not Builder-native

Builder has `heatmapTile` as a layer subtype, but it requires pre-generated tilesets (the `carto-import-export-data` tileset prep flow). ArcGIS heatmaps are computed at render time. Closest Builder equivalent: an `h3` or `quadbin` aggregation layer over the source data, manually configured. For automated migration, fall back to simple-color and record `Notes: renderer-fallback: heatmap (use h3/quadbin layer manually for parity)`.

### dotDensity has no clean Builder analogue

The closest Builder pattern is one row per dot rendered as small points — but that requires the source data already exploded into per-dot rows, which dotDensity doesn't provide. Fall back to simple-color and note.

### Multi-field `uniqueValue`

ArcGIS `uniqueValue` renderers can key on `field1` + `field2` + `field3` (concatenated). Builder's ordinal scale binds to a single field. Fall back to `field1` only and record `Notes: renderer-fallback: uniqueValue multi-field collapsed to <field1>`.

### When the WebMap renderer is empty, sample the FeatureServer-side icon's dominant color for the fallback circle

A WebMap operationalLayer can have `layerDefinition: {}` (or `drawingInfo: {}`) with no renderer override at all. The composer then falls through to the geometry-type default (a generic colored circle for point layers). Default colors (e.g. `[80, 80, 80]` grey) end up generic and don't match the source intent.

Better: when the WebMap renderer is empty AND the FeatureServer-side renderer exposes an `esriPMS` / `CIMPictureMarker` icon, sample the icon's dominant opaque color and use that as the fallback circle's fill. This keeps the layer recognizable even when the icon itself doesn't render (deck.gl `data:image/png` rendering can fail silently on some Builder paths).

```python
from PIL import Image
from collections import Counter
import io, base64

def dominant_color(b64_image):
    raw = base64.b64decode(b64_image)
    img = Image.open(io.BytesIO(raw)).convert("RGBA")
    pixels = [img.getpixel((x, y))
              for x in range(0, img.size[0], max(1, img.size[0] // 10))
              for y in range(0, img.size[1], max(1, img.size[1] // 10))]
    opaque = [p[:3] for p in pixels if p[3] > 200]
    if not opaque:
        return None
    return list(Counter(opaque).most_common(1)[0][0])
```

Use the dominant color directly, OR map to the layer's known brand color when the source has one (TfL bus red `#dc241f`, London Underground red `#e4001b`, etc.). Document the choice in `Notes:`.

Caught on TfL PTAL LSOA — `Bus Stops` WebMap layer had empty renderer; the FeatureServer-side icon was a red picture marker (dominant color [255, 0, 0]) but the migration emitted a grey circle. Sampling the source PNG dominant color produces a more faithful fallback when the icon path isn't taken.

---

## Popup quirks

### Live `popupSettings.layers` is a layer-id-keyed map, not a `properties[]` array

The first version of `popup-mapping.md` documented a `popupSettings.layers[].properties[]` + `hoverProperties` + `clickProperties` shape. That shape is wrong — the live schema returned by `carto maps schema popupsettings --json` keys `layers` by **layer id** with `{ enabled, hover: { style, fields, templateMode }, click: { style, fields, templateMode } }`, and each `fields[]` entry is `{ name, customName?, format, isExpression?, spatialIndexAggregation? }` where `format` is a **d3-format string** (`",.2f"`, `"$,.2f"`, `".3~s"`, `"%Y-%m-%d"`), not a typed `{ type, decimals, ... }` object.

Practical translations:
- ArcGIS `{ digitSeparator: true, places: 2 }` → d3 `",.2f"`.
- ArcGIS `{ digitSeparator: false, places: N }` → d3 `".Nf"` (no thousands separator).
- ArcGIS `dateFormat: "shortDate"` → d3 `"%-m/%-d/%Y"`.
- ArcGIS `dateFormat: "longMonthDayYear"` → d3 `"%B %-d, %Y"`.
- ArcGIS `stringFieldOption: "richtext"` → no direct field-list equivalent; use `templateMode: true` with a `template` HTML string if rich rendering is needed (per `carto-create-builder-maps` `references/popups.md`).

Hidden-field exclusion still applies unchanged — just don't list the field in `fields[]`. The 5-field hover cap is enforced by Builder's Tier-1 *if you author a hover popup*; in migration we default to click-only (per `popup-mapping.md`'s policy), so the cap rarely binds.

The keyed `layers.<id>` is the **layer's own id**, not the dataset `$ref` and not the dataset id. Easy to confuse.

`popup-mapping.md` was rewritten to match the live shape; treat the corrected file as the canonical reference and `carto maps schema popupsettings --json` as the final tiebreaker.

### `{name}` vs `{{name}}`

ArcGIS uses single-brace substitution (`{name}`); kepler uses double-brace Mustache (`{{name}}`). Always rewrite during translation:

```python
import re
title = re.sub(r"\{(\w+)\}", r"{{\1}}", arcgis_title)
```

Don't try to detect "is this a template?" — just run the regex unconditionally on `popupInfo.title` and `description`.

### Click-only by default — never add hover popups during migration

ArcGIS Web Maps don't have a hover-popup concept; the popup appears when the user clicks a feature. **Faithfully reproduce this** — emit popup config for click only and leave hover empty (`hover.fields: []` / `hover.enabled: false` per the live schema; see the "Live `popupSettings.layers` is a layer-id-keyed map" lesson above for the actual shape).

Do **not** apply Builder's "5-field hover cap" or otherwise split fields into hover vs. click — that's a *fresh-authoring* rule from `carto-create-builder-maps`, not a migration rule. Adding hover behavior the user didn't configure changes the map's interaction model from what they had in ArcGIS, surprises them, and is the kind of "helpful default" that backfires during migration.

This was a real bug in v0.1.7: a simple one-layer Web Map without explicit popup config ended up with a hover popup in the migrated Builder map. The fix in v0.1.8: respect the source's interaction model exactly — if the source had no popup, the target has no popup; if the source had a click popup, the target has a click popup with the same fields.

The rare exception: source `popupInfo` with an explicit hover configuration (some custom ArcGIS apps set `popupShowsAt: "hover"` or equivalent). Detect that signal explicitly; absent it, default to click-only.

### Source has no `popupInfo` → emit no popup

If a layer has no `popupInfo` (or `popupInfo: null`) in the source, **do not emit a popup** in the migrated map. Migration faithfully reproduces source behavior; the user chose not to configure popups for that layer, and the migration shouldn't introduce interaction the user didn't ask for.

This **deliberately overrides** `carto-create-builder-maps`'s "Popups — emit by default" guidance, which assumes fresh authoring (no prior config exists, end users need feature inspection somehow). Migration has prior config — the absence of `popupInfo` IS the prior config. Same v0.1.8 fix as the click-only one above; the two issues surfaced together on the same simple-map test.

To omit a layer's popup, leave it out of `popupSettings.layers.<id>` entirely. Don't emit an entry with `enabled: false` and empty `click.fields[]` — that still registers a click-handler with empty content.

### Hidden fields stay hidden

`fieldInfos[].visible: false` means the field shouldn't appear in any popup view (hover, click, info-panel). Exclude entirely — don't add to `click.fields[]` and rely on a UI toggle.

---

## Arcade quirks

### `sqlglot` validation catches most translation bugs cheaply

Per-row math translations occasionally produce SQL that's syntactically valid but semantically wrong (e.g. operator precedence misread, parenthesis mismatched). `sqlglot.parse_one(sql, dialect=...)` doesn't catch all semantic issues but catches most syntax errors before they reach `carto maps validate`.

If `sqlglot` isn't installed, the agent continues without client-side validation and relies on `carto maps validate` at compose time. This is slower but still correct — flag a one-line warning at start so the user knows.

### `Count($feature)` has no field argument

`Count($feature)` is the only aggregation that doesn't take a `$feature.X` argument — it counts rows. Translate to a Builder formula widget with `column: null` (or whatever the row-count convention is — check `carto maps schema widgets.formula`). Don't try to translate it as `Count($feature.OBJECTID)` even though that would technically work — the explicit row-count form is more idiomatic in Builder.

---

## Basemap quirks

### Google basemaps need `type: "google"` and 1-word styleIds — neither validate nor create catches the bad shape

`basemapConfig.type` is the **provider discriminator** (`"carto"` / `"google"` / `"custom"`), and it must match the styleId's family. The combination most likely to bite during migration:

- Source basemap `Imagery` / `World_Imagery` → CARTO basemap `{type: "google", styleId: "satellite"}`. **Not** `{type: "carto", styleId: "google-satellite"}`. The earlier `basemap-mapping.md` recommended `google-satellite` (no longer canonical) and didn't document the `type` discriminator at all. Both bugs get accepted by `carto maps validate` and `carto maps create` without warnings, then render as a blank CARTO canvas at view time because the viewer can't resolve the basemap.

The canonical Google styleIds (per `carto-create-builder-maps/references/basemap.md`) are 1-word: `roadmap`, `satellite`, `hybrid`, `terrain` — plus the `google-positron` / `google-dark-matter` / `google-voyager` blends (CARTO cartography on Google tile infrastructure). `google-satellite` / `google-hybrid` / `google-roadmap` are NOT valid ids.

Verification: `--render-engine light` is MapLibre-only and renders a CARTO fallback for ANY Google config (correct or not). Use `--render-engine full` and look for the Google logo + an "Imagery © …" attribution before declaring the migration done.

The "fall back to `voyager` when org has no Google Maps API key" guidance from earlier `basemap-mapping.md` revisions was based on a misdiagnosis — Google basemaps work in current CARTO orgs without an explicit org-level API key. Don't preemptively swap; render-time verify with the `full` engine.

`basemap-mapping.md` was rewritten to (a) list the correct canonical Google styleIds, (b) document the `type` discriminator, (c) describe the verification protocol, and (d) drop the API-key fallback narrative. Treat the corrected file as the canonical reference and `carto-create-builder-maps/references/basemap.md` as the final tiebreaker.

---

## Screenshot mechanics

### `--render-engine light` may silently fall back to `full` and trigger a Chromium download

`carto maps screenshot <id> --render-engine light --json` is documented as a Playwright-free path (@deck.gl/carto `fetchMap`, ~3-8 s). On at least one CLI version (`@carto/carto-cli` v0.6.3) the first invocation returns `success: false` with a Playwright error (`Executable doesn't exist at .../ms-playwright/chromium_headless_shell-...`), and on retry — after running `npx playwright install chromium` — it succeeds with `engine: "full"` even though `engineRequested: "light"`. In other words, the `light` path was never wired up on this CLI build, and Chromium is required regardless of the flag.

**For the agent during a batch:**

- If `engineRequested !== engine` in the response, that's the silent-upgrade signal — just treat it as a successful screenshot, don't loop.
- If the first call returns the `Executable doesn't exist at ... ms-playwright/...` error, run `npx playwright install chromium` (~92 MB, one-time per machine) and retry. Surface a one-line warning to the user before the install: *"first screenshot on this machine — downloading Chromium (~92 MB)."*
- After install, screenshots are reliable; the `engineRequested` mismatch is cosmetic.

The lesson generalises to any CLI version where the `light` path is incomplete — detect via the error string or the `engine !== engineRequested` field; don't gate on the flag's nominal behaviour.

---

## Widget composition

### `widgets[]` Tier-1 rules the live schema doesn't surface

`carto maps schema widgets --json` returns a JSON Schema that lists each widget type's properties but **doesn't mark `isValid`, `buckets`, or the column-entry shape as required**. They're cross-field rules `carto maps validate` enforces separately, and they bite on first authoring of every simple-app entry that ships a histogram or table widget. Caught all three on the first TfL Dashboard migration.

The three rules:

1. **Every widget needs `"isValid": true`.** Without it, Builder hides the widget and the panel renders as *"select a field"*. The viewer can't reconfigure it either.
2. **`histogram` widgets need `"buckets": <int>`** (default `30`). The component's tick loop is `for (let i = 1; i < widget.buckets; i++)` — undefined `buckets` → empty render.
3. **`table.columns` is an array of `{"field": "<col>"}` objects**, not bare strings. Bare strings round-trip through the API but the table renderer throws on mount.

The `app-absorption.md` widget-mapping table now has a "Required boilerplate" column capturing all three. Always run `carto maps validate` after composition; the validator is the source of truth, not the schema response.

Worked correct shape:

```python
# histogram
{"type": "histogram", "id": "...", "title": "...", "dataSource": ds_id,
 "column": "f2025", "operation": "count",
 "buckets": 30,           # required by Tier-1
 "isValid": True}

# table
{"type": "table", "id": "...", "title": "...", "dataSource": ds_id,
 "columns": [{"field": "site_id"}, {"field": "f2015"}],  # objects, not strings
 "isValid": True}
```

**Detection**: `carto maps validate <file> --json` returns `issues[]` with paths like `keplerMapConfig.config.widgets[<i>].isValid`, `.buckets`, or `.columns[<j>]`. Three iterations max per the always-on rules — but with the boilerplate column applied upfront, you should land clean on the first try.

---

## Process patterns

### Consult `carto-create-builder-maps` first

Every Builder authoring step has a documented recipe in `carto-create-builder-maps`: 6-phase authoring flow, "do silently, don't ask" defaults (auth status, connection UUID resolution, viewport from data extent, legend population from `/stats`, default popups for feature-identifying datasets), `keplerMapConfig` partial-vs-wholesale rule (top-level fields are partial-PATCH except `keplerMapConfig` which is wholesale), the screenshot decision rubric. Read its `SKILL.md` end-to-end before writing translation logic.

### Don't `--help` to find flags

Same as `migrate-data` "Consult `carto-agent-skills` first" — the carto-skills bundle has tested recipes for every `carto maps` invocation. Read the skill, follow the recipe.

### Reload Builder after a write

When the user has Builder open in another tab and the agent updates a map, Builder loads the map into in-memory client state once and doesn't subscribe to server events. Tell the user to reload (`Cmd/Ctrl+R`) after a successful migration so they see the result.

---

## How to add a lesson

When the agent encounters a non-obvious pattern during a run, append to `SESSION_LESSONS.md` in the working directory using the template at the bottom of [`../migrate-data/lessons.md`](../migrate-data/lessons.md). The same maintainer / end-user merge paths apply at end of phase C.7:

- **Maintainer** (source repo cloned, write access): append to this file under the matching section, bump `version` in `skills/catalog.json`, run `make sync && make validate`, commit per `CLAUDE.md`.
- **End-user** (plugin installed via marketplace): keep `SESSION_LESSONS.md` for the engagement; share with the skill maintainer if a pattern is widely useful.
