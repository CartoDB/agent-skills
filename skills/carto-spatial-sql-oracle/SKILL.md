---
name: carto-spatial-sql-oracle
description: Write spatial SQL on Oracle. **CARTO's Analytics Toolbox is NOT available on Oracle today** — Oracle is supported only as a connection target for Builder / Workflows / Maps. This skill documents the gap and steers LLMs to native Oracle Spatial (`SDO_*`) syntax instead.
license: MIT
---

# carto-spatial-sql-oracle

**CARTO's Analytics Toolbox does not ship on Oracle today.** Oracle is supported as a *connection target* for Builder, Workflows, and Maps — agents can read tables, run native SQL, and visualize the results — but `carto.*` functions don't exist on this engine. This skill is about routing intent correctly when an LLM lands on an Oracle connection.

## When to use this skill

- The connected warehouse is Oracle (`carto connections list --json | jq '.[] | select(.provider=="oracle")'`).
- The user (or another skill) is about to emit `carto.H3_FROMGEOGPOINT` or any `carto.*` call on Oracle — **stop and warn**.
- The user wants spatial SQL on Oracle — translate intent to native `SDO_*`.

## Analytics Toolbox status

**Not available.** The CARTO Analytics Toolbox overview page lists Oracle under "Coming soon" and explicitly states: *"connections are supported for workflows and visualization, but the Analytics Toolbox is not yet available for Oracle."* There is no per-engine AT page for Oracle on docs.carto.com.

Verify before promising any CARTO function:

```bash
carto connections describe <oracle-connection-name>
# No carto.* schema will appear.
```

## What CARTO supports on Oracle

- **Connect** to an Oracle DB as a data source (`carto connections create` / `list`).
- **Read** tables / views and use them as Builder map layers and Workflows inputs.
- **Run native Oracle Spatial SQL** through `carto sql query` / `carto sql job` against the connection.
- **No** enrichment, no H3/quadbin from CARTO, no LDS, no statistics, no tilesets server-side. These either run elsewhere (a BQ/Snowflake/Redshift sidecar) or are out of scope for an Oracle-only workflow.

## Native Oracle Spatial syntax — what LLMs need

Oracle Spatial uses **`SDO_GEOMETRY`** and an `SDO_*` function family. It is NOT PostGIS/ANSI-`ST_*` compatible — an LLM emitting `ST_INTERSECTS` against Oracle will fail at parse time.

| Intent | Oracle Spatial |
|---|---|
| Construct a point | `SDO_GEOMETRY(2001, 4326, SDO_POINT_TYPE(lng, lat, NULL), NULL, NULL)` |
| Test intersection | `SDO_RELATE(a, b, 'mask=ANYINTERACT') = 'TRUE'` |
| Distance (metres on geodetic SRID 4326) | `SDO_GEOM.SDO_DISTANCE(a, b, 0.005)` |
| Buffer | `SDO_GEOM.SDO_BUFFER(geom, distance_m, tolerance)` |
| Area | `SDO_GEOM.SDO_AREA(geom, tolerance, 'unit=SQ_M')` |

The **`tolerance` parameter** is mandatory on every `SDO_GEOM.*` call (typically `0.005` for metre-scale work on SRID 4326). LLMs that omit it from a PostGIS-style port will hit `ORA-13207` / `ORA-13348`.

## Spatial indexing

Oracle's spatial index is an R-tree, created via the `SPATIAL_INDEX` indextype:

```sql oracle
CREATE INDEX events_geom_sidx
ON events(geom)
INDEXTYPE IS MDSYS.SPATIAL_INDEX
PARAMETERS('sdo_indx_dims=2, layer_gtype=POINT');
```

The metadata row in `USER_SDO_GEOM_METADATA` must exist before index creation — Oracle reads it at index time for bounding-box and SRID. This is a footgun if the table was loaded without metadata.

## Performance defaults

- **Always populate `USER_SDO_GEOM_METADATA`** before creating a spatial index or running any `SDO_GEOM.*` function.
- **`SDO_FILTER` is cheap; `SDO_RELATE` is expensive.** For predicate joins, lead with `SDO_FILTER` to prune candidates, then `SDO_RELATE` to refine.
- Oracle's optimizer needs `GATHER_TABLE_STATS` (or auto-stats) on spatial-indexed tables to pick the index — neglecting stats degrades joins to nested-loop scans.

## Routing intent away from this engine

When a user wants enrichment, H3/quadbin binning, statistics (Moran's I / GWR), or geocoding on Oracle:

> "CARTO's Analytics Toolbox isn't available on Oracle today. Options: (a) run the spatial-analytics part on a BigQuery / Snowflake / Redshift connection and write the result back to Oracle, or (b) stick to native Oracle Spatial (`SDO_*`) — no CARTO functions."

Don't silently emit `carto.*` SQL that will fail.

## Always-on guidance

- **Never call `carto.<FUNCTION>` on Oracle.** No such schema exists.
- **Set SRID 4326 in every `SDO_GEOMETRY` constructor** unless the data is explicitly in a projected CRS — Oracle won't infer it.
- **Always pass `tolerance` to `SDO_GEOM.*`** functions; the parameter is non-optional.
- **For ad-hoc queries** use `carto sql query <oracle-connection> "<SDO_* SQL>"`. The CLI just transports SQL; it doesn't validate dialects.
