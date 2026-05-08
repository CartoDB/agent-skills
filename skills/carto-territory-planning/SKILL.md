---
name: carto-territory-planning
description: Builds territory planning workflows in CARTO combining territory balancing and location allocation. Triggers when the user mentions territory balancing, territory planning, sales territories, service zones, workload distribution, balanced territories, location allocation, facility placement, optimal locations, maximize coverage, minimize cost, minimize travel distance, depot placement, hub placement, warehouse siting, response time optimization, demand coverage, or wants to divide an area into balanced regions or find optimal facility locations.
license: MIT
---

# Territory Planning (Territory Balancing + Location Allocation)

Builds CARTO Workflows that solve two related spatial optimization problems: dividing areas into balanced territories (e.g. sales regions, service zones) and finding optimal facility locations that maximize coverage or minimize cost.

**Prerequisites**: Load `carto-create-workflow` for the development process, JSON structure, and validation commands. Both components require the **Territory Planning Extension Package** installed on the connection.

---

## Territory Balancing

Divides a study area into spatially contiguous territories that are balanced by a demand variable (e.g. workload, population, revenue).

### Pipeline

```
Source Data (points) -> Spatial Indexing -> Aggregate per Cell -> Territory Balancing -> Save
```

### Step 1: Load Source Data

Use `native.gettablebyname`. Input is typically point data with one or more numeric metrics to balance.

**Success**: Node outputs a table with a geometry column and numeric metric columns.

### Step 2: Convert to Spatial Index

Use `native.h3frompoint` (or `native.quadbinfromgeopoint`) to assign each point to a grid cell.

**Resolution guidance**: Higher resolution = smaller cells = finer-grained territories, but more computation. H3 resolution 8-9 is typical for city-level analysis.

**Success**: Output has a spatial index column (e.g. `h3`).

### Step 3: Aggregate per Cell

Use `native.groupby` to produce one row per cell with the metrics to balance:
- **Group by**: the spatial index column (`h3`)
- **Aggregation**: e.g. `geom,count,revenue,sum,population,avg`

**Success**: One row per cell with numeric columns for demand and optional similarity features.

### Step 4: Run Territory Balancing

Use `native.territorybalancing` with:

| Input | Description | Example |
|-------|-------------|---------|
| `input_table` | Table input (from previous step) | |
| `index_column` | H3 or Quadbin column | `h3` |
| `demand_column` | Numeric column to balance across territories | `geom_count` |
| `similarity_feats` | Optional numeric columns for within-territory similarity | `["sentiment_avg", "popularity_avg"]` |
| `npartitions` | Number of territories to create | `9` |
| `keep_input_columns` | Include all input columns in output | `true` |

**Success**: Output contains all input rows with an additional territory assignment column. Each cell is assigned to exactly one territory.

### Step 5: Save

Use `native.saveastable` to persist results. The spatial index column is directly visualizable in CARTO Builder, colored by territory ID.

**Success**: Validated workflow uploadable via `carto workflows create`.

---

## Location Allocation

Finds the optimal subset of candidate facility locations that either maximize demand coverage or minimize total cost/distance.

### Pipeline

```
Demand Data (grid/points) -> Candidate Locations -> Location Allocation -> Save
```

### Step 1: Load Demand Data

Use `native.gettablebyname` to load a grid or point dataset representing demand (e.g. population per H3 cell, customer locations).

**Success**: Table with a spatial index column and a numeric demand column.

### Step 2: Load Candidate Locations

Use a second `native.gettablebyname` for potential facility locations (e.g. existing infrastructure, candidate sites).

If candidates need filtering, use `native.wheresimplified` or `native.limit` to reduce the set -- fewer candidates = faster computation.

**Success**: Table with a spatial index column representing candidate sites.

### Step 3: Run Location Allocation

Choose the variant based on the objective:

#### Maximize Coverage

Use `native.locallocallocation_maximizecoverage`:

| Input | Description | Example |
|-------|-------------|---------|
| `demand` | Table with demand values | |
| `demand_index_column` | Spatial index column in demand table | `h3` |
| `demand_column` | Numeric demand variable | `population` |
| `candidates` | Table with candidate locations | |
| `candidates_index_column` | Spatial index column in candidates table | `h3` |
| `nfacilities` | Number of facilities to open | `5` |
| `coverageradius` | Maximum service distance (meters for geography) | `5000` |

**Success**: Output identifies which facilities to open and which demand cells each facility serves, maximizing total covered demand within the radius.

#### Minimize Total Cost

Use `native.locallocallocation_minimizetotalcost`:

| Input | Description | Example |
|-------|-------------|---------|
| `demand` | Table with demand values | |
| `demand_index_column` | Spatial index column in demand table | `h3` |
| `demand_column` | Numeric demand variable | `population` |
| `candidates` | Table with candidate locations | |
| `candidates_index_column` | Spatial index column in candidates table | `h3` |
| `nfacilities` | Number of facilities to open | `5` |

**Success**: Output identifies which facilities to open, minimizing total weighted travel distance between demand and assigned facilities.

### Step 4: Save

Use `native.saveastable` to persist results.

**Success**: Validated workflow uploadable via `carto workflows create`.

---

## Gotchas

- **Provider casing & SQL dialect.** This skill uses lowercase column names (`h3`, `geom_count`, `population`, `sentiment_avg`, etc.) — BigQuery / Databricks / Postgres / Redshift convention. On Snowflake, unquoted identifiers surface UPPERCASE — reference them as `H3`, `GEOM_COUNT`, `POPULATION`, `SENTIMENT_AVG`. See `carto-create-workflow/references/providers/<provider>.md` for casing rules and SQL dialect equivalents.
- **Extension package required**: Both territory balancing and location allocation require the Territory Planning Extension Package installed on the specific connection being used. This is NOT available by default -- the user must have it installed. Validation will fail if the package is missing.
- **Location allocation is computationally expensive** with many candidates. Pre-filter candidates (by geography, capacity, or other criteria) to keep the candidate set small. Hundreds of candidates can be slow; thousands may time out.
- **Coverage radius units** depend on the spatial reference system -- typically meters when using geography types. Verify the unit matches your intent.
- **Territory balancing optimizes a trade-off** between spatial contiguity and balance. Perfect balance is not guaranteed -- territories will be approximately equal in the demand variable, not exactly equal.
- **Grid resolution sensitivity**: Results change significantly with the input grid resolution. Finer grids give more precise boundaries but increase computation. Start with H3 resolution 8 for city-scale and adjust.
- **The component names** use `native.territorybalancing` (no dot separator in "territory balancing") and `native.locallocallocation_maximizecoverage` / `native.locallocallocation_minimizetotalcost` (note the double "local" prefix).
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
| Combined territory + allocation | First run location allocation to pick hub locations, then run territory balancing to assign areas to each hub |
