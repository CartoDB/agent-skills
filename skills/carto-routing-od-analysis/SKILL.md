---
name: carto-routing-od-analysis
description: Builds routing and origin-destination analysis workflows in CARTO. Triggers when the user mentions routing, route calculation, travel time, travel distance, OD matrix, origin-destination, isoline, isochrone, isodistance, catchment area, reachable area, drive time polygon, walk time polygon, service area, accessibility analysis, travel time matrix, distance matrix, commute patterns, trip flow, OD flow, mobility patterns, taxi trips, ride patterns, route geometry, shortest path, network distance, or wants to compute routes, generate isolines, build travel matrices, or analyze movement patterns between origins and destinations.
license: MIT
---

# Routing and Origin-Destination Analysis

Computes routes, travel time/distance matrices, and isoline catchment areas (driving, walking and other modes), plus OD flow pattern analysis via spatial indexing. Two access paths, by scale:

- **Single / ad-hoc (MCP-first)**: for one route, one location's isolines, or a small OD matrix, the CARTO MCP tools `route`, `calculate_isolines`, and `calculate_od_matrix` answer directly (each also has a `capabilities` operation to list supported modes/range types). No workflow needed. These run on any MCP host, including sandboxed chat hosts where the CLI can't. Prefer them for interactive requests.
- **Table-scale / repeatable**: for computing over a whole table or a reusable pipeline, use the Workflow patterns below. Load `carto-create-workflow` for the development process, JSON structure, and validation — it covers both paths (MCP `create_workflow` / `validate_workflow` / `run_workflow` when attached; the `carto workflows` CLI otherwise; routing signals in `carto-basics/references/access-paths.md`).

Over an API-token MCP session the ad-hoc/authoring tools are hidden (read/discovery only) — fall back to the CLI or reconnect over OAuth.

---

## Instructions

Three main workflow patterns exist. Choose based on the use case:

| Pattern | Component | Use when |
|---------|-----------|----------|
| Isoline/Isochrone | `native.isolines` | You need catchment polygons around locations (e.g. "everywhere reachable within 10 min") |
| OD Matrix | `native.createroutingmatrix` | You need travel time/distance between every origin-destination pair (analytics, no geometry) |
| Route Creation | `native.createroutes` | You need actual route line geometries between OD pairs (visualization, detailed path) |

None of these exist on PostgreSQL connections: there, use the ad-hoc MCP tools above for small requests, or offer `native.buffer` catchments or Pattern D. Create Routing Matrix is also missing on Databricks SQL warehouse connections. Modes and extra options depend on the org's LDS provider: read them with `carto workflows components get <name> --connection <conn> --json` (MCP: `read_workflow_components method=get`) before filling the node, and use the `mode` values exactly as listed.

---

### Pattern A: Isoline/Isochrone Generation

Pipeline:
```
Source Points -> (Filter) -> Isolines -> (Polyfill / Enrich) -> Save
```

#### Step A1: Load Source Points

Use `native.gettablebyname` to load locations (stores, stations, facilities).

**Success**: Table with a geometry column and a unique location identifier.

#### Step A2: Generate Isolines

Use `native.isolines` with:

| Input | Description | Example |
|-------|-------------|---------|
| `mode` | Travel mode, lowercase. Allowed values depend on the org's isolines provider (TomTom has no `walk`); read them with `components get` | `car` or `walk` |
| `type` | What the range measures | `time` or `distance` |
| `range` | Threshold value | Seconds for time (e.g. `600` = 10 min), meters for distance (e.g. `5000` = 5 km) |

**Success**: Each input row gets its reachable-area polygon in `geom`. The input geometry column is dropped (kept as `orig_geom` on recent Analytics Toolbox versions) and `carto_isoline_metadata` holds per-row provider errors.

#### Step A3: Post-Processing (optional)

Common follow-ups after isoline generation:
- **Polyfill + Enrich**: Convert isoline polygons to H3 with `native.h3polyfill`, then enrich with demographics or POI data (see trade-area-analysis skill).
- **Overlap analysis**: Use `native.spatialjoin` to find which isolines overlap, identifying areas served by multiple locations.
- **Coverage union**: Use `native.summarize` with `geom,combine` (output `geom_union`) to merge all isolines into one footprint, or `native.groupby` with `geom,combine` to merge per group. On Snowflake and Redshift `combine` collects the polygons rather than dissolving them. `native.summarize` is not available on Oracle.

#### Step A4: Save

Use `native.saveastable` to persist isoline polygons or enriched results, then validate and upload the workflow (MCP `create_workflow` / `validate_workflow`, or `carto workflows create`).

