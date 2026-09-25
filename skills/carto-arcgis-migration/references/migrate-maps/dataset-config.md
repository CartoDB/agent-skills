# Dataset config — kepler `datasets[]` shape

`datasets[]` is a **top-level array on the bundle**, a sibling of `title` and `keplerMapConfig` — not a key inside `visState`. It binds each layer to a warehouse table or SQL query, and every layer's `config.dataId` references one dataset.

```json
{
  "title": "My map",
  "datasets": [ { "$ref": "stores", "type": "table", "...": "..." } ],
  "keplerMapConfig": { "version": "v1", "config": { "visState": { "layers": [ ... ] } } }
}
```

Datasets placed under `visState` are invisible: nothing reads them, and every layer that referenced one fails to resolve its `dataId`.

This file documents the fields that matter for migration. **Always re-fetch the live schema with `carto maps schema dataset --json` and let it win** when this document disagrees.

## Identity: `$ref` is a name, not a UUID

`$ref` declares a NEW dataset and is a **symbolic name** you choose (`"stores"`, `"bus_stops"`). Layers and widgets point at it through the **prefixed** form:

- layer → `config.dataId: "$ref:stores"`
- widget → `dataSource: "$ref:stores"`

The server assigns the real UUID on create and the CLI substitutes it before the config is sent. A bare string — a UUID you generated, or the ref name without the `$ref:` prefix — is rejected on create (*"Plain-string dataId … won't resolve on create"*), because there is nothing to substitute and Kepler then drops the layer.

`id` is the other half of the pair: it targets an **existing** dataset on update, and is what a `carto maps get` returns. The two are mutually exclusive — a dataset carries `$ref` or `id`, never both.

## Required fields

Only three are required for a new dataset. The rest are optional but worth setting for a migration.

| Field | Type | Source / how to populate |
|---|---|---|
| `$ref` (new) / `id` (existing) | string | Symbolic name you choose for a new dataset; layers reference it as `"$ref:<name>"`. `id` instead when updating a dataset that already exists. |
| `type` | **required** — `"table"` or `"query"` | `"table"` when binding to a plain DW table. `"query"` when the layer needs derived columns (translated Arcade expressions). |
| `source` | **required** — string | The FQN for `type: "table"` (e.g. `demo-bq.shared.stores`). A SQL string for `type: "query"`. |
| `connectionId` | **required** — UUID string | The connection's **UUID**, NOT the name. Resolve via `carto connections list --json \| jq -r '.[] \| select(.name=="<name>") \| .id'`. Cache per batch; one connection per migration is the common case. |
| `geoColumn` | string | The geometry column name as it exists in the warehouse. Get from `carto connections describe <conn> <fqn> --json`; CARTO DW convention is `geom`. Spatial-index datasets prefix it: `"h3:<col>"` / `"quadbin:<col>"`. |
| `columns` | string array | **All columns the dataset exposes through the tilejson.** See "Why columns must be set" below. |
| `format` | `"tilejson"` \| `"raster"` | Derived from `type` when omitted, so you rarely write it. `tilejson` for everything served as vector tiles. |
| `label` | string | Display name in Builder's data panel. Use the source's title or layer name. |

**Don't emit `connectionName`.** It is server-derived, not writable — the server decorates a dataset with it on read, and no write route accepts it back. The same applies to `sourceWorkflowNodeId`, `sourceWorkflowId`, `mapId`, `providerId`, `createdAt` and `updatedAt`: they belong to the response shape only. `connectionId` is the one that identifies the connection on write.

## Why `columns` must be set

Builder's tilejson generator uses `dataset.columns` at view time to decide which warehouse columns to include in each tile's feature payload. Without it:

