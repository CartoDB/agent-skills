---
name: carto-pattern-site-selection
description: Builds site selection and cannibalization analysis workflows in CARTO. Triggers when the user mentions site selection, cannibalization, cannibalizing, new store location, where to open, optimal location, facility placement, network impact, overlapping catchments, twin areas, similar locations, look-alike areas, find locations like my best, store overlap, revenue impact of new store, commercial hotspots, demand hotspots, location scoring, location ranking, expand network, new branch, franchise placement, EV charging siting, or wants to evaluate candidate sites, quantify overlap between trade areas, or find areas that resemble top-performing locations.
license: MIT
---

# Site Selection and Cannibalization Analysis

Builds CARTO Workflows that identify optimal locations for new facilities (stores, stations, offices) by combining spatial criteria, and that quantify cannibalization risk from overlapping catchment areas. Also covers twin-area and similar-location discovery.

**Prerequisites**: Load `carto-create-workflow` for the development process, JSON structure, and validation commands. Load `carto-pattern-trade-area-analysis` if the workflow involves isochrones, buffers, or catchment enrichment — that skill covers the catchment pipeline in detail.

---

## Decision Tree

| User intent | Pattern |
|-------------|---------|
| "Where should I open a new store?" | Site Selection (scoring + ranking) |
| "Will a new store hurt existing ones?" | Cannibalization Analysis |
| "Find locations similar to my best performers" | Twin Areas / Similar Locations |

---

## Instructions

### Pattern A: Site Selection (Scoring + Ranking)

```
Existing locations + Target area -> Spatial indexing -> Enrich with demographics/POIs -> Score/Rank -> Filter top candidates -> Save
```

#### Step 1: Load Data

Load two datasets with `native.gettablebyname`:
- **Existing locations** (current stores/facilities)
- **Target area** (e.g. city boundary, district polygons, or a grid covering the study area)

**Success**: Both tables loaded with geometry columns and unique identifiers.

#### Step 2: Build Candidate Grid

Polyfill the target area into H3 or Quadbin cells using `native.h3polyfill` or `native.quadbinpolyfill`. Each cell is a candidate micro-location.

**Success**: A contiguous grid of cells covering the study area.

#### Step 3: Enrich Candidates

Attach demand signals to each cell — population, income, foot traffic, POI density — using `native.h3enrich`, `native.joinv2`, or the Data Observatory.

**Success**: Each grid cell has numeric columns representing demand/suitability factors.

#### Step 4: Filter by Proximity to Existing Locations

Use `native.h3distance` to compute hop distance from each candidate cell to the nearest existing location. Filter out cells that are too close (cannibalization risk) or too far (logistics cost).

- `native.h3distance` returns **hop count**, not physical distance. Convert using the approximate edge length for the resolution (e.g. H3 res 8 ~ 460m edge, so 3 hops ~ 1.4 km).

**Success**: Candidate cells are within a sensible distance band from existing locations.

#### Step 5: Score and Rank

Use the scoring pattern from `trade-area-analysis`:
1. **Normalize** each variable to [0,1] with `native.normalize`
2. **Composite score** via `native.selectexpression` with user-defined weights
3. **Rank** with `native.orderby` (descending) + `native.limit` (top N)

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

Load existing locations and proposed locations (or a single table with a flag column distinguishing them).

**Success**: Both sets loaded with geometry and unique identifiers.

#### Step 2: Generate Trade Areas

Create catchment areas around both existing and proposed locations using `native.isolines` (realistic) or `native.buffer` (simple). Use the same parameters for both sets to ensure comparability.

**Success**: Every location has a catchment polygon with consistent parameters.

#### Step 3: Polyfill to Spatial Index

Convert all catchment polygons to H3 or Quadbin cells with `native.h3polyfill`. Preserve the location identifier and an `is_proposed` flag.

**Success**: One row per cell per location, with location ID and type flag.

#### Step 4: Find Overlap

Use `native.joinv2` (inner join on the spatial index column) between existing-location cells and proposed-location cells. The result contains cells shared by at least one existing and one proposed location.

**Success**: Output contains only cells that fall in both an existing and a proposed catchment.

#### Step 5: Measure Impact

Use `native.groupby` to aggregate overlap:
- **Per existing location**: count of overlapping cells / total cells in that location's catchment = overlap percentage
- **Enrich overlap cells** with population or revenue to quantify shared demand

