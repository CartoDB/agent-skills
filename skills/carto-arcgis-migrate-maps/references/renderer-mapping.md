# Renderer mapping — ArcGIS `drawingInfo` → kepler `visState.layers[]`

ArcGIS Web Maps store layer styling in `operationalLayers[].layerDefinition.drawingInfo` (or `operationalLayers[].drawingInfo` directly in older specs). CARTO Builder uses the kepler.gl-derived `keplerMapConfig.config.visState.layers[]` shape — `visualChannels` for data-bound styling and `visConfig` for per-layer constants.

This feature covers three renderer types end-to-end: `simple`, `uniqueValue`, `classBreaks`. Heatmap, dotDensity, temporal, and predominance fall back to simple-color and are recorded as `Notes: renderer-fallback: <type>` on the manifest entry.

Always validate the emitted JSON against the live schema:

```bash
carto maps schema layer.tileset --json
carto maps schema visualChannels --json
carto maps schema visConfig --json
```

If this document disagrees with the live schema, the schema wins.

## Layer-type decision

ArcGIS layer types map to kepler layer subtypes per the source data's geometry, not the ArcGIS class:

| Source data geometry (from `carto connections describe <conn> <fqn>`) | kepler layer subtype |
|---|---|
| `point` | `tileset` (point) |
| `line` / `linestring` | `tileset` (line) |
| `polygon` / `multipolygon` | `tileset` (polygon) |
| `h3` (pre-aggregated) | `h3` |
| `quadbin` (pre-aggregated) | `quadbin` |

Don't trust the source layer's `esriGeometryType` alone — use the migrated DW table's geometry type so kepler renders correctly.

## Renderer 1: `simple`

Source shape (basic `esriSMS` example):

```json
{
  "type": "simple",
  "symbol": {
    "type": "esriSMS",
    "color": [255, 0, 0, 255],
    "size": 8,
    "outline": { "color": [0, 0, 0, 255], "width": 1 }
  },
  "label": "Stores"
}
```

Translation: single-color layer with the symbol's color/size as `visConfig` defaults. No visualChannels.

```json
{
  "type": "tileset",
  "config": {
    "visConfig": {
      "fillColor": [255, 0, 0],
      "radius": 8,
      "strokeColor": [0, 0, 0],
      "strokeWidth": 1,
      "opacity": 1.0
    },
    "visualChannels": {}
  }
}
```

For polygons: use `fillColor` from `symbol.color`, `strokeColor` + `strokeWidth` from `symbol.outline`. For lines: `strokeColor` + `strokeWidth` only. The exact field names depend on kepler subtype — fetch the live schema before composing.

### Per-symbol-type sub-branches

`simple` covers more than `esriSMS`. Handle each symbol type:

| Symbol `type` | What it is | Translation |
|---|---|---|
| `esriSMS` (style `esriSMSCircle`) | Simple circle marker | Translates faithfully per the example above |
| `esriSMS` (style `esriSMSSquare` / `Diamond` / `Cross` / `X` / `Triangle`) | Non-circle simple marker | Collapse to circle — kepler tileset has no built-in non-circle marker. Preserve color + size; record `Notes: marker-shape-collapsed: <style>` |
| `esriPMS` (picture marker — URL or base64 image) | Custom icon | Follow [`marker-upload.md`](marker-upload.md): acquire + dedup-by-hash + multipart `POST /assets` (`type=MapMarker`) + reference the returned asset `id` in `visConfig.customMarkersId` (or `customMarkersField` + `customMarkersRange.markerMap[]` for categorical — verify against live schema). Size from `symbol.width` / `height` |
| `esriSLS` | Simple line | Translates faithfully — `strokeColor` + `strokeWidth` |
| `esriSFS` (solid polygon fill) | Solid polygon fill | Translates faithfully — `fillColor` (+ `strokeColor` if outline present) |
| `esriPFS` (picture fill polygon) | Pattern/picture polygon fill | Collapse to solid `fillColor` — Builder has no pattern fills. Use the picture's dominant color if extractable, else a sensible default. Record `Notes: picture-fill-collapsed: <source>` |
| `esriTS` (text symbol) | Text label | Doesn't apply to renderer translation (text symbols belong to `labelingInfo`, not `drawingInfo`) — skip silently |
| **`CIMSymbolReference`** (from ArcGIS Pro 2.0+) | Cartographic Information Model symbol (richer than legacy `esri*` shapes; multi-layered, typed colors, effects, variations) | Per [`cim-symbols.md`](cim-symbols.md): walk `symbol.symbolLayers[]`. `CIMPictureMarker` → same flow as `esriPMS` via `marker-upload.md` (most CIM URLs are `data:` URIs — decode the base64 directly). `CIMVectorMarker` / `CIMCharacterMarker` → colored circle using the extracted dominant fill color + size. `CIMSolidFill` / `CIMSolidStroke` (on line / polygon symbols) → translate faithfully. Pattern fills / gradients / effects / variations → collapse with descriptive Notes |

