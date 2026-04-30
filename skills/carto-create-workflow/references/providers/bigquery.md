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

---

## Customsql `$a` / `$b` placeholders

In `native.customsql`, the `$a` / `$b` / `$c` placeholders expand to the upstream temp-table FQNs at run time. When the project ID contains a hyphen (e.g. `cartodb-on-gcp-datascience`), the expanded identifier must be backtick-quoted or BigQuery raises `Syntax error: unexpected keyword on at [...]`.

**Always wrap the placeholders in backticks** in BigQuery customsql bodies:

```sql
SELECT a.id, b.value
FROM `$a` a
JOIN `$b` b ON a.id = b.id
```

Unquoted `$a`/`$b` will pass `validate` (offline, structural-only) but fail `verify-remote` and runtime execution as soon as the expanded name contains a hyphen.
