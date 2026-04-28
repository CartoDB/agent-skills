# `sql query` vs `sql job` — execution model

## `sql query` — interactive read

```bash
carto sql query <connection> [sql]
carto sql query <connection> --file query.sql
echo "SELECT COUNT(*) FROM ds.t" | carto sql query <connection>
```

- POST by default; no caching; **1-minute timeout** (server-side).
- Returns rows in tabular text or JSON (with `--json`).
- Best for `SELECT`s that finish in seconds.

### `--cache` flag

```bash
carto sql query <connection> "SELECT * FROM ds.t" --cache
```

- Switches to **GET** with a cacheable URL.
- Cached for 1 year on CARTO's edge.
- **1-minute timeout still applies** on cache miss.
- Subject to URL-length limits (~8KB query); large queries fall back to error.
- Use only when the SQL is deterministic and small.

## `sql job` — DDL/DML and long-running queries

```bash
carto sql job <connection> "CREATE TABLE ds.out AS SELECT ..."
carto sql job <connection> --file long_query.sql
```

- Submits the SQL as a job, polls until completion, prints the final job status.
- **No timeout.** Polls indefinitely.
- **Returns no rows.** For `CREATE TABLE AS SELECT`, the rows go to the new table; query that table afterwards with `sql query`.
- Use for: `CREATE TABLE`, `UPDATE`, `DELETE`, `INSERT`, any query that legitimately takes >1 min.

## When to choose which

| Situation | Tool |
|---|---|
| `SELECT` returning <1000 rows in <30 s | `sql query` |
| `SELECT` deterministic, called repeatedly | `sql query --cache` |
| `SELECT` over a 100M-row spatial join, takes ~5 min | `sql job` (write to staging table, then `sql query` from it) |
| `CREATE TABLE AS SELECT` | `sql job` |
| `UPDATE`/`DELETE`/`INSERT` | `sql job` |
| Schema discovery | `connections describe` (see `carto-explore-datawarehouse`), not raw SQL |

## Stdin / file / inline patterns

All three accept SQL the same way:

```bash
# Inline argument (watch shell quoting)
carto sql query carto_dw "SELECT 1"

# --file (cleaner for multi-line / long SQL)
carto sql query carto_dw --file analysis.sql

# Piped on stdin
cat analysis.sql | carto sql query carto_dw
```

The `--file` flag is the most reliable — no shell quoting, easy to keep alongside the rest of the agent's working files.

## JSON output

```bash
carto sql query carto_dw "SELECT id, ST_AsText(geom) AS wkt FROM ds.points LIMIT 3" --json
```

```json
[
  {"id": "abc", "wkt": "POINT(-73.98 40.75)"},
  ...
]
```

For large result sets prefer `sql job` to a destination table, then `sql query` with explicit `LIMIT`/`OFFSET` rather than streaming a giant JSON blob through the CLI.
