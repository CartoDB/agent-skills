# Dataset config — kepler `datasets[]` shape

`keplerMapConfig.config.visState.datasets[]` (also at `.datasets[]` on top-level `carto maps get` output) binds each layer to a warehouse table or SQL query. Every layer's `dataId` references one dataset's `$ref` (on input) / `id` (on output).

This file documents the fields that matter for migration. **Always re-fetch the live schema with `carto maps schema dataset --json` and let it win** when this document disagrees.

## Required fields

| Field | Type | Source / how to populate |
|---|---|---|
| `$ref` (input) / `id` (output) | string | A stable UUID-like identifier you generate per dataset. Layers reference this via `dataId`. Generate once per dataset (e.g. `uuid.uuid4()`). |
| `type` | `"table"` or `"query"` | `"table"` when binding to a plain DW table. `"query"` when the layer needs derived columns (translated Arcade expressions). |
| `source` | string | The FQN for `type: "table"` (e.g. `demo-bq.shared.stores`). A SQL string for `type: "query"`. |
| `connectionId` | UUID string | The connection's **UUID**, NOT the name. Resolve via `carto connections list --json \| jq -r '.[] \| select(.name=="<name>") \| .id'`. Cache per batch; one connection per migration is the common case. |
| `connectionName` | string | Connection name (e.g. `"carto_dw"`). Builder writes both UUID and name; we follow suit. |
| `geoColumn` | string | The geometry column name as it exists in the warehouse. Get from `carto connections describe <conn> <fqn> --json`; CARTO DW convention is `geom`. |
| `columns` | string array | **All columns the dataset exposes through the tilejson.** Must be **non-null and non-empty**. See "Why columns must be set" below. |
| `format` | `"tilejson"` | The only value used for tileset layers. |
| `label` | string | Display name in Builder's data panel. Use the source's title or layer name. |

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
| `color` | **REQUIRED — NOT NULL constraint at the backend.** Data-panel chip color in Builder UI | Must be a **hex string** like `"#7F3C8D"` (Builder's default purple). **NOT** an int array `[r, g, b]` — the column is `text`, not `int[]`; the API coerces int arrays to `text[]` form (`"{128,128,128}"`) that Builder can't parse on read. **NOT** `null` either — the column is `NOT NULL`. When migrating, cycle a small palette across datasets: `#7F3C8D` / `#11A579` / `#3969AC` / `#F2B701` / `#E73F74` / `#80BA5A` / `#E68310` / `#008695` by index mod 8 (mirrors Builder's chip palette). |
| `aggregationExp` | Set only when the layer is `h3` / `quadbin` and needs server-side aggregation | Leave `null` for `tileset` layers. |
| `aggregationResLevel` | Same scope as `aggregationExp` | Leave `null` for tileset. |
| `spatialIndex` | Set when the source has a pre-computed h3/quadbin column | Leave `null` for regular tileset. |
| `queryTemplate` | For parameterized queries (with SQL parameters) | Leave `null` if no parameters. |
| `queryParameters` | **`null` when no parameters** (NOT `[]`) — verified against manual Builder maps | An empty array round-trips through some serializers and diverges from what Builder writes. |
| `uniqueIdProperty` | The column used to identify features | **MUST be a column that exists in `columns[]` for this dataset.** Resolution order: (1) source layer's `objectIdField` from the ArcGIS service JSON, normalized to the casing as it appears in the warehouse `columns[]` (typically lowercased after GeoParquet → BigQuery / Snowflake / Redshift round-trip); (2) if that name is **not** in `columns[]` after normalization — fall back to the first match among `objectid`, `fid`, `id`, `oid` (case-insensitive) that **is** in `columns[]`; (3) if none match, set `null` and record `Notes: no-unique-id-resolved`. **Never copy `"objectid"` across datasets without verifying** — File Geodatabase / Shapefile / GeoPackage extracts frequently land with `fid` (or no OID column at all). A stale `uniqueIdProperty` makes that layer's tilejson SQL throw server-side. See `references/lessons.md` "`uniqueIdProperty` must reference a column that exists". |
| `sourceWorkflowNodeId` | Workflows integration | Leave `null` for direct dataset migrations. |

## Top-level filter state

In addition to the per-dataset config, `keplerMapConfig.config.filters` (a **top-level** field on `keplerMapConfig.config`, NOT inside `visState`) tracks active filter state per dataset. Builder's loader iterates this object during initial load.

**Required shape**: object keyed by dataset `$ref` (the UUID), with empty `{}` values when no filters are active:

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

**Wrong shape** (the kepler-legacy array form that Builder no longer accepts):

```json
{ "config": { "filters": [] } }
```

The array form causes Builder to crash on initial load with a full-page 500 error. The `light`-engine screenshot still renders correctly because deck.gl's `fetchMap` doesn't read `filters` — only Builder does. **Verified failure mode**, MCIL2 / TfL Bus Routes incident.

Generate the filters object as a final compose step after every dataset has its `$ref` assigned:

```python
keplerMapConfig["config"]["filters"] = {ds["$ref"]: {} for ds in datasets}
```

There's no need to populate filter contents; users add filters in Builder UI after the map loads.

## Worked example

A migrated Hosted Feature Layer `Stores` landing as `carto-dw-ac-xxxx.shared.stores`:

```python
import json, subprocess, uuid

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

# 4) Compose the dataset entry
dataset = {
    "$ref": str(uuid.uuid4()),
    "type": "table",
    "source": fqn,
    "label": "Stores",
    "connectionId": connection_id,
    "connectionName": "carto_dw",
    "geoColumn": geo_column,
    "columns": column_names,        # mandatory; non-null
    "format": "tilejson",
    "uniqueIdProperty": unique_id,  # never a hardcoded "objectid"
}
```

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
- Multiple layers reference the same source FQN with different styles? Each layer gets its own dataset entry (own `$ref` UUID), but the columns + geoColumn are identical (fetched once).
- A dataset's `source` is a SQL query (`type: "query"`), not a table FQN? The agent constructed the SQL; the columns array is whatever the `SELECT` produces. Don't try to introspect via `connections describe` — describe the underlying base table, then append the derived field names.
