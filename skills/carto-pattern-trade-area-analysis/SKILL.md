---
name: carto-pattern-trade-area-analysis
description: Builds trade area and catchment analysis workflows in CARTO. Triggers when the user mentions trade area, catchment area, isochrone, site selection, where to open, best location, billboard, OOH, audience targeting, drive time, walk time, coverage area, commercial hotspot, site scoring, location ranking, or wants to generate isochrones, score candidate locations, or identify the best sites for retail, advertising, or services.
license: MIT
---

# Trade Area Analysis

Builds CARTO Workflows that define catchment areas around candidate locations, enrich them with data, and score/rank locations for site selection, billboard placement, or coverage analysis.

**Prerequisites**: Load `carto-create-analytics-workflow` for the development process, JSON structure, and validation commands.

---

## Instructions

A trade area workflow always follows this pipeline:

```
Candidate Locations → (Filter) → Catchment Areas → Spatial Index → Enrich → Aggregate → Score/Rank → Save
```

### Step 1: Load Candidate Locations

Use `native.gettablebyname` to load stores, billboards, POIs, or any point dataset representing candidate locations.

**Success**: Node outputs a table with a geometry column (e.g. `geom`) and a unique location identifier.

### Step 2: Filter/Limit Candidates (optional)

Use `native.wheresimplified` to narrow candidates (e.g. specific city, category). Use `native.orderby` + `native.limit` for top-N by a metric (e.g. top 50 by revenue).

**Success**: Output contains only the candidate subset relevant to the analysis. Reducing candidates early prevents combinatorial explosion downstream.

### Step 3: Generate Catchment Areas

Choose the catchment method based on the use case:

| Method | Component | When to use | Key params |
|--------|-----------|-------------|------------|
| Isochrones | `native.isolines` | Site selection, retail — realistic road-network areas | `mode`: car/walk; `type`: time/distance; `range`: seconds or meters |
| Buffers | `native.buffer` | Billboard coverage, proximity — simple geometric circles | `distance`: meters |

**Isochrones vs Buffers**: Isochrones follow the road network and produce realistic catchment shapes but require a CARTO LDS API call. Buffers are purely geometric circles — simpler and faster, suitable for proximity analysis or billboard coverage.

**Success**: Each candidate location has an associated polygon representing its catchment area.

### Step 4: Convert Catchment to Spatial Index

Use `native.h3polyfill` or `native.quadbinpolyfill` to tessellate catchment polygons into grid cells. The resolution must match the enrichment dataset you plan to use.

**Success**: Output contains one row per grid cell per location, with both the spatial index column and the location identifier preserved.

### Step 5: Enrich with Data

Join grid cells with a spatial features dataset or use `native.h3enrich`:
- **JOIN approach**: `native.joinv2` or `native.spatialjoin` with a pre-indexed enrichment table
- **Enrich approach**: `native.h3enrich` to pull variables from CARTO's Data Observatory

**Success**: Each grid cell row has enrichment variables (e.g. population, income, foot traffic) attached.

### Step 6: Aggregate Back to Locations

Use `native.groupby` to collapse grid-cell rows back to one row per location:
- **Group by**: the location identifier column
- **Aggregation**: `population,sum,income,avg` (comma-separated column,method pairs)

**Success**: Output has one row per candidate location with aggregated enrichment metrics.

### Step 7: Score and Rank

Three-part scoring pattern:

1. **Normalize** each variable to [0,1] using `native.normalize` (one call per variable, or chain multiple)
2. **Composite score** via `native.selectexpression`: weighted addition of normalized variables, e.g. `normalized_population * 0.4 + normalized_income * 0.3 + normalized_traffic * 0.3`
3. **Rank** using `native.orderby` (descending by composite score) + `native.limit` (top N)

**Success**: Output is a ranked list of candidate locations with a composite score and the contributing normalized variables.

### Step 8: Save

Use `native.saveastable` to persist the ranked results.

**Success**: Validated workflow that can be uploaded via `carto workflows create`.

---

## Gotchas

- Isochrone and route components call CARTO's LDS API — they require a valid connection with API access enabled. Buffers do not.
- Cross Join for distance matrices can explode with many locations x many grid cells. Filter and limit candidates first (Step 2) to keep the pipeline manageable.
- H3 resolution must match the enrichment dataset resolution. Check the enrichment table's index column before choosing resolution.
- Buffer distance is in **meters**. Isoline range is in **seconds** (for `type=time`) or **meters** (for `type=distance`).
- The `native.commercialhotspots` component expects `variablecolumns` as a Python-style list string (`['col1', 'col2']`) and `weights` as comma-separated values — inconsistent with other components.
- When aggregating enrichment back to locations (Step 6), ensure the GROUP BY uses the **location identifier**, not the grid cell index. Grouping by the grid cell produces per-cell results instead of per-location.
- When using `native.h3distance` for competitor proximity, the output is grid-based. Join it back to the location table to get per-location distance metrics.

---

## Reference Templates

These files are working examples in this skill directory:

| File | Description |
|------|-------------|
| `isochrones_from_points.json` | Retail stores in Boston — 5-min walk-time isochrones via LDS API |
| `identify_best_billboards.json` | Billboard site scoring — buffer, enrich, normalize, weighted composite score, top-N |
| `commercial_hotspots.json` | Commercial hotspot detection — H3 distance to competitors, weighted hotspot analysis |

---

## Common Variations

| Variant | How |
|---------|-----|
| Retail site selection | Isochrones (walk/drive) -> H3 polyfill -> enrich with demographics -> score by population + income |
| Billboard/OOH placement | Buffers -> H3 polyfill -> enrich with audience/traffic -> normalize + weighted score -> top-N |
| Commercial hotspot detection | H3 grid -> `native.h3distance` for competitor proximity -> `native.commercialhotspots` with weights and p-value threshold |
| Drive-time coverage analysis | Isochrones (car, multiple ranges) -> union -> dissolve to find total coverage area |
| Walk-time catchment comparison | Isochrones (walk, 5/10/15 min) -> enrich each band -> compare population captured per band |
| Franchise territory planning | Isochrones per candidate -> check overlap -> filter non-overlapping set -> score remaining |
