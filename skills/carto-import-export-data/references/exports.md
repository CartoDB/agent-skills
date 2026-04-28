# Exporting data

CARTO is **import-heavy by design** — once data is in the warehouse, the warehouse owns it, and exports are usually warehouse-native (BigQuery `EXPORT DATA`, Snowflake `COPY INTO`, Postgres `\copy`, etc.). The CLI exposes one export surface: `carto activity export` for usage data.

## `carto activity export` — CARTO activity data only

Bulk-export the activity / API-usage / user-list data CARTO maintains about your org.

```bash
carto activity export [options]
```

| Flag | Meaning |
|---|---|
| `--start-date <YYYY-MM-DD>` | Required. |
| `--end-date <YYYY-MM-DD>` | Required. |
| `--format csv\|parquet` | Default: `csv`. |
| `--category activity\|apiUsage\|userList\|groupList` | Default: all four. |
| `--output-dir <path>` | Default: `./activity-data`. |

Plan gate: **Enterprise Large+ only.** Files land on disk; the CLI waits and downloads.

```bash
carto activity export \
  --start-date 2026-04-01 \
  --end-date 2026-04-28 \
  --format parquet \
  --output-dir ./apr-2026
```

For *querying* (rather than dumping) the same data, use `carto activity query` — it runs DuckDB SQL locally on the cached download. See [`carto-query-datawarehouse/references/activity-queries.md`](../../carto-query-datawarehouse/references/activity-queries.md).

## Exporting warehouse data — use the warehouse

For warehouse data (the tables CARTO reads/writes), CARTO does **not** ship a generic `carto export` command. Use the warehouse's native facility:

### BigQuery

```sql bigquery
EXPORT DATA OPTIONS (
  uri = 'gs://my-bucket/export-*.parquet',
  format = 'PARQUET',
  overwrite = true
) AS
SELECT * FROM `my_project.demo.events`
WHERE event_date >= '2026-04-01';
```

Run via `carto sql job <connection> --file export.sql`.

### Snowflake

```sql snowflake
COPY INTO @my_stage/events_apr2026
FROM (
  SELECT * FROM ANALYTICS.PUBLIC.EVENTS
  WHERE EVENT_DATE >= '2026-04-01'
)
FILE_FORMAT = (TYPE = PARQUET)
HEADER = TRUE
OVERWRITE = TRUE;
```

### Postgres / Redshift

```sql postgres
COPY (
  SELECT * FROM events
  WHERE event_date >= '2026-04-01'
)
TO 's3://my-bucket/events.csv'
WITH (FORMAT CSV, HEADER TRUE);
```

(Redshift uses `UNLOAD` instead of `COPY ... TO` — confirm syntax for the specific engine.)

### Databricks

```sql databricks
COPY INTO 's3://my-bucket/events/'
FROM (SELECT * FROM main.analytics.events)
FILEFORMAT = PARQUET;
```

## Why no generic CLI export?

- Warehouse-native unloads run **inside the warehouse**, never round-tripping through CARTO. They're 10–100× faster for large data.
- Permissions live in the warehouse — using the native unload uses the *user's* warehouse credentials directly, not CARTO's connection credential.
- Format / partitioning / compression options vary wildly per engine; a generic CLI wrapper would either lose fidelity or duplicate every engine's full unload spec.

If a user expects `carto export <table>` to work, redirect them to the SQL approach above.
