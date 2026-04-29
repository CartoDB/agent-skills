---
name: carto-pattern-routing-od-analysis
description: Builds routing and origin-destination analysis workflows in CARTO. Triggers when the user mentions routing, route calculation, travel time, travel distance, OD matrix, origin-destination, isoline, isochrone, isodistance, catchment area, reachable area, drive time polygon, walk time polygon, service area, accessibility analysis, travel time matrix, distance matrix, commute patterns, trip flow, OD flow, mobility patterns, taxi trips, ride patterns, route geometry, shortest path, network distance, or wants to compute routes, generate isolines, build travel matrices, or analyze movement patterns between origins and destinations.
license: MIT
---

# Routing and Origin-Destination Analysis

Builds CARTO Workflows that compute routes, travel time/distance matrices, and isoline catchment areas. Supports driving and walking modes. Also covers OD flow pattern analysis using spatial indexing.

**Prerequisites**: Load `carto-create-workflow` for the development process, JSON structure, and validation commands.

---

## Instructions

Three main workflow patterns exist. Choose based on the use case:

| Pattern | Component | Use when |
|---------|-----------|----------|
| Isoline/Isochrone | `native.isolines` | You need catchment polygons around locations (e.g. "everywhere reachable within 10 min") |
| OD Matrix | `native.routesodmatrix` | You need travel time/distance between every origin-destination pair (analytics, no geometry) |
| Route Creation | `native.routes` | You need actual route line geometries between OD pairs (visualization, detailed path) |

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
| `mode` | Travel mode | `car` or `walk` |
| `range_type` | What the range measures | `time` or `distance` |
| `range` | Threshold value | Seconds for time (e.g. `600` = 10 min), meters for distance (e.g. `5000` = 5 km) |

**Success**: Each input point has an associated polygon geometry representing the reachable area.

#### Step A3: Post-Processing (optional)

Common follow-ups after isoline generation:
- **Polyfill + Enrich**: Convert isoline polygons to H3 with `native.h3polyfill`, then enrich with demographics or POI data (see trade-area-analysis skill).
- **Overlap analysis**: Use `native.spatialjoin` to find which isolines overlap, identifying areas served by multiple locations.
- **Coverage union**: Use `native.dissolve` to merge all isoline polygons into a single coverage footprint.

#### Step A4: Save

Use `native.saveastable` to persist isoline polygons or enriched results.

**Success**: Validated workflow uploadable via `carto workflows create`.

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

Use `native.routesodmatrix` with:

| Input | Description |
|-------|-------------|
| `mode` | `car` or `walk` |
| Origins input | Connected from the origins table node |
| Destinations input | Connected from the destinations table node |

**Output columns**: `origin_id`, `destination_id`, `duration_s`, `distance_m`.

**Success**: One row per origin-destination pair with travel time and distance.

#### Step B3: Filter or Aggregate (optional)

Common post-processing:
- **Nearest destination**: Use `native.groupby` to find the minimum `duration_s` per origin, then join back to get the nearest destination.
- **Threshold filter**: Use `native.where` to keep only pairs within a time/distance limit (e.g. `duration_s < 1800` for 30-min threshold).
- **Accessibility score**: Count destinations reachable within a threshold per origin using `native.groupby`.

#### Step B4: Save

Use `native.saveastable`.

**Success**: Validated workflow uploadable via `carto workflows create`.

---

### Pattern C: Route Geometries

Pipeline:
```
Origins Table -> ┐
                 ├-> Routes -> Save
Destinations Table -> ┘
```

#### Step C1: Load Origins and Destinations

Same as Pattern B -- two `native.gettablebyname` nodes with point geometries.

#### Step C2: Compute Routes

Use `native.routes` with:

| Input | Description |
|-------|-------------|
| `mode` | `car` or `walk` |
| Origins input | Connected from the origins table node |
| Destinations input | Connected from the destinations table node |

**Output**: Route line geometries with `duration_s` and `distance_m` attributes.

**Success**: One route geometry per OD pair, visualizable on a map.

#### Step C3: Save

Use `native.saveastable`.

**Success**: Validated workflow uploadable via `carto workflows create`.

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

Use `native.selectexpression` to compute H3 cells for both origin and destination points:
- Origin H3: derive from pickup coordinates
- Destination H3: derive from dropoff coordinates

Alternatively, if the data has separate geometry columns, use `native.h3frompoint` for each.

#### Step D3: Aggregate Flows

Use `native.groupby` to count trips per (origin_h3, destination_h3) pair:
- **Group by**: `origin_h3, destination_h3`
- **Aggregation**: `origin_h3,count` (trip count per OD pair)

**Success**: One row per unique OD cell pair with trip count -- ready for flow visualization.

#### Step D4: Save

Use `native.saveastable`.

---

## Gotchas

- Isolines and routing components consume **LDS (Location Data Services) quota**. Check available quota with `LDS_QUOTA_INFO` before bulk operations. Buffers (`native.buffer`) do not consume LDS quota and are a free alternative for simple circular catchments.
- OD matrices grow **quadratically**: N origins x M destinations = N*M rows. Filter or sample inputs to keep the matrix manageable. For 1000 origins x 1000 destinations, you get 1 million rows.
- **Walking mode** has a much shorter practical range than driving. Walking isolines beyond 20-30 minutes or OD matrices beyond a few kilometers produce unreliable or empty results.
- **Route geometries can be large**. For pure analytics (time/distance only), prefer the OD matrix (Pattern B) over full routes (Pattern C) to reduce data volume.
- **Time-of-day** affects driving results due to congestion. Specify `departure_time` if the component supports it; otherwise results reflect typical/average conditions.
- **Isoline polygons may overlap** for nearby locations. If enriching afterwards, polyfill to a spatial index and deduplicate cells to avoid double-counting.
- For **OD flow visualization** (Pattern D), use H3 cell center points rather than raw coordinates for cleaner aggregation and visualization. A coarser resolution (e.g. H3 res 7-8) produces more meaningful flow patterns than fine resolutions.
- The LDS routing components require a **connection with LDS API access enabled**. Validation may fail if the connection lacks this permission.

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
| Service area coverage | Isolines (car, multiple ranges e.g. 5/10/15 min) -> union -> measure total population covered |
| Nearest facility | OD matrix -> group by origin -> min(duration_s) -> join back to get nearest destination ID |
| Accessibility scoring | OD matrix -> filter by threshold -> count destinations per origin -> score by reachable count |
| Fleet route planning | Routes between depot and delivery points -> aggregate total distance/time per route |
| Commute flow analysis | Trip data -> H3 origin + H3 destination -> group by OD pair -> count -> visualize top flows |
| Multi-modal comparison | Run isolines twice (car + walk) -> compare coverage polygons -> identify transit-dependent areas |
