# Data sources

A **data source** is a function from `@carto/api-client` that returns metadata + tile URL templates for a deck.gl tile layer, plus a `widgetSource` for charts. Every CARTO app starts here.

## Picking a source

| User has… | Source family | Pair with |
|---|---|---|
| Points / lines / polygons in a warehouse table | `vectorTable*`, `vectorQuery*`, `vectorTileset*` | `VectorTileLayer` |
| Pre-aggregated data on H3 cells | `h3Table*`, `h3Query*`, `h3Tileset*` | `H3TileLayer` |
| Pre-aggregated data on quadbin cells | `quadbinTable*`, `quadbinQuery*`, `quadbinTileset*` | `QuadbinTileLayer` |
| Continuous raster (temperature, elevation, NDVI) | `rasterSource` | `RasterTileLayer` |
| Polygons joined to data by ID (admin boundaries) | `boundaryTableSource`, `boundaryQuerySource` | `VectorTileLayer` |

Three flavors per family:

- **`*TableSource`** — point at a table. Simplest. `tableName: 'project.dataset.table'`.
- **`*QuerySource`** — point at a SQL query. Use when you need joins, computed columns, parameters.
- **`*TilesetSource`** — point at a pre-built tileset. Fastest at scale (>10M rows). See [`carto-import-export-data`](../../carto-import-export-data) for tileset prep.

## Common shape

Every source helper takes the same `cartoConfig` plus its own specifics:

```ts
import {
  vectorTableSource,
  vectorQuerySource,
  h3TableSource,
  rasterSource,
  boundaryTableSource,
} from '@carto/api-client';

const cartoConfig = {
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL,
  accessToken,
  connectionName: import.meta.env.VITE_CONNECTION_NAME,
};

const a = vectorTableSource({
  ...cartoConfig,
  tableName: 'demo.public.stores',
  columns: ['id', 'name', 'revenue'],   // optional — only fetch what you need
  filters: filtersObj,                  // optional — see filters.md
});

const b = vectorQuerySource({
  ...cartoConfig,
  sqlQuery: 'SELECT * FROM demo.public.stores WHERE region = @region',
  queryParameters: { region: 'NY' },    // see inputs-and-parameters.md
});

const c = h3TableSource({
  ...cartoConfig,
  tableName: 'demo.public.population_h3',
  aggregationExp: 'SUM(population) AS population',
  aggregationResLevel: 4,                // default 4 — lower = bigger cells
});

const d = rasterSource({
  ...cartoConfig,
  tableName: 'demo.public.temperature_raster',
});

const e = boundaryTableSource({
  ...cartoConfig,
  tilesetTableName: 'carto-boundaries.us.county_tileset',
  columnsTableName: 'demo.public.county_metrics',
  propertiesSqlQuery: 'SELECT geoid, metric_a, metric_b FROM demo.public.county_metrics',
});
```

Each call returns `Promise<TilejsonResult & WidgetXxxSourceResult>`. Pass the *promise* (not the awaited value) to the layer's `data` prop — deck.gl handles the await internally.

## Aggregation expressions (H3 / quadbin)

`aggregationExp` is required for H3 / quadbin sources. It's the SQL expression that aggregates source rows up to each cell:

```ts
aggregationExp: 'COUNT(*) AS count'
aggregationExp: 'SUM(population) AS population, AVG(income) AS income'
aggregationExp: 'AVG(value) AS value'
```

The aliased columns are what you reference in `getFillColor`, `getElevation`, and widget calls.

`aggregationResLevel` controls cell size. For H3, 4 is country-level, 8 is neighborhood, 12 is per-building. For quadbin, 6 is similar to H3 4. Test interactively — bigger numbers = smaller cells = more tiles = slower.

## Filters

The same `filters` object lives on the source *and* on widget calls (so charts and the map agree). See [`filters.md`](filters.md). Mutating it triggers re-fetch.

## When to use Query vs Table

- **Table**: trivial, just a table.
- **Query**: needs `WHERE`, `JOIN`, `CASE`, computed columns, or input parameters via `queryParameters`.
- **Tileset**: data is huge AND read-only AND already prepared as a tileset. Filters are applied client-side, not pushed to SQL — different perf profile.

## Gotchas

- **`tableName` is fully-qualified** — `project.dataset.table` (BigQuery), `DATABASE.SCHEMA.TABLE` (Snowflake), `schema.table` (Postgres / Redshift), `catalog.schema.table` (Databricks). Match the warehouse syntax exactly.
- **`columns` reduces wire bytes** for large tables — pass it whenever you don't need every column.
- **Widget calls share the source's filters** automatically when you pass the same `filters` object. Don't pass it twice; pass it once and let the widget read it through `widgetSource`.
- **Switching source type means switching layer type.** A `vectorTableSource` only works with `VectorTileLayer`, etc. See [`layers.md`](layers.md).
- **`spatialDataColumn`** defaults to `geom` (varies per warehouse). If your geometry column has a different name, pass it: `spatialDataColumn: 'geometry'`.
