---
name: carto-trade-area-analysis
description: Builds trade area and catchment analysis workflows in CARTO. Triggers when the user mentions trade area, catchment area, isochrone, site selection, where to open, best location, billboard, OOH, audience targeting, drive time, walk time, coverage area, commercial hotspot, site scoring, location ranking, or wants to generate isochrones, score candidate locations, or identify the best sites for retail, advertising, or services.
license: MIT
---

# Trade Area Analysis

Builds CARTO Workflows that define catchment areas around candidate locations, enrich them with data, and score/rank locations for site selection, billboard placement, or coverage analysis.

**Prerequisites**: Load `carto-create-workflow` for the development process, JSON structure, and validation. It covers both access paths — the MCP server's workflow tools (`create_workflow`, `validate_workflow`, `run_workflow`) when attached, the `carto workflows` CLI otherwise. Routing signals: `carto-basics/references/access-paths.md`.

**Ad-hoc catchments**: for a one-off isochrone around a handful of points, use the `calculate_isolines` MCP tool (available over OAuth, or on a token session whose Allowed APIs include **LDS**) — the workflow patterns below are for table-scale, repeatable analysis.

---

## Instructions

A trade area workflow always follows this pipeline:

```
Candidate Locations → (Filter) → Catchment Areas → Spatial Index → Enrich → Aggregate → Score/Rank → Save
```

### Step 1: Load Candidate Locations

Load stores, billboards, POIs, or any point dataset representing candidate locations as a `ReadTable` source node (see `carto-create-workflow`). Source nodes and `native.gettablebyname` both emit on handle `out`, not `result`.

**Success**: Node outputs a table with a geometry column (e.g. `geom`) and a unique location identifier.

### Step 2: Filter/Limit Candidates (optional)

Use `native.wheresimplified` to narrow candidates (e.g. specific city, category). Use `native.orderby` with `desc: true` (the default is ascending) + `native.limit` for top-N by a metric (e.g. top 50 by revenue).

**Success**: Output contains only the candidate subset relevant to the analysis. Reducing candidates early prevents combinatorial explosion downstream.

### Step 3: Generate Catchment Areas

Choose the catchment method based on the use case:

| Method | Component | When to use | Key params |
|--------|-----------|-------------|------------|
| Isochrones | `native.isolines` | Site selection, retail — realistic road-network areas | `mode`: options follow the account's LDS provider (TomTom has no `walk`); read them from `read_workflow_components` or `carto workflows components get native.isolines`; `type`: `time` or `distance`; `range`: one value per node, seconds for `time` (10 min = 600), meters for `distance`. The polygon replaces the point column, as `geom` |
| Buffers | `native.buffer` | Billboard coverage, proximity — simple geometric circles | `distance` + `units` (`Meters` default, or `Miles`). Adds the circle as `<geo>_buffer` (e.g. `geom_buffer`) and keeps the point column |

**Isochrones vs Buffers**: Isochrones follow the road network and produce realistic catchment shapes but require a CARTO LDS API call. Buffers are purely geometric circles — simpler and faster, suitable for proximity analysis or billboard coverage.

**Success**: Each candidate location has an associated polygon representing its catchment area.

### Step 4: Convert Catchment to Spatial Index

Use `native.h3polyfill` or `native.quadbinpolyfill` to tessellate catchment polygons into grid cells. Set `geo` to the catchment polygon: `geom` after `native.isolines`, `<geo>_buffer` after `native.buffer`; polyfilling the point column gives one cell per location. Leave `aggregate` false (default) so the location id is kept. The cell column is `h3` or `quadbin`; geometry columns are dropped.

Size cells so each catchment holds many of them: walk catchments (5-15 min, ~0.5-5 km²) at H3 9 (≈ 0.11 km²) or 10 (≈ 0.015 km²); 10-30 min drives at H3 8 (≈ 0.74 km²) or 7 (≈ 5.2 km²). Quadbin cells are ≈ 40075/2^z km wide at the equator: z16-17 for walk, z14-15 for drive. Never leave `native.quadbinpolyfill` at its default 12 (≈ 10 km cells). Match the enrichment table's resolution only when you join on the cell column (Step 5).

**Success**: Output contains one row per grid cell per location, with both the spatial index column and the location identifier preserved.

### Step 5: Enrich with Data

Join grid cells with a spatial features dataset or use an enrich component:
- **JOIN approach**: `native.joinv2` on the cell column (`h3` = `h3`) against an enrichment table indexed at the same resolution. Not `native.spatialjoin`: it joins geometry columns only, and polyfilled cells carry no geometry.
- **Enrich approach**: `native.h3enrich` (H3) or `native.quadbinenrich` (Quadbin), with any table that has a geometry column or a Data Observatory subscription as `source`, at any grid resolution. `variables` = `col,method` pairs; output columns are `<col>_<method>` (e.g. `population_sum`).

**Success**: Each grid cell row has enrichment variables (e.g. population, income, foot traffic) attached.

### Step 6: Aggregate Back to Locations

Use `native.groupby` to collapse grid-cell rows back to one row per location:
- **Group by**: the location identifier column
- **Aggregation**: `<col>,<method>` pairs using the names the previous node produced, e.g. `population_sum,sum,income_avg,avg` after h3enrich. Outputs get the method as a suffix (`population_sum_sum`, `income_avg_avg`).

The output has no geometry: `native.joinv2` it back to the candidate table on the location id before scoring or saving, so the result can be mapped.

**Success**: Output has one row per candidate location with aggregated enrichment metrics and its geometry.

### Step 7: Score and Rank

