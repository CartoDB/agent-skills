---
name: carto-raster-operations
description: Transforms RaQuet rasters in CARTO with named raster operations, using the Analytics Toolbox procedures RASTER_CLIP, RASTER_MASK, RASTER_FILTER, RASTER_MERGE, RASTER_RECLASSIFY, RASTER_SET_NODATA, RASTER_REPLACE_NODATA, RASTER_SELECT_BANDS, RASTER_STACK and RASTER_VECTORIZE, or the matching Raster Operations Workflows components (BigQuery, Snowflake). Triggers when the user wants to clip a raster to a polygon or area of interest, mask it with another raster, filter or threshold pixel values, merge or mosaic rasters, reclassify values into classes, set or fill nodata, select or stack bands, or convert a raster into polygons (vectorize / polygonize). For arbitrary pixel expressions, band math or spectral indices, use carto-raster-algebra instead.
license: MIT
---

# Raster Operations

Ten Analytics Toolbox procedures that read **RaQuet v0.5.0** raster tables and write a **new** one (`RASTER_VECTORIZE` writes polygons). Each has a **Raster Operations** Workflows node (group *Raster Operations*, component names `carto.raster*`) that runs the same procedure. Providers: BigQuery (including CARTO Data Warehouse) and Snowflake only.

Not for arbitrary pixel expressions (band math, indices, deltas between rasters, custom formulas): use `carto-raster-algebra`. Operations here chain well with it, since they all share the RaQuet v0.5.0 format.

**Prerequisites**: `carto-explore-datawarehouse` to find the rasters; `carto-query-datawarehouse` to run SQL (every `CALL` creates a table, so use the async/job path); `carto-create-workflow` to build a workflow.

| Reference | Contents |
|---|---|
| [references/operations.md](references/operations.md) | Per procedure: signature, parameters, options, one example per cloud |
| [references/semantics.md](references/semantics.md) | Nodata rules, overviews, limits, and where results differ from GDAL / rasterio / QGIS |
| [references/workflows.md](references/workflows.md) | Workflows nodes, how they map to the procedures, chaining recipes, troubleshooting |

---

## Instructions

### Step 1: Pick the operation

| I want to... | Use |
|---|---|
| Cut a raster to a polygon / area of interest | `RASTER_CLIP` |
| Keep pixels where another raster (e.g. land cover = 3, cloud-free) says so | `RASTER_MASK` |
| Keep pixels by their own value (`< 15`, `in (10, 20)`) | `RASTER_FILTER` |
| Join adjacent or overlapping rasters into one (mosaic) | `RASTER_MERGE` |
| Group values into classes (optionally coloured and labelled) | `RASTER_RECLASSIFY` |
| Declare which value means "no data" (and rewrite those pixels) | `RASTER_SET_NODATA` |
| Fill the nodata pixels with a constant | `RASTER_REPLACE_NODATA` |
| Keep, reorder or drop bands of one raster | `RASTER_SELECT_BANDS` |
| Combine the bands of several rasters into one multi-band raster | `RASTER_STACK` |
| Turn a (classified) raster into polygons | `RASTER_VECTORIZE` |
| A formula between pixels or bands | `carto-raster-algebra` |

### Step 2: Inspect the inputs

```sql bigquery
SELECT metadata FROM `project.dataset.raster` WHERE block = 0
```

On Snowflake the columns are usually upper case (`METADATA`, `BLOCK`). Record `version`, each band's `name`, `type`, `nodata`, `scale`, `offset`, plus `tiling.block_width`, `tiling.max_zoom`, `compression`.

**Success**: You know the band names, the nodata of each band and the grid of every input.

### Step 3: Check the inputs are supported

If a check fails, stop and tell the user what to fix. The procedures reject these cases anyway.

- **RaQuet v0.5.0 only**: `version` must be `0.5.x`. Legacy v0 rasters have no upgrade path: **re-import** them.
- **No RGB imports**: a 3-band 8-bit RGB image imported as lossy WebP (interleaved) is not supported. Re-import it without the color tags, see `carto-raster-algebra` ([references/running.md](../carto-raster-algebra/references/running.md)).
- **Same grid** to merge, mask or stack: same block size and `max_zoom`. There is **no automatic resampling**: resample the source files and re-import.
- Block size must be square, a power of two and divisible by 16. No `time` dimension, no JPEG/WebP tiles.
- Operations that evaluate pixel values reject `int64`, `uint64` and `float16` bands (`SELECT_BANDS` and `STACK` only copy them).

**Success**: The inputs are compatible, or the user knows what to re-import.

### Step 4: Run it

Options are **one JSON string or `NULL`**. Unknown keys are rejected naming the key. Every call writes a **new** table: it fails if `output_table` exists or is an input, and an empty result is an error (no table is created). Never drop an existing table without asking: pick a new name.

BigQuery (use the toolbox project for the data's region: `carto-un` is the US one):

```sql bigquery
CALL `carto-un`.carto.RASTER_CLIP(
  'project.dataset.elevation',
  'project.dataset.study_area',
  'project.dataset.elevation_study_area',
  NULL
);
```

Snowflake (use the database and schema where the toolbox is installed):

```sql snowflake
CALL carto.RASTER_CLIP(
  'MYDB.MYSCHEMA.ELEVATION',
  'MYDB.MYSCHEMA.STUDY_AREA',
  'MYDB.MYSCHEMA.ELEVATION_STUDY_AREA',
  NULL
);
```

Signatures and options for all ten: [references/operations.md](references/operations.md). Put long statements in a file: inside a double-quoted shell argument, the shell expands `$a`.

**Success**: The output table exists and its metadata row (`block = 0`) lists the expected bands.

### Step 5: Chain and verify

Each output is a normal v0.5.0 raster, so feed it to the next step. Typical chains: clip, then filter; merge, then reclassify, then vectorize. Recipes in [references/workflows.md](references/workflows.md). After the last step read the output metadata row (`STATISTICS_*` per band) and open it in Builder as a raster layer (`carto-create-builder-maps`).

---

## Gotchas

- **Clip keeps more pixels than GDAL by default**: any pixel whose square overlaps the polygon, not only those with the centre inside. Pass `{"intersect_center": true}` for the GIS rule.
- **Set nodata rewrites pixels**, unlike `gdal_edit -a_nodata`. **Replace nodata** takes a *stored* value (no scale/offset).
- **Merge needs `overlap_rule`** (no default) and identical band count, type, scale, offset and nodata in every input; use `RASTER_SET_NODATA` first if nodata differs.
- **Filter and mask act on physical values** (`value * scale + offset`) by default; `{"apply_scale_offset": false}` compares stored values. A float32 `== 0.1` matches nothing: use `between`.
- **Reclassify and vectorize on multi-band rasters need `"band"`**; reclassify's output holds that band only.
- **Overviews are not coarser versions of the result** for filter, reclassify, conditional mask and merge `sum`/`mean`: each zoom is computed from the input's own tile at that zoom. Use `{"overviews": "none"}` when only the native zoom matters.
- Workflows nodes take the frequent parameters as inputs and every other option as one JSON object in **Options** (`customoptions`).
- Examples in the references come from the product docs; run them on a small raster first.
