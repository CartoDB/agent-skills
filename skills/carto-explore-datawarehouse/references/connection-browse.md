# Browsing and describing a connection

Both operate on an existing connection (see [`carto-connect-datawarehouse`](../../carto-connect-datawarehouse) to create one).

| Task | MCP (`explore_data`) | CLI fallback |
|---|---|---|
| Walk the hierarchy (project → dataset → table) | method `list_resources` (pass a path to drill in) | `carto connections browse <name> [path]` |
| Full-text find a resource across a connection | method `search` | — |
| Columns + types for one table | method `describe` | `carto connections describe <name> <table-path>` |

`explore_data` works even on token-authenticated MCP sessions. Use the CLI when the server isn't attached or the exploration is scripted.

## Walking the hierarchy

```bash
# Top level — projects/databases visible to the connection
carto connections browse carto_dw

# BigQuery: into a project, list datasets; then into a dataset, list tables
carto connections browse carto_dw "carto-demo-data"
carto connections browse carto_dw "carto-demo-data.demo_tables"

# Snowflake: into a database, then a schema
carto connections browse snowflake-prod "ANALYTICS"
carto connections browse snowflake-prod "ANALYTICS.PUBLIC"
```

CLI options: `--page <n>`, `--page-size <n>` (default 30), `--json`. Output items carry a `type` that varies by engine — `project`, `dataset`, `schema`, `table`, `view`, `tileset`.

```json
{
  "items": [
    {"name": "demo_tables", "type": "dataset"},
    {"name": "demo_views",  "type": "dataset"}
  ],
  "page": 1, "page_size": 30, "total": 2
}
```

## Describing a table

Returns columns and types for one specific table.

```bash
carto connections describe carto_dw "carto-demo-data.demo_tables.nyc_collisions"
```

```json
{
  "name": "nyc_collisions",
  "type": "table",
  "columns": [
    {"name": "collision_id",  "type": "INT64"},
    {"name": "borough",       "type": "STRING"},
    {"name": "incident_date", "type": "DATE"},
    {"name": "geom",          "type": "GEOGRAPHY"}
  ],
  "row_count_estimate": 2118000
}
```

Use the column list for everything downstream:

- Confirm the geometry column name (`geom`, `geometry`, `the_geom`, …).
- Confirm types before writing `ST_*` predicates — if `geom` is a `STRING`, it's WKT to parse, not a native geography.
- Pull a column list to project instead of `SELECT *`.

## Pagination (CLI)

```bash
carto connections browse <name> "<path>" --page-size 100
carto connections browse <name> "<path>" --page 3 --page-size 100
```

Prefer one large page over many small ones — fewer round-trips.

## Errors

- **`Path not found`** — path is wrong, or the credential CARTO uses can't see it. Browse one level up.
- **`Permission denied`** — warehouse-side: the connection's underlying credential lacks `dataViewer`/`SELECT` on the path. See the matching engine reference in [`carto-connect-datawarehouse`](../../carto-connect-datawarehouse).
