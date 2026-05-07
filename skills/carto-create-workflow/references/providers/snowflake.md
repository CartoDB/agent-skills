# Snowflake Provider Notes

Provider-specific details for building workflows with Snowflake connections.

---

## Table Fully-Qualified Names

Format: `DATABASE.SCHEMA.TABLE`

```
DVICENTE_AT.WORKFLOWS_DATA.MADRID_BIKE_ACCIDENTS
```

Use `carto connections browse <connection>` to navigate `database > schema > table`.

---

## Column Casing

Snowflake **uppercases all unquoted identifiers** automatically. When referencing columns in workflow inputs, always use UPPERCASE names:

```json
{
  "inputs": [
    { "name": "geo", "type": "Column", "value": "GEOM" },
    { "name": "column", "type": "Column", "value": "ACCIDENT_TYPE" }
  ]
}
```

Use `carto connections describe <connection> "DATABASE.SCHEMA.TABLE"` to see exact column names. They will be uppercase.

**Note**: Snowflake is case-insensitive for unquoted identifiers — `geom`, `Geom`, and `GEOM` all resolve to the same column. However, using UPPERCASE consistently avoids ambiguity and matches what `describe` returns.

**This applies to component-generated columns too.** For example, the `native.buffer` component creates a column called `geom_buffer`, but on Snowflake it becomes `GEOM_BUFFER`. When referencing generated columns in downstream nodes (e.g. spatial join's `maintablejoincolumn`), use UPPERCASE.

**Skill convention**: pattern skills and workflow examples document column names in **lowercase** (e.g. `geom`, `h3`, `population_sum`, `morans_i`, `index`, `gi`, `p_value`, `quadrant`). On Snowflake, surface those same identifiers as UPPERCASE (`GEOM`, `H3`, `POPULATION_SUM`, `MORANS_I`, `INDEX`, `GI`, `P_VALUE`, `QUADRANT`) wherever you reference them in expressions, predicates, or downstream component inputs.

---

## Analytics Toolbox

Snowflake uses the Analytics Toolbox at `CARTO.CARTO`. This should be resolved automatically when using `--connection`.

The AT path resolves automatically when using `--connection`.

---

## Schedule Expressions

Snowflake uses standard cron expressions:

```
"0 8 * * *"       # Daily at 08:00
"0 9 * * 1"       # Mondays at 09:00
"0 */2 * * *"     # Every 2 hours
```

---

## SQL Dialect

- Uses `CREATE TRANSIENT TABLE` (not `CREATE TABLE`) for intermediate results
- Uses `CREATE OR REPLACE VIEW` for source nodes
- Identifier quoting uses double quotes: `"DATABASE"."SCHEMA"."TABLE"`
- Lateral flatten syntax: `lateral FLATTEN(input => array_col) elem`

### Common dialect equivalents

For canonical (BigQuery-shaped) examples in pattern skills, here are the Snowflake equivalents:

| Operation | Snowflake | BigQuery (canonical) |
|---|---|---|
| Truncate datetime to week | `DATE_TRUNC('WEEK', x)` | `DATETIME_TRUNC(CAST(x AS TIMESTAMP), WEEK)` |
| Format number to 2 decimals | `TO_VARCHAR(x, 'FM999990.00')` | `FORMAT('%.2f', x)` |
| Lateral / unnest array | `lateral FLATTEN(input => arr) elem` | `UNNEST(arr) AS elem` |
| Point from lon/lat | `ST_POINT(lon, lat)` | `ST_GEOGPOINT(lon, lat)` |

---

## connectionProvider Value

Set `"connectionProvider": "snowflake"` in the workflow JSON top-level. This value must match the actual provider of the connection you validate/execute against. Mismatches will cause SQL generation to use the wrong dialect.

```json
{
  "schemaVersion": "1.0.0",
  "title": "My Snowflake Workflow",
  "connectionProvider": "snowflake",
  "nodes": [],
  "edges": []
}
```
