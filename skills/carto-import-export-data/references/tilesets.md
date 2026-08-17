# Tilesets

A **tileset** is a pre-aggregated, multi-resolution copy of a geospatial dataset, stored in the warehouse as a regular table with a particular layout. Maps consume tilesets instead of raw tables when the dataset is too large to render row-by-row (typically >1M rows for points; far less for polygons).

## Why tilesets

- A 100M-row points table would fetch 100M rows to render the whole world. A tileset returns only the points visible in the current viewport at the current zoom level.
- Polygons get pre-simplified per zoom level — country boundaries at z=2 are coarse; at z=14 full resolution.
- The tileset table lives in the warehouse, so all warehouse access controls apply.

## When to build one

| Dataset | Tileset? |
|---|---|
| < 100k rows | No — direct table is fine. |
| 100k – 1M points | Maybe — depends on map UI fluidity expectations. |
| > 1M points, or > 100k complex polygons | Yes. |
| Heatmaps, hex/H3 aggregations, admin-polygon stacks at multiple zooms | Always. |

## How tilesets are created

CARTO ships **tileset SQL functions** in the spatial extension. The pattern:

1. Import or stage the source data (see [imports.md](imports.md)), or use an existing warehouse table.
2. Run the tileset-creation function as an async query — output is a *new* warehouse table.
3. Reference the tileset table in a map (the map JSON sets `type: "tileset"` on the dataset).

Function names/signatures differ per engine — confirm with `explore_data` (`method: describe`) on the spatial-extension schema, or the CARTO docs. Pseudo-code shape:

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

## Materializing it

Tileset creation is long-running — always run it as an async job, never a synchronous query:

- **MCP:** `execute_async_query` `method: "submit"` with the CALL statement, then poll `method: "status"`.
- **CLI:** `carto sql job carto_dw --file create_events_tileset.sql`.

A medium tileset (10–50M rows) typically takes 5–30 minutes depending on warehouse compute size.

## Inspecting a tileset

`explore_data` (`method: describe`) on `my_project.demo.events_tileset`, or `carto connections describe carto_dw "my_project.demo.events_tileset"`. The columns are mostly internal — what matters is that the table exists; the *map JSON* (see [`carto-create-builder-maps`](../../carto-create-builder-maps)) is what consumes it.

## Relation to imports

Imports land raw rows; tilesets sit on top:

```
file/url ──[import]──> raw warehouse table ──[async tileset SQL]──> tileset table (used by the map)
```

For one-off small datasets, skip the tileset step and let the map read the raw table directly.

## Refreshing a tileset

No in-place refresh. Re-run the tileset SQL with the same `output_table` after the source changes (or drive it on a schedule with a Workflow — see [`carto-create-workflow`](../../carto-create-workflow)). The run drops and recreates the table; if maps consume it, plan a brief render gap or build under a `_v2` name and swap.
