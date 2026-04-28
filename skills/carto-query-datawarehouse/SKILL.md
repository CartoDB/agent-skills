---
name: carto-query-datawarehouse
description: Write spatial SQL against the connected warehouse — dialect-specific guidance, performance defaults, and CARTO's query/job execution model.
license: MIT
---

# carto-query-datawarehouse

Run SQL — spatial or otherwise — against any connection CARTO has registered. The CLI exposes two surfaces:

- **`carto sql query`** — `SELECT` queries that return rows. Has a 1-minute timeout. Optional client-side caching.
- **`carto sql job`** — DDL/DML jobs (`CREATE TABLE AS SELECT`, `UPDATE`, `INSERT`). No timeout; polls until done; returns no rows.

Plus a sibling for usage analytics:

- **`carto activity query`** — DuckDB-backed SQL over downloaded CARTO activity data. Local execution, separate from warehouse SQL.

## When to use this skill

- The user wants to count rows, run an exploratory `SELECT`, or build a transformation.
- The user is debugging slow / failing SQL.
- The agent needs to materialize an intermediate table before authoring a map.
- The user wants to run an ad-hoc spatial join, buffer, or H3 aggregation.

## Quick reference

```bash
# Read query (returns rows; 1-min timeout)
carto sql query <connection> "SELECT * FROM dataset.table LIMIT 10"

# Long-running job (DDL/DML; polls to completion; no rows back)
carto sql job <connection> "CREATE TABLE my_ds.out AS SELECT ..."

# From file
carto sql query <connection> --file query.sql

# Piped
echo "SELECT 1" | carto sql query <connection>
```

| Use | Command |
|---|---|
| Exploratory `SELECT` (small result, fast) | `sql query` |
| Cached `SELECT` (deterministic, 1y TTL) | `sql query ... --cache` |
| `CREATE TABLE AS SELECT`, large `UPDATE` | `sql job` |
| 5+ minute aggregation | `sql job` (queries time out at 1 min) |

`--cache` switches to GET with a cached response (1 year, 1 min timeout). Use only for queries that are deterministic and small enough for a URL.

## What's in this skill

| Topic | Reference |
|---|---|
| `sql query` vs `sql job`, caching, timeouts | [references/sql-jobs-and-caching.md](references/sql-jobs-and-caching.md) |
| Spatial SQL idioms — BigQuery dialect | [references/spatial-sql-bigquery.md](references/spatial-sql-bigquery.md) |
| Spatial SQL idioms — Snowflake dialect | [references/spatial-sql-snowflake.md](references/spatial-sql-snowflake.md) |
| Spatial SQL idioms — Postgres / PostGIS dialect | [references/spatial-sql-postgres.md](references/spatial-sql-postgres.md) |
| Querying CARTO activity data (local DuckDB) | [references/activity-queries.md](references/activity-queries.md) |

## Always-on guidance

- **Always specify a connection.** `<connection>` in `sql query <connection> ...` is the connection name from `connections list`, not the warehouse project ID.
- **Use `--json` when an agent will parse the output.** Default text output is for humans.
- **Prefer `sql job` for any query that might exceed 60 s.** `sql query` has a hard 1-minute server-side timeout regardless of the user's patience.
- **Don't `SELECT *` on warehouse tables blindly.** Spatial tables can be 100M+ rows; always project columns and add `LIMIT` for exploration.
- **Dialect mismatch is the #1 source of confusion.** `ST_DWithin` exists in PostGIS and Redshift, but is `ST_DWITHIN` in Snowflake and lives under `ST_DWithin` in BigQuery's `bigquery-public-data.geo_us_boundaries` style. The reference per dialect explains the canonical form.
- **For activity-data analysis** (who edited what, quota usage, login patterns), use `activity query` — it runs DuckDB SQL locally over downloaded data. See [references/activity-queries.md](references/activity-queries.md).