Three-part pattern (see `carto-composite-scoring` for the full method): **normalize** each variable with its own `native.normalize` node (one `column` per node; it adds `<column>_norm`); **composite score** via `native.selectexpression` (`column` = `score`, `expression` e.g. `population_sum_sum_norm * 0.4 + income_avg_avg_norm * 0.3 + traffic_sum_sum_norm * 0.3`); **rank** with `native.orderby` (`desc: true`) + `native.limit` (top N).

**Success**: A ranked list of candidate locations with a composite score and the contributing normalized variables.

### Step 8: Save

Use `native.saveastable` to persist the ranked results.

**Success**: Validated workflow that can be uploaded via `create_workflow` (MCP) or `carto workflows create` (CLI).

---

## Gotchas

- **Provider casing & SQL dialect.** This skill uses lowercase column names (`geom`, `h3`, `population_sum`, `score`, etc.) — BigQuery / Databricks / Postgres / Redshift convention. On Snowflake, unquoted identifiers surface UPPERCASE — reference them as `GEOM`, `H3`, `POPULATION_SUM`, `SCORE`. See `carto-create-workflow/references/providers/<provider>.md` for casing rules and SQL dialect equivalents.
- **Provider limits.** PostgreSQL has no `native.isolines`, `native.h3enrich` or `native.quadbinenrich`: use `native.buffer` and the JOIN approach. Redshift has no H3 polyfill: use `native.quadbinpolyfill`.
- Isolines call CARTO LDS through the Analytics Toolbox; the workflow's token gets LDS access automatically, with no connection setting to enable. Each successful isoline uses one unit of the account's LDS isolines quota, so a run spends input rows x isolines nodes. Filter candidates first and tell the user the expected count before running. Buffers use no quota.
- Cross Join for distance matrices can explode with many locations x many grid cells. Filter and limit candidates first (Step 2) to keep the pipeline manageable.
- Buffer `distance` is in `units` (Meters by default). Isoline `range` is in **seconds** (for `type=time`) or **meters** (for `type=distance`).
- `native.commercialhotspots` (BigQuery, Snowflake, Databricks only) has no `variablecolumns` input: `weights` carries the variables, as a JSON-encoded string of `[column, weight, reverse]` triples, e.g. `[["population_sum", 0.7, false], ["h3_distance_min", 0.3, false]]`. `indexcol` must be named `h3`, `quadbin`, `index` or `geoid`. On Databricks cluster connections also set `kernel` and `clustertype` (`hotspots`, `coldspots` or `all`): that path has no defaults and the run fails without them.
- When aggregating enrichment back to locations (Step 6), ensure the GROUP BY uses the **location identifier**, not the grid cell index. Grouping by the grid cell produces per-cell results instead of per-location.
- `native.h3distance` compares two H3 columns of the same row. For each cell's distance to its nearest competitor: `native.h3frompoint` on competitors, `native.crossjoin` with the grid (competitor cell becomes `h3_joined`; on Databricks cluster connections `native.crossjoin` prefixes columns with `l_` / `r_` instead, e.g. `r_h3`), `native.h3distance` (`h3`, `h3_joined`), then `native.groupby` `h3_distance,min` by `h3`. Join that back to the grid or the locations.

---

## Reference Templates

These files are working examples in this skill directory:

| File | Description |
|------|-------------|
| `isochrones_from_points.json` | Retail stores in Boston — 5-min walk-time isochrones via LDS API. `native.isolines` is on v2 (lowercase wire-value `mode` list, `customoptions` / `traveltime_*` inputs). |
| `identify_best_billboards.json` | Billboard site scoring — buffer, enrich, normalize, weighted composite score, top-N |
| `commercial_hotspots.json` | Commercial hotspot detection — H3 distance to competitors, weighted hotspot analysis |

**Refreshing component versions.** Templates pin each node's `data.version` to what was current when harvested. When a native component bumps versions (e.g. `native.isolines` v1 → v2 added transport modes plus `customoptions` and `traveltime_*` inputs), the older template still parses but flags `verify-remote` warnings and misses new inputs. To refresh, read the live schema — `read_workflow_components` (MCP) or `carto workflows components get <component> --connection <conn> --json` (CLI) — then update the node's `data.version` and `inputs` in lockstep. Cross-reference `Selection` values against `carto-create-workflow/SKILL.md`: `options` may show display labels, but wire values are the lowercase / snake_case forms.

---

## Common Variations

| Variant | How |
|---------|-----|
| Retail site selection | Isochrones (walk/drive) -> H3 polyfill -> enrich with demographics -> score by population + income |
| Billboard/OOH placement | Buffers -> H3 polyfill -> enrich with audience/traffic -> normalize + weighted score -> top-N |
| Commercial hotspot detection | H3 grid -> enrich demand -> min hop distance to competitors (h3frompoint -> crossjoin -> h3distance -> groupby min) -> `native.commercialhotspots` (weights JSON triples, kring, pvaluethresh); BigQuery, Snowflake, Databricks only |
| Drive-time coverage analysis | One `native.isolines` node per range (car) -> `native.selectexpression` adds a `band` column to each -> `native.unionall` -> `native.groupby` `geom,combine` by `band` (output `geom_union`; dissolves on BigQuery, Databricks and Oracle, only collects on Snowflake and Redshift) |
| Walk-time catchment comparison | One `native.isolines` node per band (walk, type time, range 300 / 600 / 900) -> enrich each band -> compare population captured per band |
| Franchise territory planning | Isochrones per candidate -> check overlap -> filter non-overlapping set -> score remaining |
