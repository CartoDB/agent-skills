---
name: carto-pattern-gwr
description: Builds Geographically Weighted Regression (GWR) workflows in CARTO. Triggers when the user mentions GWR, geographically weighted regression, spatially varying relationships, local regression, local coefficients, spatial regression, "what drives X in different areas", "why do prices vary spatially", "local factors affecting Y", varying coefficients, coefficient maps, spatial non-stationarity, or wants to model how the relationship between a dependent variable and predictors changes across geography. Produces per-cell regression coefficients that reveal how predictor importance shifts from place to place.
license: MIT
---

# Geographically Weighted Regression (GWR)

Builds CARTO Workflows that model spatially varying relationships between a dependent variable and one or more independent variables using GWR. Unlike global regression (one set of coefficients for the entire study area), GWR produces **local coefficients per spatial unit**, revealing how relationships change across space. Example: "bedrooms add $50k to price in downtown but only $20k in suburbs."

**Prerequisites**: Load `carto-create-workflow` for the development process, JSON structure, and validation commands.

---

## Instructions

A GWR workflow follows this pipeline:

```
Source Data -> (Filter) -> Spatial Indexing (H3/Quadbin) -> Aggregation (dependent + independent vars per cell) -> GWR -> Save
```

### Step 1: Load Source Data

Use `native.gettablebyname`. The input table must contain at least one numeric dependent variable and one or more numeric independent (predictor) variables.

**Success**: Node outputs a table with the necessary numeric columns.

### Step 2: Filter (if needed)

Use `native.wheresimplified` or `native.where` to narrow the dataset (e.g. remove nulls from key columns, filter by category or date range).

**Success**: Output contains only rows with valid, non-null values for the dependent and all independent variables.

### Step 3: Spatial Indexing

If the data is not already indexed, convert point geometries to spatial index cells:

- `native.h3frompoint` for H3
- `native.quadbinfromgeopoint` for Quadbin

If the data already contains an H3 or Quadbin column (common for pre-aggregated datasets), skip this step.

**Resolution guidance**:

| Resolution | Cell size | Use case |
|------------|-----------|----------|
| H3 res 7 | ~5 km edge | City-level relationships |
| H3 res 8 | ~2 km edge | Neighborhood-level |
| H3 res 9 | ~500m edge | Street-level (needs dense data) |

**Success**: Every row has a spatial index column (e.g. `h3`).

### Step 4: Aggregate per Cell

Use `native.groupby` to produce one row per cell with aggregated values for the dependent and all independent variables:

- **Group by**: the spatial index column (`h3`)
- **Aggregation**: `price,avg,bedrooms,avg,bathrooms,avg` (adapt to the actual columns)

The dependent variable should be aggregated with `avg` or `sum` depending on what makes sense. Independent variables are typically averaged.

**Success**: Output has exactly one row per unique cell, with numeric columns for the target and all predictors.

### Step 5: Run GWR

Use `native.gwr` with:

| Input | Description | Default |
|-------|-------------|---------|
| `index_column` | Column with H3/Quadbin indexes | `h3` |
| `label_column` | Target / dependent variable to model (must be numeric) | - |
| `features_columns` | Predictor / independent variable columns (array of strings) | - |
| `kernel_function` | Weighting function for neighbors | `gaussian` |
| `kring_distance` | K-ring size (neighborhood radius in hops) | `3` |
| `fit_intercept` | Whether to fit an intercept term | `true` |

**Kernel options**: `gaussian` (recommended -- smooth distance decay), `uniform`, `triangular`, `quadratic`, `quartic`.

**K-ring size**: Controls the neighborhood radius.
- Too small (1-2): noisy, unstable coefficients.
- Too large (5+): over-smoothed, approaches global regression.
- Start with `3` as a balanced default.

**Success**: Output contains per-cell columns: `index`, `intercept`, one coefficient column per independent variable, `r_squared`, and `residual`. (See the Provider casing note in Gotchas — Snowflake surfaces these UPPERCASE.)

### Step 6: Save