Use `native.selectexpression` to compute the overlap ratio.

**Success**: Each existing location has an overlap metric showing how much of its catchment is shared with proposed locations.

#### Step 6: Save

Use `native.saveastable`.

**Success**: Validated workflow with per-location cannibalization metrics.

---

### Pattern C: Twin Areas / Similar Locations

```
Top-performing locations -> Trade areas -> Enrich -> Build similarity model -> Score all candidate areas -> Rank -> Save
```

#### Step 1: Identify Reference Locations

Load the full location dataset. Filter to top performers (e.g. top quartile by revenue) using `native.wheresimplified` or `native.orderby` + `native.limit`.

**Success**: A subset of high-performing locations isolated as the reference set.

#### Step 2: Generate and Enrich Trade Areas

Create isochrone or buffer trade areas around reference locations. Polyfill to H3/Quadbin. Enrich with demographics, POIs, and any relevant variables.

**Success**: Each reference location has a rich demographic profile.

#### Step 3: Build Twin Areas Model

Use `native.buildtwinareasmodel` (BUILD_TWIN_AREAS_MODEL) to create a PCA-based similarity model from the enriched reference locations.

- Input: enriched reference locations with numeric feature columns
- The model captures the multivariate "signature" of successful locations

**Success**: A model artifact that encodes the demographic profile of top performers.

#### Step 4: Find Similar Locations

Use `native.findsimilarlocations` (FIND_SIMILAR_LOCATIONS) to score all candidate areas against the twin-areas model.

- Input: candidate areas enriched with the same variables used to build the model
- Output: similarity score per candidate

**Success**: Every candidate area has a similarity score relative to the reference set.

#### Step 5: Rank and Save

Rank by similarity score descending. Save top candidates.

**Success**: A ranked list of areas most similar to top-performing locations.

---

### Commercial Hotspots Variant

For demand-driven site selection (e.g. "where is unmet demand highest?"), use `native.commercialhotspots`:

1. Build an H3 grid over the study area
2. Enrich with the target demand variable (e.g. population aged 15-34)
3. Run `native.commercialhotspots` with `variablecolumns` and `weights`
4. Filter results by significance (`p_value < 0.05`)
5. Optionally filter by `native.h3distance` from existing locations to focus on underserved areas

**Note**: `variablecolumns` uses Python-style list syntax (`['col1', 'col2']`), and `weights` is comma-separated — see the `trade-area-analysis` gotchas for details.

---

## Gotchas

- **Provider casing & SQL dialect.** This skill uses lowercase column names (`h3`, `is_proposed`, `population`, etc.) — BigQuery / Databricks / Postgres / Redshift convention. On Snowflake, unquoted identifiers surface UPPERCASE — reference them as `H3`, `IS_PROPOSED`, `POPULATION`. See `carto-create-workflow/references/providers/<provider>.md` for casing rules and SQL dialect equivalents.
- `native.commercialhotspots` requires the **Retail module** of the Analytics Toolbox. Validate with `--connection` to confirm availability.
- Twin Areas and Similar Locations use **PCA** internally — results are sensitive to variable selection and scaling. Include only relevant, non-redundant variables. Normalize inputs if scales differ widely.
- Cannibalization overlap depends heavily on **trade area definition** (buffer radius, isoline time). Small changes in parameters can flip results. Document the chosen parameters and rationale.
- `native.h3distance` returns **hop count**, not physical distance. Multiply by the approximate cell edge length for the resolution to get a rough metric distance (e.g. res 8 ~ 460m, res 9 ~ 174m per hop).
- When comparing across regions of different sizes, **normalize demographics** to per-capita or per-area values to avoid size bias (e.g. population density instead of total population).
- The "best" location depends entirely on the **criteria and weights chosen** — there is no objectively correct answer. Always document assumptions and let the user adjust weights.
- For the twin-areas model, use the **same set of enrichment variables** for both the reference locations and the candidates. Mismatched variables will cause the model to fail or produce meaningless scores.

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
| Bank branch optimization | Twin areas from top branches -> find similar underserved areas -> propose new branches |
| Competitor proximity analysis | H3 distance to competitor locations -> filter cells far from competitors but near demand |
