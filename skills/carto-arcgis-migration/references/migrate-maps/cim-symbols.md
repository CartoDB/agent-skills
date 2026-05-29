# CIM symbols — handling ArcGIS Pro's symbol format

ArcGIS Pro publishes layers using the Cartographic Information Model (CIM), a richer symbol format than the legacy `esriSMS` / `esriPMS` / `esriSLS` / `esriSFS` shapes. CIM symbols appear in the Web Map JSON or Feature Service `drawingInfo` as `CIMSymbolReference` — a wrapper around a `CIMPointSymbol`, `CIMLineSymbol`, `CIMPolygonSymbol`, or `CIMTextSymbol` containing one or more **symbol layers** (`symbolLayers[]`).

This file documents what CIM constructs the skill supports faithfully, what it collapses to a simpler form, and where the inevitable cartographic loss gets recorded in `Notes:` on the manifest entry.

## When CIM symbols appear

CIM is the default symbol format for layers authored in **ArcGIS Pro 2.0+**. Legacy ArcMap-published services and older Map Viewer Classic Web Maps still use `esriSMS` / `esriPMS` / etc. A single portal often has both — a Feature Service published from Pro carries CIM in its drawingInfo; the same Web Map referencing both Pro- and ArcMap-published services will mix shapes. The skill handles both via the detection branch.

## Detection

```python
def is_cim_symbol(symbol):
    return symbol.get("type") == "CIMSymbolReference"
```

When true, walk into `symbol["symbol"]` (the actual CIM symbol) and handle per the per-type sections below. CIM appears anywhere a legacy symbol can appear: `simple.symbol`, `uniqueValueInfos[i].symbol`, `classBreakInfos[i].symbol`.

## CIM color extraction

CIM colors are **typed objects** (unlike legacy RGBA arrays). Build a single extractor and use it everywhere:

```python
import colorsys

def cim_color_to_rgb(c):
    """Returns (r, g, b) ints 0-255 from a CIM color."""
    if not c:
        return (128, 128, 128)
    t = c.get("type")
    v = c.get("values", [])
    if t == "CIMRGBColor":      # [r, g, b, alpha%]
        return (int(v[0]), int(v[1]), int(v[2]))
    if t == "CIMHSVColor":      # [h°, s%, v%, alpha%]
        r, g, b = colorsys.hsv_to_rgb(v[0]/360, v[1]/100, v[2]/100)
        return (int(r*255), int(g*255), int(b*255))
    if t == "CIMHSLColor":      # [h°, s%, l%, alpha%]
        r, g, b = colorsys.hls_to_rgb(v[0]/360, v[2]/100, v[1]/100)
        return (int(r*255), int(g*255), int(b*255))
    if t == "CIMCMYKColor":     # [c%, m%, y%, k%, alpha%] — no-color-profile formula
        c_, m, y, k = v[0]/100, v[1]/100, v[2]/100, v[3]/100
        return (int(255*(1-c_)*(1-k)), int(255*(1-m)*(1-k)), int(255*(1-y)*(1-k)))
    if t == "CIMGrayColor":     # [gray, alpha%]
        return (int(v[0]), int(v[0]), int(v[0]))
    return (128, 128, 128)      # unknown — fall back to grey

def cim_color_to_opacity(c):
    """Returns 0.0-1.0 from a CIM color's alpha%."""
    if not c:
        return 1.0
    v = c.get("values", [])
    t = c.get("type")
    if t in ("CIMRGBColor", "CIMHSVColor", "CIMHSLColor"):
        return v[3] / 100 if len(v) > 3 else 1.0
    if t == "CIMCMYKColor":
        return v[4] / 100 if len(v) > 4 else 1.0
    if t == "CIMGrayColor":
        return v[1] / 100 if len(v) > 1 else 1.0
    return 1.0
```

**CIM alphas are 0-100 (percent)**, not 0-255 like legacy colors. Forgetting this turns every map into "fully transparent" — easy mistake. The CMYK-to-RGB conversion is the simple no-color-profile formula; ICC-profile-aware conversion is out of scope (CIM almost always emits RGB in practice).

## `CIMPointSymbol` — walk `symbolLayers[]`

Each layer is one of these types. Handle the topmost rendering layer (typically the last marker layer in source order — earlier layers are halos/strokes):

