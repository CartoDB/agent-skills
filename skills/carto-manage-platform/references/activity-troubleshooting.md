# Activity-data troubleshooting

Operational issues hit when running `carto activity export` and `carto activity query`. The SQL-side issues live in [`../../carto-query-datawarehouse/references/activity-queries.md`](../../carto-query-datawarehouse/references/activity-queries.md) — this page covers infrastructure, plan gates, and environmental failures.

## DuckDB install issues

`activity query` requires the DuckDB NPM package. Symptom on first use:

```
DuckDB is required for SQL queries but is not installed.
Install it with: npm install duckdb
```

```bash
npm install duckdb
```

DuckDB is a **native module**. Compilation can take 5–10 minutes the first time. Required toolchain:

| OS | Prerequisite |
|---|---|
| macOS | Xcode Command Line Tools — `xcode-select --install` |
| Linux | `apt-get install build-essential` (or distro equivalent) |
| Windows | Visual Studio Build Tools |

Node 16+ required. `node --version` to confirm.

If `npm install duckdb` fails:

1. **Check toolchain** — try compiling any other native module to confirm the toolchain itself works.
2. **Try with verbose**: `npm install duckdb --verbose` — identifies which compilation step is failing.
3. **Pin Node** — some Node versions briefly broke duckdb's bindings. `nvm install 20 && nvm use 20`.
4. **Pre-built binary** — recent duckdb releases ship pre-built binaries for common platforms. Failures are usually unusual platforms (musl Linux, ARM Windows).

## Plan gate (Enterprise Large+)

Activity export is gated to **Enterprise Large+** plans. Lower plans see:

```
Error: Activity data is not available for your plan
```

If the user is on a lower plan, this is a contract upgrade conversation, not a CLI issue. Don't try to work around it.

## Authentication failures

```bash
carto auth status                 # confirms auth is alive
carto auth login --no-launch-browser   # re-auth if needed
```

If `auth status` shows authenticated but `activity query` returns "Authentication failed", the OAuth scope may be limited. Re-run `auth login` to refresh with full scopes; API tokens from the Workspace Developer section often have a narrower scope that excludes activity data.

## TLS / network issues

In sandboxed harnesses, the network may block CARTO's activity-data endpoints. Whitelist domains per [`../../carto-basics/references/installation.md`](../../carto-basics/references/installation.md). Symptom: `getaddrinfo EAI_AGAIN` or `request to ... failed`.

For self-managed environments behind a proxy, set `HTTPS_PROXY` and confirm the proxy doesn't break TLS:

```bash
export HTTPS_PROXY=http://proxy.internal:8080
carto activity status
```

## Cache and disk space

`activity query` caches downloads at `/tmp/carto-activity-cache/`. Each cache entry is keyed by `{startDate}_{endDate}_parquet`. For a 30-day window, the cache can be hundreds of MB.

```bash
# See what's cached
ls -lh /tmp/carto-activity-cache/

# Force fresh download for a date range
carto activity query --start-date 2026-04-01 --end-date 2026-04-28 \
  --no-cache \
  --sql "SELECT 1"

# Clear all cached data
rm -rf /tmp/carto-activity-cache/
```

If the agent's host has a small `/tmp`, the first export of a wide date range can fill it; clear stale cache entries proactively.

## Date range gotchas

- **End date is exclusive** in some endpoint versions, inclusive in others. If a query that should return today's events doesn't, extend `end-date` by one day.
- **Timezone**: timestamps are UTC. Filtering by `CURRENT_DATE - INTERVAL '1 day'` in a non-UTC server timezone can shift results by a day.
- **Maximum span**: very large date ranges (>180 days) may time out the export. Pull in 30-day chunks for long history.

## Validating data exists for the date range

Before complex queries, sanity-check:

```bash
carto activity query \
  --start-date 2026-04-01 \
  --end-date   2026-04-28 \
  --sql "SELECT COUNT(*) AS n FROM activity"
```

A `0` count for a known-active range usually means a data-export gap on CARTO's side — open a support ticket with the date range.
