# Map config defaults — required kepler boilerplate Builder won't load without

`keplerMapConfig.config` and `keplerMapConfig.config.visState` have a number of fields Builder's loader **requires to be present with specific shapes** — even on a minimal map where the user has configured nothing. The screenshot `light` engine (deck.gl `fetchMap`) reads only data + layers + basemap, so it doesn't notice these missing fields; Builder's loader iterates all of them during initial load and crashes when they're `null` / `{}` / absent.

Every shape below is **verified against a manually-created Builder map** (the only reliable source of truth — `carto maps schema` marks many of these as optional even though Builder's runtime treats them as required).

## Required `keplerMapConfig.config` keys

Of these seven, the schema requires only `mapState` and `visState` — the rest are optional to the validator and are here because Builder's runtime wants them anyway. Emit all seven:

```json
{
  "config": {
    "basemapConfig":  { "styleId": "voyager" },
    "mapState":       { ... },
    "mapStyle":       { "styleType": "voyager" },
    "uiState": {
      "commentsVisible": true,
      "controlsPaneOpen": false,
      "descriptionOpen": false,
      "descriptionPreview": false
    },
    "filters":        { "<dataset-id>": {}, ... },
    "spatialFilter":  null,
    "visState":       { ... }
  }
}
```

`mapState` is rejected when absent, not defaulted — a viewport has no right answer, and a map that opens over the wrong part of the world reads as working. `mapStyle` is the opposite: omit it and it is filled from `basemapConfig.styleId`. Emitting it explicitly, as above, is still the right habit — it keeps the pair visible in the bundle and the two ids obviously in step.

`uiState` as `{}` (empty) **crashes Builder** — its panel initialization reads each of the four sub-fields and throws on undefined. Always populate with the four defaults above.

`spatialFilter` MUST be `null` (or omitted) — **never `{}`**. The schema's `anyOf [object, null]` accepts both. Builder UI writes `null`. `carto maps validate` and `carto maps create` both pass with `{}`. But Builder's loader iterates `spatialFilter` expecting a populated GeoJSON Feature shape; with `{}` it dereferences a non-existent `.geometry.type` (or similar), throws `TypeError: Cannot read properties of undefined (reading 'type')` inside an `Array.map`, and the `ErrorBoundary` shows the inline 500 page. There is **no failed XHR** and **no console.error** (TrackJS silences `componentDidCatch`'s log). This is the most pernicious "validate-passes, runtime-crashes" trap caught so far. See `lessons.md` "`spatialFilter: {}` crashes Builder even with zero datasets".

## Required `visState` keys

Only `layers` is required by the schema; the other five are optional there and emitted for Builder's benefit:

```json
{
  "visState": {
    "animationConfig": { "currentTime": null, "speed": 1 },
    "filters":         [],
    "interactionConfig": {
      "brush":      { "enabled": false, "size": 0.5 },
      "coordinate": { "enabled": false },
      "geocoder":   { "enabled": false },
      "tooltip":    { "compareMode": false, "compareType": "absolute", "enabled": true }
    },
    "layerBlending": "normal",
    "layers":        [ ... ],
    "splitMaps":     []
  }
}
```

| Field | Required shape | Why it can't be `null` |
|---|---|---|
| `animationConfig` | `{currentTime: null, speed: 1}` | Time-slider widgets read it even when no temporal data is configured |
| `filters` (inside visState) | `[]` empty array | Kepler legacy filter list. **Different from `config.filters` at the top level (object keyed by dataset id) — both must be present** |
| `interactionConfig` | `{brush, coordinate, geocoder, tooltip}` with the sub-objects above | Builder's event-handler setup iterates the keys. `tooltip` is mandatory whenever `interactionConfig` is present — the static SDK reads `tooltip.enabled` after guarding only the parent object |
| `layerBlending` | string `"normal"` | Layer compositing mode; deck.gl default but Builder won't infer |
| `splitMaps` | `[]` empty array | Split-view feature reads this; `null` crashes the panel even when no split is active |

### `interactionConfig` is the legacy popup path — mind the interaction with `popupSettings`

`interactionConfig` is the pre-`popupSettings` way of declaring tooltips, and it is deprecated. Two consequences matter for migration:

- When a map **has** `popupSettings`, `interactionConfig` is ignored. Never author popups here.
- When a map has **no** `popupSettings`, Builder converts `interactionConfig` into one on load, and the conversion is one-way: the next save persists the generated `popupSettings`.

That second branch is exactly the case this skill produces for a source layer with no `popupInfo` (see [`popup-mapping.md`](popup-mapping.md) "Empty popups"). Emitting `tooltip: {enabled: true}` there asks Builder to manufacture the popups the migration deliberately left out. **When the map emits no `popupSettings`, set `"enabled": false` on the tooltip**; keep `true` only when `popupSettings` is present, where it is inert anyway.

## `basemapConfig.type` — always omit

`basemapConfig.type` is **not required for any basemap**. The shape Builder UI writes is `{"styleId": "<id>"}` regardless of whether the basemap is a CARTO default, a Google variant, or a custom MapLibre style. The `styleId` alone is enough for Builder to route the basemap to the right provider.

Earlier guidance to set `type: "carto"` / `type: "google"` / `type: "custom"` was wrong — verified against manually-created Builder maps with each provider.

`basemapConfig` takes exactly two keys — `styleId` (required) and the optional `visibleLayerGroups` — and nothing else. Any other key, `type` included, is dropped.

| Basemap source | `basemapConfig` shape |
|---|---|
| CARTO default (`voyager` / `positron` / `dark-matter`) | `{"styleId": "<id>"}` |
| Google (`satellite` / `roadmap` / `hybrid` / `terrain` / `google-3d` / `google-positron` / `google-dark-matter` / `google-voyager`) | `{"styleId": "<id>"}` |
| Custom MapLibre style | `{"styleId": "custom:<accountBasemapId>"}`, with the style's own configuration in `config.customBaseMaps.customStyle` under that same id |

`visibleLayerGroups` is all-or-nothing: omit it to accept the defaults, or send **all six** keys (`land`, `water`, `building`, `road`, `border`, `label`). A partial record hides the groups it leaves out in Builder while an embed ignores the filtering entirely, so the same map renders differently in the two.

`mapStyle.styleType` mirrors `basemapConfig.styleId` in all cases (per `basemap-mapping.md`'s "Setting both fields" rule).

## How to apply during migration

Insert these defaults as a single compose step after layers and datasets are built:

```python
def apply_mapconfig_defaults(kepler_map_config, dataset_ids, basemap_style_id):
    cfg = kepler_map_config["config"]

    cfg["uiState"] = {
        "commentsVisible": True,
        "controlsPaneOpen": False,
        "descriptionOpen": False,
        "descriptionPreview": False,
    }
    cfg["filters"] = {ds_id: {} for ds_id in dataset_ids}   # top-level object form

    # Legacy tooltip path: Builder turns it into popupSettings when the map has
    # none, so leave it disabled unless the map actually ships popupSettings.
    has_popups = bool(cfg.get("popupSettings", {}).get("layers"))

    vs = cfg["visState"]
    vs["animationConfig"]   = {"currentTime": None, "speed": 1}
    vs["filters"]           = []                            # legacy array form (different from cfg.filters!)
    vs["interactionConfig"] = {
        "brush":      {"enabled": False, "size": 0.5},
        "coordinate": {"enabled": False},
        "geocoder":   {"enabled": False},
        "tooltip":    {"compareMode": False, "compareType": "absolute", "enabled": has_popups},
    }
    vs["layerBlending"]     = "normal"
    vs["splitMaps"]         = []

    # basemapConfig — styleId alone, whatever the provider. No `type` field exists.
    cfg["basemapConfig"] = {"styleId": basemap_style_id}
    cfg["mapStyle"]      = {"styleType": basemap_style_id}

    # spatialFilter — explicit null. NEVER {} (Builder runtime crashes — validator accepts both).
    cfg["spatialFilter"] = None
```

Call this once per map after composing `visState.layers`, `popupSettings` and the datasets.

## Why these aren't surfaced by `carto maps schema`

`carto maps schema` documents the **schema** — what fields are accepted. Builder's **runtime** is stricter: many fields marked optional in the schema are effectively required for the loader to not crash. The validator and `carto maps create` both pass when these fields are null/absent; `light`-engine screenshots render fine. Builder is the only thing that breaks, and only at view time.

**Methodology**: never build a `keplerMapConfig` from scratch using only the schema's `required` fields. Always start from a manually-created Builder map's structure (a "known-good template") and modify the layer/dataset details. The known-good template captures Builder's effective requirements that the schema doesn't.

See `lessons.md` "Diff against a manually-created Builder map" for the workflow that surfaces missing-field bugs.