---

### Pattern B: OD Matrix (Travel Time/Distance)

Pipeline:
```
Origins Table -> ┐
                 ├-> OD Matrix -> (Filter/Aggregate) -> Save
Destinations Table -> ┘
```

#### Step B1: Load Origins and Destinations

Use two `native.gettablebyname` nodes -- one for origins, one for destinations. Both need geometry columns.

**Success**: Two tables, each with point geometries and unique identifiers.

#### Step B2: Compute OD Matrix

Use `native.createroutingmatrix` with:

| Input | Description |
|-------|-------------|
| `originstable` / `destinationstable` | Table inputs; the edges' target handles use these names |
| `originsgeomcolumn` / `destinationsgeomcolumn` | Point geometry column in each table (required) |
| `mode` | An option `components get` lists for this org; it varies by routing provider (e.g. `Car`, `Pedestrian`, `Driving`, `Walking`) |

**Output columns**: every origin column prefixed `origin_` (e.g. `origin_store_id`, `origin_geom`), every destination column prefixed `destination_`, plus `route_duration` (seconds), `route_distance` (meters) and `carto_routing_matrix_metadata` (per-pair provider errors).

**Success**: One row per origin-destination pair with travel time and distance.

#### Step B3: Filter or Aggregate (optional)

Common post-processing:
- **Nearest destination**: Use `native.groupby` grouped by the origin id (`origin_<id>`) with `route_duration,min` (output `route_duration_min`), then join back on origin id and duration to get the nearest destination.
- **Threshold filter**: Use `native.where` to keep only pairs within a limit (e.g. `route_duration < 1800` for 30 minutes, or `route_distance < 5000` for 5 km).
- **Accessibility score**: Count destinations reachable within a threshold per origin using `native.groupby`.

#### Step B4: Save

Use `native.saveastable`, then validate and upload (MCP `create_workflow` or `carto workflows create`).

---

### Pattern C: Route Geometries

Pipeline:
```
Origins + Destinations -> Cross Join (or Join on a pairing key) -> Create Routes -> Save
```

#### Step C1: Load and Pair Origins and Destinations

Load both tables with `native.gettablebyname`. Create Routes reads one table where each row holds an origin and a destination point, so pair them with `native.crossjoin` (every pair) or `native.joinv2` on a pairing key. After a cross join the destination geometry is `<col>_joined`, or `r_<col>` on Databricks cluster connections, where `native.crossjoin` prefixes columns with `l_` / `r_`.

#### Step C2: Compute Routes

Use `native.createroutes` with:

| Input | Description |
|-------|-------------|
| `source` | Table with one origin-destination pair per row (target handle `source`) |
| `origin` / `destination` | The two point geometry columns of that table (must differ) |
| `newcol` | Name of the route column (default `geom`) |
| `mode` | An option `components get` lists for this org; it varies by routing provider (e.g. `Car`, `Pedestrian`, `Driving`, `Walking`) |

**Output**: One route line per row in `newcol` (default `geom`) plus `carto_routing_metadata`, the provider's response as a JSON string. There are no duration or distance columns; use Create Routing Matrix when you need them.

#### Step C3: Save

Use `native.saveastable`, then validate and upload (MCP `create_workflow` or `carto workflows create`).

---

### Pattern D: OD Flow Analysis (Grid-Based)

For analyzing trip/movement patterns at scale (e.g. taxi trips, bike rides, commute flows) without calling routing APIs.

Pipeline:
```
Trip Data -> H3 (origin) + H3 (destination) -> Group By (origin_h3, dest_h3) -> Save
```

#### Step D1: Load Trip Data

Use `native.gettablebyname`. The table should have both origin and destination coordinates (e.g. pickup_lon/lat, dropoff_lon/lat).

#### Step D2: Index Origins and Destinations to H3

If the table has coordinates, build each point with `native.geogpoint` (`lat`, `lon`; output column `geom`), renaming `geom` with `native.renamecolumn` before building the second one.

Run `native.h3frompoint` on the origin geometry and rename `h3` to `origin_h3` with `native.renamecolumn`, then run it on the destination geometry and rename `h3` to `destination_h3`. Each call writes a column named `h3`, so skipping the rename fails on a duplicate column. `native.h3frompoint` is not available on Redshift; use `native.quadbinfrompoint` there (it writes `quadbin`, same renaming).

#### Step D3: Aggregate Flows

Use `native.groupby` to count trips per (origin_h3, destination_h3) pair:
- **Group by**: `origin_h3, destination_h3`
- **Aggregation**: `origin_h3,count` (trip count per OD pair)

