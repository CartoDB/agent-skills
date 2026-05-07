---
name: carto-pattern-hotspot-analysis
description: Builds Getis-Ord Gi* hotspot analysis workflows in CARTO. Triggers when the user mentions hotspots, coldspots, spatial clusters, Getis-Ord, Gi*, cluster detection, concentration areas, "where do X cluster", spacetime hotspot, temporal clusters, time-varying patterns, hotspot trends, emerging hotspots, Mann-Kendall, or wants to find statistically significant spatial or spatiotemporal patterns in point or grid data.
license: MIT
---

# Hotspot Analysis with Getis-Ord Gi*

Builds CARTO Workflows that identify statistically significant spatial clusters (hotspots and coldspots) using the Getis-Ord Gi* statistic.

**Prerequisites**: Load `carto-create-workflow` for the development process, JSON structure, and validation commands.

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

**Preferred approach**: First polyfill the study area boundary (e.g. district polygons) with `native.h3polyfill` to create a complete, gap-free grid. Then enrich this grid with the data to analyze (e.g. count points per cell via `native.h3enrich` or a manual join + group by). This ensures every cell in the study area has a value (even if 0), which Getis-Ord needs — gaps in the grid distort the neighborhood calculations and can produce misleading results.

**Simpler alternative** (when no study area boundary is available): Convert point geometries directly to grid cells with `native.h3frompoint` or `native.quadbinfromgeopoint`. Be aware this only produces cells where data exists, leaving gaps that may affect the statistic.

**Resolution guidance** — higher resolution = smaller cells = more local patterns:

| Resolution | Cell size | Use case |
|------------|-----------|----------|
| H3 res 7 | ~5 km edge | District/city-level patterns |
| H3 res 8 | ~2 km edge | Neighborhood-level |
| H3 res 9 | ~500m edge | Street-level |

**Success**: A contiguous grid covering the study area, with every cell assigned a spatial index column (e.g. `h3`).

### Step 4: Aggregate per Cell

Use `native.groupby` to produce one row per cell with a numeric value:
- **Group by**: the spatial index column (`h3`)
- **Aggregation**: `h3,count` (or `value_col,sum` / `value_col,avg`)

If using the polyfill approach, cells with no data should have a value of 0 (use `COALESCE(count, 0)` via `native.selectexpression` after joining).

**Success**: Output has exactly one row per unique cell with a count/sum column — no gaps.

### Step 5: Run Getis-Ord Gi*

Use `native.getisord` with:

| Input | Description | Default |
|-------|-------------|---------|
| `indexcol` | Column with H3/Quadbin indexes | `h3` |
| `valuecol` | Numeric column to analyze | `h3_count` |
| `kernel` | Weighting function for neighbors | `uniform` |
| `size` | K-ring size (neighborhood radius in hops) | `3` |

**Kernel options**: `uniform`, `triangular`, `quadratic`, `quartic`, `gaussian`. Default to `uniform` (equal weight to all neighbors) unless the user has a reason to decay weight with distance.

**K-ring size**: Larger = smoother, broader patterns. Smaller = more localized clusters.

**Success**: Output contains `index`, `gi` (z-score), and `p_value` columns for every cell. (See the Provider casing note in Gotchas — Snowflake surfaces these UPPERCASE.)

### Step 6: Filter Significant Results (optional)

Use `native.where` to keep only statistically significant cells:
- `p_value < 0.05` — 95% confidence
- `p_value < 0.05 AND gi > 0` — hotspots only
- `p_value < 0.05 AND gi < 0` — coldspots only

**Success**: Only cells with statistically meaningful clustering remain.

### Step 7: Save

Use `native.saveastable` to persist results. The H3/Quadbin column is directly visualizable in CARTO Builder without geometry conversion.

**Success**: Validated workflow that can be uploaded via `carto workflows create`.

---

## Output Columns

| Column | Meaning |
|--------|---------|
| `index` | Spatial index cell ID (H3 or Quadbin) |
| `gi` | Gi* z-score — positive = hotspot, negative = coldspot |
| `p_value` | Statistical significance — lower = more confident |

