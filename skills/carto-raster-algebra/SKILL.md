---
name: carto-raster-algebra
description: Computes new rasters from existing ones in CARTO with raster algebra (pixel-by-pixel expressions over one or more RaQuet rasters). Triggers when the user wants to subtract, add, compare, combine, threshold or mask rasters, compute band math or spectral indices (NDVI, NDWI, NBR...), change detection or before/after deltas (e.g. signal coverage gained by a new site), map algebra, raster calculator, or "operations between two raster sources and their bands" — in the Analytics Toolbox (SQL) or in Workflows.
license: MIT
---

# Raster Algebra

Computes a **new raster** by evaluating an expression pixel by pixel over one or more RaQuet raster tables. Available as the Analytics Toolbox procedure `RASTER_ALGEBRA` (BigQuery, Snowflake) and as the **Raster Algebra** Workflows component. The output is a RaQuet v0.5.0 raster table, directly mappable in Builder.

**Prerequisites**: `carto-explore-datawarehouse` to find the rasters and read their metadata; `carto-query-datawarehouse` to run the procedure (it's DDL — use the async / job path); `carto-create-workflow` when building it as a workflow.

---

## Instructions

### Step 1: Inspect every input raster

Read each input's metadata row:

```sql bigquery
SELECT metadata FROM `project.dataset.raster` WHERE block = 0
```

Record band names/types, `nodata`, `scale`/`offset`, `tiling` (block size, zooms), `bounds`, `time`.

**Success**: You know which band holds which variable (see each band's `description`/`colorinterp`) and each input's grid.

### Step 2: Check the inputs can be combined

Inputs must share **block size** and **native zoom** (`tiling.max_zoom`). Extents may differ — the output covers only the overlap. If they differ in resolution, stop and tell the user: the rasters must be re-imported at a common resolution (automatic resampling is not supported). Rasters with a `time` dimension and JPEG/WebP-compressed rasters are not supported.

**Success**: Same `block_width` and `max_zoom` for all inputs, overlapping `bounds`.

### Step 3: Write the expression

Inputs are `$a`, `$b`, … in the order passed. Reference bands as `$a.band_1`, by name (`$a.nir`) or index (`$a[4]`); a single-band input is just `$a`. Full syntax and recipes: [`references/expressions.md`](references/expressions.md).

- Several outputs at once: `ndvi = (...); mask = (...)`.
- Comparisons return 1/0; use `if(cond, a, b)` for conditional values.
- **Nodata is strict**: an output pixel is nodata if *any* input pixel it references is nodata, or the result is not finite (division by zero, log of a negative). Don't try to "fill" nodata inside the expression — it won't be reached.
- **Stored values vs physical values**: by default the expression sees stored (DN) values. If bands have `scale`/`offset` (e.g. reflectance stored as integers), pass `{"apply_scale_offset": true}`.

**Success**: Every input is referenced; every band name exists in the metadata.

### Step 4: Choose options

Defaults (`float32`, nodata `NaN`, all zoom levels) suit indices and ratios. For masks/classes use an integer `output_type` and set `output_nodata`; use `overviews: none` for exact results of non-linear expressions. Details: [`references/expressions.md`](references/expressions.md).

### Step 5: Run it

SQL (BigQuery shown; Snowflake uses `ARRAY_CONSTRUCT(...)` and `<database>.<schema>` for the Toolbox location):

```sql bigquery
CALL `carto-un`.carto.RASTER_ALGEBRA(
  ['project.dataset.coverage_before', 'project.dataset.coverage_after'],
  'delta = $b - $a; gained = $b > -100 and $a <= -100',
  'project.dataset.coverage_delta',
  '{"output_type": "float32"}'
);
```

It fails — without creating anything — on a missing band, grid mismatch, unreferenced input, invalid expression, or an existing output table. Report the error message to the user verbatim: it names the band/input/grid property at fault.

In **Workflows**, use the `carto.rasteralgebra` component (group *Raster Operations*):

| Input / param | Value |
|---|---|
| `sourcea` … `sourced` | Raster tables for `$a` … `$d`. Connect them in order; every connected raster must be used in the expression. |
| `expression` | The expression (multiline; `;` separates outputs). |
| `output_type`, `overviews`, `apply_scale_offset` | As in Step 4 (advanced). |

The output is a raster table; persist it with `native.saveastable` to map it in Builder.

**Success**: The output table has one row with `block = 0` whose metadata lists the output bands with `STATISTICS_*` values — quote those to summarize the result.

### Step 6: Summarize or visualize

Per-tile statistics columns (`<band>_count`, `_min`, `_max`, `_sum`, `_mean`, `_stddev`) allow cheap summaries without decoding pixels, e.g. area gained = `SUM(gained_sum)` pixels at native zoom times the pixel area. Map the output in Builder as a raster layer (see `carto-create-builder-maps`).

---

## Gotchas

- Overviews computed with `overviews: evaluate` apply the expression to overview (downsampled) pixels — fine for display, approximate for thresholds/ratios. For exact aggregates, filter to the native zoom: `(block >> 52) & 31 = max_zoom` (BigQuery).
- Output band names must be valid identifiers and not end in `_count`, `_min`, etc.
- Legacy CARTO rasters (metadata with `block_resolution`) must be re-imported to RaQuet first.