- `carto maps validate` accepts the null silently (Tier-1 doesn't enforce it).
- `carto maps create` may emit `warnings[]` with `code: "DATASET_WONT_RENDER"` (or similar — depends on CLI version), or may stay silent on older CLI builds.
- `carto maps screenshot --render-engine light` **succeeds** — deck.gl's `fetchMap` infers columns from `/stats` or schema introspection.
- **Builder errors 500 on view** — the tilejson generator can't construct a tile request without an explicit column list.

This is a real-world failure mode caught during testing: a TfL Bus Route map migrated cleanly, the screenshot looked correct, but every layer 500'd in Builder because every dataset had `columns: null`. The screenshot success was a red herring; the map was unusable.

**Always populate `columns` explicitly.** Never emit `null`.

## How to populate `columns`

For `type: "table"`:

```bash
carto connections describe <connection-name> <fqn> --json | jq -r '[.columns[].name]'
```

Returns a JSON array of column names. Assign the whole array to `dataset.columns`.

**Always include `geoColumn`** in the array (Builder needs the geometry column in the tile payload). Don't trim to "just the columns the renderer uses" — the cost of a few extra columns in tile payloads is negligible compared to the cost of an incomplete list when a popup or filter binding ends up referencing one that wasn't included. Trimming is a Builder-side optimization the user can do after.

For `type: "query"` (when an Arcade per-row math expression is translated to a derived SQL field):

The columns list is whatever the SQL `SELECT` clause produces. If the query is `SELECT *, (pop / NULLIF(area, 0)) * 1000 AS _density FROM <fqn>`, columns = source table's columns + `["_density"]`. Fetch the source table's columns first, append the derived field names.

## Optional fields

| Field | When to set | Notes |
|---|---|---|
| `name` | Internal identifier; not displayed | Builder accepts `null`; leave it unless you have a reason. |
| `color` | Data-panel chip color in Builder UI | A **hex string** like `"#7F3C8D"` (Builder's default purple). **NOT** an int array `[r, g, b]` — the backing column is `text`, not `int[]`; the API coerces int arrays to `text[]` form (`"{128,128,128}"`) that Builder can't parse on read. Omitting it is fine (the column defaults to empty), but a migration should set one: cycle a small palette across datasets — `#7F3C8D` / `#11A579` / `#3969AC` / `#F2B701` / `#E73F74` / `#80BA5A` / `#E68310` / `#008695` by index mod 8 (mirrors Builder's chip palette). |
| `aggregationExp` | Set on `h3` / `quadbin` datasets that aggregate server-side | Leave `null` for `tileset` layers. When set, each bound visual channel needs its matching `visConfig.<channel>Aggregation` or the channel renders nothing. |
| `aggregationResLevel` | Same scope as `aggregationExp` | Leave `null` for tileset. Valid range is `[1, 6]` for h3 and `[1, 9]` for quadbin; outside it Builder's resolution slider can't represent the value. |
| `spatialIndex` | Set when the source has a pre-computed h3/quadbin column | `"h3"` or `"quadbin"`. Leave `null` for regular tileset. Pair it with the prefixed `geoColumn` (`"h3:<col>"` / `"quadbin:<col>"`). |
| `queryTemplate` | For parameterized queries (with SQL parameters) | Leave `null` if no parameters. |
| `queryParameters` | Bound values for the query placeholders | `null` when there are none. The container shape depends on the provider: a dict keyed by `sqlName` for BigQuery and Databricks, a positional array for everything else. |
| `uniqueIdProperty` | The column used to identify features | **MUST be a column that exists in `columns[]` for this dataset.** Resolution order: (1) source layer's `objectIdField` from the ArcGIS service JSON, normalized to the casing as it appears in the warehouse `columns[]` (typically lowercased after GeoParquet → BigQuery / Snowflake / Redshift round-trip); (2) if that name is **not** in `columns[]` after normalization — fall back to the first match among `objectid`, `fid`, `id`, `oid` (case-insensitive) that **is** in `columns[]`; (3) if none match, set `null` and record `Notes: no-unique-id-resolved`. **Never copy `"objectid"` across datasets without verifying** — File Geodatabase / Shapefile / GeoPackage extracts frequently land with `fid` (or no OID column at all). A stale `uniqueIdProperty` makes that layer's tilejson SQL throw server-side. See `references/lessons.md` "`uniqueIdProperty` must reference a column that exists". |

## Top-level filter state

In addition to the per-dataset config, `keplerMapConfig.config.filters` (a **top-level** field on `keplerMapConfig.config`, NOT inside `visState`) tracks active filter state per dataset. Builder's loader iterates this object during initial load.

**Shape**: an object keyed by dataset id, with empty `{}` values when no filters are active. The contract types it as a plain string-keyed record, so nothing checks the keys for you:

```json
{
  "config": {
    "filters": {
      "32484a43-c235-4cae-9bd9-11e88f32044b": {},
      "c4db231b-e098-4596-a120-43c32538eecd": {},
      "8e80d1e2-cc05-4982-a0fc-8816f2bd4d32": {}
    }
  }
}
```

**Wrong shape** (the kepler-legacy array form, which belongs inside `visState`, not here):

```json
{ "config": { "filters": [] } }
```

The array form causes Builder to crash on initial load with a full-page 500 error. The `light`-engine screenshot still renders correctly because deck.gl's `fetchMap` doesn't read `filters` — only Builder does. **Verified failure mode**, MCIL2 / TfL Bus Routes incident.

Generate the filters object as a final compose step, once each dataset's id is known:

```python
keplerMapConfig["config"]["filters"] = {ds_id: {} for ds_id in dataset_ids}
```

There's no need to populate filter contents; users add filters in Builder UI after the map loads.

## Worked example

A migrated Hosted Feature Layer `Stores` landing as `carto-dw-ac-xxxx.shared.stores`:

```python
import json, subprocess

# 1) Resolve connection UUID (cache per batch — same connection across the migration)
conn_list = json.loads(subprocess.check_output(
    ["carto", "connections", "list", "--json"]
))
connection_id = next(c["id"] for c in conn_list if c["name"] == "carto_dw")

# 2) Fetch column list from the warehouse for this FQN
fqn = "carto-dw-ac-xxxx.shared.stores"
desc = json.loads(subprocess.check_output(
    ["carto", "connections", "describe", "carto_dw", fqn, "--json"]
))
column_names = [c["name"] for c in desc["columns"]]
geo_column = next((c["name"] for c in desc["columns"] if c.get("type") in ("geometry", "geography")), "geom")

# 3) Resolve uniqueIdProperty against the actual column list — never assume "objectid"
#    Source ArcGIS layer JSON exposes `objectIdField` (e.g. "OBJECTID", "fid").
source_oid = arcgis_layer_json.get("objectIdField")  # may be None
columns_lower = {c.lower(): c for c in column_names}
unique_id = None
if source_oid and source_oid.lower() in columns_lower:
    unique_id = columns_lower[source_oid.lower()]
else:
    for candidate in ("objectid", "fid", "id", "oid"):
        if candidate in columns_lower:
            unique_id = columns_lower[candidate]
            break
# unique_id may still be None — that's fine; emit it as None and record a Note.

# 4) Compose the dataset entry. `$ref` is a symbolic name, not a UUID — the
#    layer points at it as "$ref:stores" and the server assigns the real id.
dataset = {
    "$ref": "stores",
    "type": "table",
    "source": fqn,
    "label": "Stores",
    "connectionId": connection_id,  # UUID; connectionName is server-derived, don't send it
    "geoColumn": geo_column,
    "columns": column_names,        # populate explicitly
    "format": "tilejson",
    "uniqueIdProperty": unique_id,  # never a hardcoded "objectid"
}

# 5) Every layer that reads it uses the prefixed reference
layer["config"]["dataId"] = "$ref:stores"
```

Derive each `$ref` from the source layer's name (slugified, deduplicated within the map) so the bundle stays readable and the reference is obvious at a glance.

Cache the `(connection_name) → connection_id` lookup AND the `(fqn) → (columns, geoColumn)` lookup per batch — each connection/table gets described exactly once.

## Detecting and patching null columns post-create

If a migration shipped maps with `columns: null` (pre-v0.1.14 skill, or a manual edit slipped through), repair them:

```bash
MAP_ID="<id>"
CONN_NAME="<connection-name>"

carto maps get "$MAP_ID" --json > /tmp/m.json

# Build {fqn: [cols]} for every unique source in this map
FQNS=$(jq -r '.datasets[].source' /tmp/m.json | sort -u)
COLS_MAP='{}'
for FQN in $FQNS; do
    COLS=$(carto connections describe "$CONN_NAME" "$FQN" --json | jq '[.columns[].name]')
    COLS_MAP=$(jq --arg fqn "$FQN" --argjson cols "$COLS" '. + {($fqn): $cols}' <<< "$COLS_MAP")
done

# Patch each dataset's columns; preserve everything else
jq --argjson m "$COLS_MAP" '.datasets |= map(.columns = $m[.source])' /tmp/m.json > /tmp/m2.json

carto maps update "$MAP_ID" --datasets-mode replace --json < /tmp/m2.json
```

Reload Builder; the 500 clears.

## When in doubt

- `carto connections describe` doesn't return a `columns` array (older CLI versions)? Fall back to `carto sql query --connection <name> --query "SELECT * FROM <fqn> LIMIT 0" --json` and read the column names from the response schema.
- Source has > 100 columns and tile-payload size is a concern? Leave them all in for v1. Trim is a post-migration Builder optimization.
- `connections describe` returns the connection metadata but no geometry-column hint? On `carto_dw`, trust the convention `geom` (and verify it's in the `columns` array). On external warehouses, run `SELECT column_name FROM INFORMATION_SCHEMA.COLUMNS WHERE table_name = '<table>' AND data_type LIKE '%GEOG%'` (BigQuery) or the warehouse equivalent. Recall: `INFORMATION_SCHEMA` isn't queryable on `carto_dw` (per `migrate-data/references/lessons.md`).
- Multiple layers reference the same source FQN with different styles? Each layer gets its own dataset entry under its own `$ref` name, but the columns + geoColumn are identical (fetched once).
- A dataset's `source` is a SQL query (`type: "query"`), not a table FQN? The agent constructed the SQL; the columns array is whatever the `SELECT` produces. Don't try to introspect via `connections describe` — describe the underlying base table, then append the derived field names.
