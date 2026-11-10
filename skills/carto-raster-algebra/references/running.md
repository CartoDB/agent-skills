# Running raster algebra

## Inputs: RaQuet v0.5.0 rasters

Check `version` in each input's metadata row. Rasters written by the [raquet](https://github.com/CartoDB/raquet) tools are v0.5.0. Rasters imported into CARTO before RaQuet v0.5.0 was enabled for the organization are in the earlier version, and raster algebra rejects them.

If an input is in the earlier version, tell the user to import it again, then confirm `version` is `0.5.0` in the new table's metadata row. If a new import is still in the earlier version, RaQuet v0.5.0 isn't enabled for the organization yet: the user can write the raster with the raquet tools, or ask their CARTO contact.

### RGB images

When a raster with exactly three 8-bit bands tagged red, green and blue is imported into CARTO, it is stored as an image: `band_layout` is `interleaved`, `compression` is `webp` (lossy), and the table has a single `pixels` column instead of one column per band. Raster algebra can't read it, and neither can `RASTER_VALUES` or `RASTER_AGG_VALUES`.

To analyze it, tell the user to clear the color tags in the source file and import it again. The pixel values don't change:

```bash
gdal_translate -colorinterp undefined,undefined,undefined input.tif output.tif
```

The new table has one column per band and lossless compression. Confirm it in its metadata row before running raster algebra.

### Grid

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

Component `carto.rasteralgebra` (title Raster Algebra, group Raster Operations). Read its spec with `carto workflows components get carto.rasteralgebra --connection <connection> --json` (or MCP `read_workflow_components`). If it isn't found, the organization doesn't have it enabled yet, or the connection's toolbox is older than the minimum version. Then use the SQL procedure, except on a Snowflake toolbox older than 1.28.0: update the toolbox first (see the Snowflake note in SKILL.md).

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
- Raster source nodes are `ReadTable` source nodes with `data.type: "raster"`, which makes their Map tab show the raster. The CLI accepts it from version 0.14.0; earlier versions reject it in `workflows validate`.
- `carto workflows validate` checks the bundle's structure and components, not the data. Run `carto workflows verify-remote --connection <connection>` (MCP `validate_workflow method=verify`) to check the workflow against the warehouse before running it.
- Workflow variables are not expanded in the expression or the options.
- The component replaces its own output on every run, unlike the procedure.


## Output

- One column per output band, plus `<band>_count`, `_min`, `_max`, `_sum`, `_mean` and `_stddev` per band, `block` and `metadata`. On Snowflake the column names are upper case (`BLOCK`, `GAINED_SUM`); band names in the metadata keep the case used in the expression.
- Metadata row (`block = 0`): RaQuet v0.5.0 metadata, with `STATISTICS_*` per band computed at native resolution, `tiling.max_zoom` and `tiling.pixel_zoom`, and `processing.expression` and `processing.inputs`.
- `<band>_count` is the number of valid (not nodata) pixels in the tile; `_sum` of a 1/0 mask is the number of pixels where it is 1.

The table also holds overview blocks (with `overviews: evaluate`), so filter to native-resolution blocks before adding up: their quadbin resolution equals `tiling.max_zoom`. Pixels where a `gained` mask is 1:

```sql bigquery
SELECT SUM(t.gained_sum) AS gained_pixels
FROM `project.dataset.coverage_delta` AS t
WHERE t.block != 0
  AND `carto-un`.carto.QUADBIN_RESOLUTION(t.block) = (
    SELECT CAST(JSON_VALUE(metadata, '$.tiling.max_zoom') AS INT64)
    FROM `project.dataset.coverage_delta`
    WHERE block = 0
  )
```

```sql snowflake
SELECT SUM(t.GAINED_SUM) AS GAINED_PIXELS
FROM MYDB.MYSCHEMA.COVERAGE_DELTA AS t
WHERE t.BLOCK != 0
  AND CARTO.CARTO.QUADBIN_RESOLUTION(t.BLOCK) = (
    SELECT PARSE_JSON(METADATA):tiling.max_zoom::INT
    FROM MYDB.MYSCHEMA.COVERAGE_DELTA
    WHERE BLOCK = 0
  )
```

For a band's mean over the whole raster, use `STATISTICS_MEAN` from the metadata, or `SUM(<band>_sum) / SUM(<band>_count)` over native-resolution blocks.

In Workflows, the Map tab previews the output. To show it in a map, open the table in Builder as a raster layer (see `carto-create-builder-maps`).