| Symbol layer type | Translation |
|---|---|
| **`CIMPictureMarker`** | The easy case. Treat like `esriPMS`: extract the `url` (often a `data:image/png;base64,...` URI — see "Picture markers" below), feed into [`marker-upload.md`](marker-upload.md). Single upload per unique icon via multipart `POST /assets`; categorical icons supported when the live kepler schema exposes `customMarkersField` + `customMarkersRange.markerMap[]`. Size from `CIMPictureMarker.size`. |
| **`CIMVectorMarker`** | Vector graphics with inner CIM symbol layers. Extract the dominant fill color from `markerGraphics[0].symbol.symbolLayers[]` — first `CIMSolidFill`'s `color`. Apply as a colored circle with `radius = CIMVectorMarker.size / 2`. Record `Notes: cim-vector-marker-collapsed-to-circle (color=#<hex>, size=<n>pt)`. Full vector-marker rendering is out of scope — would require a CIM-to-raster renderer this toolchain doesn't have. |
| **`CIMCharacterMarker`** | Glyph from a font (Esri dingbats, Wingdings, custom symbol font). Extract color from `symbol.symbolLayers[0].color`. Apply as a colored circle with `radius = CIMCharacterMarker.size / 2`. Record `Notes: cim-character-marker-collapsed-to-circle (font=<fontFamilyName>, char=<characterIndex>)`. Font-based glyph rendering is out of scope; collapse is faithful enough for most operational maps. |

For a **`CIMPointSymbol` with multiple marker layers** (e.g. a halo stroke + a picture marker + an inner accent), pick the topmost marker (last `CIMPicture/Vector/CharacterMarker` in source order, usually the most visually prominent). Drop the others; record `Notes: cim-multi-layer-collapsed (<N> layers → 1; kept top marker <type>)`.

## `CIMLineSymbol` — walk `symbolLayers[]`

| Symbol layer type | Translation |
|---|---|
| `CIMSolidStroke` | `strokeColor` from `color`; `strokeWidth` from `width` (in points; close enough to pixels at typical zoom levels). The common case. |
| `CIMPictureStroke` / `CIMHatchStroke` | Pattern lines. Builder has no line patterns. Collapse to a `CIMSolidStroke` color + width derived from the underlying stroke. Record `Notes: cim-line-pattern-collapsed: <type>`. |
| `CIMVectorMarker` (as a line ornament — arrow, dash mark) | Line ornaments aren't in Builder. Drop the ornament layer; preserve the line color/width from the other strokes. Record `Notes: cim-line-ornament-dropped`. |

When multiple `CIMSolidStroke` layers are present (e.g. casing + main stroke), pick the topmost (last in source order) for color and width.

## `CIMPolygonSymbol` — walk `symbolLayers[]`

| Symbol layer type | Translation |
|---|---|
| `CIMSolidFill` | `fillColor` from `color`. The most common case. |
| `CIMSolidStroke` | `strokeColor` + `strokeWidth` from `color` / `width`. |
| `CIMPictureFill` / `CIMHatchFill` / `CIMGradientFill` | Patterns and gradients. Builder doesn't support these on polygons. Collapse to a single color: `CIMGradientFill` → midpoint stop color; `CIMHatchFill` → the hatch line color as a flat fill; `CIMPictureFill` → the picture's dominant color (or default grey if unextractable). Record `Notes: cim-fill-pattern-collapsed: <type>`. |

