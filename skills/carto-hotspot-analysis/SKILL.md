---
name: carto-hotspot-analysis
description: Builds Getis-Ord Gi* hotspot analysis workflows in CARTO. Triggers when the user mentions hotspots, coldspots, spatial clusters, Getis-Ord, Gi*, cluster detection, concentration areas, "where do X cluster", spacetime hotspot, temporal clusters, time-varying patterns, hotspot trends, emerging hotspots, Mann-Kendall, or wants to find statistically significant spatial or spatiotemporal patterns in point or grid data.
license: MIT
---

# Hotspot Analysis with Getis-Ord Gi*

Builds CARTO Workflows that identify statistically significant spatial clusters (hotspots and coldspots) using the Getis-Ord Gi* statistic.

**Prerequisites**: Load `carto-create-workflow` for the development process, JSON structure, and validation commands — it covers both access paths (the MCP server's workflow tools such as `create_workflow`, `validate_workflow`, and `run_workflow` when attached; the `carto workflows` CLI otherwise; routing signals in `carto-basics/references/access-paths.md`).

---

## Instructions

A hotspot workflow always follows this pipeline:

```
Source Data → (Filter) → Spatial Indexing → Aggregation → Getis-Ord Gi* → (Filter Significant) → Save
```

### Step 1: Load Source Data

Use `native.gettablebyname`. The input table typically contains point geometries.

**Success**: Node outputs a table with a geometry column (e.g. `geom`).

### Step 2: Filter (if needed)

Use `native.wheresimplified` or `native.where` to narrow the dataset before analysis (e.g. filter by category, date range, non-null values).

**Success**: Output contains only the subset relevant to the analysis.

### Step 3: Build a Complete Grid

**Preferred approach**: Polyfill the study area boundary (e.g. district polygons) with `native.h3polyfill` (`geo` = the boundary geometry, `resolution`, `aggregate: true` so each cell appears once; the cell column is `h3`). Then count the points into that grid with `native.h3enrich`: wire the grid into its `target` input and the points into `source`, and set `target_col` = `h3`, `source_col` = the points' geometry column, `variables` = `<point id column>,count` (output column `<point id column>_count`). This path needs no group-by in Step 4. Every cell in the study area then has a row, which Getis-Ord needs: gaps in the grid distort the neighborhood calculations and can produce misleading results.

**Simpler alternative** (when no study area boundary is available): Convert point geometries directly to grid cells with `native.h3frompoint` or `native.quadbinfrompoint`. Be aware this only produces cells where data exists, leaving gaps that may affect the statistic. With `native.quadbinfrompoint` the new column is `quadbin` (not `h3`): group by `quadbin` and aggregate `quadbin,count` (gives `quadbin_count`). Its default resolution 12 gives cells about 9.8 km wide at the equator; each level up halves the width. On Databricks, Getis-Ord accepts H3 only.

**Resolution guidance** — higher resolution = smaller cells = more local patterns:

| Resolution | Average cell (edge / area) | Use case |
|------------|----------------------------|----------|
| H3 res 6 | ~3.7 km edge / ~36 km² | Metro or regional patterns |
| H3 res 7 | ~1.4 km edge / ~5.2 km² | District / city-level patterns |
| H3 res 8 | ~0.53 km edge / ~0.74 km² | Neighborhood-level |
| H3 res 9 | ~0.20 km edge / ~0.11 km² | Street / block-level |

Each resolution step makes cells about 7x smaller in area (about 2.6x shorter edge).

**Success**: A contiguous grid covering the study area, with every cell assigned a spatial index column (e.g. `h3`).

### Step 4: Aggregate per Cell

Use `native.groupby` to produce one row per cell with a numeric value:
- **Group by**: the spatial index column (`h3`)
- **Aggregation**: `h3,count` (or `value_col,sum` / `value_col,avg`)

On the polyfill path, cells with no points can come back NULL instead of 0 (always when you join the grid to the counts yourself). Add a new column with `native.selectexpression` (`column`: e.g. `value`; `expression`: `COALESCE(<count column>, 0)`, e.g. `COALESCE(store_id_count, 0)` after counting `store_id` with `native.h3enrich`) and use that new column as `valuecol`. Pick a new name: the component appends the column to all existing ones.

**Success**: Output has exactly one row per unique cell with a count/sum column — no gaps.

### Step 5: Run Getis-Ord Gi*

Use `native.getisord` with:

| Input | Description | Value |
|-------|-------------|-------|
| `indexcol` | Column with H3/Quadbin indexes | the index column from Step 3 (e.g. `h3`) |
| `valuecol` | Numeric column to analyze | the count/sum column from Step 4 (e.g. `h3_count`) |
| `kernel` | Weighting function for neighbors | no default: always set it |
| `size` | K-ring size (neighborhood radius in hops), 1-10 | `3` (default) |

**Kernel options**: `uniform`, `triangular`, `quadratic`, `quartic`, `gaussian`. Default to `uniform` (equal weight to all neighbors) unless the user has a reason to decay weight with distance. On Databricks the input is named `databricks_kernel` (options `uniform`, `triangular`, `quadratic`, `quartic`, `gaussian`, `bounded_gaussian`, `inverse`, `inverse_square`, `exponential`); `kernel` does not exist there.

**K-ring size**: Larger = smoother, broader patterns. Smaller = more localized clusters.

**Success**: Output contains the index column, `gi` (z-score) and `p_value` for every cell. On BigQuery the index column is named `index`; on Snowflake and Databricks it keeps the input column's name (e.g. `h3`). (See the Provider casing note in Gotchas.)

### Step 6: Filter Significant Results (optional)

Use `native.where` to keep only statistically significant cells:
- `p_value < 0.05` — 95% confidence
- `p_value < 0.05 AND gi > 0` — hotspots only
- `p_value < 0.05 AND gi < 0` — coldspots only

**Success**: Only cells with statistically meaningful clustering remain.

### Step 7: Save

Use `native.saveastable` with `destination` set to the fully qualified output table name (ask the user where to write it). The H3/Quadbin column is directly visualizable in CARTO Builder without geometry conversion.

**Success**: Validated workflow that can be uploaded via `create_workflow` (MCP) or `carto workflows create` (CLI).

---

## Output Columns

| Column | Meaning |
|--------|---------|
| `index` (BigQuery) or the input index column name (Snowflake, Databricks) | Spatial index cell ID (H3 or Quadbin) |
| `gi` | Gi* z-score — positive = hotspot, negative = coldspot |
| `p_value` | Statistical significance — lower = more confident |

---

## Gotchas

- **Provider support.** `native.getisord` runs on BigQuery, Snowflake and Databricks. The spacetime components run on BigQuery and Snowflake only. On PostgreSQL, Redshift or Oracle connections none of them exist: say hotspot analysis is not available on that connection and offer to build it on a BigQuery, Snowflake or Databricks connection.
- **Provider casing & SQL dialect.** This skill documents columns in lowercase (BigQuery / Databricks convention). On Snowflake, unquoted identifiers surface UPPERCASE: reference `H3`, `GI`, `P_VALUE`, `H3_COUNT` in expressions (the output index column keeps its input name, e.g. `H3`; there is no `INDEX`). For dialect-specific SQL fragments (e.g. `DATETIME_TRUNC` in the spacetime pipeline), see `carto-create-workflow/references/providers/<provider>.md` for the equivalents table.
- The Getis-Ord component requires the Analytics Toolbox. Offline validation (`validate_workflow` over MCP, or `carto workflows validate`) can't resolve the AT location — confirm it with the CLI-only `carto workflows verify-remote --connection <conn>` before running.
- On BigQuery the output index column is named `index`, not `h3` or `quadbin`; on Snowflake and Databricks it keeps the `indexcol` name. Rename it (e.g. with `native.renamecolumn`) if you need to join back to the original data.
- `native.where` and `native.wheresimplified` have two outputs, `match` and `unmatch`; wire the next node from `match` (sourceHandle `match`). There is no `result` output.
- If you call `native.h3boundary` to materialize cell geometries for visualization, the new column is named `<h3col>_geo` (e.g. `index_geo`), **not** `geom`. Reference it accordingly in downstream nodes.
- The `valuecol` must be numeric. If you're counting features, the group-by step must produce a count column — don't pass the raw index column as the value.
- Resolution too high + large area = very many cells, which can be slow or hit memory limits. Start with a moderate resolution and refine.
- An empty result from the filter step (Step 6) usually means the k-ring size is too small or the data is too sparse for significant clustering. Try increasing `size` or lowering the resolution.

---

## Spacetime Variants

Getis-Ord Spacetime (`native.getisordspacetime`), Spacetime Hotspot Classification (`native.spacetimehotspotsclassification`) and Time Series Clustering (`native.timeseriesclustering`) are covered in [references/spacetime.md](references/spacetime.md): their required inputs, how columns are renamed between steps, and the significance pre-filter for clustering.

---

## Reference Templates

These files are working examples (skill-local, in this skill's folder):

| File | Description |
|------|-------------|
| `poi_hotspot.json` | Stockholm amenity POIs — H3 res 9, uniform kernel, k=3 |
| `space_time_hotspot.json` | Barcelona accidents — spacetime Gi*, H3 res 9, weekly bins |
| `spacetime_hotspot_classification.json` | London collisions — spacetime Gi* + classification, gaussian kernel |

---

## Common Variations

| Variant | How |
|---------|-----|
| Polygon input instead of points | Use `native.h3polyfill` instead of `native.h3frompoint` |
| Enrich existing grid | Use `native.h3enrich` to count points into a grid (avoids manual group-by + join) |
| Combine with other data | Join Getis-Ord output with enrichment or attribute tables before saving |
| Spacetime / trend classification | See the Spacetime Variants section above |
