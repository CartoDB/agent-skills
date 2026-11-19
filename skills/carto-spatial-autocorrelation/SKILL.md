---
name: carto-spatial-autocorrelation
description: Builds Moran's I spatial autocorrelation workflows in CARTO. Triggers when the user mentions spatial autocorrelation, Moran's I, spatial dependency, spatial correlation, spatial outliers, HH HL LH LL quadrants, high-high clusters, low-low clusters, spatial weight matrix, "is there clustering", "are values spatially correlated", local indicators of spatial association, LISA, spatial randomness test, or wants to determine whether a variable exhibits spatial clustering, dispersion, or randomness across a gridded dataset. Also relevant when the user needs to classify locations into cluster types (HH, HL, LH, LL) rather than just identifying hotspots and coldspots.
license: MIT
---

# Spatial Autocorrelation with Moran's I

Builds CARTO Workflows that measure spatial autocorrelation using Moran's I, determining whether a variable exhibits clustering, dispersion, or randomness, and classifying each location into HH/HL/LH/LL quadrants.

**Prerequisites**: Load `carto-create-workflow` for the development process, JSON structure, and validation commands — it covers both access paths (the MCP server's workflow tools such as `create_workflow`, `validate_workflow`, and `run_workflow` when attached; the `carto workflows` CLI otherwise; routing signals in `carto-basics/references/access-paths.md`).

**When to use Moran's I vs Getis-Ord Gi***:
- **Moran's I**: "Is there clustering?" (global, `native.moransi`) + classify cells into HH, HL, LH, LL and find spatial outliers (local, `native.localmoransi`)
- **Getis-Ord Gi***: "Where are the hotspots/coldspots?" + magnitude of clustering (z-scores)

---

## Instructions

A Moran's I workflow follows this pipeline:

```
Source Data -> (Filter) -> Spatial Indexing (H3) -> Aggregation -> Moran's I -> (Filter Significant) -> Save
```

### Step 1: Load Source Data

Use `native.gettablebyname`. The input table typically contains point geometries or pre-indexed grid data.

**Success**: Node outputs a table with a geometry column (e.g. `geom`) or an existing spatial index column.

### Step 2: Filter (if needed)

Use `native.wheresimplified` or `native.where` to narrow the dataset (e.g. filter by category, date range, non-null values).

**Success**: Output contains only the subset relevant to the analysis.

### Step 3: Spatial Indexing

Convert point geometries to H3 cells using `native.h3frompoint`.

**Resolution guidance** -- higher resolution = smaller cells = more local patterns:

| Resolution | Average cell (edge / area) | Use case |
|------------|----------------------------|----------|
| H3 res 6 | ~3.7 km edge / ~36 km² | Metro or regional patterns |
| H3 res 7 | ~1.4 km edge / ~5.2 km² | District / city-level patterns |
| H3 res 8 | ~0.53 km edge / ~0.74 km² | Neighborhood-level |
| H3 res 9 | ~0.20 km edge / ~0.11 km² | Street / block-level (used in Berlin POI tutorial) |

Each resolution step makes cells about 7x smaller in area (about 2.6x shorter edge).

**Success**: Every row has a spatial index column (e.g. `h3`).

### Step 4: Aggregate per Cell

Use `native.groupby` to produce one row per cell with a numeric value:
- **Group by**: the spatial index column (`h3`)
- **Aggregation**: `h3,count` (or `value_col,sum` / `value_col,avg`)

**Success**: Output has exactly one row per unique cell with a numeric column (e.g. `h3_count`).

### Step 5: Run Moran's I

There are two components; choose by the user's question:

- **Is there spatial clustering overall?** Use `native.moransi` (global Moran's I). Output: one row with one column, `morans_i`. No index, significance or quadrant columns.
- **Which cells are HH / LL / HL / LH (LISA)?** Use `native.localmoransi` (local Moran's I). Output: one row per cell with the index column, `value` (local Moran's I), `psim` (pseudo p-value from permutations) and `quad` (numeric quadrant code), plus `EIc`, `VIc`, `EI`, `VI`.

Both take:

| Input | Description | Value |
|-------|-------------|-------|
| `indexcol` | Column with H3/Quadbin indexes | the index column from Step 3 (e.g. `h3`) |
| `valuecol` | Numeric column to test for autocorrelation | the count column from Step 4 (e.g. `h3_count`) |
| `size` | K-ring neighborhood radius (in hops), 1-10 | `3` (default) |
| `decay` | Distance decay function for spatial weights | no default: always set it (`uniform` unless the user wants decay) |
| `permutations` | `native.localmoransi` only: permutations used for `psim`, 1-1000 | default 1: set at least 99 (999 for final results) |

**Decay options**: `uniform`, `inverse`, `inverse_square`, `exponential`.
- `uniform`: Equal weight to all neighbors within the k-ring
- `exponential`: Weight decreases exponentially with distance (used in Berlin POI tutorial)

**Permutations**: `psim` is computed from the permutations and cannot reach 0.05 with very few of them; with the default of 1, every cell gets `psim` = 0.5.

**K-ring size**: Larger = broader neighborhood = smoother global patterns. Smaller = more localized assessment. The choice of neighborhood size significantly affects results.

**Success**: `native.moransi` returns one row; `native.localmoransi` returns one row per cell. (See the Provider casing note in Gotchas — Snowflake surfaces these UPPERCASE.)

### Step 6: Filter Significant Results (recommended, local Moran's I only)

Use `native.where` on the `native.localmoransi` output and wire the next node from its `match` output. Quadrant classification is only meaningful for significant cells.

Common filters:
- `psim < 0.05` -- all significant cells (95% confidence)
- `psim < 0.05 AND quad = 1` -- high-value clusters (HH) only
- `psim < 0.05 AND quad IN (3, 4)` -- spatial outliers (LH, HL) only

**Success**: Only cells with statistically meaningful spatial patterns remain.

### Step 7: Save

Use `native.saveastable` with `destination` set to the fully qualified output table name (ask the user where to write it). The H3/Quadbin column is directly visualizable in CARTO Builder without geometry conversion.

**Success**: Validated workflow that can be uploaded via `create_workflow` (MCP) or `carto workflows create` (CLI).

---

## Output Columns

| Column | Component | Meaning |
|--------|-----------|---------|
| `morans_i` | `native.moransi` | Global Moran's I for the whole grid |
| `index` | `native.localmoransi` | Cell ID. Named `index` on BigQuery, `h3` or `quadbin` on Snowflake, the input index column name on Databricks |
| `value` | `native.localmoransi` | Local Moran's I -- positive = similar neighbors (HH or LL), negative = dissimilar neighbors (HL or LH) |
| `psim` | `native.localmoransi` | Pseudo p-value from the permutations -- lower = more confident |
| `quad` | `native.localmoransi` | Quadrant as a number (codes below) |

### Interpreting Results

**Global Moran's I** (`morans_i`, overall pattern):
- \> 0 = spatial clustering (similar values near each other)
- < 0 = spatial dispersion (dissimilar values near each other)
- Near 0 = spatial randomness

**Local quadrants** (`quad`, per-cell classification):
| `quad` | Quadrant | Meaning | Interpretation |
|--------|----------|---------|----------------|
| 1 | HH | High value surrounded by high values | Cluster core |
| 2 | LL | Low value surrounded by low values | Low-value cluster |
| 3 | LH | Low value surrounded by high values | Spatial outlier (low anomaly) |
| 4 | HL | High value surrounded by low values | Spatial outlier (high anomaly) |

---

## Gotchas

- **Provider support.** `native.moransi` and `native.localmoransi` run on BigQuery, Snowflake and Databricks Warehouse connections only, and on Databricks only with H3. On Databricks cluster, PostgreSQL, Redshift or Oracle connections they do not exist: say Moran's I is not available on that connection and offer to build it on a supported one.
- **Provider casing & SQL dialect.** This skill documents columns in lowercase (BigQuery / Databricks convention). On Snowflake, unquoted identifiers surface UPPERCASE: reference `H3`, `H3_COUNT`, `MORANS_I`, and for local Moran's I `H3` (or `QUADBIN`), `VALUE`, `PSIM`, `QUAD` in expressions. See `carto-create-workflow/references/providers/<provider>.md` for casing rules and SQL dialect equivalents.
- The Moran's I components require the Analytics Toolbox. Offline validation can't resolve the AT location — confirm it with a remote verify before running: `validate_workflow` `method: verify` over MCP, or `carto workflows verify-remote --connection <conn>` on the CLI.
- `native.localmoransi` names the index column `index` on BigQuery, `h3` or `quadbin` on Snowflake, and keeps the input name on Databricks. Rename it (e.g. with `native.renamecolumn`) if you need to join back to the original data. `native.moransi` returns no index column.
- `native.where` and `native.wheresimplified` have two outputs, `match` and `unmatch`; wire the next node from `match` (sourceHandle `match`). There is no `result` output.
- The `valuecol` must be numeric. If you are counting features, the group-by step must produce a count column -- do not pass the raw index column as the value.
- Resolution too high + large area = very many cells, which can be slow or hit memory limits. Start with a moderate resolution and refine.
- Moran's I is sensitive to the definition of neighborhood. Both k-ring size and decay function choice materially affect results. Document your choices and consider testing alternatives.
- Quadrant classification is only meaningful for statistically significant cells. Always filter by `psim` before interpreting `quad`: non-significant cells may show any quadrant by chance.
- The decay input parameter is named `decay` (not `kernel`). Check the component schema if unsure.

---

## Reference Templates

| Resource | Description |
|----------|-------------|
| [BQ Tutorial](https://academy.carto.com/advanced-spatial-analytics/spatial-analytics-for-bigquery/step-by-step-tutorials/computing-the-spatial-autocorrelation-of-pois-locations-in-berlin) | Computing spatial autocorrelation of POI locations in Berlin (BigQuery) |
| [SF Tutorial](https://academy.carto.com/advanced-spatial-analytics/spatial-analytics-for-snowflake/step-by-step-tutorials/computing-the-spatial-autocorrelation-of-pois-locations-in-berlin) | Same tutorial for Snowflake |
| Workflow template | "Computing the spatial auto-correlation of point of interest locations" (available in CARTO Workspace) |

---

## Common Variations

| Variant | How |
|---------|-----|
| Pre-indexed data | Skip Step 3 if data already has H3/Quadbin column |
| Polygon input instead of points | Use `native.h3polyfill` instead of `native.h3frompoint` |
| Complete grid (no gaps) | Polyfill the study area with `native.h3polyfill` (`aggregate: true`), then count the points into it with `native.h3enrich` (`target` = the grid, `source` = the points, `target_col` = `h3`, `source_col` = the point geometry, `variables` = `<id column>,count`). Replace NULL counts with 0 (`COALESCE`) in a new `native.selectexpression` column |
| Combine with Getis-Ord | Run both analyses on the same aggregated grid, then join results for a richer picture |
| Filter to outliers only | Keep `quad` 3 and 4 (LH, HL) with `psim < 0.05` to find anomalous locations |
