---
name: carto-spatial-sql-databricks
description: Write spatial SQL on Databricks (Lakehouse, Photon). CARTO's Analytics Toolbox here is a thin layer — it adds enrichment, LDS, quadbin indexing, and spatial statistics, but H3 and ST_* primitives come from Databricks' own native spatial SQL. Covers the split and the LLM traps.
license: MIT
---

# carto-spatial-sql-databricks

CARTO's Analytics Toolbox (AT) on Databricks is **in Beta** and intentionally narrow: it ships enrichment, LDS, quadbin, and statistics — and **delegates H3 and ST_* primitives to Databricks' native spatial SQL**. This skill covers the split and the gotchas.

## When to use this skill

- The connected warehouse is Databricks (`carto connections list --json | jq '.[] | select(.provider=="databricks")'`).
- You're calling CARTO `carto.carto.*` functions OR Databricks-native `h3_*` / `ST_*`.
- You're choosing between H3 string-form and int-form storage.
- You're materializing a workflow output and want the right Z-order / clustering.

## Analytics Toolbox on Databricks (Beta)

Installed into **Unity Catalog** via a SQL Warehouse. Default catalog/schema: **`carto.carto`** (configurable). Call form: `<catalog>.<schema>.<FUNCTION>(...)`.

Prereqs:
- Unity Catalog enabled on the workspace.
- A SQL Warehouse.
- Grants for `CREATE CONNECTION`, `CREATE CATALOG`, `CREATE MANAGED STORAGE`.

See [getting-access](https://docs.carto.com/data-and-analysis/analytics-toolbox-for-databricks/getting-access).

```sql databricks
SELECT carto.carto.QUADBIN_FROMLONGLAT(ST_X(geom), ST_Y(geom), 16) AS quadbin
FROM my_catalog.my_schema.events;
```

## Modules shipped (narrow set)

| Module | What's in it |
|---|---|
| `data` | `ENRICH_POINTS`, `ENRICH_POLYGONS`, `ENRICH_GRID` (grid_type accepts `'h3'` or `'quadbin'`) |
| `lds` | `GEOCODE_TABLE`, `CREATE_ISOLINES`, `CREATE_ROUTES`, quota helpers |
| `quadbin` | Full 17-function suite (`QUADBIN_FROMLONGLAT`, `QUADBIN_POLYFILL`, `QUADBIN_KRING`, `QUADBIN_TOPARENT`, ...) |
| `statistics` | `MORANS_I_H3` / `_QUADBIN`, `LOCAL_MORANS_I_*`, `GETIS_ORD_*`, `GWR_GRID`, `P_VALUE`, `CREATE_SPATIAL_COMPOSITE_UNSUPERVISED` |

**That's it.** No `h3` module, no `accessors`, no `transformations`, no `tiler`, no `processing`. Defaults for everything else: **Databricks-native spatial SQL** (`h3_longlatash3string`, `h3_distance`, `ST_BUFFER`, `ST_INTERSECTS`, etc., GA in Photon-enabled DBR 13.3+).

## Spatial type system — LLM traps

- **CARTO does NOT ship an `h3` AT module on Databricks.** The docs URL `analytics-toolbox-for-databricks/reference/h3` 404s — confirmed gap. Use **Databricks-native h3_***.
- **Databricks has only `GEOMETRY` (planar WKB)**, no `GEOGRAPHY` type. Distances default to planar units; for metres on lat/lng input use `ST_DISTANCESPHEROID` or project first.
- **H3 has two storage forms** on Databricks: `BIGINT` from `h3_longlatash3`, and `STRING` from `h3_longlatash3string`. CARTO **statistics functions take the STRING form** — using BIGINT will fail type-matching.
- **Quadbin is `BIGINT`** (CARTO AT), same as every other engine that ships quadbin.
- The interop pattern: produce H3 with native `h3_longlatash3string`, then feed it into CARTO `MORANS_I_H3` etc.

## Spatial indexing

Databricks doesn't expose explicit spatial indexes. Performance hinges on file layout:

- **Z-order (or Liquid Clustering)** the fact table on the H3 string column at the working resolution.
- **Partition by date** for time-windowed analytics; Z-order on H3 inside the partition.
- For Delta tables that will join repeatedly on the same H3 resolution, materializing a column at that exact resolution (`h3_longlatash3string(lng, lat, 9)`) is the lever.

```sql databricks
OPTIMIZE my_catalog.my_schema.events ZORDER BY (h3);
```

CARTO doesn't publish a Databricks-specific spatial-index page — the recipe above is the practical default.

## Performance defaults

- **Use Databricks-native `h3_*` and `ST_*` for primitives** — they're Photon-accelerated. CARTO AT calls (especially statistics) run as SQL UDFs; reserve them for what the native doesn't cover.
- **Pre-compute H3 strings once** at ingest; don't recompute per query.
- **Partition + Z-order > recomputing on the fly** for any join you'll run repeatedly.

## Module gaps vs flagship (BigQuery)

Biggest subset of all engines. Missing on Databricks:

| Missing module | What to use instead |
|---|---|
| `h3` | Databricks-native `h3_*` (Photon-accelerated, GA in DBR 13.3+) |
| `accessors`, `constructors`, `measurements`, `processing`, `transformations` | Databricks-native `ST_*` |
| `tiler` | No equivalent; vector tilesets aren't produced on Databricks today |
| `clustering`, `random`, `placekey`, `raster`, `retail`, `s2`, `cpg`, `geohash`, `telco`, `http_request`, `import` | No equivalent on Databricks AT |
| `routing` | Folded into `lds` |

## Always-on guidance

- **Default to Databricks-native for primitives.** Only reach for `carto.carto.*` for enrichment, LDS, quadbin indexing, and statistics.
- **String-form H3 for CARTO statistics functions.** Native BIGINT H3 won't type-match.
- **Photon must be enabled** for native `ST_*` / `h3_*` to perform — verify on the SQL Warehouse settings if queries look slow.
- **Confirm the catalog/schema** — default `carto.carto` is configurable at install; the CLI's `connections list` will reflect the install location.
