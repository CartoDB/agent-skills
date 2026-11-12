---
name: carto-composite-scoring
description: Guides the user through building composite score workflows when they ask about composite scores, indexes, multi-variable scores, ranking areas, site scoring, market potential, resilience indexes, risk indexes, weighted scores, PCA, or supervised/unsupervised scoring.
license: MIT
---

Use this skill whenever the user wants to create a composite score, index, or multi-variable ranking in a CARTO Workflow.

**Prerequisites**: Load `carto-create-workflow` for the development process. It covers both access paths — the MCP server's workflow tools (`create_workflow`, `validate_workflow`, `run_workflow`) when attached, the `carto workflows` CLI otherwise. Routing signals: `carto-basics/references/access-paths.md`.

## Instructions

### Step 1: Determine the scoring approach

Ask the user the following decision tree:

1. **"Do you have a target/outcome variable?"** (e.g. revenue, sales, crime rate)
   - Yes → **Supervised** method using `native.spatialcompositesupervised`
2. **"No target, but do you have expert knowledge of variable importance?"** (i.e. custom weights)
   - **2a. Transparency matters more than node count** → `native.normalize` per variable + `native.selectexpression` with the weighted-sum literally in SQL (`a_norm * 0.5 + b_norm * 0.2 + c_norm * 0.3`). Inputs and weights are inspectable inline in Workflows; each normalized column is materialized; no Analytics Toolbox dependency. Use when stakeholders need to see/audit the formula, or when you're not running on AT.
   - **2b. Want the AT pipeline (scaling, aggregation, bucketing) handled for you** → `native.spatialcompositeunsupervised` with `scoringmethod: "CUSTOM_WEIGHTS"`. One node, but the formula is hidden inside the component.
3. **"No target, no weights?"**
   - → **Unsupervised** method with `ENTROPY` or `FIRST_PC` using `native.spatialcompositeunsupervised`

Availability: `native.spatialcompositesupervised` runs on BigQuery and Snowflake only; `native.spatialcompositeunsupervised` on BigQuery, Snowflake and Databricks. Neither exists on PostgreSQL, Redshift or Oracle: use path 2a there. If the user wants a supervised score on a connection without it, say it is not available there and offer an unsupervised score or path 2a.

**Success**: You have identified which component and scoring method to use before designing the pipeline.

### Step 2: Build the pipeline

#### Supervised pipeline (`native.spatialcompositesupervised`)

1. Load the spatial features dataset (pre-indexed at H3 or Quadbin)
2. Load the target/outcome dataset
3. Join both on the spatial index column with `native.join` (`maintable` = features, `secondarytable` = target, `maincolumn` / `secondarycolumn` = the index, `jointype: "Inner"`). Every secondary-table column gets a `_joined` suffix, so the target becomes e.g. `revenue_change_joined`: use that name, or rename it with `native.renamecolumn`.
4. Choose `inputpredictors`: the feature columns **plus the target column**, never the index column. The component reads only `indexcol` and `inputpredictors`, so no separate select node is needed.
5. Run `native.spatialcompositesupervised` (table input `source`) with `indexcol` (the index column), `inputpredictors` (array, includes the target), `modelvariablecolumn` (the target), and:
   - `modelregressor`: keep the default, `LINEAR_REG` on BigQuery and `snowflake.ml.modeling.linear_model.LinearRegression` on Snowflake (`LINEAR_REG` fails on Snowflake)
   - `bucketizemethod`: `EQUAL_INTERVALS_ZERO_CENTERED`
   - `automaticnbuckets`: `false`, `nbuckets`: `5`
   - `removeoutliers`: `true`
   - `r2thr`: `0.4` (default `0.5`)
6. Output (`result`): `spatial_score`, the residual (observed minus predicted, bucketized when `bucketizemethod` is set), plus the index column. It identifies areas that over/under-perform relative to the model.

**Success**: The workflow joins features with the target variable, passes the numeric features plus the target as `inputpredictors`, and produces a residual-based score per spatial cell.

#### Unsupervised pipeline (`native.spatialcompositeunsupervised`)

