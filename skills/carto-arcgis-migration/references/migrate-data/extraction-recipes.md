# Extraction recipes — ArcGIS source → GeoParquet

The skill emits one `out/<item-id>.parquet` file per Datasets manifest entry. Three extraction paths; the agent picks silently based on the manifest entry's `Type:`:

1. **`arcgis` Python + `geopandas`** (preferred for service-backed items) — `pip show arcgis geopandas pyarrow` succeeds without error. Cleanest paging, automatic type coercion. Use for `Feature Service`, `Map Service`, hosted tables.
2. **`curl + jq` + small Python helper** (fallback for service-backed items) — `arcgis` Python not installed, but `geopandas` + `pyarrow` are. Page via the REST API directly, parse with `jq`, build the GeoDataFrame in a one-shot Python step.
3. **File-format download + `geopandas.read_file`** — for items whose `Type:` is `GeoJson`, `Shapefile`, `KML`, `GeoPackage`, `File Geodatabase`, etc. These are static files in AGOL/Portal; there's no `/query` endpoint to page. See [Recipe 3](#recipe-3-file-format-items-no-query-endpoint) below.

If `geopandas` / `pyarrow` are missing, stop the skill and ask the user to install: `pip install geopandas pyarrow` (and optionally `arcgis`). Do not silently fall back to GeoJSON — GeoParquet is the v1 contract.

## Probe step (Phase 2) — service-backed items only

For service-backed items (`Feature Service`, `Map Service`, hosted tables), run two cheap probes per layer/table. **File-format items skip this** — they have no `/query` endpoint; use the search-result `size` for the byte-precheck instead, and derive row count after the file is read in Recipe 3.

```bash
# Row count
curl -s "$SOURCE/query?where=1%3D1&returnCountOnly=true&f=json" \
  | jq -r '.count'

# Sample page size — page 1, default record count
curl -s "$SOURCE/query?where=1%3D1&outFields=*&outSR=4326&f=geojson&resultRecordCount=2000&resultOffset=0" \
  -o /tmp/probe.geojson
SAMPLE_BYTES=$(wc -c < /tmp/probe.geojson)
SAMPLE_ROWS=$(jq '.features | length' /tmp/probe.geojson)
```

Estimate full size: `est_bytes = (SAMPLE_BYTES / SAMPLE_ROWS) × total_rows × 1.3`.

If `est_bytes > 1 GB`, mark the entry `skipped` with `Reason: exceeds-1gb-staging-not-implemented` and continue to the next entry.

## Recipe 1: `arcgis` Python + `geopandas`

Best when `arcgis` is installed (it handles auth, paging, and edge cases).

```python
import os
import geopandas as gpd
from arcgis.gis import GIS
from arcgis.features import FeatureLayer

gis = GIS("https://<portal>", token=os.environ["ARCGIS_TOKEN"])
layer = FeatureLayer("https://services.../FeatureServer/0", gis=gis)

# Query in WGS84, all fields, deterministic order
oid_field = layer.properties.objectIdField
fset = layer.query(
    where="1=1",
    out_fields="*",
    out_sr=4326,
    order_by_fields=oid_field,
    return_geometry=True,
    result_record_count=2000,
)

# Convert to GeoDataFrame; arcgis Python handles M/Z stripping if asked
gdf = gpd.GeoDataFrame.from_features(fset.features, crs="EPSG:4326")

# Hosted Tables (no geometry) — use a regular DataFrame
import pandas as pd
df = pd.DataFrame([f.attributes for f in fset.features])

gdf.to_parquet("out/<item-id>.parquet", index=False)
```

For paged extraction across very large layers, page with `result_offset` until `exceeded_transfer_limit` is `False`:

```python
all_features = []
offset = 0
while True:
    fset = layer.query(
        where="1=1",
        out_fields="*",
        out_sr=4326,
        order_by_fields=oid_field,
        result_offset=offset,
        result_record_count=2000,
    )
    all_features.extend(fset.features)
    if not fset.exceeded_transfer_limit:
        break
    offset += len(fset.features)
```

## Recipe 2: `curl + jq` + Python helper

Use when `arcgis` Python isn't available. Paging via REST, write to NDJSON, then convert to GeoParquet in one Python invocation.

