# Marker upload — preserving ArcGIS picture marker symbols

ArcGIS layers frequently style points with custom icons via `esriPMS` (Picture Marker Symbol). The image lives on the symbol as either a URL or base64-encoded `imageData`. To preserve these in the migrated Builder map, upload each unique icon to CARTO's workspace-api **`POST /assets`** endpoint, then reference the returned asset `id` in the kepler layer's marker config.

> **There is no `carto maps markers` CLI subcommand.** The CARTO CLI's `carto maps` surface is `list / get / create / update / delete / copy / validate / publish / schema / datasets / agents / screenshot` only. Marker assets upload via a multipart `POST /assets` call to the workspace API — the same endpoint Builder's UI uses when a user uploads a custom marker. **The `type` enum is `mapMarker`** (camelCase — `MapMarker` is 400-rejected: `Invalid enum value … Expected 'accountLogo' | 'mapMarker'`). `file=<binary>`. Response: `{ id, url }`. Permission required: `write:maps`. Accepted extensions: `png`, `svg` only.

This file documents the **detect → acquire → dedup → upload → reference → fallback** flow. The renderer translators in [`renderer-mapping.md`](renderer-mapping.md) call into this flow when they encounter `esriPMS` symbols on `simple` or `uniqueValue` renderers.

## When this flow runs

Per renderer:

- **`simple` renderer** with `symbol.type == "esriPMS"` — one icon for the whole layer.
- **`uniqueValue` renderer** with one or more `uniqueValueInfos[i].symbol.type == "esriPMS"` — per-category icons (often the most common ArcGIS pattern: different icon per store type / hazard level / category).
- **`classBreaks` renderer** with per-break picture markers — less common; same per-bin upload pattern as uniqueValue if encountered.
- **CIM picture markers** (`CIMSymbolReference` with a `CIMPictureMarker` symbol layer) — see [`cim-symbols.md`](cim-symbols.md). The extraction step differs (CIM URLs are typically `data:image/...;base64,...` URIs — decode the base64 directly rather than HTTP-fetching), but every subsequent step (dedup by content hash, upload, reference in kepler) is identical. The cache in `out/markers/.cache.json` doesn't distinguish CIM-sourced vs legacy `esriPMS`-sourced icons: same content hash → same single upload.

`esriPFS` (Picture Fill Symbol for polygons) and CIM `CIMPictureFill` / `CIMHatchFill` / `CIMGradientFill` (on polygons) are **not** uploaded — Builder doesn't support pattern fills. Fall back to solid `fillColor` derived from the picture's / pattern's dominant color (or default grey) with `Notes: picture-fill-collapsed: <source>` or `Notes: cim-fill-pattern-collapsed: <type>`.

## Detection

```python
def is_picture_marker(symbol):
    return symbol.get("type") == "esriPMS"
```

If true, the symbol has one of:

- `imageData` (base64-encoded image) + `contentType` (`image/png` / `image/svg+xml` / `image/jpeg`).
- `url` (external URL to the image, possibly portal-hosted).
- Both (`imageData` is the embedded version of what `url` would serve).

## Acquisition — prefer `imageData` over `url`

`imageData` is always reachable; the renderer's `url` may need portal auth that the agent's token can't reach, or may point at a host firewalled from where the agent runs.

```python
import base64, hashlib
from pathlib import Path

MARKERS_DIR = Path("out/markers")
MARKERS_DIR.mkdir(parents=True, exist_ok=True)

def acquire_icon(symbol):
    if symbol.get("imageData"):
        raw = base64.b64decode(symbol["imageData"])
        ext = _ext_from_content_type(symbol.get("contentType", "image/png"))
    elif symbol.get("url"):
        raw = _http_get_with_token(symbol["url"])  # uses ARCGIS_TOKEN
        ext = _ext_from_bytes_or_url(raw, symbol["url"])
    else:
        return None  # No usable source — caller falls back to colored circle

    digest = hashlib.sha256(raw).hexdigest()[:16]
    path = MARKERS_DIR / f"{digest}.{ext}"
    if not path.exists():
        path.write_bytes(raw)
    return path, digest

def _ext_from_content_type(ct):
    return {
        "image/png":     "png",
        "image/svg+xml": "svg",
        "image/jpeg":    "jpg",
        "image/gif":     "png",  # CARTO doesn't accept GIF; convert via Pillow
    }.get(ct, "png")

def _ext_from_bytes_or_url(data, url):
    if data.startswith(b"<svg") or data.startswith(b"<?xml"): return "svg"
    if data.startswith(b"\x89PNG"):                          return "png"
    if data.startswith(b"\xff\xd8\xff"):                     return "jpg"
    if url.lower().endswith(".svg"):                         return "svg"
    if url.lower().endswith(".png"):                         return "png"
    return "png"  # default; CARTO will reject if truly unsupported
```