1. Load the spatial features dataset
2. Encode any categorical/ordinal variables to numeric using `native.casewhen` (e.g. "Low_density_urban" → 4, "High_density_urban" → 2). It adds a new column and keeps the original.
3. Reverse variables where higher = worse: with `CUSTOM_WEIGHTS` set `reverse` to `true` in `weights`; with `ENTROPY` / `FIRST_PC` add `native.selectexpression` (`column`: `<col>_rev`, `expression`: `-1 * <col>`).
4. Keep only the index column and the numeric feature columns (`native.select`, table input `table`, or `native.dropcolumn`), dropping geometry, the original text columns and any column replaced in step 3. With `ENTROPY` / `FIRST_PC` the component treats every column except `indexcol` as a variable; with `CUSTOM_WEIGHTS` it reads only the `weights` columns, so this step is optional there.
5. Run `native.spatialcompositeunsupervised` with parameters:
   - `indexcol`: the unique id column (required; keep it in the input table)
   - `scoringmethod`: `CUSTOM_WEIGHTS` / `ENTROPY` / `FIRST_PC` (default `ENTROPY`)
   - `weights`: required if `CUSTOM_WEIGHTS`. **Wire format is a JSON-encoded string of triples `[[<column>, <weight>, <reverse>], ...]`** — `column` is the feature column name, `weight` is a numeric weight (normalized internally to sum to 1), `reverse` is a boolean (`true` flips the variable so higher = worse becomes higher = better without needing a CASE WHEN). Example: `'[["population_density", 0.5, false], ["accident_rate", 0.5, true]]'`. **Not** an object map.
   - `correlationvar`: required with `FIRST_PC` (a column of the input table, not the index); `correlationthr`: default `0.2`
   - `scaling`: `RANKING` and `aggregation`: `LINEAR`, used only with `CUSTOM_WEIGHTS` (ignored for `ENTROPY` / `FIRST_PC`). `STANDARD_SCALER` cannot be combined with `GEOMETRIC`.
   - `outputformatting`: `RETURN_RANGE`, with `returnrange`: `"[0, 1]"` (a JSON-encoded string, not an array)
6. Output: `result` has `spatial_score` plus the index column; connect downstream nodes to `result`. The second output, `lookup`, holds bucket bounds (`lower_bound`, `upper_bound`, `spatial_score`) and is only useful with a bucketing `outputformatting`.

**Success**: All input variables are numeric, variable directions are aligned (higher = better for the score), and the output is a normalized score per spatial cell.

## Gotchas

- **Provider casing & SQL dialect.** This skill uses lowercase column names (BigQuery / Databricks). On Snowflake, unquoted identifiers surface UPPERCASE — reference `POPULATION_DENSITY`, `ACCIDENT_RATE`, `SPATIAL_SCORE`, etc. in weights, expressions, and downstream SQL. See `carto-create-workflow/references/providers/<provider>.md` for casing rules and SQL dialect equivalents.
- **All input variables must be numeric, with aligned direction.** Encode ordinal strings ("low"/"medium"/"high") via CASE WHEN first, and where "higher is worse" multiply by -1 (or set the `reverse` flag) before scoring — forgetting this inverts the score meaning.
- **Supervised R-squared threshold** (`r2thr`, default 0.5; 0.4 is more permissive). If the model fits poorly, the residual-based score is mostly noise; the component outputs only `spatial_score`, so check the fit separately.
- **Custom weights are normalized internally** to sum to 1. The absolute values do not matter, only the ratios.
- **Supervised scores are residuals**, not raw values. The score identifies areas that DEVIATE from the model, not areas with the highest raw values.
- **Index column**: keep it in the input table and pass it as `indexcol`; never list it in `inputpredictors` or `weights`. Drop geometry and other non-feature columns before an `ENTROPY` / `FIRST_PC` node. For supervised, `inputpredictors` must include the target.
- **`weights` is a JSON-encoded string although its type is `ColumnNumber`.** The component schema (via `read_workflow_components` MCP or `carto workflows components get native.spatialcompositeunsupervised --json`) reports `type: "ColumnNumber"`; send `[[<column>, <weight>, <reverse>], ...]` as a string (see Step 2 and the unsupervised template). A native array fails validation.
- **`indexcol.allowedColumns` is a UI hint, not a validator.** The schema lists `["geoid", "h3", "quadbin"]` for `native.spatialcompositeunsupervised.indexcol`, but it's a Workflows dropdown hint — any unique identifier column works at runtime (e.g. `store_id`, `cell_id`).

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