Use `native.saveastable` to persist results. The spatial index column is directly visualizable in CARTO Builder -- style the map by coefficient columns to create coefficient maps showing spatial variation.

**Success**: Validated workflow that can be uploaded via `carto workflows create`.

---

## Output Columns

| Column | Meaning |
|--------|---------|
| `index` | Spatial index cell ID (H3 or Quadbin) |
| `intercept` | Local intercept term |
| `<variable_name>` | Local coefficient for each independent variable |
| `r_squared` | Local model fit (0-1) -- higher = better local explanation |
| `residual` | Difference between observed and predicted value |

The engine declares these lowercase. See the Provider casing note in Gotchas for Snowflake.

---

## Gotchas

- **Provider casing & SQL dialect.** This skill documents columns in lowercase (BigQuery / Databricks / Postgres / Redshift convention). On Snowflake, unquoted identifiers surface UPPERCASE — reference `H3`, `INDEX`, `PRICE`, `R_SQUARED`, `INTERCEPT`, etc. in expressions. See `carto-create-workflow/references/providers/<provider>.md` for casing rules and SQL dialect equivalents.
- The GWR component requires the Analytics Toolbox. Always run `carto workflows verify-remote --connection <conn>` to ensure the AT path is resolved. `carto workflows validate` is offline and cannot resolve AT location.
- The dependent variable must be continuous and numeric. Categorical targets need a different approach (e.g. classification).
- Cells with null values in ANY variable (dependent or independent) will be excluded from the model. Pre-filter or impute nulls before running GWR.
- Multicollinearity between independent variables degrades results. If two predictors are highly correlated (e.g. `bedrooms` and `total_rooms`), drop one or combine them. Check correlation before including multiple similar variables.
- K-ring size matters significantly: too small = noisy, unstable coefficients; too large = over-smoothed results that approach a global regression. Start with `3` and adjust.
- `r_squared` per cell indicates local model fit. Very low values across many cells suggest important predictors are missing from the model.
- The `features_columns` input is an array of column names (e.g. `["bedrooms", "bathrooms"]`), not a comma-separated string.
- The output column is named `index`, not the original spatial index column name. If joining back to original data, rename it with `native.renamecolumn`.
- Sparse data at high resolutions leads to unreliable coefficients. Ensure enough cells have data for all variables before choosing a high resolution.

---

## Reference Templates

| Resource | Description |
|----------|-------------|
| [BQ Tutorial: Airbnb Listings Prices (GWR)](https://academy.carto.com/advanced-spatial-analytics/spatial-analytics-for-bigquery/step-by-step-tutorials/applying-gwr-to-understand-airbnb-listings-prices) | BigQuery step-by-step: Berlin Airbnb price vs bedrooms/bathrooms, H3 res 7, kring 3, Gaussian kernel |
| [SF Tutorial: Airbnb Listings Prices (GWR)](https://academy.carto.com/advanced-spatial-analytics/spatial-analytics-for-snowflake/step-by-step-tutorials/applying-gwr-to-understand-airbnb-listings-prices) | Snowflake step-by-step: same analysis adapted for Snowflake |

**Workflow template** (available in CARTO Workspace): "Applying Geographical Weighted Regression (GWR) to model the local spatial relationships in your data"

**Builder use case**: Analyzing Airbnb ratings in Los Angeles -- models `overall_rating` vs `value_review`, `cleanliness`, `location`, enriched with Data Observatory sociodemographics. Uses H3 res 7, kring 3, Gaussian kernel.

---

## Common Variations

| Variant | How |
|---------|-----|
| Pre-aggregated data (already one row per cell) | Skip Steps 3-4, go directly to GWR |
| Enrich with Data Observatory | Add `native.enrichgrid` before GWR to include sociodemographic predictors |
| Coefficient comparison | Save results, then use Builder to style map by each coefficient column separately |
| Filter by model fit | Add `native.where` after GWR to keep only cells with `r_squared > 0.5` (or another threshold) |
| Combine with hotspot analysis | Run GWR first, then use residuals as input to Getis-Ord to find clusters of under/over-prediction |
