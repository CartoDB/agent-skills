# Query execution model — sync vs async

CARTO runs SQL two ways. Pick by whether the statement returns rows and how long it runs.

| Path | MCP tool | CLI | Behaviour |
|---|---|---|---|
| **Sync read** | `execute_query` | `carto sql query` | `SELECT`s that return rows. 1-minute server-side timeout. |
| **Async job** | `execute_async_query` (`submit`/`status`/`cancel`) | `carto sql job` | DDL/DML and long queries. No timeout; poll to completion; returns no rows. |

Both MCP tools are available even on token-authenticated sessions. Use the CLI when the MCP server isn't attached or the SQL is scripted/CI.

## Sync read — `execute_query` / `carto sql query`

```bash
carto sql query <connection> "SELECT COUNT(*) FROM ds.t"
carto sql query <connection> --file query.sql
echo "SELECT 1" | carto sql query <connection>
```

- No caching by default; **1-minute timeout**. Best for `SELECT`s that finish in seconds.
- `--json` for machine-readable rows.

### `--cache` (CLI) / cached read

```bash
carto sql query <connection> "SELECT * FROM ds.t" --cache
```

Switches to a cacheable GET (1-year edge cache). The 1-minute timeout still applies on a cache miss, and the URL-length limit (~8KB query) means large queries fall back to an error. Use only for deterministic, small SQL.

## Async job — `execute_async_query` / `carto sql job`

```bash
carto sql job <connection> "CREATE TABLE ds.out AS SELECT ..."
carto sql job <connection> --file long_query.sql
```

- Submits the SQL as a job, polls until completion, prints final job status. **No timeout.**
- **Returns no rows.** For `CREATE TABLE AS SELECT`, the rows land in the new table — query it afterward with a sync read.
- Use for: `CREATE TABLE`, `UPDATE`, `DELETE`, `INSERT`, or any `SELECT` that legitimately takes >1 min.

## Which to choose

| Situation | Path |
|---|---|
| `SELECT` returning <1000 rows in <30 s | sync (`execute_query`) |
| `SELECT` deterministic, called repeatedly | sync + `--cache` (CLI) |
| `SELECT` over a 100M-row join, ~5 min | async → write staging table, then sync-read it |
| `CREATE TABLE AS SELECT` / `UPDATE` / `DELETE` / `INSERT` | async (`execute_async_query`) |
| Schema discovery | `explore_data` (`describe`) — see `carto-explore-datawarehouse`, not raw SQL |

## CLI input forms

All three of inline / `--file` / stdin work the same way; `--file` is the most reliable (no shell quoting):

```bash
carto sql query carto_dw "SELECT 1"           # inline
carto sql query carto_dw --file analysis.sql  # file
cat analysis.sql | carto sql query carto_dw   # stdin
```

For large result sets, run an async job to a destination table, then read it back with explicit `LIMIT`/`OFFSET` rather than streaming a giant JSON blob through the CLI.
