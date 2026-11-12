---
name: carto-spatial-enrichment
description: Guides the user through spatial enrichment workflows — triggered by requests to enrich, add demographics, estimate population around locations, compute spatial features, sociodemographic analysis, "what's around" queries, buffer/isochrone + join patterns, or trade area enrichment.
license: MIT
---

# Spatial Enrichment in CARTO Workflows

**Prerequisites**: Load `carto-create-workflow` for the development process — it covers both access paths (the MCP server's workflow tools such as `create_workflow`, `validate_workflow`, and `run_workflow` when attached; the `carto workflows` CLI otherwise; routing signals in `carto-basics/references/access-paths.md`). There is no direct enrichment MCP tool — enrichment always runs as a Workflow, so route through those workflow tools.

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
| Isochrones | `native.isolines` | Drive-time or walk-time areas (consumes LDS quota; not available on PostgreSQL, use a buffer there) |
| Direct polygon | (none needed) | Source data is already polygons |
| Direct points | (none needed) | Skip to Step 4 with `native.enrichpoints` |

`native.buffer` keeps the input geometry and adds the buffer polygon as a new column `<geo>_buffer` (e.g. `geom_buffer`). Point the next node's geometry input (`geo` on a polyfill, `target_col` on an enrich node) at `geom_buffer`, not `geom`. `native.isolines` replaces the input geometry column with the isoline polygon in `geom`.

### Step 3: Spatial indexing (polyfill)

Convert areas into a grid for enrichment. **This step is required when using grid-based enrichment (`native.h3enrich`, `native.quadbinenrich`) or manual JOIN.**

- H3 grid (most common): `native.h3polyfill` -- writes the cell id to column `h3` (String)
- Quadbin grid: `native.quadbinpolyfill` -- writes column `quadbin` (Number); `resolution` is a zoom level (0-26)

The enrich nodes read the source's geometry, so choose the resolution for the analysis (see below). Only when you JOIN against a table that is already an H3 or Quadbin grid (Step 4, B) must the polyfill resolution equal that table's resolution.

**Key decision -- index type**: Use H3 unless the enrichment data is natively in Quadbin, or the connection is Redshift, which has no `native.h3polyfill` (use Quadbin there).

**Size the grid to the areas.** A polyfill keeps only cells whose centre falls inside the polygon (default mode `center`). H3 average cell: res 6 ≈ 36 km² (edge 3.7 km), res 7 ≈ 5.2 km² (1.4 km), res 8 ≈ 0.74 km² (0.53 km), res 9 ≈ 0.11 km² (0.20 km). A 1 km buffer (≈ 3.1 km²) holds about 4 cells at res 8, about 30 at res 9, and can hold none at res 7. Use cells at most about a tenth of the smallest area. When the resolution is fixed by the enrichment data, set the polyfill mode to `intersects` where the component schema for the connection lists a mode input (`components get` / `read_workflow_components`).

### Step 4: Enrich

**Provider availability.** PostgreSQL has no enrich nodes (`native.enrichpoints`, `native.enrichpolygons`, `native.h3enrich`, `native.quadbinenrich`): there, enrich with `native.spatialjoin` + `native.groupby`, or polyfill + `native.joinv2` on the index. Oracle has no `native.spatialjoin`.

Two approaches, each with different column naming:

**A) CARTO ENRICH procedures** (Analytics Toolbox; recommended for Data Observatory or spatial features data):
- `native.h3enrich` -- enrich an H3 grid
- `native.quadbinenrich` -- enrich a Quadbin grid
- `native.enrichpoints` -- enrich points directly (skip Step 3)
- `native.enrichpolygons` -- enrich polygons directly (skip Step 3)
- Inputs: `target` (the table to enrich: points, polygons, or the polyfill output) and `source` (the data). Set `target_col` to the target's geometry column (the `h3` / `quadbin` column on the grid nodes) and `source_col` to the source's geometry column. A table that is only an H3 or Quadbin index cannot be a source; JOIN it on the index instead (B). Validation does not require `source_col`, so a missing one fails only when the workflow runs. Source and target must be different nodes.
- Set `variables` as one comma-separated string of column/method pairs, e.g. `"population,sum,income,avg"`. Methods are lowercase `sum`, `avg`, `min`, `max`, `count`, on numeric source columns only. A column can take several methods, but a column/method pair cannot repeat.
- Output columns are named `{variable}_{aggregation}` (e.g. `population_sum`, `air_quality_avg`)
- Data Observatory: the subscription path (`variables` use the subscription's variable names; `source_col` is ignored) runs only when `source` is a Data Observatory source node, which the user adds in Workflows by dragging the subscription onto the canvas; BigQuery, Snowflake and Redshift only. A subscription table loaded with `ReadTable` is an ordinary source and needs a geometry column.

**`native.enrichpolygons` vs `native.spatialjoin + native.groupby`** — both bypass the grid step (Step 3) and aggregate a source dataset directly onto target polygons. Pick by these trade-offs:

| Approach | Pros | Cons |
|---|---|---|
| `native.enrichpolygons` | One node; dedicated UI in Workflows; semantically clearest | Analytics Toolbox dependency; intermediate joined rows aren't inspectable; aggregation methods constrained to the `SelectColumnAggregation` list |
| `native.spatialjoin` + `native.groupby` | No AT dependency; intermediate joined table is inspectable in Workflows; full control over join predicate (`intersects` / `covers` / `touches`), join type, and column aliasing | Two nodes; verbose; must set `maintablecolumns` / `secondarytablecolumns` on the spatial join to keep the schema tight; not available on Oracle; Snowflake has no `touches` predicate |

Default to `native.enrichpolygons` for simple sum/avg of a single source onto target polygons. Switch to `native.spatialjoin + native.groupby` when you need a non-default predicate, an aggregation the enrich nodes lack (they offer only sum, avg, min, max, count on numeric columns), or visibility into the intermediate join. The same trade-off applies between `native.enrichpoints` and the equivalent `spatialjoin + groupby` chain for point targets.

**B) Manual JOIN** on the spatial index column:
- Use `native.joinv2` (input handles `lefttable` / `righttable`) with the H3/Quadbin column as `lefttablekeycolumn` / `righttablekeycolumn`
- Choose output columns in `lefttablecolumns` / `righttablecolumns`, each a JSON string `[{"name":"<col>","joinname":"<output col>"}]`; `[]` selects none. Output columns take the `joinname` values.
- `jointype` defaults to `Inner` (silently drops unmatched cells); use `Left` to keep them