The engine declares these lowercase. See the Provider casing note in Gotchas for Snowflake.

---

## Gotchas

- **Provider casing & SQL dialect.** This skill documents columns in lowercase (BigQuery / Databricks / Postgres / Redshift convention). On Snowflake, unquoted identifiers surface UPPERCASE — reference `H3`, `INDEX`, `GI`, `P_VALUE`, `H3_COUNT` in expressions. For dialect-specific SQL fragments (e.g. `DATETIME_TRUNC` below), see `carto-create-workflow/references/providers/<provider>.md` for the equivalents table.
- The Getis-Ord component requires the Analytics Toolbox. Always run `carto workflows verify-remote --connection <conn>` to ensure the AT path is resolved. `carto workflows validate` is offline and cannot resolve AT location.
- The output column is named `index`, not `h3` or `quadbin`. If you need to join back to original data, rename it (e.g. with `native.renamecolumn`).
- If you call `native.h3boundary` to materialize cell geometries for visualization, the new column is named `<h3col>_geo` (e.g. `index_geo`), **not** `geom`. Reference it accordingly in downstream nodes.
- The `valuecol` must be numeric. If you're counting features, the group-by step must produce a count column — don't pass the raw index column as the value.
- Resolution too high + large area = very many cells, which can be slow or hit memory limits. Start with a moderate resolution and refine.
- An empty result from the filter step (Step 6) usually means the k-ring size is too small or the data is too sparse for significant clustering. Try increasing `size` or lowering the resolution.
- Date columns must be DATETIME type for spacetime Getis-Ord. CAST if your data has DATE or TIMESTAMP.
- Temporal bandwidth choice dramatically affects results. `bandwidth=1` detects rapid changes; `bandwidth=3+` smooths over longer trends.
- For time-series clustering, pre-filter to only significant cells (the 60% heuristic) to avoid clustering noise.
- The spacetime classification component runs internally on the Gi* output -- do NOT filter by p_value before classification, or the trend test will have incomplete data.

---

## Spacetime Variants

**Getis-Ord Spacetime** (`native.getisordspacetime`):
- Extends basic Gi* to detect clusters in both space AND time.
- Additional inputs: `kerneltime` (uniform/gaussian), `bandwidth` (number of time steps), `timeinterval` (week/month/day).
- Data must be pre-aggregated into time bins (e.g. weekly counts per H3 cell).
- Pipeline: points -> H3 -> create time column (BigQuery: `DATETIME_TRUNC(CAST(datetime AS TIMESTAMP), WEEK)`; Snowflake / Databricks / Postgres: `DATE_TRUNC('WEEK', datetime)`) -> GROUP BY (h3, time_bin) -> Getis-Ord Spacetime -> filter `p_value < 0.05 AND gi > 0`.

**Spacetime Hotspot Classification** (`native.spacetimehotspotsclassification`):
- Chains AFTER Getis-Ord Spacetime output.
- Classifies each cell's temporal trend: new hotspot, consecutive, intensifying, diminishing, sporadic, oscillating, historical.
- Uses Modified Mann-Kendall trend test with a significance threshold (default 0.05).
- Pipeline: ... -> Getis-Ord Spacetime -> Spacetime Hotspots Classification.

**Time Series Clustering** (`native.timeseriesclustering`):
- Groups locations by similarity of their temporal Gi* pattern.
- Chain: Getis-Ord Spacetime -> filter significant cells -> Cluster Time Series.
- Method: `profile` (shape-based) or `value` (magnitude-based).
- Filtering heuristic from the template: keep cells where >=60% of time steps have `p_value < 0.05`.

---

## Reference Templates

These files are working examples (skill-local files in `hotspot-analysis/`, others in the project root):

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
| Spacetime hotspots | Use `native.getisordspacetime` — see Spacetime Variants section above |
| Classify hotspot trends | Use `native.spacetimehotspotsclassification` — chains after spacetime Gi* output |
