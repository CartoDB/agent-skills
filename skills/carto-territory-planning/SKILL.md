---
name: carto-territory-planning
description: Builds territory planning workflows in CARTO combining territory balancing and location allocation. Triggers when the user mentions territory balancing, territory planning, sales territories, service zones, workload distribution, balanced territories, location allocation, facility placement, optimal locations, maximize coverage, minimize cost, minimize travel distance, depot placement, hub placement, warehouse siting, response time optimization, demand coverage, or wants to divide an area into balanced regions or find optimal facility locations.
license: MIT
---

# Territory Planning (Territory Balancing + Location Allocation)

Builds CARTO Workflows that solve two related spatial optimization problems: dividing areas into balanced territories (e.g. sales regions, service zones) and finding optimal facility locations that maximize coverage or minimize cost.

**Prerequisites**: Load `carto-create-workflow` for the development process, JSON structure, and validation. It covers both access paths — the MCP server's workflow tools (`create_workflow`, `validate_workflow`, `run_workflow`) when attached, the `carto workflows` CLI otherwise. Routing signals: `carto-basics/references/access-paths.md`. Both components require the **Territory Planning Extension Package** installed on the connection. Territory Balancing exists only on BigQuery; Location Allocation on BigQuery (prefix `territoryplanning.`) and Snowflake (prefix `territoryplanning-sf.`). Check with `carto workflows components list --connection <conn> --search territory --json` (MCP: `read_workflow_components method=list`) and read inputs and outputs with `components get`; if nothing comes back, the package is not installed on that connection. On other providers the closest native option for territories is `native.clusterkmeans` (proximity clusters in a `cluster` column, without demand balancing; BigQuery, Snowflake, Redshift, PostgreSQL).

---

## Territory Balancing

Divides a study area into spatially contiguous territories that are balanced by a demand variable (e.g. workload, population, revenue). BigQuery only.

### Pipeline

```
Source Data (points) -> Spatial Indexing -> Aggregate per Cell -> Territory Balancing -> Save
```

### Step 1: Load Source Data

Use `native.gettablebyname`. Input is typically point data with one or more numeric metrics to balance.

**Success**: Node outputs a table with a geometry column and numeric metric columns.

### Step 2: Convert to Spatial Index

Use `native.h3frompoint` (or `native.quadbinfrompoint`) to assign each point to a grid cell.

**Resolution guidance**: Higher resolution = smaller cells = finer-grained territories, but more computation. H3 resolution 8-9 is typical for city-level analysis.

**Success**: Output has a spatial index column (e.g. `h3`).

### Step 3: Aggregate per Cell

Use `native.groupby` to produce one row per cell with the metrics to balance:
- **Group by**: the spatial index column (`h3`)
- **Aggregation**: e.g. `geom,count,revenue,sum,population,avg`

Use a count or sum as the demand column (it must add up across cells); averages and ratios only work as similarity features.

**Success**: One row per cell with numeric columns for demand and optional similarity features.

### Step 4: Run Territory Balancing

Use `territoryplanning.territorybalancing` (BigQuery only) with:

| Input | Description | Example |
|-------|-------------|---------|
| `input_table` | Table input; the edge's target handle is `input_table` | |
| `index_column` | H3 or Quadbin column | `h3` |
| `demand_column` | Numeric column to balance across territories | `geom_count` |
| `similarity_feats` | Optional numeric columns for within-territory similarity | `["sentiment_avg", "popularity_avg"]` |
| `npartitions` | Number of territories to create | `9` |
| `keep_input_columns` | Include all input columns in output | `true` |

**Success**: The output (source handle `output_table`, not `result`) has the index column, a `cluster` column with the territory ID, and the input columns when `keep_input_columns` is true. Each cell is assigned to exactly one territory.

### Step 5: Save

Use `native.saveastable` to persist results. The spatial index column is directly visualizable in CARTO Builder, colored by `cluster`.

**Success**: Validated workflow uploadable via `create_workflow` (MCP) or `carto workflows create` (CLI).

