---
name: carto-site-selection
description: Builds site selection and cannibalization analysis workflows in CARTO. Triggers when the user mentions site selection, cannibalization, cannibalizing, new store location, where to open, optimal location, facility placement, network impact, overlapping catchments, twin areas, similar locations, look-alike areas, find locations like my best, store overlap, revenue impact of new store, commercial hotspots, demand hotspots, location scoring, location ranking, expand network, new branch, franchise placement, EV charging siting, or wants to evaluate candidate sites, quantify overlap between trade areas, or find areas that resemble top-performing locations.
license: MIT
---

# Site Selection and Cannibalization Analysis

Builds CARTO Workflows that identify optimal locations for new facilities (stores, stations, offices) by combining spatial criteria, and that quantify cannibalization risk from overlapping catchment areas.

**Prerequisites**: Load `carto-create-workflow` for the development process, JSON structure, and validation. It covers both access paths — the MCP server's workflow tools (`create_workflow`, `validate_workflow`, `run_workflow`) when attached, the `carto workflows` CLI otherwise. Routing signals: `carto-basics/references/access-paths.md`. Load `carto-trade-area-analysis` if the workflow involves isochrones, buffers, or catchment enrichment — it covers the catchment pipeline in detail.

---

## Decision Tree

| User intent | Pattern |
|-------------|---------|
| "Where should I open a new store?" | Site Selection (scoring + ranking) |
| "Will a new store hurt existing ones?" | Cannibalization Analysis |
| "Find locations similar to my best performers" | Twin Areas: no native component; offer the Pattern C approximation |

---

## Instructions

### Pattern A: Site Selection (Scoring + Ranking)

```
Existing locations + Target area -> Spatial indexing -> Enrich with demographics/POIs -> Score/Rank -> Filter top candidates -> Save
```

#### Step 1: Load Data

Load each table as a `ReadTable` source node (see `carto-create-workflow`). Source nodes and `native.gettablebyname` both emit on handle `out`, not `result`.
- **Existing locations** (current stores/facilities)
- **Target area** (e.g. city boundary, district polygons, or a grid covering the study area)

**Splitting candidates from existing network when both sit in one table.** If the user's source is a single table where "candidates" are defined by a numeric threshold (e.g. `revenue ≥ X`, `size ≥ Y`), use one `native.where` with that predicate and wire its **`match`** output to the candidate pipeline and its **`unmatch`** output to the existing-network pipeline. Two streams from one node — dramatically cleaner than `orderby + limit + customsql NOT IN`, and avoids a customsql entirely. The threshold approximates "top N"; if the user explicitly says "exactly top 25", `orderby + limit` is still the right call but pay the extra-node cost knowingly.

**Success**: Both tables loaded with geometry columns and unique identifiers.

#### Step 2: Build Candidate Grid

Polyfill the target area into H3 or Quadbin cells using `native.h3polyfill` or `native.quadbinpolyfill`. Each cell is a candidate micro-location.

Set `resolution` explicitly. H3 8 (edge ≈ 0.53 km, ≈ 0.74 km²) for drive-time or city-wide screening; H3 9 (≈ 0.20 km, ≈ 0.11 km²) for walkable urban siting. Quadbin 15 (≈ 1.2 km wide at the equator, narrower toward the poles) to 17 (≈ 0.3 km). Never leave `native.quadbinpolyfill` at its default 12 (≈ 10 km cells). If you will enrich by joining an indexed table, use that table's resolution.

**Success**: A contiguous grid of cells covering the study area.

#### Step 3: Enrich Candidates

Attach demand signals (population, income, foot traffic, POI density) with `native.h3enrich` (H3 grid) or `native.quadbinenrich` (Quadbin grid), whose `source` can be any table with a geometry column or a Data Observatory subscription; or with `native.joinv2` on the cell column against a table indexed at the same resolution.

If candidates are continuous polygons (catchments / districts) rather than a grid, the choice between `native.enrichpolygons` and `native.spatialjoin + native.groupby` matters — see [`carto-spatial-enrichment`](../carto-spatial-enrichment/SKILL.md) Step 4 for the trade-off (AT dependency vs node count vs predicate / join control).

**Success**: Each grid cell has numeric columns representing demand/suitability factors.

