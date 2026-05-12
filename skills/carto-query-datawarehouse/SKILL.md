---
name: carto-query-datawarehouse
description: Run SQL — spatial or otherwise — against any CARTO-connected warehouse. This skill is the dispatcher — it covers `sql query` vs `sql job` execution model and routes the agent to the per-engine spatial-SQL skill that matches the connection's provider.
license: MIT
---

# carto-query-datawarehouse

Run SQL — spatial or otherwise — against any connection CARTO has registered. The CLI exposes two surfaces:

- **`carto sql query`** — `SELECT` queries that return rows. 1-minute timeout. Optional client-side caching.
- **`carto sql job`** — DDL/DML jobs (`CREATE TABLE AS SELECT`, `UPDATE`, `INSERT`). No timeout; polls until done; returns no rows.

Plus a sibling for usage analytics:

- **`carto activity query`** — DuckDB-backed SQL over downloaded CARTO activity data. Local execution, separate from warehouse SQL.

For **CARTO Analytics Toolbox functions and engine-specific spatial behavior** (type system, indexing, perf), route to the per-engine skill below.

## When to use this skill

- The user wants to count rows, run an exploratory `SELECT`, or build a transformation.
- The user is debugging slow / failing SQL.
- The agent needs to materialize an intermediate table before authoring a map.
- You need to decide between `sql query` and `sql job`, or use `--cache`.

For spatial SQL idioms, AT modules, or perf-tuning a spatial join, **don't stay here — load the matching per-engine skill.**

## Detect the engine, then route

```bash
carto connections list --json | jq '.[] | {name, provider}'
```

The `provider` field decides which dialect skill the agent should consult:

| Provider | Skill | Notes |
|---|---|---|
| `bigquery` | [`carto-spatial-sql-bigquery`](../carto-spatial-sql-bigquery) | Flagship AT — every module ships. |
| `snowflake` | [`carto-spatial-sql-snowflake`](../carto-spatial-sql-snowflake) | Most modules; native app from marketplace. |
| `databricks` | [`carto-spatial-sql-databricks`](../carto-spatial-sql-databricks) | Narrow AT — defaults to Databricks-native for H3 / ST_*. Beta. |
| `postgres` | [`carto-spatial-sql-postgres`](../carto-spatial-sql-postgres) | Thin AT (h3 / quadbin / tiler). Rest via PostGIS native. |
| `redshift` | [`carto-spatial-sql-redshift`](../carto-spatial-sql-redshift) | **No standalone H3 module** — use quadbin. |
| `oracle` | [`carto-spatial-sql-oracle`](../carto-spatial-sql-oracle) | **No AT available.** Connection target only. Native `SDO_*`. |

## Cross-cutting matrices

### Function-call syntax

| Engine | Call form | Example |
|---|---|---|
| BigQuery | `` `<project>`.carto.<FN> `` | `` `carto-un`.carto.H3_FROMGEOGPOINT(...) `` |
| Snowflake | `<DB>.<SCHEMA>.<FN>` (default `CARTO.CARTO`) | `carto.carto.H3_FROMGEOGPOINT(...)` |
| Databricks | `<catalog>.<schema>.<FN>` (default `carto.carto`) | `carto.carto.QUADBIN_FROMLONGLAT(...)` |
| Postgres | `carto.<fn>` (lowercase) | `carto.h3_fromgeogpoint(...)` |
| Redshift | `carto.<FN>` | `carto.QUADBIN_FROMLONGLAT(...)` |
| Oracle | n/a — no AT | use `SDO_*` natives |

### Spatial-index storage type

| Engine | H3 | Quadbin |
|---|---|---|
| BigQuery | `STRING` (hex) | `INT64` |
| Snowflake | `VARCHAR` | `NUMBER` |
| Databricks | `STRING` (native, not CARTO) | `BIGINT` |
| Postgres | `VARCHAR(16)` | `BIGINT` |
| Redshift | **n/a** (no H3 module) | `BIGINT` |
| Oracle | **n/a** | **n/a** |

### Module coverage (yes / no / native)

| Module | BQ | SF | DBX | PG | RS | Oracle |
|---|---|---|---|---|---|---|
| h3 | ✓ | ✓ | **native only** | ✓ | **✗** | ✗ |
| quadbin | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| data (ENRICH) | ✓ | ✓ | ✓ | ✗ | ✓ | ✗ |
| lds | ✓ | ✓ | ✓ | ✗ | ✓ | ✗ |
| statistics | ✓ | ✓ | ✓ (subset) | ✗ | ✓ | ✗ |
| transformations | ✓ | ✓ | ✗ | ✗ | ✓ | ✗ |
| tiler | ✓ | ✓ | ✗ | ✓ | ✓ | ✗ |
| processing | ✓ | ✓ | ✗ | ✗ | ✓ | ✗ |
| measurements | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ |
| s2 | ✓ | ✓ | ✗ | ✗ | ✓ | ✗ |
| geohash | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |
| raster | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ |
| retail / cpg / telco | ✓ (BQ only) | retail only | ✗ | ✗ | retail only | ✗ |

If the user asks for an AT module that's not shipped on their engine, **say so explicitly** rather than silently emit a `function not found` error. The dialect skills cover what to substitute.

## Quick reference (engine-agnostic)

```bash
# Read query (returns rows; 1-min timeout)
carto sql query <connection> "SELECT COUNT(*) FROM ds.t"

# Long-running job (DDL/DML; polls to completion; no rows back)
carto sql job <connection> "CREATE TABLE ds.out AS SELECT ..."

# From file
carto sql query <connection> --file query.sql

# JSON output for agents
carto sql query <connection> "SELECT 1" --json
```

| Use | Command |
|---|---|
| Exploratory `SELECT` (small result, fast) | `sql query` |
| Cached `SELECT` (deterministic, 1y TTL) | `sql query ... --cache` |
| `CREATE TABLE AS SELECT`, large `UPDATE` | `sql job` |
| 5+ minute aggregation | `sql job` (queries time out at 1 min) |

`--cache` switches to GET with a cached response (1 year TTL). Use only for queries that are deterministic and small enough for a URL (~8KB).

## References

| Topic | Reference |
|---|---|
| `sql query` vs `sql job`, caching, timeouts | [references/sql-jobs-and-caching.md](references/sql-jobs-and-caching.md) |
| Querying CARTO activity data (local DuckDB) | [references/activity-queries.md](references/activity-queries.md) |

## Always-on guidance

- **Always specify a connection.** `<connection>` is the name from `connections list`, not a warehouse project ID.
- **Use `--json` when an agent will parse the output.** Default text output is for humans.
- **Prefer `sql job` for any query that might exceed 60 s.** `sql query` has a hard 1-minute server-side timeout.
- **Don't `SELECT *`** on warehouse tables blindly — geometry-bearing tables can be 100M+ rows with huge per-row payloads.
- **Detect the dialect first, then route.** Cross-engine SQL doesn't exist — pick the right per-engine skill before emitting `carto.*` calls.
- **For activity-data analysis** (who edited what, quota usage, login patterns), use `carto activity query` → DuckDB SQL locally. See [references/activity-queries.md](references/activity-queries.md).
