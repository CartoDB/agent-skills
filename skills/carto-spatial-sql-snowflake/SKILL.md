---
name: carto-spatial-sql-snowflake
description: Write spatial SQL on Snowflake using CARTO's Analytics Toolbox. Covers the AT module catalog, Snowflake's GEOGRAPHY vs GEOMETRY split, H3 / quadbin storage, Search Optimization for spatial, and the Native App vs manual install paths.
license: MIT
---

# carto-spatial-sql-snowflake

CARTO's Analytics Toolbox (AT) on Snowflake covers nearly the full BigQuery set, with a few modules absent. This skill covers what's CARTO-specific; generic Snowflake `ST_*` semantics live in Snowflake's own docs.

## When to use this skill

- The connected warehouse is Snowflake (`carto connections list --json | jq '.[] | select(.provider=="snowflake")'`).
- You're calling `carto.*` functions on Snowflake.
- The user has to choose between `GEOGRAPHY` and `GEOMETRY` types.
- You're sizing a warehouse / clustering key for a spatial workload.

## Analytics Toolbox on Snowflake

Two install paths:

- **Native App from Snowflake Marketplace** (recommended) — there's an *Analytics Toolbox* listing and an open-source *Lite* variant. Self-installing, version-managed by Snowflake. See [native-app-from-snowflakes-marketplace](https://docs.carto.com/data-and-analysis/analytics-toolbox-for-snowflake/getting-access/native-app-from-snowflakes-marketplace).
- **Manual install** — `CALL CARTO.CARTO.INSTALL(...)`. Canonical DB/schema: `CARTO.CARTO`. Functions are then called as `<DB>.<SCHEMA>.<FUNCTION>(...)`.

```sql snowflake
SELECT carto.carto.H3_FROMGEOGPOINT(geom, 9) AS h3_index
FROM ANALYTICS.PUBLIC.EVENTS;
```

## Modules shipped

| Module | Purpose |
|---|---|
| `accessors` | Extract geometry properties |
| `clustering` | K-means on spatial points |
| `constructors` | Splines, ellipses, envelopes |
| `data` | Data Observatory enrichment |
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
| `s2` | Google S2 cells |
| `statistics` | Moran's I, Getis-Ord, GWR, etc. |
| `tiler` | Vector tile materialization |
| `transformations` | Buffer, hull, simplify |

**Not shipped on Snowflake:** `cpg`, `geohash`, `routing` (folded into `lds`), `telco`. Steer LLMs away from those module paths.

## Spatial type system — LLM traps

- **Snowflake has BOTH `GEOGRAPHY` and `GEOMETRY`**, and they behave differently. `GEOGRAPHY` is WGS84 spheroid (metres); `GEOMETRY` is planar with an SRID. Functions with the same name return different units depending on which type you pass. CARTO AT functions **default to `GEOGRAPHY`** — check signatures in the SQL reference before passing `GEOMETRY`.
- **H3 indexes are stored as `VARCHAR`** (hex string), same as BigQuery. `H3_STRING_TOINT` / `H3_INT_TOSTRING` convert to `NUMBER`.
- **Quadbin is `NUMBER`** (INT64). Same as every other engine that ships quadbin.
- **`ST_MAKEPOINT(longitude, latitude)`** — longitude-first. Snowflake errors are silent (point in wrong hemisphere).
- Function names are uppercase-canonical (`ST_DWITHIN`, `H3_FROMGEOGPOINT`). Lowercase works but renders inconsistent in scripts.

## Spatial indexing

Snowflake has no R-tree. Two acceleration paths:

- **Search Optimization Service for `GEOGRAPHY`** — warehouse-managed, accelerates `ST_INTERSECTS` / `ST_CONTAINS` lookups. Costs storage + compute; right for high-cardinality lookup tables.
- **Clustering keys** on the H3 `VARCHAR` or quadbin `NUMBER` column of large fact tables — the more predictable path for CARTO workloads.

```sql snowflake
ALTER TABLE analytics.public.events
  CLUSTER BY (h3);
```

Pre-binning to H3/quadbin with `H3_POLYFILL_TABLE` or `QUADBIN_POLYFILL` is the standard CARTO pattern; cluster on the resulting column.

## Performance defaults

- **Pre-bin large point tables** to H3 or quadbin once; reuse the indexed column across queries.
- **Scale the warehouse before optimizing the SQL** if a join is sluggish — Snowflake parallelizes spatial joins on larger warehouses.
- **Avoid `SELECT *`** on `GEOGRAPHY`-bearing tables.
- For Builder tilesets, `CREATE_SPATIAL_INDEX_TILESET` over `CREATE_SIMPLE_TILESET` for very large datasets.

## Module gaps vs flagship (BigQuery)

| Missing on Snowflake | What to do instead |
|---|---|
| `cpg` | No equivalent — flag the gap to the user |
| `geohash` | Use H3 or quadbin instead |
| `routing` (standalone) | Use `lds` — it carries isolines / routing on Snowflake |
| `telco` | No equivalent on Snowflake |

## Always-on guidance

- **Qualify calls with the DB and schema where AT lives.** Default is `CARTO.CARTO.<FUNCTION>` — don't emit unqualified `H3_FROMGEOGPOINT`.
- **Decide `GEOGRAPHY` vs `GEOMETRY` deliberately.** For CARTO AT functions, GEOGRAPHY is the default and matches the BQ flagship; only pick `GEOMETRY` when the user explicitly works in a projected CRS.
- **For ad-hoc queries** use `carto sql query`; for warehouse-scale materialization use `carto sql job` (see [`../carto-query-datawarehouse/references/sql-jobs-and-caching.md`](../carto-query-datawarehouse/references/sql-jobs-and-caching.md)).
