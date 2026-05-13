# Databricks Provider Notes

Provider-specific details for building workflows with Databricks connections.

---

## Table Fully-Qualified Names

Format: `` `catalog`.schema.table ``

Catalogs with special characters (hyphens, spaces) **must** be backtick-quoted:

```
`acme-catalog`.workflows_data.madrid_bike_accidents
```

Schemas and tables with only alphanumeric/underscore characters do not need quoting.

Use `carto connections browse <connection>` to navigate `catalog > schema > table`.

---

## Column Casing

Databricks **preserves original case** of column names. Column references must match exactly as stored.

**Skill convention**: pattern skills use **lowercase** column names (`geom`, `h3`, `population_sum`, `morans_i`, etc.). On Databricks this is preserved verbatim — match the convention. (Snowflake uppercases unquoted identifiers — see `snowflake.md`.)

**Gotcha with column name `geom`**: Databricks may auto-promote a `STRING` column named `geom` to `geometry(0)` when creating tables via DDL with uppercase column names. Use lowercase column names in `CREATE TABLE` statements to avoid this.

---

## Geometry

Databricks uses native `geometry` with an explicit SRID. Always use **`geometry(4326)`** (WGS84):

- From WKT: `ST_GEOMFROMWKT(wkt_string, 4326)`
- From GeoJSON: `ST_GEOMFROMGEOJSON(geojson_string)` — automatically produces `geometry(4326)`
- From lat/lon: `ST_POINT(lon, lat, 4326)` — note: **longitude first**, then latitude
- To WKT: `ST_ASTEXT(geom)`

**Avoid `geometry(0)`** — this is an unspecified SRID and will cause issues with spatial operations. Always specify SRID 4326.

---

## Analytics Toolbox

Databricks uses the Analytics Toolbox installed as stored procedures in a dedicated schema within the catalog. The path is resolved automatically when using `--connection`.

Example AT procedure call (from generated SQL):
```sql
CALL `acme-catalog`.`<at_schema>`.ENRICH_POLYGONS_WEIGHTED(...)
```

---

## Schedule Expressions

Databricks uses **Quartz cron** expressions (6 fields, with seconds and a `?` placeholder for day-of-week / day-of-month):

```
"0 0 8 * * ?"       # Daily at 08:00:00
"0 0 9 ? * MON"     # Mondays at 09:00
"0 0 */2 * * ?"     # Every 2 hours
```

Standard 5-field cron (`0 8 * * *`) will fail at `schedule add` time — Databricks only accepts Quartz syntax. See `carto workflows --help` for the full dialect-per-engine table.

---

## SQL Dialect

- Uses backticks for identifier quoting: `` `catalog`.`schema`.`table` ``
- Supports `CREATE TABLE ... USING DELTA` for persistent tables
- Uses `BEGIN ... END` blocks for workflow execution (multi-statement)
- `DROP TABLE IF EXISTS` for cleanup before writing results
- Lateral explode syntax: `LATERAL VIEW explode(array_col) AS elem`

### Common dialect equivalents

For canonical (BigQuery-shaped) examples in pattern skills, here are the Databricks equivalents:

| Operation | Databricks | BigQuery (canonical) |
|---|---|---|
| Truncate datetime to week | `date_trunc('WEEK', x)` | `DATETIME_TRUNC(CAST(x AS TIMESTAMP), WEEK)` |
| Format number to 2 decimals | `format_string('%.2f', x)` | `FORMAT('%.2f', x)` |
| Lateral / unnest array | `LATERAL VIEW explode(arr) AS elem` | `UNNEST(arr) AS elem` |
| Point from lon/lat | `ST_POINT(lon, lat, 4326)` | `ST_GEOGPOINT(lon, lat)` |

---

## connectionProvider Value

Set `"connectionProvider": "databricksWarehouse"` in the workflow JSON top-level. Note: the value is **`databricksWarehouse`** (not `"databricks"`).

```json
{
  "schemaVersion": "1.0.0",
  "title": "My Databricks Workflow",
  "connectionProvider": "databricksWarehouse",
  "nodes": [],
  "edges": []
}
```

## Table FQN in Workflow Inputs

Catalog names with special characters (hyphens) do **not** need backtick-quoting inside workflow JSON input values. The engine adds quoting automatically in generated SQL. For example, use:

```json
{ "name": "source", "type": "Table", "value": "acme-catalog.workflows_data.my_table" }
```

**Exception**: In `native.customsql`, when using `$a`/`$b` placeholders and the catalog contains hyphens, wrap them as `` `$a` `` and `` `$b` `` so the expanded temp table name gets backtick-quoted in the generated SQL.