When both `CIMSolidFill` AND `CIMSolidStroke` are present, use both. When only one is present, leave the other unset (kepler's default).

## `CIMTextSymbol`

Belongs to labeling (`labelingInfo`), not renderer drawingInfo. If encountered in a renderer context (shouldn't happen but the spec allows it), skip silently — text-only renderers don't render features.

## Effects (halos, glows, drop shadows)

CIM supports symbol effects via `symbolLayers[i].effects[]`. Builder has no equivalent:

```python
def has_effects(symbol_layer):
    return bool(symbol_layer.get("effects"))
```

Drop the `effects` array; the base color/shape still applies. Record `Notes: cim-effects-dropped: <effect-types>` when at least one effect was present.

## Multi-layer symbol heuristic

Real-world CIM symbols often stack 3-6 layers (halo + outline + main marker + secondary marker + drop shadow + ...). The skill's collapse heuristic, applied in this priority order:

1. **Markers first**: pick the topmost `CIMPicture/Vector/CharacterMarker` (largest `size` if multiple are tied for "topmost").
2. **Fills next**: for compound symbols, the largest `CIMSolidFill` is the "main color".
3. **Strokes last**: only use strokes when no fill or marker is present (i.e. on line symbols, or polygon symbols with outline only).

Record `Notes: cim-multi-layer-collapsed (<N> source layers → 1 kepler layer)` for any symbol the skill collapses (> 1 layer in source).

## Variations and primitive overrides

CIM symbols can be **varied per feature** via `CIMSymbolReference.symbolName` lookups + `CIMVisualVariable` references, or via `primitiveOverrides[]` (per-attribute runtime symbol modifications). These are powerful (and Arcade-like in their per-feature dynamicism) but out of scope:

- `symbolName` variations → skill uses the base CIM symbol only. Record `Notes: cim-variations-not-applied (<N>)`.
- `primitiveOverrides[]` → drop the overrides; record `Notes: cim-primitive-overrides-dropped (<N>)`.

For most practical use cases, a `uniqueValue` or `classBreaks` renderer with per-class CIM symbols is more common than per-feature variations — and those translate normally through the renderer-mapping flow (each class's CIM symbol is walked individually).

## Picture markers — same pipeline as `esriPMS`

`CIMPictureMarker` is the closest CIM analogue to legacy `esriPMS`. The translation reuses [`marker-upload.md`](marker-upload.md) entirely — only the extraction step differs slightly because the image lives in a `url` field that's often a `data:` URI:

```python
import base64

def extract_cim_picture_bytes(picture_marker_layer):
    """Returns (bytes, ext) for a CIMPictureMarker symbol layer."""
    url = picture_marker_layer.get("url", "")
    if url.startswith("data:"):
        # data:image/<type>;base64,<base64>
        header, b64 = url.split(",", 1)
        ct = header.replace("data:", "").split(";")[0]
        ext = {"image/png": "png", "image/svg+xml": "svg", "image/jpeg": "jpg"}.get(ct, "png")
        return base64.b64decode(b64), ext
    # External URL — same fetch + sniff flow as esriPMS
    raw = _http_get_with_token(url)
    return raw, _ext_from_bytes_or_url(raw, url)
```

After extraction, the rest is identical: content-hash dedup → `POST /assets` (multipart, `type=MapMarker`) → reference the returned `id` in kepler `visConfig.customMarkersId` (or `customMarkersField` + `customMarkersRange.markerMap[]` for categorical). The `out/markers/.cache.json` cache treats CIM-extracted icons no differently from `esriPMS` ones — same icon (by content hash) uploads once. See [`marker-upload.md`](marker-upload.md) "Upload" for the multipart helper.

## Vector marker color extraction (graceful collapse)

When `CIMVectorMarker` is the only marker layer (no `CIMPictureMarker` available), extract the dominant color to make the colored-circle fallback feel less arbitrary:

```python
def dominant_color_from_cim_vector_marker(layer):
    """Walk markerGraphics[].symbol.symbolLayers[] for the first CIMSolidFill color."""
    for g in layer.get("markerGraphics", []):
        for s in g.get("symbol", {}).get("symbolLayers", []):
            if s.get("type") == "CIMSolidFill":
                return cim_color_to_rgb(s.get("color"))
        # No fill — try a stroke
        for s in g.get("symbol", {}).get("symbolLayers", []):
            if s.get("type") == "CIMSolidStroke":
                return cim_color_to_rgb(s.get("color"))
    return (128, 128, 128)  # neutral grey default
```

This gives the user a circle in roughly the right color, which is much more useful than a default-color circle. Size always from `CIMVectorMarker.size`.

## When in doubt

- Symbol's inner `type` is a `CIM*` variant not listed above (`CIMObjectMarker3D`, `CIMProceduralSymbol`, etc.)? Fall back to a colored circle at default size + neutral grey color; record `Notes: cim-symbol-unsupported: <type>`.
- Symbol has `useRealWorldSymbolSizes: true` (sizes interpreted in map units, not points/pixels)? Drop the flag silently — Builder uses pixel sizes throughout; the visual difference at typical zoom levels is minor.
- `symbolLayers[]` is empty? Fall back to a colored circle at default size + neutral grey; record `Notes: cim-symbol-empty`.
- A `CIMVectorMarker` has a single `markerGraphics[0]` that's a circle (`CIMGeometricEffectCircularSegment` or polygon approximating a circle)? Same colored-circle treatment — extract color, set size; no special-cased "this is actually round so it's faithful" logic. Builder's circle is close enough.
- The CIM symbol is wrapped in a `CIMScaleDependentSizeVariation` (different sizes per zoom level)? Use the default/middle scale's size. Record `Notes: cim-scale-dependent-sizes-collapsed` only if the size variation is significant (smallest:largest > 4x).
