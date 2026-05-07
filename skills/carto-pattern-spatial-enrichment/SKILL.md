---
name: carto-pattern-spatial-enrichment
description: Guides the user through spatial enrichment workflows -- triggered by requests to enrich, add demographics, estimate population around locations, compute spatial features, sociodemographic analysis, "what's around" queries, buffer/isochrone + join patterns, or trade area enrichment.
license: MIT
---

# Spatial Enrichment in CARTO Workflows

**Prerequisites**: Load `carto-create-workflow` for the development process.

This skill covers the universal pattern for enriching spatial data with demographics, risk scores, or any variable from a spatial features dataset.

---

## Instructions

Follow the 5-step universal enrichment pattern. Each step maps to one or more workflow components.

### Step 1: Load source data

Load the business entities (stores, points, polygons) that need enrichment.

- Points or polygons from a table: use a `ReadTable` source node
- Custom geometry: use `native.tablefromgeojson` to inline a GeoJSON polygon

### Step 2: Define target area

Choose one method based on the use case:

| Method | Component | When to use |
|--------|-----------|-------------|
| Buffer | `native.buffer` | Distance-based area (e.g. 1km around each store) |
| Isochrones | `native.isolines` | Drive-time or walk-time areas |
| Direct polygon | (none needed) | Source data is already polygons |
| Direct points | (none needed) | Skip to Step 4 with `native.enrichpoints` |

### Step 3: Spatial indexing (polyfill)

Convert areas into a grid for enrichment. **This step is required when using grid-based enrichment (`native.h3enrich`) or manual JOIN.**

- H3 grid (most common): `native.h3polyfill` -- set `resolution` to match the enrichment dataset
- Quadbin grid: `native.quadbinpolyfill` -- set `resolution` to match the enrichment dataset

**Key decision -- index type**: Use H3 unless the enrichment data is natively in Quadbin.

### Step 4: Enrich

Two approaches, each with different column naming:

**A) CARTO ENRICH procedures** (recommended for Data Observatory or spatial features data):
- `native.h3enrich` -- enrich an H3 grid
- `native.enrichpoints` -- enrich points directly (skip Step 3)
- `native.enrichpolygons` -- enrich polygons directly (skip Step 3)
- Output columns are named `{variable}_{aggregation}` (e.g. `population_sum`, `air_quality_avg`)

**B) Manual JOIN** on the spatial index column:
- Use `native.join` with the H3/Quadbin column as the join key
- Output columns from the secondary table get a `_joined` suffix
- Default is INNER JOIN (silently drops unmatched cells)

**Aggregation method guidance**:
- `SUM` -- population counts, totals
- `MAX` / `MIN` -- risk scores, thresholds
- `AVG` -- quality metrics, indices

### Step 5: Save results

Use `native.saveastable` to persist the enriched output.

If the goal is per-entity enrichment (e.g. population per store), add a second JOIN + GROUP BY to aggregate grid-level results back to the source entity level.

**Success**: The workflow loads source data, defines areas, indexes to a grid (if needed), enriches with the target variables using the correct aggregation, and saves the result. Column names in downstream references match the enrichment method used.

---

## Gotchas

- **Provider casing & SQL dialect.** This skill documents output column names in lowercase (`population_sum`, `air_quality_avg`, `<column>_joined`, etc.) — BigQuery / Databricks / Postgres / Redshift convention. On Snowflake, unquoted identifiers surface UPPERCASE — reference them as `POPULATION_SUM`, `AIR_QUALITY_AVG`, `<COLUMN>_JOINED`. See `carto-create-workflow/references/providers/<provider>.md` for casing rules and SQL dialect equivalents.
- **Resolution alignment is critical.** The polyfill resolution MUST match the enrichment dataset's native resolution (e.g. H3 resolution 8 with resolution 8 spatial features). A mismatch produces zero JOIN matches with NO error.
- **Manual JOIN drops unmatched cells.** `native.join` defaults to INNER JOIN, silently dropping cells with no enrichment data. Use LEFT JOIN if completeness matters.
- **Deduplicate after polyfill.** Use `SELECT DISTINCT` or GROUP BY on the index column to remove duplicate cells. If you need to preserve source identity (e.g. which store each cell came from), set `includecols: true` in the polyfill node.
- **Column naming differs by method.** ENRICH procedures produce `{variable}_{aggregation}` columns. Manual JOIN produces `{column}_joined` columns. Plan downstream SQL references accordingly.
- **Buffer distance is in meters.** Isoline range units depend on type: seconds for time-based, meters for distance-based.
- **Re-aggregation needed for entity-level results.** After grid enrichment, data is at the cell level. To get per-store or per-location totals, add a second JOIN + GROUP BY step to roll cell-level values back to the source entity.

---

## Reference Templates

Templates included in this skill folder (from the CARTO Workflows template repository):

| File | Pattern | Description |
|------|---------|-------------|
| [enrich_grid.json](enrich_grid.json) | GeoJSON polygon -> H3 polyfill -> ENRICH_GRID | Enrich a custom area with sociodemographic H3 data |
| [enrich_points.json](enrich_points.json) | Filter points -> ENRICH_POINTS | Enrich point locations with polygon-based risk data |
| [estimate_population_around_retail_stores.json](estimate_population_around_retail_stores.json) | Points -> Buffer -> H3 polyfill -> JOIN -> GROUP BY | Full entity-level enrichment with re-aggregation |

---

## Common Variations

| Variation | Steps used | Key differences |
|-----------|-----------|-----------------|
| Enrich points directly | 1 -> 4 -> 5 | Skip grid; use `native.enrichpoints` |
| Enrich polygons directly | 1 -> 4 -> 5 | Skip grid; use `native.enrichpolygons` |
| Buffer + grid enrichment | 1 -> 2 -> 3 -> 4 -> 5 | `native.buffer` then polyfill then enrich |
| Isochrone + grid enrichment | 1 -> 2 -> 3 -> 4 -> 5 | `native.isolines` then polyfill then enrich |
| Re-aggregate to source entity | 1 -> 2 -> 3 -> 4 -> JOIN + GROUP BY -> 5 | Add second JOIN to map cells back to source entities |
