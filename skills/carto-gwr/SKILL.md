---
name: carto-gwr
description: Builds Geographically Weighted Regression (GWR) workflows in CARTO. Triggers when the user mentions GWR, geographically weighted regression, spatially varying relationships, local regression, local coefficients, spatial regression, "what drives X in different areas", "why do prices vary spatially", "local factors affecting Y", varying coefficients, coefficient maps, spatial non-stationarity, or wants to model how the relationship between a dependent variable and predictors changes across geography. Produces per-cell regression coefficients that reveal how predictor importance shifts from place to place.
license: MIT
---

# Geographically Weighted Regression (GWR)

Builds CARTO Workflows that model spatially varying relationships between a dependent variable and one or more independent variables using GWR. Unlike global regression (one set of coefficients for the entire study area), GWR produces **local coefficients per spatial unit**, revealing how relationships change across space. Example: "bedrooms add $50k to price in downtown but only $20k in suburbs."

**Prerequisites**: Load `carto-create-workflow` for the development process, JSON structure, and validation commands — it covers both access paths (the MCP server's workflow tools such as `create_workflow`, `validate_workflow`, and `run_workflow` when attached; the `carto workflows` CLI otherwise; routing signals in `carto-basics/references/access-paths.md`).

**Availability**: `native.gwr` exists only on BigQuery, Snowflake and Databricks SQL warehouse connections, not on PostgreSQL, Redshift, Oracle or Databricks cluster connections. On Databricks it supports H3 only, not Quadbin.

---

## Instructions

A GWR workflow follows this pipeline:

```
Source Data -> (Filter) -> Spatial Indexing (H3/Quadbin) -> Aggregation (dependent + independent vars per cell) -> GWR -> Save
```

### Step 1: Load Source Data

Use `native.gettablebyname` (`source`: the table FQN). Its output handle is `out`, not `result`. The input table must contain at least one numeric dependent variable and one or more numeric independent (predictor) variables.

**Success**: Node outputs a table with the necessary numeric columns.

### Step 2: Filter (if needed)

Use `native.where` with an `expression` such as `price IS NOT NULL AND bedrooms IS NOT NULL` to drop nulls, or to filter by category or date range. `native.wheresimplified` (`column`, `operator`, `value`) only compares one column to a value. Both emit `match` (kept rows) and `unmatch`: connect `match`.

**Success**: Output contains only rows with valid, non-null values for the dependent and all independent variables.

### Step 3: Spatial Indexing

If the data is not already indexed, convert point geometries to spatial index cells:

- `native.h3frompoint` for H3 (adds column `h3`)
- `native.quadbinfrompoint` for Quadbin (adds column `quadbin`)

Set `resolution` explicitly: `native.h3frompoint` defaults to 8 and `native.quadbinfrompoint` to 12 (~10 km cells).

If the data already contains an H3 or Quadbin column (common for pre-aggregated datasets), skip this step.

**Resolution guidance**:

| Resolution | Cell size | Use case |
|------------|-----------|----------|
| H3 res 7 | ~1.4 km edge, ~5.2 km² | City-level relationships |
| H3 res 8 | ~0.53 km edge, ~0.74 km² | Neighborhood-level |
| H3 res 9 | ~0.20 km edge, ~0.11 km² | Street-level (needs dense data) |

Quadbin cells are ~2.4 km wide at resolution 14, ~0.6 km at 16 and ~0.3 km at 17 at the equator, smaller toward the poles.

**Success**: Every row has a spatial index column (e.g. `h3`).

### Step 4: Aggregate per Cell

Use `native.groupby` to produce one row per cell with aggregated values for the dependent and all independent variables:

- **Group by** (`groupby`): `["h3"]`
- **Aggregation** (`columns`): `"price,avg,bedrooms,avg,bathrooms,avg"` (adapt to the actual columns)

Output columns are suffixed with the method: `price_avg`, `bedrooms_avg`, `bathrooms_avg`. Use these names in the GWR `label_column` and `features_columns`.

The dependent variable should be aggregated with `avg` or `sum` depending on what makes sense. Independent variables are typically averaged.

**Success**: Output has exactly one row per unique cell, with numeric columns for the target and all predictors.

### Step 5: Run GWR

Use `native.gwr`. Connect the incoming edge to `targetHandle: "input_table"` (not `source`); the output handle is `result`.

Always set every input below on the node. The component does not fill defaults for `kring_distance`, `kernel_function` or `fit_intercept`: an omitted one compiles to `undefined` in the SQL and the run fails.

| Input | Value |
|-------|-------|
| `index_column` | The H3/Quadbin column, e.g. `h3` (required) |
| `label_column` | Numeric target, e.g. `price_avg` (required) |
| `features_columns` | Array of predictor columns, e.g. `["bedrooms_avg", "bathrooms_avg"]` (required) |
| `kernel_function` | `gaussian` (recommended; the component default is `uniform`) |
| `kring_distance` | `3` |
| `fit_intercept` | `true` |

**Kernel options**: `gaussian` (recommended -- smooth distance decay), `uniform`, `triangular`, `quadratic`, `quartic`.

**K-ring size**: Controls the neighborhood radius.
- Too small (1-2): noisy, unstable coefficients.
- Too large (5+): over-smoothed, approaches global regression.
- Start with `3` as a balanced default.

**Success**: Output has one row per cell: the index column (same name as `index_column`), one `<feature>_coef_estimate` column per feature, and `intercept` when `fit_intercept` is true. (See the Provider casing note in Gotchas — Snowflake surfaces these UPPERCASE.)

### Step 6: Save

Use `native.saveastable` to persist results. The spatial index column is directly visualizable in CARTO Builder -- style the map by coefficient columns to create coefficient maps showing spatial variation.

**Success**: Validated workflow that can be uploaded via `create_workflow` (MCP) or `carto workflows create` (CLI).

---

## Output Columns

| Column | Meaning |
|--------|---------|
| `<index_column>` | Spatial index cell ID, same name as the input index column (e.g. `h3`) |
| `intercept` | Local intercept term (only when `fit_intercept` is true) |
| `<feature>_coef_estimate` | Local coefficient for each feature, e.g. `bedrooms_avg_coef_estimate` |

GWR outputs no per-cell R² or residual column.

---

## Gotchas

- **Provider casing & SQL dialect.** This skill documents columns in lowercase (BigQuery / Databricks). On Snowflake, unquoted identifiers surface UPPERCASE — reference `H3`, `PRICE_AVG`, `BEDROOMS_AVG_COEF_ESTIMATE`, `INTERCEPT`, etc. in expressions. See `carto-create-workflow/references/providers/<provider>.md` for casing rules and SQL dialect equivalents.
- The GWR component requires the Analytics Toolbox. Offline validation (`validate_workflow` over MCP, or `carto workflows validate`) can't resolve the AT location — confirm it with the CLI-only `carto workflows verify-remote --connection <conn>` before running.
- The dependent variable must be continuous and numeric. Categorical targets need a different approach (e.g. classification).
- Cells with null values in ANY variable (dependent or independent) will be excluded from the model. Pre-filter or impute nulls before running GWR.
- Multicollinearity between independent variables degrades results. If two predictors are highly correlated (e.g. `bedrooms` and `total_rooms`), drop one or combine them. Check correlation before including multiple similar variables.
- The `features_columns` input is an array of column names (e.g. `["bedrooms", "bathrooms"]`), not a comma-separated string.
- The output keeps the input index column's name (e.g. `h3`) and has only that column, `intercept` and the `_coef_estimate` columns. To compare with the original values, join it back to the GWR input on that column with `native.join`; the secondary table's columns get a `_joined` suffix.
- Sparse data at high resolutions leads to unreliable coefficients. Ensure enough cells have data for all variables before choosing a high resolution.

---

## Reference Templates

| Resource | Description |
|----------|-------------|
| [BQ Tutorial: Airbnb Listings Prices (GWR)](https://academy.carto.com/advanced-spatial-analytics/spatial-analytics-for-bigquery/step-by-step-tutorials/applying-gwr-to-understand-airbnb-listings-prices) | BigQuery step-by-step: Berlin Airbnb price vs bedrooms/bathrooms, H3 res 7, kring 3, Gaussian kernel |
| [SF Tutorial: Airbnb Listings Prices (GWR)](https://academy.carto.com/advanced-spatial-analytics/spatial-analytics-for-snowflake/step-by-step-tutorials/applying-gwr-to-understand-airbnb-listings-prices) | Snowflake step-by-step: same analysis adapted for Snowflake |

**Workflow template** (available in CARTO Workspace): "Applying Geographical Weighted Regression (GWR) to model the local spatial relationships in your data"

**Example use case**: Analyzing Airbnb ratings in Los Angeles -- models `overall_rating` vs `value_review`, `cleanliness`, `location`, enriched with Data Observatory sociodemographics. Uses H3 res 7, kring 3, Gaussian kernel.

---

## Common Variations

| Variant | How |
|---------|-----|
| Pre-aggregated data (already one row per cell) | Skip Steps 3-4, go directly to GWR |
| Enrich with Data Observatory | Add `native.h3enrich` (or `native.quadbinenrich`) before GWR: `target` = your grid, `source` = the Data Observatory table, `target_col` / `source_col` = the index columns, `variables` = e.g. `"population,sum"`. New columns are named `<column>_<method>` (e.g. `population_sum`) |
| Coefficient comparison | Save results, then use Builder to style map by each coefficient column separately |
| Combine with hotspot analysis | Join the GWR output (main) to the GWR input (secondary) on the index column, compute the residual with `native.selectexpression` (e.g. `price_avg_joined - (intercept + bedrooms_avg_coef_estimate * bedrooms_avg_joined + bathrooms_avg_coef_estimate * bathrooms_avg_joined)`), then run `native.getisord` on it to find clusters of under/over-prediction |