#### Step 4: Filter by Proximity to Existing Locations

`native.h3distance` compares two H3 columns of the same row; it does not search another table. For each candidate cell's hop distance to the nearest existing location:

1. `native.h3frompoint` on the existing locations, at the grid's resolution (adds `h3`).
2. `native.crossjoin`: `maintable` = candidate grid, `secondarytable` = location cells. Secondary columns get a `_joined` suffix, so the location cell is `h3_joined`. It yields cells x locations rows, so filter the grid first.
3. `native.h3distance`: `h3_1` = `h3`, `h3_2` = `h3_joined` (adds `h3_distance`).
4. `native.groupby`: `columns` = `h3_distance,min`, `groupby` = `h3` (gives `h3_distance_min`).
5. `native.joinv2` back to the enriched grid on `h3`, then `native.where` on `h3_distance_min` to drop cells too close (cannibalization risk) or too far (logistics cost). It is a hop count, not metric distance (see Gotchas).

**Distance semantics — measure cannibalization from the catchment polygon, not the candidate point.** When candidates are points with a generated trade area (isoline / buffer — see `carto-trade-area-analysis`), run `native.distance` with `main` = the candidates' **catchment polygons** (`geom` after `native.isolines`, `<geo>_buffer` after `native.buffer`) and `secondary` = the existing locations. `ST_DISTANCE(polygon, point) = 0` whenever the competitor sits inside the trade area — exactly the cannibalization signal you want; point-to-point distance hides overlap. Set `radius` (`units` Meters by default) to the farthest distance at which a competitor still matters, about the catchment's own reach (~800 m for a 10-minute walk). `radius` is a cutoff: it does not change `nearest_distance`, and candidates with no competitor inside it are dropped from the output. To keep them, `native.joinv2` (`jointype` Left) from the full candidate list on the id, and read a NULL `nearest_distance` as no competitor within `radius`. This polygon-to-point pattern is the middle ground between Pattern A's H3 hop filter and Pattern B's full grid-overlap analysis — use it whenever the candidate already has a continuous catchment geometry.

**Success**: Candidate cells are within a sensible distance band from existing locations, and any cannibalization signal is measured from the catchment polygon when one exists.

#### Step 5: Score and Rank

Use the scoring pattern from `trade-area-analysis`:
1. **Normalize** each variable with its own `native.normalize` node (one `column` per node). It adds `<column>_norm` (0-1; z-score with `zscores: true`); the score expression must use those names.
2. **Composite score** via `native.selectexpression` with user-defined weights
3. **Rank** with `native.orderby` (`desc: true`; the default is ascending) + `native.limit` (top N)

**Success**: A ranked shortlist of candidate cells with composite scores and contributing variables.

#### Step 6: Save

Use `native.saveastable`. The H3/Quadbin column is directly visualizable in CARTO Builder.

**Success**: Validated workflow ready to upload.

---

### Pattern B: Cannibalization Analysis

```
Existing + Proposed locations -> Trade areas (isoline/buffer) -> Polyfill to grid -> Intersect/Join -> Measure overlap -> Save
```

#### Step 1: Load Data

Load existing locations and proposed locations (or a single table with a flag column distinguishing them). If both sets sit in a single table and the split is defined by a numeric threshold (e.g. `revenue ≥ X`), see Pattern A Step 1's `native.where` match/unmatch split — it produces both streams from one node and avoids customsql.

**Success**: Both sets loaded with geometry and unique identifiers.

#### Step 2: Generate Trade Areas

Create catchment areas around both existing and proposed locations using `native.isolines` (realistic) or `native.buffer` (simple). Use the same parameters for both sets to ensure comparability.

**Success**: Every location has a catchment polygon with consistent parameters.

#### Step 3: Polyfill to Spatial Index

Polyfill each catchment set with `native.h3polyfill` (or `native.quadbinpolyfill`), same resolution for both. Set `geo` to the catchment polygon: `geom` after `native.isolines`, `<geo>_buffer` (e.g. `geom_buffer`) after `native.buffer`; polyfilling the point column gives one cell per location.
- **Existing set**: leave `aggregate` false (default) so the location id is kept.
- **Proposed set**: `aggregate: true` returns the distinct cells of all proposed catchments, so a cell shared by two proposed sites counts once. Keep `aggregate` false only if the user also wants impact per proposed site.

