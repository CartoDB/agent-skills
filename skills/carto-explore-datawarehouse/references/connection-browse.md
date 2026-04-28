# `connections browse` and `connections describe`

Both commands operate on an existing connection (see [`carto-connect-datawarehouse`](../../carto-connect-datawarehouse) to create one).

## `connections browse`

Walks the warehouse hierarchy one level at a time.

```bash
carto connections browse <connection-name> [path]
```

**Options:**
- `--page <n>` — page number (default: 1)
- `--page-size <n>` — items per page (default: 30)
- `--json` — machine-readable output

### Examples

```bash
# Top level — projects/databases visible to the connection
carto connections browse carto_dw

# Inside a BigQuery project, list datasets
carto connections browse carto_dw "carto-demo-data"

# Inside a dataset, list tables
carto connections browse carto_dw "carto-demo-data.demo_tables"

# Snowflake: into a database, list schemas
carto connections browse snowflake-prod "ANALYTICS"

# Snowflake: into a schema, list tables
carto connections browse snowflake-prod "ANALYTICS.PUBLIC"
```

### Output shape (JSON)

```json
{
  "items": [
    {"name": "demo_tables", "type": "dataset"},
    {"name": "demo_views",  "type": "dataset"}
  ],
  "page": 1,
  "page_size": 30,
  "total": 2
}
```

`type` varies by engine — `project`, `dataset`, `schema`, `table`, `view`, `tileset` are all valid values.

## `connections describe`

Returns columns and types for one specific table.

```bash
carto connections describe <connection-name> <table-path>
```

### Example

```bash
carto connections describe carto_dw \
  "carto-demo-data.demo_tables.nyc_collisions"
```

### Output (truncated)

```json
{
  "name": "nyc_collisions",
  "type": "table",
  "columns": [
    {"name": "collision_id",   "type": "INT64"},
    {"name": "borough",        "type": "STRING"},
    {"name": "incident_date",  "type": "DATE"},
    {"name": "geom",           "type": "GEOGRAPHY"},
    ...
  ],
  "row_count_estimate": 2118000
}
```

### Use the column list for everything downstream

- Confirm the geometry column name (`geom`, `geometry`, `the_geom`, …).
- Confirm types before writing `ST_*` predicates — if `geom` is a `STRING`, the user has a WKT column they need to parse, not a native geography.
- Pull a column list for `LIMIT` queries instead of `SELECT *`.

## Pagination on long lists

```bash
carto connections browse <name> "<path>" --page-size 100
carto connections browse <name> "<path>" --page 3 --page-size 100
```

For agents iterating over hundreds of tables, prefer one large page over many small ones — fewer round-trips.

## Errors

- **`Path not found`** — the path is wrong, or the credential CARTO uses can't see it. Try `connections browse` one level up.
- **`Permission denied`** — warehouse-side permission issue. The CARTO connection's underlying credential lacks `dataViewer`/`SELECT` on the path. See the matching engine reference in [`carto-connect-datawarehouse`](../../carto-connect-datawarehouse).
