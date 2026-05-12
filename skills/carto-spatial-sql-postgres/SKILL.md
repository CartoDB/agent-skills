---
name: carto-spatial-sql-postgres
description: Write spatial SQL on PostgreSQL / PostGIS using CARTO's Analytics Toolbox. The AT here is intentionally thin (h3, quadbin, tiler only) — PostGIS itself covers the rest. Covers the install gotchas (plv8 for H3), identifier casing, and the GiST / SP-GiST / BRIN index choice.
license: MIT
---

# carto-spatial-sql-postgres

CARTO's Analytics Toolbox (AT) on PostgreSQL is **a thin shell over PostGIS**: only `h3`, `quadbin`, and `tiler`. Everything else (constructors, transformations, measurements, statistics, enrichment, geocoding) **isn't shipped on Postgres AT** — use PostGIS native, or expect not to have it.

## When to use this skill

- The connected warehouse is Postgres (`carto connections list --json | jq '.[] | select(.provider=="postgres")'`).
- You're calling `carto.h3_*` / `carto.quadbin_*` / `carto.create_*_tileset`.
- You're standing up the AT on a fresh database (manual install, `plv8` dependency).
- You're picking between GiST, SP-GiST, and BRIN indexes on a geometry column.

## Analytics Toolbox on PostgreSQL

**Manual install only.** Run the [`modules.sql` script](https://docs.carto.com/data-and-analysis/analytics-toolbox-for-postgresql/getting-access/manual-installation) — it installs into a `carto` schema. Prereqs:

- **PostGIS extension** (`CREATE EXTENSION postgis;`) — required.
- **`plv8` extension** — required *only* for the `h3` module. Without it, `quadbin` and `tiler` still work.

⚠ **The install script drops all prior `carto`-schema functions** before re-creating them. If you've added anything there yourself, save it.

Call form: `carto.<function>(...)` — **lowercase**. Postgres folds identifiers to lowercase unless double-quoted, so `carto.H3_FROMGEOGPOINT` becomes `carto.h3_fromgeogpoint` automatically. Be explicit.

```sql postgres
SELECT carto.h3_fromgeogpoint(geom, 9) AS h3_index
FROM events;
```

## Modules shipped (only three)

| Module | What's in it |
|---|---|
| `h3` | 17 functions: `h3_frompoint`, `h3_polyfill`, `h3_kring`, `h3_boundary`, `h3_string_toint`, `h3_int_tostring`, etc. Requires `plv8`. |
| `quadbin` | 19 functions: `quadbin_fromlonglat`, `quadbin_polyfill`, `quadbin_kring`, `quadbin_toparent`, ... |
| `tiler` | `create_simple_tileset`, `create_point_aggregation_tileset`, `create_spatial_index_tileset` |

**Not on Postgres AT:** no `accessors`, `clustering`, `constructors`, `cpg`, `data` (enrichment), `geohash`, `http_request`, `import`, `lds` (geocoding / routing), `measurements`, `placekey`, `processing`, `random`, `raster`, `retail`, `routing`, `s2`, `statistics`, `telco`, `transformations`.

If the user wants enrichment, geocoding, Moran's I, GWR, or buffers on Postgres: **enrichment / LDS / statistics aren't available** — push the user to BigQuery / Snowflake / Redshift if they need them. Buffers, transformations, accessors, measurements: use PostGIS native (`ST_Buffer`, `ST_Area`, `ST_X`, etc.).

## Spatial type system — LLM traps

- **PostGIS has both `geometry` and `geography`**, lowercase. SRID matters: most CARTO AT functions assume **WGS84 (EPSG:4326)** input. Mixed-SRID joins error loudly; mixed `geometry`-vs-`geography` silently coerces with subtle distance differences.
- **Cast to `geography` for distance in metres.** Native `ST_Distance` on `geometry` returns the SRID's unit — for 4326 that's degrees, which is useless for thresholds.
- **H3 is `VARCHAR(16)`** (string form). `carto.h3_string_toint` / `carto.h3_int_tostring` convert to `INT` — note `INT`, not `BIGINT` (PG-specific narrowing).
- **Quadbin is `BIGINT`** — same as every other engine that ships quadbin.
- **Identifier case-folding** bites LLMs that paste BQ/Snowflake-cased examples. Always lowercase or double-quote.

## Spatial indexing

Postgres natives, choose by data shape:

| Index | Use for |
|---|---|
| **GiST** on `geometry`/`geography` | Standard spatial index. The right default for joins, `ST_DWithin`, `ST_Intersects`. |
| **SP-GiST** | Point-only datasets. Faster than GiST for point-in-polygon. |
| **BRIN** | Very large tables clustered by location. Cheap to maintain; coarser. |
| **B-tree** on H3 / quadbin VARCHAR/BIGINT | The right index for joins on a pre-binned spatial-index column. |

```sql postgres
CREATE INDEX events_geom_gix  ON events       USING GIST (geom);
CREATE INDEX events_h3_btree ON events_h3    (h3);
```

Without a GiST index, `ST_DWithin` does a full table scan — the #1 cause of "PostGIS is slow."

## Performance defaults

- **GiST or SP-GiST on every queryable geometry column.** Not optional for production.
- **Cast to `geography` for metre-true distance**; cast back to `geometry` for projection-aware operations.
- **Pre-bin large point tables to quadbin** (no `plv8` dependency, works on managed Postgres without admin rights).
- **`CLUSTER table USING <gist_index>`** after large loads to co-locate physically.

## Module gaps vs flagship (BigQuery)

The narrowest AT module set of any engine. The skill should warn:

- **No enrichment** (`data`) → CARTO Data Observatory subscriptions can't be applied via SQL on Postgres AT today; do enrichment on BQ/Snowflake/Redshift, then materialize back to Postgres if needed.
- **No statistics** → Moran's I, GWR, Getis-Ord aren't on Postgres AT. PostGIS has nothing equivalent.
- **No LDS** → geocoding / isolines / routing not available on Postgres AT.

## Always-on guidance

- **Always qualify with the `carto` schema and use lowercase.** `carto.h3_fromgeogpoint(...)`.
- **Verify `plv8` is installed** before promising H3 functions to the user — on managed Postgres (RDS / Cloud SQL) `plv8` may or may not be available depending on the provider's extension allowlist.
- **For ad-hoc queries** use `carto sql query`; for materialization use `carto sql job` (see [`../carto-query-datawarehouse/references/sql-jobs-and-caching.md`](../carto-query-datawarehouse/references/sql-jobs-and-caching.md)).