**Success**: One row per cell per existing location, and the cells covered by proposed catchments.

#### Step 4: Find Overlap

Use `native.joinv2` (`jointype` Inner, on the cell column) between existing-location cells and proposed-location cells. The result contains the existing-catchment cells that a proposed catchment also covers.

**Success**: Output contains only cells that fall in both an existing and a proposed catchment.

#### Step 5: Measure Impact

Per existing location:
1. `native.groupby` on the existing-location cells: `columns` = `h3,count`, `groupby` = the location id (total cells).
2. `native.groupby` on the overlap join: same `columns` and `groupby` (overlapping cells). With per-proposed-site cells, also group by the proposed id.
3. `native.joinv2` with `jointype` Left from totals to overlap on the id, so locations with no overlap stay in.
4. `native.selectexpression`: `COALESCE(<overlap count>, 0) * 1.0 / <total count>` as `overlap_pct` (`* 1.0` avoids integer division on PostgreSQL and Redshift).

To quantify shared demand, enrich the overlap cells with population or revenue before step 2 and sum it.

**Success**: Each existing location has an overlap metric showing how much of its catchment is shared with proposed locations.

#### Step 6: Save

Use `native.saveastable`.

**Success**: Validated workflow with per-location cannibalization metrics.

---

### Pattern C: Twin Areas / Similar Locations

Workflows has no twin-areas or similar-locations component on any connection. Do not invent one or name an Analytics Toolbox procedure for it. Tell the user so, then offer this approximation and build it only if they agree:

1. Filter the top performers (e.g. `native.where` on revenue, or `native.orderby` `desc: true` + `native.limit`).
2. Build trade areas around the top performers and the candidates with the same method and parameters, and enrich both with the same variables (`carto-trade-area-analysis`).
3. Compare the top performers' averages with the whole network (`native.groupby` with `<col>,avg`) to find the variables where they stand out.
4. Score the candidates on those variables with Pattern A Step 5, weighting the distinguishing variables most (`carto-composite-scoring`), then rank and save.

**Success**: A ranked list of candidate areas, described to the user as a weighted score on the variables that set top performers apart, not a similarity model.

---

### Commercial Hotspots Variant

For demand-driven site selection (e.g. "where is unmet demand highest?") on BigQuery, Snowflake or Databricks, use `native.commercialhotspots` (combined Getis-Ord Gi* over several weighted variables; working example: `carto-trade-area-analysis/commercial_hotspots.json`):

1. Build an H3 grid over the study area and enrich it with the demand variables (Pattern A Steps 2-3). The cell column must be named `h3`, `quadbin`, `index` or `geoid`.
2. To favour underserved cells, add the minimum hop distance to existing locations first (Pattern A Step 4 chain) and include it in `weights`.
3. Run `native.commercialhotspots` with `indexcol` = the cell column, `weights` (see Note), `kring` (default 3) and `pvaluethresh` (default 0.05). Cells above `pvaluethresh` are already dropped, so no filter node is needed.
4. The output holds only the cell column (renamed `index` on BigQuery), `combined_gi` and `p_value`. Join it back to the enriched grid on the cell column to keep the other variables.

**Note**: there is no `variablecolumns` input. `weights` is a JSON-encoded string of `[column, weight, reverse]` triples, e.g. `[["population_sum", 0.7, false], ["h3_distance_min", 0.3, false]]`. Weights are normalized to sum to 1; `reverse: true` flips a variable where lower is better.

---

## Gotchas

