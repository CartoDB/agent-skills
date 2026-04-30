# Databricks Provider Notes

Provider-specific details for building workflows with Databricks connections.

---

## Table Fully-Qualified Names

Format: `` `catalog`.schema.table ``

Catalogs with special characters (hyphens, spaces) **must** be backtick-quoted:

```
`engineering-catalog-default`.dvicente_workflows_data.madrid_bike_accidents
```

Schemas and tables with only alphanumeric/underscore characters do not need quoting.

Use `carto connections browse <connection>` to navigate `catalog > schema > table`.

---

## Column Casing

Databricks **preserves original case** of column names. Column references must match exactly as stored.

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
CALL `engineering-catalog-default`.`dedicated_1061_carto`.ENRICH_POLYGONS_WEIGHTED(...)
```

---

## Schedule Expressions

Databricks uses standard cron expressions:

```
"0 8 * * *"       # Daily at 08:00
"0 9 * * 1"       # Mondays at 09:00
"0 */2 * * *"     # Every 2 hours
```

---

## SQL Dialect

- Uses backticks for identifier quoting: `` `catalog`.`schema`.`table` ``
- Supports `CREATE TABLE ... USING DELTA` for persistent tables
- Uses `BEGIN ... END` blocks for workflow execution (multi-statement)
- `DROP TABLE IF EXISTS` for cleanup before writing results
- Lateral explode syntax: `LATERAL VIEW explode(array_col) AS elem`

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
{ "name": "source", "type": "Table", "value": "engineering-catalog-default.dvicente_workflows_data.my_table" }
```

**Exception**: In `native.customsql`, when using `$a`/`$b` placeholders and the catalog contains hyphens, wrap them as `` `$a` `` and `` `$b` `` so the expanded temp table name gets backtick-quoted in the generated SQL.
