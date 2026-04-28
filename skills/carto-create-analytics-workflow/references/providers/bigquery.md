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