- **Provider casing & SQL dialect.** This skill uses lowercase column names (`h3`, `is_proposed`, `population`, etc.) — BigQuery / Databricks / Postgres / Redshift convention. On Snowflake, unquoted identifiers surface UPPERCASE — reference them as `H3`, `IS_PROPOSED`, `POPULATION`. See `carto-create-workflow/references/providers/<provider>.md` for casing rules and SQL dialect equivalents.
- **Provider limits.** Redshift has no H3 polyfill, frompoint or distance components: use Quadbin. PostgreSQL has no `native.isolines`, `native.h3enrich`, `native.quadbinenrich` or `native.enrichpolygons`: use `native.buffer` and `native.joinv2` against an indexed table. `native.distance` runs only on BigQuery, Snowflake, Redshift and PostgreSQL. `native.commercialhotspots` runs only on BigQuery, Snowflake and Databricks.
- `native.commercialhotspots` runs Analytics Toolbox procedures. The component catalog lists it on those connections whether or not the toolbox is installed, and neither `validate` nor `verify` probes the procedure; a missing toolbox only shows when the workflow runs.
- Cannibalization overlap depends heavily on **trade area definition** (buffer radius, isoline time). Small changes in parameters can flip results. Document the chosen parameters and rationale.
- `native.h3distance` returns **hop count**, not metric distance. One hop is about 1.5-1.7 x the cell edge (centre to centre): ≈ 2.1-2.4 km at res 7 (edge ≈ 1.4 km), ≈ 0.8-0.9 km at res 8 (edge ≈ 0.53 km), ≈ 0.30-0.35 km at res 9 (edge ≈ 0.20 km).
- When comparing across regions of different sizes, **normalize demographics** to per-capita or per-area values to avoid size bias (e.g. population density instead of total population).
- The "best" location depends entirely on the **criteria and weights chosen** — there is no objectively correct answer. Always document assumptions and let the user adjust weights.

---

## Reference Templates

### Academy Tutorials

| Tutorial | Provider | URL |
|----------|----------|-----|
| Pizza Hut Honolulu — site selection with commercial hotspots | BigQuery | [Link](https://academy.carto.com/advanced-spatial-analytics/spatial-analytics-for-bigquery/step-by-step-tutorials/opening-a-new-pizza-hut-location-in-honolulu) |
| Pizza Hut Honolulu — site selection with commercial hotspots | Snowflake | [Link](https://academy.carto.com/advanced-spatial-analytics/spatial-analytics-for-snowflake/step-by-step-tutorials/opening-a-new-pizza-hut-location-in-honolulu) |
| Store cannibalization — quantifying new store impact | BigQuery | [Link](https://academy.carto.com/advanced-spatial-analytics/spatial-analytics-for-bigquery/step-by-step-tutorials/store-cannibalization-quantifying-the-effect-of-opening-new-stores-on-your-existing-network) |
| Starbucks cannibalization — H3 grid overlap analysis | BigQuery | [Link](https://academy.carto.com/advanced-spatial-analytics/spatial-analytics-for-bigquery/step-by-step-tutorials/an-h3-grid-of-starbucks-locations-and-simple-cannibalization-analysis) |
| Store cannibalization — Quadkey grid overlap | Snowflake | [Link](https://academy.carto.com/advanced-spatial-analytics/spatial-analytics-for-snowflake/step-by-step-tutorials/a-quadkey-grid-of-stores-locations-and-simple-cannibalization-analysis) |
| Find twin areas of top-performing stores | BigQuery | [Link](https://academy.carto.com/advanced-spatial-analytics/spatial-analytics-for-bigquery/step-by-step-tutorials/find-twin-areas-of-top-performing-stores) |
| Find similar locations based on trade areas | BigQuery | [Link](https://academy.carto.com/advanced-spatial-analytics/spatial-analytics-for-bigquery/step-by-step-tutorials/find-similar-locations-based-on-their-trade-areas) |
| EV charging station site selection | Workflows | [Link](https://academy.carto.com/creating-workflows/step-by-step-tutorials/optimizing-site-selection-for-ev-charging-stations) |

---

## Common Variations

| Variant | How |
|---------|-----|
| Retail expansion | Isochrones -> enrich with demographics + competitor density -> composite score -> top N |
| Franchise territory planning | Cannibalization pattern to ensure non-overlapping catchments before awarding territories |
| EV charging / public services | Grid-based demand (population, traffic) + distance-from-existing filter -> rank underserved cells |
| Billboard / OOH placement | Buffers -> audience enrichment -> normalize + weight -> top N (see `trade-area-analysis`) |
| Bank branch optimization | Score candidate cells on the variables that distinguish top branches, then rank (Pattern A) |
| Competitor proximity analysis | `native.h3frompoint` on competitors -> `native.crossjoin` with the grid -> `native.h3distance` -> `native.groupby` `h3_distance,min` by `h3` -> keep cells far from competitors but near demand |