---

## Location Allocation

Finds the subset of candidate facilities that minimizes total cost, minimizes the maximum cost, or maximizes demand coverage, and assigns each demand point to an open facility. BigQuery and Snowflake only; names below use the BigQuery prefix (`territoryplanning-sf.` on Snowflake).

### Pipeline

```
Demand -> Demand Points Preparation ------------------┐
Candidates -> Facilities Preparation -----------------┤
Candidate x demand costs -> Cost Matrix Preparation --┼-> Location-Allocation -> Save
(optional) Constraints Definition --------------------┘
```

Every preparation node emits on source handle `output_table`.

### Step 1: Prepare Demand Points

Load demand with `native.gettablebyname` (e.g. population per H3 cell, customer locations), then add `territoryplanning.demandpoints` (target handle `dpoints_table`): `dpoints_id` = unique id, `dpoints_geom` = point geometry, `demand_bool: true` and `demand_col` = the demand value. For an H3 grid, first add a point per cell with `native.h3center` (`h3col: h3`, new column `h3_geom`) and use `h3` as the id.

**Success**: Output `output_table` with `dpoint_id`, `geom`, `demand`.

### Step 2: Prepare Candidate Facilities

Load candidates with a second `native.gettablebyname`. If candidates need filtering, use `native.wheresimplified` or `native.limit` -- fewer candidates = faster computation. Then add `territoryplanning.facilities` (target handle `candidates_table`): `candidates_id` = unique id, `candidates_geom` = point geometry. Existing sites that must stay open go in `required_table` with `required_bool: true`; competitors in `competitors_table` with `competitors_bool: true`. Ids must be unique across candidate, required and competitor facilities.

**Success**: Output `output_table` with `facility_id`, `geom`, `facility_type`.

### Step 3: Build the Cost Matrix

Location-Allocation needs one row per candidate and demand point with a cost:
- **Travel time or road distance**: `native.createroutingmatrix` (origins = candidates, destinations = demand points). It returns `route_duration` in seconds and `route_distance` in meters, prefixes the input columns with `origin_` / `destination_`, and consumes LDS quota for every pair.
- **Straight-line distance**: `native.crossjoin` (candidates as `maintable`, demand as `secondarytable`; secondary columns get the suffix `_joined`, or every column gets an `l_` / `r_` prefix on Databricks cluster connections), then `native.selectexpression` with `ST_DISTANCE(<candidate geom>, <demand geom>_joined)` (meters for geography columns).

Then add `territoryplanning.costs` (target handle `costs_table`): `facilities_column`, `dpoints_column`, `cost_column`. The ids must be the same ones given to the two preparation nodes.

**Success**: Output `output_table` with `facility_id`, `dpoint_id`, `cost`.

### Step 4: Run Location-Allocation

Use `territoryplanning.locationallocation` with:

| Input | Description | Example |
|-------|-------------|---------|
| `facilities_table` | Output of Facilities Preparation (edge from its `output_table`) | |
| `dpoints_table` | Output of Demand Points Preparation | |
| `costs_table` | Output of Cost Matrix Preparation | |
| `optimization_strategy` | `Minimize total cost`, `Minimize maximum cost` or `Maximize coverage` | `Maximize coverage` |
| `demand_bool` | `true` to use the demand set in Demand Points Preparation | `true` |
| `limit_facilities_bool` + `max_facilities` | Maximum number of facilities to open (an upper bound) | `true`, `5` |

Read the other options (required and competitor facilities, budget, groups, `time_limit`) with `components get`.

**Success**: Two outputs. `output_table` (source handle `output_table`) has one row per assignment: `facility_id`, `dpoint_id`, `demand`, `geom`. `metrics_table` has `objective_value`, `gap`, `solving_time`, `termination_reason`.

#### Maximize Coverage

Set `optimization_strategy: "Maximize coverage"` and `coverage_radius`: the maximum cost a facility can cover, in the cost matrix's units (e.g. `900` for 15 min when the cost is `route_duration` in seconds). The default is `10`.

