# Tilesets

A **tileset** is a pre-aggregated, multi-resolution copy of a geospatial dataset, stored in the warehouse as a regular table with a particular layout. Maps consume tilesets instead of raw tables when the dataset is too large to render row-by-row (typically >1M rows for points; far less for polygons).

## Why tilesets

- A 100M-row points table would fetch 100M rows to render the whole world. A tileset returns only the points visible in the current viewport at the current zoom level.
- Polygons get pre-simplified per zoom level — country boundaries at z=2 are coarse; at z=14 they're full resolution.
- The tileset table lives in the warehouse, so all warehouse access controls apply.

## When to build one

| Dataset size | Tileset? |
|---|---|
| < 100k rows | No — direct table is fine. |
| 100k – 1M points | Maybe — depends on map UI fluidity expectations. |
| > 1M points | Yes. |
| > 100k complex polygons | Yes. |
| Tilesets always needed for: heatmaps, hex/H3 aggregations, country/admin polygon stacks at multiple zoom levels. |

## How tilesets are created

CARTO ships **tileset SQL functions** in the spatial extension. The pattern:

1. Import or stage the source data via `carto imports create` (or it's already a warehouse table).
2. Run a `carto sql job` invoking the tileset-creation function — output is a *new* warehouse table.
3. Reference the tileset table in a map (the map JSON sets `type: "tileset"` on the dataset).

The exact function names depend on the warehouse — see CARTO docs for the Spatial Extension. Pseudo-code shape:

```sql
CALL carto.CREATE_POINT_AGGREGATION_TILESET(
  source_table => 'my_project.demo.events',
  output_table => 'my_project.demo.events_tileset',
  geom_column  => 'geom',
  zoom_min     => 0,
  zoom_max     => 14,
  aggregations => ARRAY[STRUCT('count', 'COUNT(*)')]
);
```

The function name and signature differ per engine; check `connections describe` on the spatial-extension schema, or the docs.

## Building one with `sql job`

Tileset creation is a long-running operation — always use `carto sql job` (no timeout), not `sql query`:

```bash
carto sql job carto_dw --file create_events_tileset.sql
```

A medium-sized tileset (10–50M rows) typically takes 5–30 minutes depending on warehouse compute size.

## Inspecting a tileset

```bash
carto connections describe carto_dw \
  "my_project.demo.events_tileset"
```

The columns are mostly internal — what matters for an agent is that the table exists; the *map JSON* (Phase 2's `carto-create-builder-maps`) is what consumes it.

## Relation to imports

Imports land raw rows. Tilesets sit on top. The typical pipeline is:

```
file/url ──[imports create]──> raw warehouse table
              │
              └──[sql job]──> tileset table (used by the map)
```

For one-off, small datasets, you can skip the tileset step and let the map read the raw table directly.

## Refreshing a tileset

There's no in-place refresh. Re-run the `sql job` with the same `output_table` after the source data changes (or use a Workflow on a schedule — see [`carto-create-analytics-workflow`](../../carto-create-analytics-workflow)).

The new run drops and recreates the tileset table. If maps consume it, plan a brief render gap or build the new tileset under a `_v2` name and swap.
