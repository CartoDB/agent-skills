# Running raster algebra

## Inputs: get RaQuet v0.5.0 rasters

Check `version` in each input's metadata row. Rasters written by the [raquet](https://github.com/CartoDB/raquet) tools are v0.5.0. Rasters imported into CARTO (Data Explorer, Imports API) are still written in the earlier RaQuet version by default, and raster algebra rejects them.

The Imports API can write v0.5.0 when asked. `carto import` has no option for it, so call the API directly with a `config` field, which is a JSON **string**:

```bash
API_BASE="https://<tenant_id>.api.carto.com"   # tenant_id from: carto auth status --json
TOKEN="<CARTO token>"                          # e.g. the CLI profile token in ~/.carto_credentials.json

curl -X POST "${API_BASE}/v3/imports" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "connection": "<connection name>",
    "destination": "<project>.<dataset>.<table>",
    "url": "<URL of the GeoTIFF>",
    "config": "{\"raquetVersion\":\"0.5.0\"}"
  }'
# Returns a jobId. Poll GET ${API_BASE}/v3/imports/<jobId> until status is success or failure.
```

Then read the new table's metadata row and confirm `version` is `0.5.0`.

Inputs must also share block size and native resolution (`tiling.max_zoom`). Rasters are never resampled: resample the source files to a common resolution before importing them.

## Options

| Procedure option | Component field | Default | Notes |
|---|---|---|---|
| `output_type` | Output data type | `float32` | `uint8`, `int8`, `uint16`, `int16`, `uint32`, `int32`, `float32`, `float64`. Integer results are rounded (halves up); values that don't fit become nodata. |
| `output_nodata` | (none) | `NaN` for floats; the min (signed) or max (unsigned) value for integers, e.g. 255 for `uint8` | Set it when the default is a valid result, e.g. `254` for a 0/255 mask. It must fit the output type. |
| `overviews` | Overviews | `evaluate` ("Compute all zoom levels") | `none` is "Native resolution only". `evaluate` computes every zoom level that all inputs share, so the result can be shown at any zoom right away. |
| `apply_scale_offset` | Use physical values (apply band scale and offset) | `true` | `false` works on the stored values. Bands without scale and offset are used as they are. |
| `compression` | (none) | `gzip` | Or `none`. Applies to the output tiles; input compression is read from each input's metadata. |
| `compression_level` | (none) | `1` | 1 to 9. |

The procedure takes options as a JSON string, or `NULL` for the defaults: `'{"output_type": "uint8", "output_nodata": 254}'`.

In Workflows there is no `output_nodata`, so pick a type whose nodata value can't be a result: a class map with values up to 255 needs `uint16`, not `uint8`.

## SQL

The `CALL` creates a table, so run it as a job: MCP `execute_async_query`, or `carto sql job <connection> --file call.sql`. Put the statement in a file: inside a double-quoted shell argument, the shell expands `$a` and `$b`.

BigQuery (including CARTO Data Warehouse). Use the toolbox project for the data's region: `carto-un` (US multi-region), `carto-un-eu` (EU multi-region), or the regional project listed in CARTO's Analytics Toolbox regions table.

```sql bigquery
CALL `carto-un`.carto.RASTER_ALGEBRA(
  ['project.dataset.sentinel2'],
  'ndvi = ($a.band_4 - $a.band_3) / ($a.band_4 + $a.band_3); vegetation = $a.band_4 > 1000',
  'project.dataset.sentinel2_ndvi',
  '{"overviews": "none"}'
);
```

Snowflake. Use the database and schema where the toolbox is installed (often `CARTO.CARTO`):

```sql snowflake
CALL CARTO.CARTO.RASTER_ALGEBRA(
  ARRAY_CONSTRUCT('MYDB.MYSCHEMA.COVERAGE_BEFORE', 'MYDB.MYSCHEMA.COVERAGE_AFTER'),
  '$b - $a',
  'MYDB.MYSCHEMA.COVERAGE_DELTA',
  NULL
);
```

- The dataset or schema of the output must exist.
- The procedure fails if the output table already exists or is one of the inputs. Ask before dropping a table; otherwise pick a new name.
- Everything (expression, bands, grids, options) is validated before any table is created. If a later step fails, the incomplete output is removed.

## Workflows

Component `carto.rasteralgebra` (title Raster Algebra, group Raster Operations). Read its spec with `carto workflows components get carto.rasteralgebra --connection <connection> --json` (or MCP `read_workflow_components`). If it isn't found, the organization doesn't have it enabled yet, or the connection's toolbox is older than the minimum version: use the SQL procedure.

| Input | Type | Value |
|---|---|---|
| `sourcea` ... `sourced` | Table | Rasters bound to `$a` ... `$d`. Connect them in order; every connected raster must be used. |
| `expression` | String | The expression. |
| `output_type` | Selection | Default `float32`. |
| `overviews` | Selection | `evaluate` (default) or `none`. |
| `apply_scale_offset` | Boolean | Default `true`. |

