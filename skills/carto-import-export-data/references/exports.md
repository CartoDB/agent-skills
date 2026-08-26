# Exporting and transferring data

Three distinct jobs, three paths:

| Goal | MCP (OAuth) | CLI / SQL fallback |
|---|---|---|
| Pull a query/table out of the warehouse to a file | `export_data` (`submit`/`status`) | warehouse-native unload via SQL |
| Copy a table between two connections | `transfer_data` (`submit`/`status`, `source_connection` → `destination_connection`) | `carto import` from a staged unload |
| Dump CARTO activity / API-usage data to disk | — (no MCP equivalent) | `carto activity export` |

`export_data` / `transfer_data` are hidden on token-authenticated MCP sessions — use the CLI / warehouse-native path there. Warehouse-native unloads stay valuable even with MCP attached: they run **inside** the warehouse (10–100× faster for large data) using the *user's* warehouse credentials, and preserve every engine's partitioning/compression fidelity.

## `carto activity export` — CARTO activity data only (CLI-only)

Bulk-export the activity / API-usage / user-list data CARTO maintains about your org. No MCP tool covers this.

```bash
carto activity export [options]
```

| Flag | Meaning |
|---|---|
| `--start-date <YYYY-MM-DD>` / `--end-date <YYYY-MM-DD>` | Required range. |
| `--format csv\|parquet` | Default: `csv`. |
| `--category activity\|apiUsage\|userList\|groupList` | Default: all four. |
| `--output-dir <path>` | Default: `./activity-data`. |

Plan gate: **Enterprise Large+ only.** Files land on disk; the CLI waits and downloads.

```bash
carto activity export --start-date 2026-04-01 --end-date 2026-04-28 \
  --format parquet --output-dir ./apr-2026
```

To *query* rather than dump the same data, use `carto activity query` (DuckDB SQL over the cached download) — see [`carto-query-datawarehouse/references/activity-queries.md`](../../carto-query-datawarehouse/references/activity-queries.md).

## Warehouse-native unloads

For arbitrary warehouse tables, `export_data` submits the unload for you; the SQL below is the equivalent you'd run via `execute_async_query` or `carto sql job` when you need full control over the engine's options.

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

Run any of these with `execute_async_query` (`method: submit`) over MCP, or `carto sql job <connection> --file export.sql` on the CLI. If a user expects a generic `carto export <table>`, route them to `export_data` or the SQL above.