**Aggregation method guidance** (write methods in lowercase in `variables`):
- `sum` -- population counts, totals
- `max` / `min` -- risk scores, thresholds
- `avg` -- quality metrics, indices
- `count` -- number of source features

### Step 5: Save results

Use `native.saveastable` to persist the enriched output.

If the goal is per-entity enrichment (e.g. population per store), add a second JOIN + GROUP BY to aggregate grid-level results back to the source entity level.

**Success**: A validated workflow that loads source data, defines areas, enriches with the correct aggregation, and saves — with downstream column references matching the enrichment method used. Upload via `create_workflow` (MCP) or `carto workflows create` (CLI).

---

## Gotchas

- **Provider casing & SQL dialect.** This skill documents output column names in lowercase (`population_sum`, `air_quality_avg`, etc.) — the BigQuery / Databricks / Redshift convention. On Snowflake and Oracle, unquoted identifiers surface UPPERCASE — reference them as `POPULATION_SUM`, `AIR_QUALITY_AVG`. See `carto-create-workflow/references/providers/<provider>.md` for casing rules and SQL dialect equivalents.
- **Resolution alignment for a manual JOIN.** When joining on the index (B), the polyfill resolution MUST match the grid table's native resolution (e.g. H3 resolution 8 with resolution 8 spatial features). A mismatch produces zero JOIN matches with NO error.
- **Manual JOIN drops unmatched cells.** `native.joinv2` defaults to `Inner`, silently dropping cells with no enrichment data. Use `Left` if completeness matters.
- **Duplicate cells after polyfill.** With `aggregate: false` (the default) the polyfill emits one row per source feature per cell and copies every non-geometry source column (e.g. `store_id`), so overlapping areas repeat cells. Set `aggregate: true` to get distinct `h3` / `quadbin` cells only (source columns dropped). `includegeocolumns: true` also keeps the source geometry column.
- **Column naming differs by method** (see Step 4): ENRICH procedures produce `{variable}_{aggregation}`; `native.joinv2` produces the `joinname` you set.
- **Buffer distance is in `units`** (`Meters`, the default, or `Miles`). Isoline `range` is seconds for `type: time` and meters for `type: distance`.
- **Re-aggregation needed for entity-level results.** Grid enrichment leaves data at the cell level; add a second JOIN + GROUP BY to roll it back to per-store / per-location totals (see Step 5).

---

## Reference Templates

Templates included in this skill folder (from the CARTO Workflows template repository):

| File | Pattern | Description |
|------|---------|-------------|
| [enrich_grid.json](enrich_grid.json) | GeoJSON polygon -> H3 polyfill -> ENRICH_GRID | Enrich a custom area with sociodemographic H3 data |
| [enrich_points.json](enrich_points.json) | Filter points -> ENRICH_POINTS | Enrich point locations with polygon-based risk data |
| [estimate_population_around_retail_stores.json](estimate_population_around_retail_stores.json) | Points -> Isolines -> H3 polyfill -> JOIN -> GROUP BY | Full entity-level enrichment with re-aggregation (uses the legacy `native.join`; author new joins with `native.joinv2`) |

---

## Common Variations

| Variation | Steps used | Key differences |
|-----------|-----------|-----------------|
| Enrich points directly | 1 -> 4 -> 5 | Skip grid; use `native.enrichpoints` |
| Enrich polygons directly | 1 -> 4 -> 5 | Skip grid; use `native.enrichpolygons` |
| Buffer + grid enrichment | 1 -> 2 -> 3 -> 4 -> 5 | `native.buffer` then polyfill then enrich |
| Isochrone + grid enrichment | 1 -> 2 -> 3 -> 4 -> 5 | `native.isolines` then polyfill then enrich |
| Re-aggregate to source entity | 1 -> 2 -> 3 -> 4 -> JOIN + GROUP BY -> 5 | Add second JOIN to map cells back to source entities |