```bash
SOURCE="https://services.../FeatureServer/0"
TOKEN="$ARCGIS_TOKEN"
OFFSET=0
NUM=2000
OID_FIELD=$(curl -s "$SOURCE?f=json&token=$TOKEN" | jq -r '.objectIdField // "OBJECTID"')

> /tmp/features.ndjson
while :; do
  PAGE=$(curl -s "$SOURCE/query" \
    --data-urlencode "where=1=1" \
    --data-urlencode "outFields=*" \
    --data-urlencode "outSR=4326" \
    --data-urlencode "f=geojson" \
    --data-urlencode "orderByFields=$OID_FIELD" \
    --data-urlencode "resultOffset=$OFFSET" \
    --data-urlencode "resultRecordCount=$NUM" \
    --data-urlencode "token=$TOKEN")

  # Stream features as NDJSON — one feature per line
  echo "$PAGE" | jq -c '.features[]' >> /tmp/features.ndjson

  PAGE_COUNT=$(echo "$PAGE" | jq '.features | length')
  EXCEEDED=$(echo "$PAGE" | jq -r '.exceededTransferLimit // false')
  [ "$EXCEEDED" = "true" ] || break
  OFFSET=$((OFFSET + PAGE_COUNT))
done
```

Convert NDJSON → GeoParquet:

```python
import json
import geopandas as gpd
from shapely.geometry import shape

features = []
with open("/tmp/features.ndjson") as f:
    for line in f:
        feat = json.loads(line)
        features.append(feat)

gdf = gpd.GeoDataFrame.from_features(features, crs="EPSG:4326")
gdf.to_parquet("out/<item-id>.parquet", index=False)
```

## Recipe 3: file-format items (no `/query` endpoint)

Use when the manifest entry's `Type:` is `GeoJson`, `Shapefile`, `KML`, `GeoPackage`, `File Geodatabase`, etc. — items uploaded to AGOL/Portal as static blobs rather than backed by a service. The flow is download → unpack-if-needed → `geopandas.read_file` → typecast → write Parquet.

### Probe (size-only)

The discover skill records `size` in the search result; reuse it from `MIGRATION_INVENTORY.json`:

```python
import json
inv = json.loads(open("MIGRATION_INVENTORY.json").read())
size_bytes = next(
    r["size"] for r in inv["search"]["results"] if r["id"] == ITEM_ID
)
if size_bytes > 1_000_000_000:
    # Mark skipped: exceeds-1gb-staging-not-implemented
    ...
```

Row count comes from the read step below — there's no cheap pre-read count for file blobs.

### Download

`/sharing/rest/content/items/<item-id>/data` returns the raw uploaded blob:

```bash
TOKEN=$(cat /tmp/agol_token)
curl -sSf -L \
  "https://www.arcgis.com/sharing/rest/content/items/$ITEM_ID/data?token=$TOKEN" \
  -o "work/$ITEM_ID.bin"
```

Determine the on-disk extension from the search-result `name` field (e.g. `retail_stores.geojson`, `ne_50m_admin_1_states_provinces.zip`) — the API doesn't add one to the response.

### Read with geopandas

```python
import zipfile
from pathlib import Path
import geopandas as gpd
from shapely import force_2d

WORK = Path("work")
OUT = Path("out")

def read_file_item(item_id: str, item_type: str, file_name: str) -> gpd.GeoDataFrame:
    blob = WORK / file_name
    if item_type == "Shapefile":
        # Shapefile blobs are zips of .shp/.shx/.dbf/.prj/.cpg
        sdir = WORK / item_id
        sdir.mkdir(exist_ok=True)
        with zipfile.ZipFile(blob) as zf:
            for name in zf.namelist():
                if name.startswith("__MACOSX/"):
                    continue  # macOS resource forks; pyogrio chokes on these
                zf.extract(name, sdir)
        shp = next(p for p in sdir.glob("*.shp") if not p.name.startswith("._"))
        return gpd.read_file(shp)
    # GeoJson, KML, GeoPackage — geopandas handles directly
    return gpd.read_file(blob)
```

### Typecast + write

Same lesson rules as service-backed extractions: force string for codes that may have leading zeros (`zip`, `fips`, phone, store_id, …); cast nullable integers to `Int64`; reproject to EPSG:4326 if the file's native CRS differs; strip M/Z if present.

```python
gdf = read_file_item(item_id, item_type, file_name)

# CRS: reproject if not 4326
if gdf.crs and gdf.crs.to_epsg() != 4326:
    note_on_entry(f"reprojected from {gdf.crs} to EPSG:4326")
    gdf = gdf.to_crs("EPSG:4326")

# Strip M/Z if present
if gdf.geometry.has_z.any():
    note_on_entry("M/Z geometry stripped")
    gdf["geometry"] = gdf["geometry"].apply(force_2d)

# Drop empty/null geometries (geopandas.to_parquet rejects them)
n_before = len(gdf)
gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty].copy()
if len(gdf) < n_before:
    note_on_entry(f"dropped {n_before - len(gdf)} empty/null geometries")

# Project-specific typecasts (apply per the manifest's known fields)
for c in ("zip", "fips", "store_id", "phone"):
    if c in gdf.columns:
        gdf[c] = gdf[c].astype("string")

gdf.to_parquet(OUT / f"{item_id}.parquet", index=False)
```