`POST /assets` accepts **PNG and SVG only** (`workspace-api/src/services/assets-service.ts` `hasValidExtension`). JPEG and GIF must be converted to PNG before upload (`Pillow`'s `Image.open(...).save("file.png")` — one frame only for animated PNG / APNG / GIF).

## Dedup via content hash

A single Web Map often references the same icon across 5+ layers (a "store" icon shared across regions). Hash the bytes (`sha256` truncated to 16 chars) and key the upload on the hash — same icon → single `POST /assets` call, reused across layers. The `upload_marker_asset` helper below carries an in-process `_ASSET_CACHE`; persist it to `out/markers/.cache.json` (`{ "<hash>": { id, url, content_type, uploaded_at } }`) so the cache survives across Web Map migrations AND re-runs — re-running `migrate-maps` against a failed entry won't re-upload icons that already succeeded. Icon files also land under `out/markers/<hash>.<ext>` for post-mortem inspection.

## Upload

Multipart `POST /assets` to the workspace API. Resolve the base URL and token from `carto auth status --json` + `~/.carto_credentials.json` so no tenant is hardcoded. **The `type` field is `mapMarker`** (camelCase — `MapMarker` 400s). Sniff the bytes header before trusting the source's `contentType` (ArcGIS sometimes lies — National Rail's PNG was declared `image/jpeg` and the workspace-api 400'd on it).

```python
import io, json, subprocess, base64, hashlib
from pathlib import Path
from PIL import Image

def _workspace_api_base():
    status = json.loads(subprocess.check_output(["carto", "auth", "status", "--json"]))
    return f"https://workspace-{status['tenant_id']}.app.carto.com"

def _bearer_token():
    creds = json.loads(Path("~/.carto_credentials.json").expanduser().read_text())
    return creds["profiles"][creds["current_profile"]]["token"]

def _sniff(raw):
    """Return (content_type, ext, raw) — converting JPEG to PNG."""
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):               return "image/png", "png", raw
    if raw.startswith(b"<svg") or raw.startswith(b"<?xml"): return "image/svg+xml", "svg", raw
    if raw.startswith(b"\xff\xd8\xff"):                     # JPEG → PNG
        buf = io.BytesIO()
        Image.open(io.BytesIO(raw)).convert("RGBA").save(buf, format="PNG", optimize=True)
        return "image/png", "png", buf.getvalue()
    return "image/png", "png", raw

_ASSET_CACHE = {}  # content-hash -> {id, url}

def upload_marker_asset(raw, name="icon"):
    """Content-hash-dedup'd multipart POST /assets. Returns {id, url} or None."""
    ct, ext, raw = _sniff(raw)
    h = hashlib.sha256(raw).hexdigest()[:16]
    if h in _ASSET_CACHE:
        return _ASSET_CACHE[h]
    tmp = f"/tmp/marker_{h}.{ext}"
    Path(tmp).write_bytes(raw)
    r = subprocess.run(
        ["curl", "-sS", "-X", "POST", f"{_workspace_api_base()}/assets",
         "-H", f"Authorization: Bearer {_bearer_token()}",
         "-F", "type=mapMarker",
         "-F", f"file=@{tmp};type={ct}"],
        capture_output=True, text=True,
    )
    resp = json.loads(r.stdout)
    if "id" in resp:
        _ASSET_CACHE[h] = resp
        return resp
    return None
```

Response: `{ "id": "<uuid>", "url": "<presigned-GET>" }`. The `url` is a **7-day presigned GET** that rotates, so persist **only the `id`** on the layer — Builder's `KeplerMapConfigSerializer` resolves `customMarkersId` → a fresh presigned `customMarkersUrl` on every map read. The transient `url` is only for the immediate verification screenshot. Persist the cache to `out/markers/.cache.json` too so re-runs of a failed entry don't re-upload — the workspace-api creates a new asset record per call, so client-side dedup is the only thing preventing duplicate uploads.

## Reference in kepler

The exact field name varies by layer subtype — **always fetch live**:

```bash
carto maps schema layer.tileset --json | jq '.properties.config.properties.visConfig.properties' | grep -iE "marker|icon"
```

Common candidates to look for in the live schema (verify before emitting). The serializer pattern is: emit the asset `id` in `customMarkersId` / `markerMap[].markerId` / `othersMarkerId`; Builder substitutes a fresh presigned URL into `customMarkersUrl` / `markerUrl` / `othersMarker` on read.

- Single-icon point tileset: `visConfig.customMarkers: true` + `visConfig.customMarkersId: "<asset-id>"`. Builder fills in `customMarkersUrl` server-side.
- Categorical icon binding: `visualChannels.customMarkersField` + `visConfig.customMarkersRange.markerMap[]` (array of `{ value, markerId }`) + optional `customMarkersRange.othersMarkerId` for unmatched categories. Builder fills in `markerUrl` and `othersMarker` server-side. Verify these field names against the live `carto maps schema layer.<subtype> --json` before emitting.

When the live schema **doesn't expose** a marker URL field on the layer subtype (some subtypes are color-only), the migration can't preserve icons — fall back per the failure table below.

## Categorical icons (uniqueValue per-category)

The common pattern:

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

Translation:

1. Acquire each unique symbol's icon (dedup by content hash — identical icons across categories upload once).
2. Upload each unique icon → get CARTO URLs.
3. Check live schema for categorical icon binding. **If supported** — reference assets by `id`, not URL (Builder substitutes a fresh presigned URL on read):
   ```json
   {
     "visualChannels": { "customMarkersField": { "name": "storeType", "type": "string" } },
     "visConfig": {
       "customMarkers": true,
       "customMarkersRange": {
         "markerMap": [
           { "value": "Cafe",       "markerId": "<asset-id-1>" },
           { "value": "Restaurant", "markerId": "<asset-id-2>" },
           { "value": "Bakery",     "markerId": "<asset-id-3>" }
         ],
         "othersMarkerId": null
       }
     }
   }
   ```
4. **If not supported** (the layer subtype has no `customMarkersField` in the live schema): collapse to a single icon. Pick the most common (by row count if known, else first in source order). Apply it as a single `customMarkersId`. Record:
   ```
   Notes: uniqueValue-icons-collapsed-to-single (<N> distinct icons; kepler subtype supports only one custom marker)
   ```

## Size and offset

**`radius` is the rendered icon size**, NOT `customMarkerSize`. The live schema documents `radius` as `[0, 200] when customMarkers: true` (vs `[0, 100]` for plain circles). `customMarkerSize` is a legacy mirror that current Builder builds ignore at view time — set both, but `radius` is the source of truth.

ArcGIS `symbol.width` / `symbol.height` are typographic points; kepler `radius` is pixels. 1pt ≈ 1px for marker icons is a good-enough approximation, but **don't halve** the source size like the legacy "radius = size_px / 2" formula did — that produces 7–12 px icons on screen when the source intent was 14–24 px. Use `max(width, height)` directly, with a sensible floor (24 px is a reasonable city-scale default):

```python
size_px = max(symbol.get("width", 24), symbol.get("height", 24))
target = max(int(size_px), 24)            # 24-px floor for legibility
vc["radius"] = target                       # Builder reads this
vc["customMarkerSize"] = target             # legacy mirror, harmless
```

`symbol.xoffset` / `symbol.yoffset` are rarely meaningful and not preserved by kepler — skip silently.

`symbol.angle` (rotation) is supported by some kepler subtypes via `visConfig.iconRotation` or similar — set it if the live schema exposes the field; otherwise drop with `Notes: marker-rotation-dropped: <angle>` if `angle != 0`.

## Multi-color icons: uploaded asset + `visConfig.filled: false`

Two changes must land together on the same layer to preserve a multi-color source PNG (Underground roundel = red outline + white interior + blue line):

1. **Upload the PNG** (via `upload_marker_asset` above) and store the returned asset `id` in `visConfig.customMarkersId`.
2. **Set `visConfig.filled: false`.** Kepler's TileLayer applies its `getFillColor` accessor only when `filled` is truthy (`workspace-www/.../KeplerGl/layers/TileLayer.ts`). With `filled: true`, every non-transparent pixel is replaced by `getFillColor` (from `layer.config.color`) and the icon collapses to one shade.

**Either alone stays monochromatic** — a `data:` URI with `filled: false`, or an uploaded asset with `filled: true` (the default), both render as one shade. TfL PTAL LSOA rounds 5–7 established this: round 5 (`fillColor` white) → server zeroed it, uniformly red; round 6 (`layer.config.color` white) → every pixel white, proving it's a REPLACE not a tint; round 7 (uploaded `customMarkersId` + `filled: false`) → source colors render.

```python
if vc.get("customMarkers"):
    vc["filled"] = False                                          # required for non-monochromatic
    if vc.get("customMarkersUrl", "").startswith("data:"):
        raw = base64.b64decode(vc["customMarkersUrl"].split(",", 1)[1])
        asset = upload_marker_asset(raw, layer_label)
        if asset:
            vc["customMarkersId"] = asset["id"]                   # durable ref; server hydrates the URL
```

**Brand color stays in `strokeColor`** (and `initialStrokeColor`): with `filled: false` the fill never renders, but Builder uses `strokeColor` for the icon's outline ring AND for the sidebar data-panel chip, so brand identity ("Underground" / "Elizabeth Line") is preserved there.

## Aspect-ratio preservation — pad non-square PNGs to square

Kepler tileset's icon layer has **a single size knob**, no per-axis width/height pair. deck.gl scales the source PNG into a square box; a non-square source gets visibly distorted (a 2560×1611 National Rail PNG rendered as a stretched 24×24 box, etc.).

**Pad the PNG to square at acquisition time** with transparent fill — the original content keeps its aspect ratio inside the canvas, and Builder renders the padded square at `radius` px. Apply BEFORE computing the content-hash so two layers sharing the same source dedupe to one padded version.

```python
import io, base64, hashlib
from PIL import Image

def pad_png_to_square(raw_bytes: bytes) -> bytes:
    img = Image.open(io.BytesIO(raw_bytes)).convert("RGBA")
    w, h = img.size
    if w == h:
        return raw_bytes
    side = max(w, h)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(img, ((side - w) // 2, (side - h) // 2))
    out = io.BytesIO()
    canvas.save(out, format="PNG", optimize=True)
    return out.getvalue()

def acquire_with_padding(raw_bytes: bytes, content_type: str):
    padded = pad_png_to_square(raw_bytes) if raw_bytes.startswith(b"\x89PNG") else raw_bytes
    b64 = base64.b64encode(padded).decode("ascii")
    data_uri = f"data:{content_type};base64,{b64}"
    h = hashlib.sha256(padded).hexdigest()[:16]
    return data_uri, h
```

Apply to both `esriPMS` (decoded from `imageData`) and `CIMPictureMarker` (decoded from the `data:` URI in `url`). If PIL is unavailable, fall back to the raw bytes and record `Notes: aspect-ratio-may-distort: PIL not installed`.

Verified failure mode: pre-fix National Rail (1.59 ratio) rendered visibly squashed at any zoom; post-fix the same icon renders at correct proportions.

## Failure modes

| Symptom | Action |
|---|---|
| Both `imageData` and `url` absent | Fall back to colored circle; `Notes: marker-no-source: <renderer>` |
| URL fetch returns 404 / network error AND no `imageData` | Fall back to colored circle; `Notes: marker-acquisition-failed: <url>` |
| Image bytes look corrupt (header check fails) | Fall back to colored circle; `Notes: marker-decode-failed: <hash>` |
| `POST /assets` returns 4xx | Log error; fall back to colored circle; `Notes: marker-upload-failed: <hash>: <error>` |
| `POST /assets` returns 5xx / network error | Retry once after a 5 s pause; on second failure, fall back; `Notes: marker-upload-failed-after-retry` |
| `POST /assets` returns `This type of file is not supported` (400) | Source extension isn't `png`/`svg`; convert via Pillow before retrying, or fall back; `Notes: marker-format-unsupported: <ext>` |
| `POST /assets` returns 403 `Not authorized to create this type of asset` | User token lacks `write:maps`; stop the batch (no point retrying); `Notes: marker-permission-denied` |
| Live kepler schema has no marker URL field for the layer subtype | Fall back to colored circle; `Notes: marker-icon-collapsed: kepler subtype doesn't support custom markers` |
| Kepler schema supports single icon but renderer is uniqueValue with multiple icons | Collapse to most common icon; `Notes: uniqueValue-icons-collapsed-to-single (<N> distinct)` |

**Always continue the batch on any of these** — they're per-symbol / per-layer issues, not whole-Web-Map failures. The migration succeeds; the map just renders less faithfully and the Notes give the user a precise list of what to fix manually.

## CARTO auth expiry during upload

`POST /assets` uses the same bearer token as every other workspace-api call — same auth-expiry rule applies. If the upload returns 401 (token expired) or 403 with `Not authorized`, stop the entire batch (per the migrate-maps and migrate-data lessons files). Don't mark the in-progress Web Map / app `failed`; leave it `in-progress` so resumption after `carto auth login` works cleanly via the manifest precheck.

## Cleanup

The `out/markers/` directory persists across runs by design — the cache is the dedup mechanism. Don't auto-clean. The user can `rm -rf out/markers/` to force re-upload (e.g. after the CARTO org's marker library was wiped), in which case the next run rebuilds from scratch.

## When in doubt

- Unsure if the bytes are PNG / SVG / JPEG? Header sniff (`<svg` / `\x89PNG` / `\xff\xd8\xff`) before trusting `contentType` — some ArcGIS exports mislabel.
- `esriPMS` symbol has an `outline` field (rare; mostly appears on polygon picture symbols)? In ArcGIS the outline applies to the marker bounding box. Kepler doesn't have an equivalent for picture markers; drop the outline silently unless `outline.width > 1` (where it's likely visually significant) — in that case record `Notes: marker-outline-dropped: width=<n>`.
- Animated PNGs (APNG) or multi-frame icons? Strip animation; use the first frame. PIL/Pillow handles this transparently when re-saving.
- CARTO org has a marker quota and the upload hits it? Stop the batch with `Failure: marker-quota-exceeded`; the user needs to clean up old markers in CARTO Workspace before retrying.