#### Minimize Total Cost

Use the same node with `optimization_strategy: "Minimize total cost"` (or `"Minimize maximum cost"` to minimize the worst assignment). The cost is whatever the cost matrix holds. Minimum usage, capacities and required/forbidden assignments only apply to these two strategies.

### Step 5: Save

Use `native.saveastable` on `output_table` (and on `metrics_table` if the user wants the solver metrics).

**Success**: Validated workflow uploadable via `create_workflow` (MCP) or `carto workflows create` (CLI).

---

## Gotchas

- **Provider casing & SQL dialect.** This skill uses lowercase column names (`h3`, `geom_count`, `facility_id`, `dpoint_id`, `route_duration`, etc.) — BigQuery convention. On Snowflake (Location Allocation only), unquoted identifiers surface UPPERCASE — reference them as `FACILITY_ID`, `DPOINT_ID`, `ROUTE_DURATION`. See `carto-create-workflow/references/providers/<provider>.md` for casing rules and SQL dialect equivalents.
- **Extension package required**: Both territory balancing and location allocation require the Territory Planning Extension Package installed on the specific connection being used. This is NOT available by default -- the user must have it installed. Validation will fail if the package is missing.
- **Location allocation is computationally expensive** with many candidates. Pre-filter candidates (by geography, capacity, or other criteria) to keep the candidate set small. The solver stops at `time_limit` (seconds, default 3600, max 7200) or once within `relative_gap` (%), and reports `gap` and `termination_reason` in `metrics_table`; check them before calling a result optimal.
- **Coverage radius is in cost units**: the same unit as the cost matrix (seconds for `route_duration`, meters for `route_distance` or a straight-line distance). The same applies to the competitor cost threshold.
- **Territory balancing optimizes a trade-off** between spatial contiguity and balance. Perfect balance is not guaranteed -- territories will be approximately equal in the demand variable, not exactly equal.
- **Grid resolution sensitivity**: Results change significantly with the input grid resolution. Finer grids give more precise boundaries but increase computation. Start with H3 resolution 8 for city-scale and adjust.
- **Component names** come from the extension, not `native.`: `territoryplanning.territorybalancing` (BigQuery only), and `territoryplanning.facilities`, `.demandpoints`, `.costs`, `.constraints`, `.locationallocation`; on Snowflake the prefix is `territoryplanning-sf.`. Extension outputs are named `output_table` (and `metrics_table`), not `result`.
- **Demand data must cover the study area**. Gaps in the demand grid mean those areas are invisible to the optimizer. Use polyfill + COALESCE(value, 0) if you need full coverage.

---

## Reference Templates

### Academy Tutorials

- [Territory Balancing tutorial](https://academy.carto.com/creating-workflows/step-by-step-tutorials/optimizing-workload-distribution-through-territory-balancing) -- step-by-step walkthrough of the Milan POS use case
- [Location Allocation tutorial](https://academy.carto.com/creating-workflows/step-by-step-tutorials/transforming-telco-network-management-decisions-with-location-allocation) -- telco network management with location allocation
- [AI Agent + Location Allocation](https://academy.carto.com/agentic-gis/step-by-step-tutorials/optimizing-rapid-response-hubs-placement-with-ai-agents-and-location-allocation) -- using AI agents with location allocation for emergency response hub placement

---

## Common Variations

| Variant | How |
|---------|-----|
| Sales territory balancing | Points -> H3 -> aggregate revenue per cell -> territory balancing with revenue as demand |
| Service zone design | Grid with population -> territory balancing to create equal-population zones |
| Warehouse/depot placement | Population grid as demand + existing warehouses as candidates -> minimize total cost |
| Emergency response hubs | Population grid as demand + candidate sites -> maximize coverage with a response-time radius |
| Retail network expansion | Customer density grid as demand + potential store locations -> maximize coverage |
| Hub placement and service areas | Location allocation picks the hubs and already assigns each demand point to one (`facility_id` per `dpoint_id`); territory balancing cannot be anchored to given hubs |
