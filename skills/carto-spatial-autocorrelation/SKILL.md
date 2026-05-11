---
name: carto-spatial-autocorrelation
description: Builds Moran's I spatial autocorrelation workflows in CARTO. Triggers when the user mentions spatial autocorrelation, Moran's I, spatial dependency, spatial correlation, spatial outliers, HH HL LH LL quadrants, high-high clusters, low-low clusters, spatial weight matrix, "is there clustering", "are values spatially correlated", local indicators of spatial association, LISA, spatial randomness test, or wants to determine whether a variable exhibits spatial clustering, dispersion, or randomness across a gridded dataset. Also relevant when the user needs to classify locations into cluster types (HH, HL, LH, LL) rather than just identifying hotspots and coldspots.
license: MIT
---

# Spatial Autocorrelation with Moran's I

Builds CARTO Workflows that measure spatial autocorrelation using Moran's I, determining whether a variable exhibits clustering, dispersion, or randomness, and classifying each location into HH/HL/LH/LL quadrants.

**Prerequisites**: Load `carto-create-workflow` for the development process, JSON structure, and validation commands.

**When to use Moran's I vs Getis-Ord Gi***:
- **Moran's I**: "Is there clustering?" + classify into cluster types (HH, HL, LH, LL) + identify spatial outliers (HL, LH)
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

| Resolution | Cell size | Use case |
|------------|-----------|----------|
| H3 res 7 | ~5 km edge | District/city-level patterns |
| H3 res 8 | ~2 km edge | Neighborhood-level |
| H3 res 9 | ~500m edge | Street-level (used in Berlin POI tutorial) |

**Success**: Every row has a spatial index column (e.g. `h3`).

### Step 4: Aggregate per Cell

Use `native.groupby` to produce one row per cell with a numeric value:
- **Group by**: the spatial index column (`h3`)
- **Aggregation**: `geoid,count` (or `value_col,sum` / `value_col,avg`)

**Success**: Output has exactly one row per unique cell with a numeric column (e.g. `geoid_count`).

### Step 5: Run Moran's I

Use `native.moransi` with:

| Input | Description | Default |
|-------|-------------|---------|
| `indexcol` | Column with H3/Quadbin indexes | `h3` |
| `valuecol` | Numeric column to test for autocorrelation | `geoid_count` |
| `size` | K-ring neighborhood radius (in hops) | `3` |
| `decay` | Distance decay function for spatial weights | `uniform` |

**Decay options**: `uniform`, `inverse`, `inverse_square`, `exponential`.
- `uniform`: Equal weight to all neighbors within the k-ring
- `exponential`: Weight decreases exponentially with distance (used in Berlin POI tutorial)

**K-ring size**: Larger = broader neighborhood = smoother global patterns. Smaller = more localized assessment. The choice of neighborhood size significantly affects results.

**Success**: Output contains `index`, `morans_i`, `p_value`, and `quadrant` columns for every cell. (See the Provider casing note in Gotchas — Snowflake surfaces these UPPERCASE.)

### Step 6: Filter Significant Results (recommended)

Use `native.where` to keep only statistically significant cells. Quadrant classification is only meaningful for significant cells.

Common filters:
- `p_value < 0.05` -- all significant cells (95% confidence)
- `p_value < 0.05 AND quadrant = 'HH'` -- high-value clusters only
- `p_value < 0.05 AND (quadrant = 'HL' OR quadrant = 'LH')` -- spatial outliers only

**Success**: Only cells with statistically meaningful spatial patterns remain.

### Step 7: Save

Use `native.saveastable` to persist results. The H3/Quadbin column is directly visualizable in CARTO Builder without geometry conversion.

**Success**: Validated workflow that can be uploaded via `carto workflows create`.

---

## Output Columns

| Column | Meaning |
|--------|---------|
| `index` | Spatial index cell ID (H3 or Quadbin) |
| `morans_i` | Local Moran's I value -- positive = similar neighbors, negative = dissimilar neighbors |
| `p_value` | Statistical significance -- lower = more confident |
| `quadrant` | Cluster classification: `HH`, `HL`, `LH`, or `LL` |

The engine declares these lowercase. See the Provider casing note in Gotchas for Snowflake.

### Interpreting Results

**Global Moran's I** (overall pattern):
- \> 0 = spatial clustering (similar values near each other)
- < 0 = spatial dispersion (dissimilar values near each other)
- Near 0 = spatial randomness

**Local quadrants** (per-cell classification):
| Quadrant | Meaning | Interpretation |
|----------|---------|----------------|
| HH | High value surrounded by high values | Cluster core |
| LL | Low value surrounded by low values | Low-value cluster |
| HL | High value surrounded by low values | Spatial outlier (high anomaly) |
| LH | Low value surrounded by high values | Spatial outlier (low anomaly) |

---

## Gotchas

- **Provider casing & SQL dialect.** This skill documents columns in lowercase (BigQuery / Databricks / Postgres / Redshift convention). On Snowflake, unquoted identifiers surface UPPERCASE — reference `H3`, `INDEX`, `MORANS_I`, `P_VALUE`, `QUADRANT`, `GEOID_COUNT` in expressions. See `carto-create-workflow/references/providers/<provider>.md` for casing rules and SQL dialect equivalents.
- The Moran's I component requires the Analytics Toolbox. Always run `carto workflows verify-remote --connection <conn>` to ensure the AT path is resolved. `carto workflows validate` is offline and cannot resolve AT location.
- The output column is named `index`, not `h3` or `quadbin`. If you need to join back to original data, rename it (e.g. with `native.renamecolumn`). This is the same behavior as Getis-Ord.
- The `valuecol` must be numeric. If you are counting features, the group-by step must produce a count column -- do not pass the raw index column as the value.
- Resolution too high + large area = very many cells, which can be slow or hit memory limits. Start with a moderate resolution and refine.
- Moran's I is sensitive to the definition of neighborhood. Both k-ring size and decay function choice materially affect results. Document your choices and consider testing alternatives.
- Quadrant classification is only meaningful for statistically significant cells. Always filter by `p_value` before interpreting quadrants -- non-significant cells may show any quadrant label by chance.
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
| Complete grid (no gaps) | Polyfill study area boundary first, then enrich with data (same approach as hotspot analysis) |
| Combine with Getis-Ord | Run both analyses on the same aggregated grid, then join results for a richer picture |
| Filter to outliers only | Keep `HL` and `LH` quadrants to find anomalous locations |
