# Marker upload — preserving ArcGIS picture marker symbols

ArcGIS layers frequently style points with custom icons via `esriPMS` (Picture Marker Symbol). The image lives on the symbol as either a URL or base64-encoded `imageData`. To preserve these in the migrated Builder map, upload each unique icon to CARTO's workspace-api **`POST /assets`** endpoint with `type=MapMarker`, then reference the returned URL in the kepler layer's marker config.

> **There is no `carto maps markers` CLI subcommand.** The CARTO CLI's `carto maps` surface is `list / get / create / update / delete / copy / validate / publish / schema / datasets / agents / screenshot` only. Marker assets upload via a multipart `POST /assets` call (`type=MapMarker`, `file=<binary>`) to the workspace API — the same endpoint Builder's UI uses when a user uploads a custom marker. Response shape: `{ id, url }`. Permission required: `write:maps`. Accepted extensions: `png`, `svg`.

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

`POST /assets` (with `type=MapMarker`) accepts **PNG and SVG only** — see [`workspace-api/src/services/assets-service.ts`](../../../../../../cloud-native/workspace-api/src/services/assets-service.ts) `hasValidExtension`. JPEG and GIF must be converted to PNG before upload (`Pillow`'s `Image.open(...).save("file.png")` — one frame only for animated PNG / APNG / GIF).

## Dedup via content hash

A single Web Map can reference the same icon across 5+ layers (e.g. a "store" icon shared across regions). Hash the bytes (`sha256` truncated to 16 chars is fine) and use the hash as the cache key. Same icon → single `POST /assets` call → same returned URL reused across layers.

Local cache structure under `out/markers/`:

```
out/markers/
├── .cache.json              # { "<hash>": { url, content_type, width, height, uploaded_at } }
├── 1a2b3c4d5e6f7g8h.png     # icon files keyed by content hash
└── 9z8y7x6w5v4u3t2s.svg
```

Maintain `out/markers/.cache.json` as the dedup index. The cache survives across Web Map migrations and across re-runs — re-running `migrate-maps` against a failed entry won't re-upload icons that already succeeded.

```python
import json
from datetime import datetime, timezone

CACHE_PATH = MARKERS_DIR / ".cache.json"

def load_cache():
    if CACHE_PATH.exists():
        return json.loads(CACHE_PATH.read_text())
    return {}

def save_cache(cache):
    CACHE_PATH.write_text(json.dumps(cache, indent=2))

def upload_or_reuse(digest, local_path, content_type):
    cache = load_cache()
    if digest in cache:
        return cache[digest]  # { id, url }
    asset = _post_marker_asset(local_path, content_type)  # see "Upload" below
    cache[digest] = {
        "id": asset["id"],
        "url": asset["url"],
        "content_type": content_type,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    }
    save_cache(cache)
    return cache[digest]
```

## Upload

Multipart `POST /assets` to the workspace API. The token + workspace URL come from `~/.carto_credentials.json` and `carto auth status --json` (so the agent doesn't hardcode tenants).

```python
import json, subprocess
from pathlib import Path

def _workspace_api_base() -> str:
    status = json.loads(subprocess.check_output(["carto", "auth", "status", "--json"]))
    return f"https://workspace-{status['tenant_id']}.app.carto.com"

def _bearer_token() -> str:
    creds = json.loads(Path("~/.carto_credentials.json").expanduser().read_text())
    return creds["profiles"][creds["current_profile"]]["token"]

def _post_marker_asset(local_path: Path, content_type: str) -> dict:
    """POST /assets with multipart/form-data; type=MapMarker. Returns {id, url}."""
    api = _workspace_api_base()
    token = _bearer_token()
    result = subprocess.run(
        [
            "curl", "-sS", "-X", "POST",
            "-H", f"Authorization: Bearer {token}",
            "-F", "type=MapMarker",
            "-F", f"file=@{local_path};type={content_type}",
            f"{api}/assets",
        ],
        capture_output=True, text=True, check=True,
    )
    response = json.loads(result.stdout)
    if "id" not in response or "url" not in response:
        raise RuntimeError(f"Unexpected /assets response: {response!r}")
    return response  # { "id": "...", "url": "https://..." }
```

The response shape is small and stable:

```json
{ "id": "<uuid>", "url": "https://<workspace-api-host>/...?fileName=<name>" }
```

The `url` is a 7-day presigned GET URL — long enough for migration runs but rotated by the asset store, so capture `id` to the cache too. Builder's `KeplerMapConfigSerializer` resolves `customMarkersId` → fresh presigned URL on every map read ([`workspace-api/src/serializers/kepler-map-config-serializer.ts`](../../../../../../cloud-native/workspace-api/src/serializers/kepler-map-config-serializer.ts)), so the durable reference in kepler config should be the asset `id`. The transient `url` is only for the immediate migration's verification screenshot.

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

## Multi-color icons: upload via `POST /assets` + set `visConfig.filled: false`

Two things must happen together to preserve a multi-color source PNG (Underground roundel = red outline + WHITE interior + BLUE crossing line, etc.):

1. **Upload the PNG to the workspace-api `/assets` endpoint** and reference it on the layer via `customMarkersId` (the server hydrates a fresh presigned `customMarkersUrl` on every map read — see `workspace-api/src/serializers/kepler-map-config-serializer.ts`).
2. **Set `visConfig.filled: false` on the icon layer.** Kepler's TileLayer applies its `getFillColor` accessor only when `visConfig.filled` is truthy (see `workspace-www/src/features/builder/ui/KeplerGl/layers/TileLayer.ts`, the color channel's `condition`). With `filled: true`, every non-transparent icon pixel is replaced by `getFillColor` (derived from `layer.config.color`) and the icon collapses into a single shade. With `filled: false`, the tint is skipped and the icon renders with its source PNG colors.

**Either alone is insufficient.** A data URI in `customMarkersUrl` with `filled: false` still renders monochromatic. An uploaded asset with `filled: true` (the kepler default) also renders monochromatic. Both fixes have to be applied to the same layer.

Verified via the TfL PTAL LSOA migration (rounds 5–7):

- Round 5: set `visConfig.fillColor` to white. Server zeroed `fillColor` to `null` for icon layers; Builder fell back to `layer.config.color` → uniformly red.
- Round 6: set `layer.config.color` to white. Builder rendered every pixel **white** — proves it's a color REPLACE, not a multiplicative tint.
- Round 7: uploaded each PNG to `/assets`, set `customMarkersId`, set `filled: false` → multi-color icons render with their source colors. **Working state.**

### Endpoint and request shape

`POST {workspaceApiUrl}/assets` — the workspace-api base URL comes from the tenant's `/config.yaml` under `apis.workspaceUrl`. For the `clausa.app.carto.com` tenant it's `https://workspace-gcp-us-east1.app.carto.com`. Resolve once per migration:

```bash
curl -sS https://<tenant>.app.carto.com/config.yaml | grep workspaceUrl
# apis:
#   workspaceUrl: "https://workspace-gcp-us-east1.app.carto.com"
```

Request:

```bash
curl -sS -X POST "${WORKSPACE_URL}/assets" \
  -H "Authorization: Bearer ${TOKEN}" \
  -F "type=mapMarker" \
  -F "file=@icon.png;type=image/png"
```

**Casing matters.** The `type` enum is **`mapMarker`** (camelCase, lowercase first letter) — the docs / older lessons that said `MapMarker` are wrong. The server returns `400 Invalid enum value … Expected 'accountLogo' | 'mapMarker'` if you send `MapMarker`.

Response: `{ id: "<uuid>", url: "<presigned-GET-7-day-TTL>" }`. Persist **only the `id`** on the layer — the server-side serializer hydrates `customMarkersUrl` on every map read, so storing the URL is unnecessary and the URL will expire after 7 days.

Accepted file types: `png`, `svg` only (`workspace-api/src/services/assets-service.ts` `hasValidExtension`). JPEG → convert to PNG first (PIL: `Image.open(buf).convert("RGBA").save(out, "PNG")`).

**Sniff the bytes header** before trusting the source's `contentType`. ArcGIS occasionally lies — National Rail's PNG bytes were declared `image/jpeg` in the source, which the workspace-api 400'd on. Sniff:

```python
if raw_bytes.startswith(b"\x89PNG\r\n\x1a\n"):       ct, ext = "image/png", "png"
elif raw_bytes.startswith(b"<svg") or \
     raw_bytes.startswith(b"<?xml"):                  ct, ext = "image/svg+xml", "svg"
elif raw_bytes.startswith(b"\xff\xd8\xff"):           # JPEG — convert to PNG via PIL
    img = Image.open(io.BytesIO(raw_bytes)).convert("RGBA")
    buf = io.BytesIO(); img.save(buf, format="PNG", optimize=True)
    raw_bytes = buf.getvalue(); ct, ext = "image/png", "png"
```

### Worked composer pattern

```python
import json, subprocess, hashlib
from pathlib import Path

ASSETS_ENDPOINT = "https://workspace-gcp-us-east1.app.carto.com/assets"

def _carto_token():
    creds = json.load(open(Path.home() / ".carto_credentials.json"))
    return creds["profiles"][creds["current_profile"]]["token"]

_ASSET_CACHE = {}  # hash -> {id, url}

def upload_marker_asset(raw_bytes, name="icon"):
    # ...sniff content_type + extension from header (see above)...
    h = hashlib.sha256(raw_bytes).hexdigest()[:16]
    if h in _ASSET_CACHE:
        return _ASSET_CACHE[h]
    tmp = f"/tmp/marker_{h}.{ext}"
    open(tmp, "wb").write(raw_bytes)
    r = subprocess.run([
        "curl", "-sS", "-X", "POST", ASSETS_ENDPOINT,
        "-H", f"Authorization: Bearer {_carto_token()}",
        "-F", "type=mapMarker",
        "-F", f"file=@{tmp};type={ct}",
    ], capture_output=True, text=True)
    resp = json.loads(r.stdout)
    if "id" in resp:
        _ASSET_CACHE[h] = resp
        return resp
    return None

# In the per-layer post-build step:
if vc.get("customMarkers"):
    vc["filled"] = False                                 # <-- required for non-monochromatic
    if vc.get("customMarkersUrl", "").startswith("data:"):
        raw = base64.b64decode(vc["customMarkersUrl"].split(",", 1)[1])
        asset = upload_marker_asset(raw, layer_label)
        if asset:
            vc["customMarkersId"]  = asset["id"]
            vc["customMarkersUrl"] = asset["url"]        # nice-to-have; server overwrites on read
```

### Content-hash dedup is still important

A single Web Map often shares one icon across multiple layers (per-region store icons, etc.). Hash the bytes, key the upload cache on the hash, upload once per unique PNG. The workspace-api creates a new asset record per call, so client-side dedup is the only thing preventing duplicate uploads. Truncated sha256 (16 chars) is fine.

### Brand color stays in `strokeColor`

With `filled: false`, the layer's fill never renders. Put the brand color in `visConfig.strokeColor` and `initialStrokeColor` so the icon gets a brand-colored outline ring around it, and so the data-panel chip in Builder's sidebar still reads "Underground" / "Elizabeth Line" / etc. (Builder also uses `strokeColor` as the chip color when fill is disabled on point layers.)

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