The node's output handle is `result`; connect it to `native.saveastable` to keep the result. Node `data`:

```json
{
  "name": "carto.rasteralgebra",
  "label": "Raster Algebra",
  "inputs": [
    {"name": "sourcea", "type": "Table", "value": null},
    {"name": "sourceb", "type": "Table", "value": null},
    {"name": "sourcec", "type": "Table", "value": null},
    {"name": "sourced", "type": "Table", "value": null},
    {"name": "expression", "type": "String", "value": "delta = $b - $a; gained = $b >= -100 and $a < -100"},
    {"name": "output_type", "type": "Selection", "value": "float32"},
    {"name": "overviews", "type": "Selection", "value": "evaluate"},
    {"name": "apply_scale_offset", "type": "Boolean", "value": true}
  ]
}
```

- Edges go from each source node's `out` handle to `sourcea`, `sourceb`, ..., and from `result` to the save node's `source`.
- The component checks the expression against the connected inputs: missing or unused rasters, connection order, band names, output names and missing `;`.
- Offline `carto workflows validate` can't resolve the toolbox. Run `carto workflows verify-remote --connection <connection>` (MCP `validate_workflow method=verify`).
- Workflow variables are not expanded in the expression or the options.
- The component replaces its own output on every run, unlike the procedure.

### Known platform issues (October 2026)

- **CLI raster sources**: `carto workflows validate` accepts only `type: "table"` on `ReadTable` source nodes. Point a plain table source at the raster table: the workflow runs, but that node doesn't show the raster on its Map tab.
- **CLI on non-US tenants**: `carto workflows run` and `carto workflows to-sql` call the US toolbox (`carto-un.carto`) on every tenant, so on non-US tenants the run fails with "Procedure is not found". Run the workflow from the Workflows editor, or call the procedure with SQL against the regional toolbox.
- **Map preview**: the Workflows Map tab doesn't preview the component's output yet. Save it as a table and open the table in Builder.
- **Unverified**: with toolbox 1.26.0 on BigQuery, Get Values from Raster and Intersect and Aggregate Raster (`RASTER_VALUES`, `RASTER_AGG_VALUES`) may fail on a Raster Algebra output because of its per-band statistics columns. Summarize with the statistics columns instead (below).

## Output

- One column per output band, plus `<band>_count`, `_min`, `_max`, `_sum`, `_mean` and `_stddev` per band, `block` and `metadata`. On Snowflake the column names are upper case (`BLOCK`, `GAINED_SUM`); band names in the metadata keep the case used in the expression.
- Metadata row (`block = 0`): RaQuet v0.5.0 metadata, with `STATISTICS_*` per band computed at native resolution, `tiling.max_zoom` and `tiling.pixel_zoom`, and `processing.expression` and `processing.inputs`.
- `<band>_count` is the number of valid (not nodata) pixels in the tile; `_sum` of a 1/0 mask is the number of pixels where it is 1.

The table also holds overview blocks (with `overviews: evaluate`), so filter to native-resolution blocks before adding up. Pixel count and area of a `gained` mask, BigQuery:

```sql bigquery
WITH m AS (
  SELECT
    CAST(JSON_VALUE(metadata, '$.tiling.max_zoom') AS INT64) AS max_zoom,
    CAST(JSON_VALUE(metadata, '$.tiling.pixel_zoom') AS INT64) AS pixel_zoom
  FROM `project.dataset.coverage_delta`
  WHERE block = 0
)
SELECT
  SUM(t.gained_sum) AS gained_pixels,
  -- Web Mercator pixel side in meters shrinks with the cosine of the latitude
  SUM(t.gained_sum * POW(40075016.686 * COS(ST_Y(`carto-un`.carto.QUADBIN_CENTER(t.block)) * ACOS(-1) / 180) / POW(2, m.pixel_zoom), 2)) AS gained_m2
FROM `project.dataset.coverage_delta` AS t
CROSS JOIN m
WHERE t.block != 0
  AND (t.block >> 52) & 31 = m.max_zoom
```

Snowflake (pixel count):

```sql snowflake
SELECT SUM(t.GAINED_SUM) AS GAINED_PIXELS
FROM MYDB.MYSCHEMA.COVERAGE_DELTA AS t
WHERE t.BLOCK != 0
  AND BITAND(BITSHIFTRIGHT(t.BLOCK, 52), 31) = (
    SELECT PARSE_JSON(METADATA):tiling.max_zoom::INT
    FROM MYDB.MYSCHEMA.COVERAGE_DELTA
    WHERE BLOCK = 0
  )
```

For a band's mean over the whole raster, use `STATISTICS_MEAN` from the metadata, or `SUM(<band>_sum) / SUM(<band>_count)` over native-resolution blocks.

To show the result, open the table in Builder as a raster layer (see `carto-create-builder-maps`).