**Success**: One row per unique OD cell pair with trip count -- ready for flow visualization.

#### Step D4: Save

Use `native.saveastable`.

---

## Gotchas

- **Provider casing & SQL dialect.** This skill uses lowercase column names (`route_duration`, `route_distance`, `origin_<col>`, `destination_<col>`, `origin_h3`, etc.) — BigQuery / Databricks / Postgres / Redshift convention. On Snowflake, reference these UPPERCASE (`ROUTE_DURATION`, `ORIGIN_H3`, ...). See `carto-create-workflow/references/providers/<provider>.md` for casing rules and SQL dialect equivalents.
- Isolines and routing components consume **LDS (Location Data Services) quota**. Check available quota with `LDS_QUOTA_INFO` before bulk operations. Buffers (`native.buffer`) do not consume LDS quota and are a free alternative for simple circular catchments.
- OD matrices grow **quadratically**: N origins x M destinations = N*M rows. Filter or sample inputs to keep the matrix manageable. For 1000 origins x 1000 destinations, you get 1 million rows.
- **Walking mode** has a much shorter practical range than driving. Walking isolines beyond 20-30 minutes or OD matrices beyond a few kilometers produce unreliable or empty results.
- **Route geometries can be large**. For pure analytics (time/distance only), prefer the OD matrix (Pattern B) over full routes (Pattern C) to reduce data volume.
- **Time of day** affects driving results. The departure-time input is provider-prefixed (`here_departure_time`, `tomtom_departure_time`, `traveltime_departure_time`, format `YYYY-MM-DDThh:mm:ss`) and only exists on Isolines and Create Routing Matrix; read the exact name with `components get`. Otherwise results reflect typical conditions.
- **Isoline polygons may overlap** for nearby locations. If enriching afterwards, polyfill to a spatial index and deduplicate cells to avoid double-counting.
- For **OD flow visualization** (Pattern D), use H3 cell center points rather than raw coordinates for cleaner aggregation and visualization. A coarser resolution (e.g. H3 res 7-8) produces more meaningful flow patterns than fine resolutions.
- **LDS access and quota are checked when the workflow runs.** If the org has no LDS quota or provider for the service, the run fails on the isolines or routing node: report that node and its error to the user.

---

## Reference Templates

| Resource | Description |
|----------|-------------|
| [Scalable Routing Tutorial](https://academy.carto.com/creating-workflows/step-by-step-tutorials/how-to-run-scalable-routing-analysis-the-easy-way) | Step-by-step scalable routing in Workflows |
| [OD Patterns Tutorial](https://academy.carto.com/creating-workflows/step-by-step-tutorials/analyzing-origin-and-destination-patterns) | Analyzing origin-destination patterns (NYC taxi example) |
| [Routing Module (BQ)](https://academy.carto.com/advanced-spatial-analytics/spatial-analytics-for-bigquery/step-by-step-tutorials/using-the-routing-module) | Using the routing module with Analytics Toolbox for BigQuery |
| [Isoline Generation Template](https://academy.carto.com/creating-workflows/workflow-templates/generating-new-spatial-data) | Generating isochrones via Workflow templates |
| [Trade Area Isolines (BQ)](https://academy.carto.com/advanced-spatial-analytics/spatial-analytics-for-bigquery/step-by-step-tutorials/generating-trade-areas-based-on-drive-walk-time-isolines) | Drive/walk-time isoline trade areas for BigQuery |
| [Trade Area Isolines (SF)](https://academy.carto.com/advanced-spatial-analytics/spatial-analytics-for-snowflake/step-by-step-tutorials/generating-trade-areas-based-on-drive-walk-time-isolines) | Drive/walk-time isoline trade areas for Snowflake |

---

## Common Variations

| Variant | How |
|---------|-----|
| Service area coverage | One Isolines node per range (`range` takes one value, e.g. `300`, `600`, `900` seconds) -> merge each with `native.summarize` `geom,combine` -> measure population covered |
| Nearest facility | OD matrix -> group by origin id -> `route_duration,min` -> join back to get the nearest destination id |
| Accessibility scoring | OD matrix -> filter by threshold -> count destinations per origin -> score by reachable count |
| Fleet route planning | Create Routing Matrix between depot and delivery points for `route_duration` / `route_distance`; Create Routes only for the line geometries (one route per row, it does not order stops) |
| Commute flow analysis | Trip data -> H3 origin + H3 destination -> group by OD pair -> count -> visualize top flows |
| Multi-modal comparison | Run isolines twice (car + walk) -> compare coverage polygons -> identify transit-dependent areas |
