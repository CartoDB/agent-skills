---
name: carto-spatial-sql-redshift
description: Write spatial SQL on Amazon Redshift using CARTO's Analytics Toolbox. The biggest gotcha here is the absence of a standalone H3 module — use quadbin for binning on Redshift. Covers the AT modules that DO ship, the 2D-only geometry quirks, and the sort-key / dist-style pattern.
license: MIT
---

# carto-spatial-sql-redshift

CARTO's Analytics Toolbox (AT) on Redshift covers most modules **but not `h3`** — the standalone H3 module is absent. **Use `quadbin` for spatial binning on Redshift.** H3 is only available indirectly inside the `lds` module's isoline functions.

## When to use this skill

- The connected warehouse is Redshift (`carto connections list --json | jq '.[] | select(.provider=="redshift")'`).
- You're calling `carto.*` AT functions on Redshift.
- The user asks for an "H3 grid on Redshift" — needs the routing flag (use quadbin instead).
- You're picking sort keys / distribution style for a spatial fact table.

## Analytics Toolbox on Redshift

Three install paths per [getting-access](https://docs.carto.com/data-and-analysis/analytics-toolbox-for-redshift/getting-access):

- **Install into the customer's Redshift database** (standard).
- **AWS VPC installation** (Self-Hosted CARTO only).
- **Open-source core package** — limited modules, free.

Functions land under a `carto.*` schema. Call form: `carto.<FUNCTION>(...)`.

```sql redshift
SELECT carto.QUADBIN_FROMLONGLAT(ST_X(geom), ST_Y(geom), 16) AS quadbin_index
FROM analytics.events;
```

## Modules shipped

| Module | What's in it |
|---|---|
| `clustering` | K-means on spatial points |
| `constructors` | `carto.ST_*` constructors |
| `data` | Enrichment (`ENRICH_POINTS` / `_POLYGONS` / `_GRID`). **`ENRICH_GRID` accepts quadbin only — no h3.** |
| `http_request` | Call out from SQL |
| `import` | Load remote files via URL |
| `lds` | Geocoding + isolines. **H3-internal isoline functions live here** (`H3_ISOLINE`, `CREATE_H3_ISOLINES`) — the only H3 surface on Redshift. |
| `placekey` | Placekey ↔ H3 |
| `processing` | Delaunay, Voronoi, polygonization |
| `quadbin` | Full 19-function suite (`BIGINT`-typed) |
| `random` | Random points within geometry |
| `s2` | Google S2 cells |
| `statistics` | Moran's I, Getis-Ord, GWR (on quadbin) |
| `tiler` | `create_simple_tileset`, `create_spatial_index_tileset` |
| `transformations` | Buffer, hull, simplify |

**Not shipped on Redshift:** standalone `h3`, `accessors`, `cpg`, `geohash`, `measurements`, `raster`, `retail`, `routing` (folded into `lds`), `telco`.

## Spatial type system — LLM traps

- **No H3 module on Redshift.** A request for `carto.H3_FROMGEOGPOINT` fails. Use `carto.QUADBIN_FROMLONGLAT` for spatial binning.
- **Redshift has both `GEOMETRY` and `GEOGRAPHY`**, but it was historically 2D-only. **Z and M dimensions aren't supported across all `ST_*` functions** — confirm function-by-function before promising 3D handling.
- **SRID defaults to 0 (unknown)** on a fresh `GEOMETRY`. Many functions return NULL or error on mismatched SRIDs. **Always set SRID explicitly with `ST_SetSRID`.**
- Mixing `GEOMETRY` and `GEOGRAPHY` requires explicit casts — silent coercion does not happen on Redshift.
- **Quadbin is `BIGINT`** — same as every other engine.
- `ENRICH_GRID(grid_type, ...)` accepts **`'quadbin'` only** on Redshift; passing `'h3'` errors. (On BigQuery / Databricks the same function accepts both.)

## Spatial indexing

Redshift has no GiST/R-tree. Acceleration comes from table layout:

- **Sort key** on the quadbin column for fact tables (`SORTKEY(quadbin)`). Compound vs interleaved depends on the join shape — compound is the right default.
- **Distribution style `KEY` on quadbin** for co-located joins (both tables distributed the same way) — eliminates network shuffle on spatial joins.
- For point-and-click analytics queries on small dimension tables, `DISTSTYLE ALL` is fine.

```sql redshift
CREATE TABLE analytics.events_quadbin
DISTSTYLE KEY DISTKEY (quadbin)
COMPOUND SORTKEY (quadbin)
AS
SELECT carto.QUADBIN_FROMLONGLAT(ST_X(geom), ST_Y(geom), 16) AS quadbin, *
FROM analytics.events_raw;
```

CARTO publishes a concept page at [key-concepts/spatial-indexes](https://docs.carto.com/data-and-analysis/analytics-toolbox-for-redshift/key-concepts/spatial-indexes), but Redshift-specific sort/dist examples aren't in docs — the recipe above is the practical pattern.

## Performance defaults

- **Pre-bin to quadbin once** at ingest; sort and distribute by it.
- **Redshift Serverless bills per query** — favor `carto sql job` (one long job) over many small `carto sql query` calls for batch work.
- **No explicit `CREATE INDEX`** for spatial in Redshift — sort key + distribution style are the only knobs.
- For Builder tilesets, `CREATE_SPATIAL_INDEX_TILESET` over `CREATE_SIMPLE_TILESET` on very large data.

## Module gaps vs flagship (BigQuery)

| Missing | What to do |
|---|---|
| `h3` | Use `quadbin` everywhere. The only H3 on Redshift is the `lds` isoline helper. |
| `accessors`, `measurements` | Use Redshift-native `ST_X`, `ST_Y`, `ST_Distance`. |
| `routing` (standalone) | Use `lds`. |
| `cpg`, `geohash`, `raster`, `retail`, `telco` | Not available on Redshift; flag the gap. |

## Always-on guidance

- **If the user asks for H3 binning on Redshift, propose quadbin instead** and call out the gap explicitly. Don't fail silently with "function not found."
- **Always `ST_SetSRID(..., 4326)` on constructed geometries** — Redshift's default SRID 0 is a silent footgun.
- **Use `carto sql job`, not `sql query`,** for tile generation, enrichment, and any statistics function on >1M rows. Redshift Serverless billing rewards larger batched jobs.
