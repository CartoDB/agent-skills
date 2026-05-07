# BigQuery Provider Notes

Provider-specific details for building workflows with BigQuery connections.

---

## Table Fully-Qualified Names

Format: `project.dataset.table`

```
cartodb-on-gcp-datascience.my_dataset.my_table
```

Use `carto connections browse <connection>` to navigate `project > dataset > table`.

---

## Column Casing

BigQuery preserves the original case of column names. Column references in workflows must match the case exactly as stored.

**Skill convention**: workflow examples and pattern skills use **lowercase** column names (`geom`, `h3`, `population_sum`, `morans_i`, etc.). On BigQuery this is preserved verbatim. (Snowflake uppercases unquoted identifiers — see `snowflake.md`.)

---

## Analytics Toolbox

BigQuery uses the Analytics Toolbox at `carto-un.carto`. This is resolved automatically when using `--connection`.

---

## Schedule Expressions

BigQuery uses English-style schedule expressions:

```
"every day 08:00"
"every monday 09:00"
"every 2 hours"
```

---

## SQL Dialect

- Supports `CREATE OR REPLACE TABLE` and `CREATE OR REPLACE VIEW`
- Uses backticks for identifier quoting: `` `project.dataset.table` ``
- Standard SQL mode (not legacy)

### Common dialect equivalents

When a pattern skill shows a SQL fragment, here are the BigQuery forms versus the other supported warehouses. Translate accordingly when the canonical example doesn't match your provider.

| Operation | BigQuery | Snowflake | Databricks | Postgres / Redshift |
|---|---|---|---|---|
| Truncate datetime to week | `DATETIME_TRUNC(CAST(x AS TIMESTAMP), WEEK)` | `DATE_TRUNC('WEEK', x)` | `date_trunc('WEEK', x)` | `date_trunc('week', x)` |
| Format number to 2 decimals | `FORMAT('%.2f', x)` | `TO_VARCHAR(x, 'FM999990.00')` | `format_string('%.2f', x)` | `to_char(x, 'FM999990.00')` |
| Lateral / unnest array | `UNNEST(arr) AS elem` | `lateral FLATTEN(input => arr) elem` | `LATERAL VIEW explode(arr) AS elem` | `LATERAL UNNEST(arr) elem` |
| Coalesce null to 0 | `COALESCE(x, 0)` | `COALESCE(x, 0)` | `COALESCE(x, 0)` | `COALESCE(x, 0)` |
| Point from lon/lat | `ST_GEOGPOINT(lon, lat)` | `ST_POINT(lon, lat)` | `ST_POINT(lon, lat, 4326)` | `ST_SetSRID(ST_MakePoint(lon, lat), 4326)` |

---

## Customsql `$a` / `$b` placeholders

In `native.customsql`, the `$a` / `$b` / `$c` placeholders expand to the upstream temp-table FQNs at run time. When the project ID contains a hyphen (e.g. `cartodb-on-gcp-datascience`), the expanded identifier must be backtick-quoted or BigQuery raises `Syntax error: unexpected keyword on at [...]`.

**Always wrap the placeholders in backticks** in BigQuery customsql bodies:

```
SELECT a.id, b.value
FROM `$a` a
JOIN `$b` b ON a.id = b.id
```

Unquoted `$a`/`$b` will pass `validate` (offline, structural-only) but fail `verify-remote` and runtime execution as soon as the expanded name contains a hyphen.
