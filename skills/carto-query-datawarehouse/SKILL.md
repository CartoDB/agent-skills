---
name: carto-query-datawarehouse
description: Write spatial SQL against the connected warehouse — dialect-specific guidance, performance defaults, and CARTO's query/job execution model.
license: MIT
---

# carto-query-datawarehouse

Run SQL — spatial or otherwise — against any connection CARTO has registered. Two execution surfaces, matched across MCP and CLI:

| | Row-returning `SELECT` (1-min timeout) | DDL/DML & long queries (no timeout, no rows) |
|---|---|---|
| **MCP** (primary) | `execute_query` | `execute_async_query` (`submit`/`status`/`cancel`) |
| **CLI** (fallback) | `carto sql query` | `carto sql job` |

> **Access-path routing.** With the CARTO MCP server attached, run SQL through `execute_query` and `execute_async_query` — both available even on token-authenticated sessions. The dialect guidance and performance rules here apply identically on either path. Use the `carto sql` CLI when the server isn't attached or the SQL is scripted/CI. `carto activity query` (local DuckDB over downloaded activity data) is **CLI-only** — no MCP equivalent. Detection signals: [`carto-basics/references/access-paths.md`](../carto-basics/references/access-paths.md).

## When to use this skill

- The user wants to count rows, run an exploratory `SELECT`, or build a transformation.
- The user is debugging slow / failing SQL.
- The agent needs to materialize an intermediate table before authoring a map.
- The user wants an ad-hoc spatial join, buffer, or H3 aggregation.

## Quick reference (CLI)

```bash
# Read query (returns rows; 1-min timeout)
carto sql query <connection> "SELECT * FROM dataset.table LIMIT 10"

# Long-running job (DDL/DML; polls to completion; no rows back)
carto sql job <connection> "CREATE TABLE my_ds.out AS SELECT ..."

# From file / piped
carto sql query <connection> --file query.sql
echo "SELECT 1" | carto sql query <connection>
```

| Use | Path |
|---|---|
| Exploratory `SELECT` (small, fast) | sync — `execute_query` / `sql query` |
| Cached `SELECT` (deterministic, 1y TTL) | `sql query ... --cache` |
| `CREATE TABLE AS SELECT`, large `UPDATE`, 5+ min aggregation | async — `execute_async_query` / `sql job` |

`--cache` (CLI) switches to a GET with a 1-year cached response; use only for deterministic, small queries.

## What's in this skill

| Topic | Reference |
|---|---|
| Sync vs async execution, caching, timeouts | [references/sql-jobs-and-caching.md](references/sql-jobs-and-caching.md) |
| Spatial SQL idioms — BigQuery dialect | [references/spatial-sql-bigquery.md](references/spatial-sql-bigquery.md) |
| Spatial SQL idioms — Snowflake dialect | [references/spatial-sql-snowflake.md](references/spatial-sql-snowflake.md) |
| Spatial SQL idioms — Postgres / PostGIS (and Redshift) dialect | [references/spatial-sql-postgres.md](references/spatial-sql-postgres.md) |
| Querying CARTO activity data (local DuckDB, CLI-only) | [references/activity-queries.md](references/activity-queries.md) |

## Always-on guidance

- **Always specify a connection.** The connection name comes from `explore_data` (`list_connections`) / `carto connections list`, not the warehouse project ID.
- **Prefer the async path for any query that might exceed 60 s.** Sync reads have a hard 1-minute server-side timeout regardless of the user's patience.
- **Don't `SELECT *` on warehouse tables blindly.** Spatial tables can be 100M+ rows; project columns and add `LIMIT` for exploration.
- **Dialect mismatch is the #1 source of confusion.** `ST_DWithin` is `ST_DWITHIN` in Snowflake, `ST_DWithin` in BigQuery/PostGIS/Redshift. The per-dialect reference gives the canonical form.
- **For activity-data analysis** (who edited what, quota usage, login patterns), use `carto activity query` — CLI-only, DuckDB over downloaded data. See [references/activity-queries.md](references/activity-queries.md).