For `esriPMS`, the resulting kepler config looks like (live-schema-validated names):

```json
{
  "type": "tileset",
  "config": {
    "visConfig": {
      "customMarkers": true,
      "customMarkersId": "<asset-id-returned-by-POST-/assets>",
      "radius": 12,
      "opacity": 1.0
    },
    "visualChannels": {}
  }
}
```

Reference the asset `id`, not the presigned `url` — Builder's `KeplerMapConfigSerializer` resolves `customMarkersId` to a fresh presigned `customMarkersUrl` on every map read.

`radius` is half of `max(symbol.width, symbol.height)` (1pt ≈ 1px for marker icons).

## Renderer 2: `uniqueValue`

Source shape:

```json
{
  "type": "uniqueValue",
  "field1": "category",
  "uniqueValueInfos": [
    { "value": "A", "symbol": {"color": [255, 0, 0, 255]}, "label": "Category A" },
    { "value": "B", "symbol": {"color": [0, 255, 0, 255]}, "label": "Category B" }
  ],
  "defaultSymbol": { "color": [128, 128, 128, 255] }
}
```

Translation: categorical color binding via visualChannels. Each `uniqueValueInfos[i].value` maps to `uniqueValueInfos[i].symbol.color` in a custom ColorRange.

```json
{
  "visualChannels": {
    "colorField": { "name": "category", "type": "string" },
    "colorScale": "ordinal"
  },
  "visConfig": {
    "colorRange": {
      "name": "Custom from ArcGIS",
      "type": "custom",
      "category": "Custom",
      "colors": ["#ff0000", "#00ff00"]
    }
  }
}
```

The categorical domain is implicit (ordinal scales pick up the value list from the source via `/stats`).

**Cardinality cap**: if `uniqueValueInfos.length > 12`, fall back to the closest CARTO qualitative palette (`Bold` or `Pastel`) and record `Notes: renderer-fallback: high-cardinality categorical (N>12)`. Builder doesn't render meaningful legends past 12 categories.

**`field2` / `field3`** (multi-field categorical): not supported in v1. Fall back to `field1` only and record `Notes: renderer-fallback: uniqueValue multi-field collapsed to <field1>`.

### Per-category picture markers (`esriPMS` and `CIMSymbolReference`) — common pattern

A very common ArcGIS pattern: each category has its own icon, not just its own color (e.g. different icons per store type, hazard level, observation kind). Works for both legacy `esriPMS` and ArcGIS Pro `CIMSymbolReference` (containing a `CIMPictureMarker` symbol layer) — the extractor differs slightly (see [`cim-symbols.md`](cim-symbols.md) for the CIM `data:` URI decoding) but the dedup-upload-reference flow is identical.

