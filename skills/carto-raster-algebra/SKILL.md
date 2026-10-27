---
name: carto-raster-algebra
description: Computes new rasters from existing ones in CARTO with raster algebra, pixel-by-pixel expressions over one or more RaQuet rasters, using the Analytics Toolbox RASTER_ALGEBRA procedure or the Raster Algebra Workflows component (BigQuery, Snowflake). Triggers when the user wants to subtract, add, compare, combine, threshold or mask rasters, compute band math or spectral indices (NDVI, NDWI, NBR...), change detection or before/after deltas (e.g. signal coverage gained by a new site), map algebra, a raster calculator, or operations between two raster sources and their bands.
license: MIT
---

# Raster Algebra

Computes a **new raster** by evaluating an expression pixel by pixel over one or more RaQuet raster tables. Two ways to run it, same engine and rules:

- The Analytics Toolbox procedure `RASTER_ALGEBRA` (SQL `CALL`), up to 26 inputs.
- The **Raster Algebra** Workflows component (`carto.rasteralgebra`, group *Raster Operations*), up to 4 inputs.

Providers: BigQuery (including CARTO Data Warehouse) and Snowflake only. Minimum Analytics Toolbox: 1.26.0 on BigQuery, 1.27.0 on Snowflake. The output is a RaQuet v0.5.0 raster table.

**Prerequisites**: `carto-explore-datawarehouse` to find the rasters; `carto-query-datawarehouse` to run SQL (the `CALL` creates a table, so use the async/job path); `carto-create-workflow` to build a workflow.

| Reference | Contents |
|---|---|
| [references/expressions.md](references/expressions.md) | Full syntax, output names, nodata rules, recipes, common errors |
| [references/running.md](references/running.md) | Importing v0.5.0 rasters, options, SQL per provider, the Workflows node, known platform issues, reading the output |

---

## Instructions

### Step 1: Inspect every input raster

```sql bigquery
SELECT metadata FROM `project.dataset.raster` WHERE block = 0
```

On Snowflake the columns are usually upper case (`METADATA`, `BLOCK`). Record per input: `version`, each band's `name`, `type`, `nodata`, `scale`, `offset` and `description`, plus `tiling.block_width`, `tiling.max_zoom`, `bounds`, `time` and `compression`.

**Success**: You know which band holds which variable, and each input's grid.

### Step 2: Check the inputs can be combined

If any check fails, stop and tell the user what to fix. The procedure rejects these cases anyway.

- **RaQuet v0.5.0**: `file_format` is `raquet` and `version` is `0.5.x`. Earlier RaQuet versions and legacy CARTO rasters fail with "RaQuet v0.5.0 is required". CARTO imports still write the earlier version by default, so re-import requesting v0.5.0 (see [references/running.md](references/running.md)).
- **Same grid**: the same `block_width`, `block_height` and `max_zoom` for every input. Rasters are not resampled: re-import them at a common resolution.
- **Overlap**: extents may differ. Each output band covers the area where the rasters it uses overlap; no overlap is an error.
- **Not supported**: a `time` dimension, and `jpeg` or `webp` compression (common in RGB imagery).

**Success**: The inputs are compatible, or the user knows what to re-import.

### Step 3: Write the expression

Inputs are `$a`, `$b`, ... in the order passed (in Workflows, the order connected). Bands are `$a.band_1` (by name) or `$a[1]` (by 1-based index); a bare `$a` works only for a single-band input. Full syntax and recipes: [references/expressions.md](references/expressions.md).

- **Use every input.** In Workflows, also connect `$a`, `$b`, ... in order, without gaps.
- **Several outputs**: separate them with `;` (line breaks don't separate them). `name = expr` names an output; unnamed ones are `band_1`, `band_2`, ... Names must be unique ignoring case, can't be `block` or `metadata`, and can't end in `_count`, `_min`, `_max`, `_sum`, `_mean` or `_stddev`.
- **Nodata is strict**: an output pixel is nodata if any input pixel its expression references is nodata, or if the result isn't finite (division by zero, log of a negative). This includes both branches of `if()`, so nodata can't be filled inside the expression.
- **Physical values**: by default, bands with `scale`/`offset` are converted (`value * scale + offset`) before evaluating. Turn this off to work on stored values.

**Success**: Every input is used and every band name exists in its metadata.

### Step 4: Choose options

| Need | Setting |
|---|---|
| Indices, ratios, deltas | Defaults: `float32`, all zoom levels |
| Masks, classes | An integer type such as `uint8`. Integer types reserve their max (unsigned) or min (signed) value as nodata, e.g. 255 for `uint8`, so a result equal to it becomes nodata |
| Result only feeds more analysis | `overviews: none` (native resolution only, cheaper) |

`output_nodata` and `compression` exist only in the procedure, not in the component. Details: [references/running.md](references/running.md).

### Step 5: Run it

SQL on BigQuery (on Snowflake, use `ARRAY_CONSTRUCT(...)` and the toolbox's `<database>.<schema>`):

```sql bigquery
CALL `carto-un`.carto.RASTER_ALGEBRA(
  ['project.dataset.coverage_before', 'project.dataset.coverage_after'],
  'delta = $b - $a; gained = $b >= -100 and $a < -100',
  'project.dataset.coverage_delta',
  NULL
);
```

- Use the toolbox project for the data's region: `carto-un` is the US one.
- It validates everything before writing anything. It fails if the output table already exists or is one of the inputs. Show the user the error as is: it names the input, band or grid property at fault.

In Workflows: one source node per raster, then **Raster Algebra**, then `native.saveastable`. Node shape and CLI limits: [references/running.md](references/running.md).

**Success**: The output table exists and its metadata row lists the output bands.

### Step 6: Check and summarize

- Read the output's metadata row (`block = 0`): each band has `STATISTICS_*` values (min, max, mean, stddev, valid percent) at native resolution.
- The per-tile columns `<band>_count`, `_min`, `_max`, `_sum`, `_mean` and `_stddev` give cheap aggregates without decoding pixels. Filter to native-resolution blocks first, because overview blocks repeat the data ([references/running.md](references/running.md)).
- To see the result on a map, save it as a table and open it in Builder.

---

## Gotchas

- With `overviews: evaluate`, overview pixels are computed from the inputs' overview pixels, so non-linear results (ratios, thresholds) are approximate at low zooms. Native-resolution pixels are exact either way.
- If a "before" raster stores "no signal" as nodata, every pixel that gains coverage is nodata in the result too. The input needs a real value there, not nodata.
- Never drop an existing output table without asking: choose a new name.
