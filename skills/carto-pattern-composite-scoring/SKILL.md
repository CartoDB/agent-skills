---
name: carto-pattern-composite-scoring
description: Guides the user through building composite score workflows when they ask about composite scores, indexes, multi-variable scores, ranking areas, site scoring, market potential, resilience indexes, risk indexes, weighted scores, PCA, or supervised/unsupervised scoring.
license: MIT
---

Use this skill whenever the user wants to create a composite score, index, or multi-variable ranking in a CARTO Workflow.

**Prerequisites**: Load `carto-create-workflow` for the development process.

## Instructions

### Step 1: Determine the scoring approach

Ask the user the following decision tree:

1. **"Do you have a target/outcome variable?"** (e.g. revenue, sales, crime rate)
   - Yes → **Supervised** method using `native.spatialcompositesupervised`
2. **"No target, but do you have expert knowledge of variable importance?"**
   - Yes → **Unsupervised** method with `CUSTOM_WEIGHTS` using `native.spatialcompositeunsupervised`
3. **"No target, no weights?"**
   - → **Unsupervised** method with `ENTROPY` or `FIRST_PC` using `native.spatialcompositeunsupervised`

**Success**: You have identified which component and scoring method to use before designing the pipeline.

### Step 2: Build the pipeline

#### Supervised pipeline (`native.spatialcompositesupervised`)

1. Load the spatial features dataset (pre-indexed at H3 or Quadbin)
2. Load the target/outcome dataset
3. Join both datasets on the spatial index column
4. Select only the relevant feature columns (drop spatial index column and geometry from feature selection — pass only actual feature variables)
5. Run `native.spatialcompositesupervised` with parameters:
   - `model_type`: `LINEAR_REG`
   - `bucketize`: `EQUAL_INTERVALS_ZERO_CENTERED`
   - `n_buckets`: `5`
   - `outlier_removal`: `true`
   - `r_squared_threshold`: `0.4`
6. Output: composite score based on regression residuals (identifies areas that over/under-perform relative to the model)

**Success**: The workflow joins features with the target variable, selects only numeric feature columns, and produces a residual-based score per spatial cell.

#### Unsupervised pipeline (`native.spatialcompositeunsupervised`)

1. Load the spatial features dataset
2. Select only the relevant feature columns
3. Encode any categorical/ordinal variables to numeric using `native.casewhen` (e.g. "Low_density_urban" → 4, "High_density_urban" → 2)
4. Optionally reverse variables where higher = worse by multiplying by -1 in the SELECT query passed to the component
5. Run `native.spatialcompositeunsupervised` with parameters:
   - `scoring_method`: `CUSTOM_WEIGHTS` / `ENTROPY` / `FIRST_PC`
   - `weights`: required if `CUSTOM_WEIGHTS`. **Wire format is a JSON-encoded string of triples `[[<column>, <weight>, <reverse>], ...]`** — `column` is the feature column name, `weight` is a numeric weight (normalized internally to sum to 1), `reverse` is a boolean (`true` flips the variable so higher = worse becomes higher = better without needing a CASE WHEN). Example: `'[["population_density", 0.5, false], ["accident_rate", 0.5, true]]'`. **Not** an object map.
   - `scaling`: `RANKING`
   - `aggregation`: `LINEAR`
   - `output`: `RETURN_RANGE` with range `[0, 1]`
6. Output: composite index score per location

**Success**: All input variables are numeric, variable directions are aligned (higher = better for the score), and the output is a normalized score per spatial cell.

## Gotchas

- **Provider casing & SQL dialect.** This skill uses lowercase column names (BigQuery / Databricks / Postgres / Redshift convention). On Snowflake, unquoted identifiers surface UPPERCASE — reference `POPULATION_DENSITY`, `ACCIDENT_RATE`, etc. in weights, expressions, and downstream SQL. See `carto-create-workflow/references/providers/<provider>.md` for casing rules and SQL dialect equivalents.
- **All input variables must be numeric.** Ordinal strings (e.g. "low"/"medium"/"high") must be manually encoded via CASE WHEN before passing to the component.
- **Variable direction matters.** If "higher is worse" for a variable, multiply by -1 before scoring. Forgetting this inverts the score meaning.
- **Supervised R-squared threshold** (default 0.4) is permissive. If model fit is poor, the residual-based score is mostly noise. Inspect model diagnostics.
- **Custom weights are normalized internally** to sum to 1. The absolute values do not matter, only the ratios.
- **Supervised scores are residuals**, not raw values. The score identifies areas that DEVIATE from the model, not areas with the highest raw values.
- **Drop the spatial index column and geometry** from the feature selection — only pass actual feature variables to the scoring component.

## Reference Templates

Both examples use Milan spatial features data at Quadbin resolution 18.

| Template | Component | File |
|---|---|---|
| Supervised — Identifying resilient neighbourhoods | `native.spatialcompositesupervised` | [composite-score-supervised.json](composite-score-supervised.json) |
| Unsupervised — Market potential scoring | `native.spatialcompositeunsupervised` | [composite-score-unsupervised.json](composite-score-unsupervised.json) |

## Common Variations

| Variation | Approach |
|---|---|
| Risk index (flood, crime, etc.) | Unsupervised with `CUSTOM_WEIGHTS`; reverse variables where higher = safer |
| Market potential / site scoring | Unsupervised with `CUSTOM_WEIGHTS` or `ENTROPY`; weight demand-side variables higher |
| Resilience index | Supervised with outcome variable (e.g. revenue change); residuals reveal over/under-performers |
| Data-driven index (no domain expertise) | Unsupervised with `FIRST_PC` or `ENTROPY` to let variance drive the weights |
| Human development / composite indicator | Unsupervised with `CUSTOM_WEIGHTS` and `RANKING` scaling for ordinal-safe aggregation |
