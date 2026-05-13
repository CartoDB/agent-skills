# Map config defaults — required kepler boilerplate Builder won't load without

`keplerMapConfig.config` and `keplerMapConfig.config.visState` have a number of fields Builder's loader **requires to be present with specific shapes** — even on a minimal map where the user has configured nothing. The screenshot `light` engine (deck.gl `fetchMap`) reads only data + layers + basemap, so it doesn't notice these missing fields; Builder's loader iterates all of them during initial load and crashes when they're `null` / `{}` / absent.

Every shape below is **verified against a manually-created Builder map** (the only reliable source of truth — `carto maps schema` marks many of these as optional even though Builder's runtime treats them as required).

## Required `keplerMapConfig.config` keys

These seven keys must all be present at the `config` level:

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
    "filters":        { "<dataset-$ref>": {}, ... },
    "spatialFilter":  null,
    "visState":       { ... }
  }
}
```

`uiState` as `{}` (empty) **crashes Builder** — its panel initialization reads each of the four sub-fields and throws on undefined. Always populate with the four defaults above.

`spatialFilter` MUST be `null` (or omitted) — **never `{}`**. The schema's `anyOf [object, null]` accepts both. Builder UI writes `null`. `carto maps validate` and `carto maps create` both pass with `{}`. But Builder's loader iterates `spatialFilter` expecting a populated GeoJSON Feature shape; with `{}` it dereferences a non-existent `.geometry.type` (or similar), throws `TypeError: Cannot read properties of undefined (reading 'type')` inside an `Array.map`, and the `ErrorBoundary` shows the inline 500 page. There is **no failed XHR** and **no console.error** (TrackJS silences `componentDidCatch`'s log). This is the most pernicious "validate-passes, runtime-crashes" trap caught so far. See `lessons.md` "`spatialFilter: {}` crashes Builder even with zero datasets".

## Required `visState` keys

These six keys must all be present in `visState`:

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
| `interactionConfig` | `{brush, coordinate, geocoder, tooltip}` with the sub-objects above | Builder's event-handler setup iterates the keys |
| `layerBlending` | string `"normal"` | Layer compositing mode; deck.gl default but Builder won't infer |
| `splitMaps` | `[]` empty array | Split-view feature reads this; `null` crashes the panel even when no split is active |

## `basemapConfig.type` — always omit

`basemapConfig.type` is **not required for any basemap**. The shape Builder UI writes is `{"styleId": "<id>"}` regardless of whether the basemap is a CARTO default, a Google variant, or a custom MapLibre style. The `styleId` alone is enough for Builder to route the basemap to the right provider.

Earlier guidance to set `type: "carto"` / `type: "google"` / `type: "custom"` was wrong — verified against manually-created Builder maps with each provider.

| Basemap source | `basemapConfig` shape |
|---|---|
| CARTO default (`voyager` / `positron` / `dark-matter`) | `{"styleId": "<id>"}` |
| Google (`satellite` / `roadmap` / `hybrid` / `terrain` / `google-positron` / `google-dark-matter` / `google-voyager`) | `{"styleId": "<id>"}` |
| Custom MapLibre style | `{"styleId": "<id>", ...custom-style-config...}` |

`mapStyle.styleType` mirrors `basemapConfig.styleId` in all cases (per `basemap-mapping.md`'s "Setting both fields" rule).

## How to apply during migration

Insert these defaults as a single compose step after layers and datasets are built:

```python
def apply_mapconfig_defaults(kepler_map_config, datasets, basemap_style_id, basemap_source):
    """basemap_source: 'carto' | 'google' | 'custom'"""
    cfg = kepler_map_config["config"]

    cfg["uiState"] = {
        "commentsVisible": True,
        "controlsPaneOpen": False,
        "descriptionOpen": False,
        "descriptionPreview": False,
    }
    cfg["filters"] = {ds["$ref"]: {} for ds in datasets}  # top-level object form

    vs = cfg["visState"]
    vs["animationConfig"]   = {"currentTime": None, "speed": 1}
    vs["filters"]           = []                            # legacy array form (different from cfg.filters!)
    vs["interactionConfig"] = {
        "brush":      {"enabled": False, "size": 0.5},
        "coordinate": {"enabled": False},
        "geocoder":   {"enabled": False},
        "tooltip":    {"compareMode": False, "compareType": "absolute", "enabled": True},
    }
    vs["layerBlending"]     = "normal"
    vs["splitMaps"]         = []

    # basemapConfig — styleId alone is sufficient regardless of source
    cfg["basemapConfig"] = {"styleId": basemap_style_id}
    cfg["mapStyle"]      = {"styleType": basemap_style_id}

    # spatialFilter — explicit null. NEVER {} (Builder runtime crashes — validator accepts both).
    cfg["spatialFilter"] = None
```

Call this once per map after composing `visState.layers` and `datasets`.

## Why these aren't surfaced by `carto maps schema`

`carto maps schema` documents the **schema** — what fields are accepted. Builder's **runtime** is stricter: many fields marked optional in the schema are effectively required for the loader to not crash. The validator and `carto maps create` both pass when these fields are null/absent; `light`-engine screenshots render fine. Builder is the only thing that breaks, and only at view time.

**Methodology**: never build a `keplerMapConfig` from scratch using only the schema's `required` fields. Always start from a manually-created Builder map's structure (a "known-good template") and modify the layer/dataset details. The known-good template captures Builder's effective requirements that the schema doesn't.

See `lessons.md` "Diff against a manually-created Builder map" for the workflow that surfaces missing-field bugs.