```json
{
  "type": "uniqueValue",
  "field1": "storeType",
  "uniqueValueInfos": [
    { "value": "Cafe",       "symbol": { "type": "esriPMS", "imageData": "...", "width": 24, "height": 24 } },
    { "value": "Restaurant", "symbol": { "type": "esriPMS", "imageData": "...", "width": 24, "height": 24 } },
    { "value": "Bakery",     "symbol": { "type": "esriPMS", "imageData": "...", "width": 24, "height": 24 } }
  ]
}
```

Translation flow per [`marker-upload.md`](marker-upload.md):

1. For each `uniqueValueInfos[i].symbol`, acquire + content-hash + upload (dedup across categories — identical icons upload once).
2. Check the live kepler schema (`carto maps schema layer.tileset`) for categorical icon-binding support:
   - **If `visualChannels.customMarkersField` + `visConfig.customMarkersRange.markerMap[]` are exposed** → emit categorical icon binding with the per-value `markerId` map (the asset `id` returned by `POST /assets`, not the presigned URL).
   - **If not exposed** → collapse to a single icon (most common by row count, or first in source order if unknown) using `visConfig.customMarkersId`, and record `Notes: uniqueValue-icons-collapsed-to-single (<N> distinct icons)`. Users can reconstruct per-category icons manually in Builder if needed.

The dedup cache lives in `out/markers/.cache.json` and survives across runs; re-running the migration won't re-upload icons that already succeeded.

## Renderer 3: `classBreaks`

Source shape:

```json
{
  "type": "classBreaks",
  "field": "population",
  "minValue": 0,
  "classBreakInfos": [
    { "classMaxValue": 1000,    "symbol": {"color": [254, 229, 217, 255]}, "label": "0-1k" },
    { "classMaxValue": 10000,   "symbol": {"color": [252, 174, 145, 255]}, "label": "1k-10k" },
    { "classMaxValue": 100000,  "symbol": {"color": [251, 106, 74, 255]},  "label": "10k-100k" },
    { "classMaxValue": 1000000, "symbol": {"color": [165, 15, 21, 255]},   "label": "100k+" }
  ]
}
```

Translation: quantize color binding. Break boundaries become `colorDomain`; symbol colors become a custom sequential ColorRange.

```json
{
  "visualChannels": {
    "colorField": { "name": "population", "type": "real" },
    "colorScale": "quantize"
  },
  "visConfig": {
    "colorDomain": [0, 1000, 10000, 100000, 1000000],
    "colorRange": {
      "name": "Custom sequential",
      "type": "custom",
      "category": "Custom",
      "colors": ["#fee5d9", "#fcae91", "#fb6a4a", "#a50f15"]
    }
  }
}
```

Note: `colorDomain` includes both `minValue` (start) and every `classMaxValue` (the breakpoints). Length is `classBreakInfos.length + 1`.

For heavy-tailed distributions (population, GDP, revenue) the source's break choices were the user's deliberate decision — preserve them rather than re-binning. CARTO's `quantize` honors the explicit `colorDomain`.

## Visual variables (additive on top of any renderer)

```json
{
  "visualVariables": [
    { "type": "colorInfo",   "field": "z", "stops": [{"value": 0, "color": [...]}, ...] },
    { "type": "sizeInfo",    "field": "x", "stops": [{"value": 0, "size": 4}, ...] },
    { "type": "opacityInfo", "field": "y", "stops": [{"value": 0, "opacity": 0.1}, ...] }
  ]
}
```

Each maps to a kepler visualChannel:

| ArcGIS visualVariable | kepler equivalent |
|---|---|
| `colorInfo` | `colorField` + `colorScale: "quantize"`; `stops[].value` → `colorDomain`; `stops[].color` → `colorRange.colors` |
| `sizeInfo` | `sizeField` + `sizeScale: "linear"` (or `quantize`); `stops[].value` → `sizeDomain`; `stops[].size` → `sizeRange` |
| `opacityInfo` | If single-value, set `visConfig.opacity`; if data-bound, route to `opacityField` if Builder supports it (fetch schema), else skip with Note |

