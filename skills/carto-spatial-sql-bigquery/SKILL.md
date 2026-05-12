---
name: carto-spatial-sql-bigquery
description: Write spatial SQL on BigQuery using CARTO's Analytics Toolbox. Covers the AT module catalog, BQ's GEOGRAPHY-only type system, H3 / quadbin / S2 indexing, and the LLM traps that bite on BQ specifically (e.g. STRING H3 vs INT64 quadbin, longitude-first constructors).
license: MIT
---

# carto-spatial-sql-bigquery

CARTO's Analytics Toolbox (AT) on BigQuery is the **flagship** — every AT module ships here. This skill covers what's CARTO-specific on BQ; generic `ST_*` semantics live in BigQuery's own docs and an LLM already knows them.

## When to use this skill

- The connected warehouse is BigQuery (`carto connections list --json | jq '.[] | select(.provider=="bigquery")'`).
- You're calling `carto.*` functions (H3, quadbin, statistics, data enrichment, tilesets).
- You're choosing between H3 and quadbin pre-binning, or designing a clustering key.
- You hit "function not found" errors — usually a region/project-ID mismatch.

## Analytics Toolbox on BigQuery

Two access models:

- **Hosted projects maintained by CARTO** (recommended). Region-specific projects, dataset name is always `carto`. Call form: `` `<project-id>`.carto.<FUNCTION>(...) `` with backticks around the project ID.
- **Manual install** into the customer's BigQuery project (paid customers).
- A **Core open-source subset** is published as a public BigQuery dataset for any user; advanced modules require a CARTO account.

Pick the project ID by region — full table at [about-analytics-toolbox-regions](https://docs.carto.com/data-and-analysis/analytics-toolbox-for-bigquery/about-analytics-toolbox-regions). Examples: `carto-un` (US multi), `carto-un-eu` (EU multi), `carto-un-eu-we1` (europe-west1), `carto-un-us-ea4` (us-east4).

```sql bigquery
SELECT `carto-un`.carto.H3_FROMGEOGPOINT(geom, 9) AS h3_index
FROM `my_project.demo.events`
```

## Modules shipped (full set)

| Module | Purpose |
|---|---|
| `accessors` | Extract geometry properties |
| `clustering` | K-means on spatial points |
| `constructors` | Splines, ellipses, envelopes |
| `cpg` | CPG analytics — trade areas, location matching |
| `data` | Data Observatory enrichment (`ENRICH_POINTS` / `_POLYGONS` / `_GRID`) |
| `geohash` | Geohash boundaries (BQ-only) |
| `h3` | H3 indexing |
| `http_request` | Call out from SQL |
| `import` | Load remote files via URL |
| `lds` | Location Data Services: geocoding, isolines, routing |
| `measurements` | Angles / distances |
| `placekey` | Placekey ↔ H3 |
| `processing` | Delaunay, Voronoi, polygonization |
| `quadbin` | Quadtree indexing |
| `random` | Random points within geometry |
| `raster` | Raster value extraction |
| `retail` | Revenue forecasting, cannibalization |
| `routing` | Travel matrices, service areas |
| `s2` | Google S2 cells |
| `statistics` | Moran's I, Getis-Ord, GWR, LOF, KNN, G-function, space-time Gi* |
| `telco` | RF propagation, path profile |
| `tiler` | Vector tile materialization (`CREATE_SIMPLE_TILESET`, `CREATE_SPATIAL_INDEX_TILESET`) |
| `transformations` | Buffer, hull, simplify |

SQL reference index: [sql-reference](https://docs.carto.com/data-and-analysis/analytics-toolbox-for-bigquery/sql-reference).

## Spatial type system — LLM traps

- **GEOGRAPHY is the only spatial type on BigQuery.** No planar `GEOMETRY`. All distances/areas are geodesic (WGS84 spheroid), in metres.
- **`ST_GEOMFROMTEXT` does not exist on BQ.** Use `ST_GEOGFROMTEXT` / `ST_GEOGFROMWKB`. An LLM writing PostGIS-style constructors will silently fail.
- **`ST_GeogPoint(lng, lat)` is longitude-first.** Reversing produces points in the wrong hemisphere with no error.
- **H3 indexes are `STRING`** (hex like `'84390cbffffffff'`) in CARTO BQ AT. The C library uses `uint64` — don't assume `INT64`. Convert with `` `<region>`.carto.H3_STRING_TOINT `` / `H3_INT_TOSTRING`.
- **Quadbin indexes are `INT64`** — opposite of H3 on the same engine. Don't mix the types up.

## Spatial indexing

BigQuery has no R-tree. Acceleration comes from:

- **Clustering on the H3 or quadbin column** of large fact tables. Predictable join performance.
- **`CLUSTER BY geom`** on `GEOGRAPHY` is supported (BQ generates an S2-cover cluster key), but H3/quadbin clustering is more predictable.
- **Partition by date** when both date and geometry filters apply — date pruning eliminates more data than spatial filters.

```sql bigquery
CREATE TABLE my_ds.events_h3
CLUSTER BY h3
AS
SELECT `carto-un`.carto.H3_FROMGEOGPOINT(geom, 9) AS h3, *
FROM my_ds.events_raw;
```

Concept page: [key-concepts/spatial-indexes](https://docs.carto.com/data-and-analysis/analytics-toolbox-for-bigquery/key-concepts/spatial-indexes).

## Performance defaults

- **Pre-bin point data to H3 or quadbin** before joining — every CARTO statistics function expects the index column already exists.
- **Never `SELECT *`** on a table with a `GEOGRAPHY` column: per-row geometry payload can be enormous.
- **`bigquery-public-data.geo_*`** datasets are free, public, and useful for joining to admin boundaries without a CARTO subscription.
- For very large datasets served to Builder, use `CREATE_SPATIAL_INDEX_TILESET` (H3/quadbin-backed) over `CREATE_SIMPLE_TILESET`.

## Module gaps vs other engines

BigQuery is the baseline — no gaps. Modules unique-to-BQ today: `cpg`, `geohash`, `telco`. Anything you find on BQ that's missing elsewhere lives in the other dialect skills' module tables.

## Always-on guidance

- **Always qualify with the region's project ID and backticks.** `` `carto-un`.carto.H3_FROMGEOGPOINT(...) `` — never bare `carto.H3_*`.
- **Pick the region that matches the data's BQ region.** Cross-region AT calls fail or get billed for cross-region egress.
- **For ad-hoc exploratory queries**, use `carto sql query <connection> ...`; for materialization or anything > 60 s, use `carto sql job` (see [`../carto-query-datawarehouse/references/sql-jobs-and-caching.md`](../carto-query-datawarehouse/references/sql-jobs-and-caching.md)).