For file-format **tables** (a `GeoJson` with no geometry would be unusual; `CSV` is the typical no-geometry file type) the same flow holds, minus the geometry handling — `pd.read_csv` instead of `gpd.read_file`, and `df.to_parquet` instead of `gdf.to_parquet`.

### Why no `/query` paging

These items are blobs in AGOL's content store — the JSON / zipped shapefile / KML lives at `/sharing/rest/content/items/<id>/data` and is served verbatim. There is no spatial index, no SQL filter, no `?where=…&resultOffset=…` URL surface. The download is one HTTP GET; everything else (paging, filtering) happens locally on the read.

If the user wants only a subset of a large file-format item (e.g. a 5 GB GeoPackage, only one of its layers) the right response in v1 is `State: skipped`, `Reason: exceeds-1gb-staging-not-implemented` — staging-fallback handling will arrive in a later feature.

## Hosted Tables (no geometry)

Same paging logic, but use `f=json` instead of `f=geojson` (GeoJSON requires geometry; tables have none):

```bash
PAGE=$(curl -s "$SOURCE/query" \
  --data-urlencode "where=1=1" \
  --data-urlencode "outFields=*" \
  --data-urlencode "f=json" \
  --data-urlencode "returnGeometry=false" \
  ...)
```

Convert to a regular Parquet (no geometry column):

```python
import pandas as pd

records = []
with open("/tmp/records.ndjson") as f:
    for line in f:
        records.append(json.loads(line)["attributes"])

df = pd.DataFrame(records)
df.to_parquet("out/<item-id>.parquet", index=False)
```

## ArcGIS field type → Parquet type

`arcgis` Python and `geopandas.from_features` handle most coercions automatically. When converting from raw REST JSON, apply the table:

| ArcGIS `type` | Pandas/Parquet target |
|---|---|
| `esriFieldTypeOID` | `int64` |
| `esriFieldTypeInteger` | `int32` (or `int64` if values exceed `int32`) |
| `esriFieldTypeSmallInteger` | `int16` |
| `esriFieldTypeSingle` | `float32` |
| `esriFieldTypeDouble` | `float64` |
| `esriFieldTypeString` | `string` |
| `esriFieldTypeDate` | `datetime64[ms, UTC]` (ArcGIS dates are epoch-ms) |
| `esriFieldTypeGeometry` | (geometry column) |
| `esriFieldTypeGUID` / `esriFieldTypeGlobalID` | `string` |
| `esriFieldTypeRaster` | unsupported — drop with `Notes: raster field dropped` |
| `esriFieldTypeBlob` / `esriFieldTypeXML` | `string` (base64-encoded if blob) |

ArcGIS dates are integer milliseconds since the epoch. Convert in Python:

```python
import pandas as pd
df["created_date"] = pd.to_datetime(df["created_date"], unit="ms", utc=True)
```

## SRS handling

Always request `outSR=4326` (WGS84). If the source refuses (rare; some ancient services), request the source's native SRS and reproject locally:

```python
gdf = gdf.to_crs("EPSG:4326")
```

Record `Notes: reprojected from EPSG:<source-srs> to EPSG:4326` on the manifest entry.

## M/Z geometry stripping

ArcGIS Feature Services often serve geometries with M (measure) or Z (elevation) values. CARTO is 2D-by-default and `geopandas` 2D operations don't preserve M/Z. Strip them at conversion:

```python
from shapely import force_2d

gdf["geometry"] = gdf["geometry"].apply(force_2d)
```

Record `Notes: M/Z geometry stripped` on the entry when this runs (detect via `gdf.geometry.has_z.any()` or `.has_m.any()` if available).

## Pagination details

- Always pass `orderByFields=<objectIdField>` (or another stable field). Without it, page boundaries can shift between calls and cause skipped or duplicated rows.
- `resultRecordCount=2000` is the conventional default — most services cap at 2000. Probe with the service's `maxRecordCount` if you need a tighter loop.
- Loop until `exceededTransferLimit=false`. Don't trust `len(features) < num` — services sometimes return fewer than `num` even when more pages exist.

## Rate limits

ArcGIS doesn't publish a hard rate limit; convention is < 600 req/min per user. The probe + paging at 2000 records/page is well within bounds for any reasonable layer (50K rows = 25 pages = 25 requests, finishes in < 30 seconds). For very large layers (1M+ rows), insert a `sleep 0.5` between pages if the source returns 429/503.

## Output directory

All extracted files land in `out/` relative to the working directory:

```
out/
├── <item-id-1>.parquet
├── <item-id-2>.parquet
└── ...
```

Don't reuse names; `<item-id>` is the ArcGIS portal item ID (32-char hex), guaranteed unique per item. Files persist after the migration so the user can re-import manually if needed.