**Conflict resolution**: when both the renderer AND a `visualVariable` bind color, the visualVariable wins (matches ArcGIS rendering precedence). Record `Notes: visualVariable-color overrode renderer-color`.

## Color helpers

ArcGIS colors are RGBA arrays `[r, g, b, a]` in 0-255. Convert to hex for kepler:

```python
def arcgis_color_to_hex(c):
    return "#{:02x}{:02x}{:02x}".format(c[0], c[1], c[2])

def arcgis_alpha_to_opacity(c):
    return round(c[3] / 255, 2)  # 0.0 - 1.0
```

Apply the alpha channel to `visConfig.opacity` (per-layer, not per-feature unless `opacityInfo` is present).

## Unsupported renderers — fallback table

| Renderer `type` | Fallback | Note recorded |
|---|---|---|
| `heatmap` | simple-color, opacity 0.5 | `renderer-fallback: heatmap (use h3/quadbin layer manually for parity)` |
| `dotDensity` | simple-color, smaller radius | `renderer-fallback: dotDensity (Builder has no 1:1 equivalent)` |
| `temporal` | simple-color from snapshot's static styling | `renderer-fallback: temporal (use Builder timeseries widget manually)` |
| `predominance` | simple-color with the highest-weighted variable's color | `renderer-fallback: predominance` |
| `pieChart` (per-feature charts) | simple-color | `renderer-fallback: pieChart (Builder doesn't render per-feature pies)` |
| Anything else | simple-color from the layer's first symbol | `renderer-fallback: <type>` |

The skill never blocks on an unsupported renderer — fall back, note, continue. The user can refine post-migration.

## Required non-null layer-config fields

Like `mapconfig-defaults.md`'s top-level boilerplate, the **layer config** has fields the schema marks optional but Builder's loader requires non-null. Verified missing-field crashes:

| Field | Required shape | Notes |
|---|---|---|
| `config.visConfig.strokeColor` | RGB int array `[r, g, b]` | The active stroke color |
| `config.visConfig.initialStrokeColor` | RGB int array `[r, g, b]` — **must be set, not null** | The "original" stroke before a visual variable applies. Builder's "revert to default" UI reads this; null crashes layer init. Default to the same value as `strokeColor`. |
| `config.visConfig.fillColor` | RGB int array `[r, g, b]` | Active fill color (for point / polygon layers). |
| `config.visConfig.initialFillColor` | RGB int array `[r, g, b]` — **must be set, not null** | Same logic as `initialStrokeColor`: default to the same value as `fillColor`. |
| `config.visConfig.opacity` | float 0.0-1.0 | Not `null`. |
| `config.visConfig.radius` | number | Not `null`. |
| `config.visConfig.thickness` | number | Line / stroke width. Not `null`. |

When composing a layer config, normalize defaults before adding it to `visState.layers[]`:

```python
def normalize_layer_defaults(layer):
    vc = layer["config"]["visConfig"]
    # Mirror initial colors from active colors when the agent didn't set them
    if vc.get("initialStrokeColor") is None:
        vc["initialStrokeColor"] = vc.get("strokeColor", [0, 0, 0])
    if vc.get("initialFillColor") is None:
        vc["initialFillColor"] = vc.get("fillColor", [128, 128, 128])
    # Sensible non-null defaults for the others
    vc.setdefault("opacity", 0.8)
    vc.setdefault("thickness", 1)
    return layer
```

## Iterative validation

After composing each layer's JSON fragment:

```bash
carto maps validate /tmp/<webmap-slug>.json --json
```

Most renderer-translation bugs surface here, not at `create` time. The validator is fast (Tier-1 offline) — run it after every meaningful edit. If after 3 iterations the layer still fails validation, mark the Web Map `failed` with `Failure: <validator-error-summary>` and continue to the next entry.
