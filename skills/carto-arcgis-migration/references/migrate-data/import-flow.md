# Import flow — `carto import` per item

The skill delegates to [`carto-import-export-data`](https://github.com/CartoDB/carto-agent-skills/tree/main/skills/carto-import-export-data) for the actual platform call. This document covers the migration-specific glue — which flags to pass, how to parse output, and how to verify post-import.

> **CLI noun**: in `carto` CLI v0.6.x, the import subcommand is **singular** (`carto import`), not the multi-word `carto imports create` that older recipes (and some upstream `carto-agent-skills` docs) reference. See [`lessons.md`](lessons.md) "carto CLI v0.6.x ships `carto import` (singular)" for the full context.

## Core invocation

For every in-scope entry whose Phase-3 extraction succeeded:

```bash
carto import \
  --file ./out/<item-id>.parquet \
  --connection "$TARGET_CONNECTION" \
  --destination "$TARGET_FQN" \
  --json
```

Add `--overwrite` when the manifest entry was `State: failed` or already had `Target FQN: ...` populated:

```bash
carto import \
  --file ./out/<item-id>.parquet \
  --connection "$TARGET_CONNECTION" \
  --destination "$TARGET_FQN" \
  --overwrite \
  --json
```

Defaults are correct for the common case:

- **Sync** (no `--async`): the CLI polls until completion and exits 0/1 based on the import job result. Good for ≤ 1 GB items where waiting a minute or two is fine.
- **Autoguessing on**: column type detection runs at the warehouse. Only pass `--no-autoguessing` when the user has reported a column-type bug from a previous run (e.g. zip codes parsed as integers, leading zeros lost). In that case ask the user before disabling.

## Building the target FQN

The manifest's front-matter records `target_warehouse`. Compose `<TARGET_FQN>` per the warehouse's syntax:

| `target_warehouse` | FQN shape | Example |
|---|---|---|
| `bigquery` | `<project>.<dataset>.<table>` | `demo-bq.migration.stores` |
| `snowflake` | `<DATABASE>.<SCHEMA>.<TABLE>` (uppercase by default) | `DEMO_DB.MIGRATION.STORES` |
| `redshift` | `<schema>.<table>` | `migration.stores` |
| `postgres` | `<schema>.<table>` | `migration.stores` |
| `databricks` | `<catalog>.<schema>.<table>` | `demo_cat.migration.stores` |
| `oracle` | `<SCHEMA>.<TABLE>` | `MIGRATION.STORES` |

Dataset/schema/catalog: prefer a stable destination set by the user during `discover` (recorded in the manifest entry as `Target FQN` if the user pre-populated it) or default to `<connection-default-dataset>.migration.<table_name>`.

**Special case — connection is `carto_dw`** (the built-in CARTO Data Warehouse): the user-bound token has no permissions on `INFORMATION_SCHEMA`, so dataset discovery via system metadata will fail. Default the destination dataset to **`shared`** (a pre-existing dataset on every `carto_dw` connection):

```
<carto_dw_project>.shared.<table_name>
```

Resolve `<carto_dw_project>` from `carto connections describe carto_dw --json`. Do not try `SELECT * FROM INFORMATION_SCHEMA.SCHEMATA` or similar metadata queries — they will fail with a permission error. See [`lessons.md`](lessons.md) "INFORMATION_SCHEMA is not queryable on `carto_dw`" for the full context.

`<table_name>` derives from the source layer's title, lowercased and slugified:

```python
import re
table_name = re.sub(r"[^a-z0-9_]+", "_", layer_title.lower()).strip("_")
```

If a name collision is detected during the idempotency precheck, append `_<short-item-id>` to disambiguate.

## Idempotency precheck

Before extracting, query the target connection to see if the table already exists. **Note** the positional form — `carto sql query <connection> "<sql>"`, not `--connection` / `--query` flags (see [`lessons.md`](lessons.md) "`carto sql query` takes `<connection>` positionally"):

```bash
carto sql query "$TARGET_CONNECTION" \
  "SELECT COUNT(*) AS n FROM $TARGET_FQN" \
  --json 2>/dev/null
```

Three outcomes:

1. **Query succeeds + returned count matches the source row count from Phase 2** → entry already migrated; skip Phases 3–4 and transition to `State: done` with the existing FQN. Record `Notes: pre-existing target table matched source count`.
2. **Query succeeds + count differs** → partial / stale migration. Use `--overwrite` in Phase 4. The agent doesn't ask the user; the precheck plus the manifest's prior state (`done` / `failed`) is enough signal.
3. **Query fails (table doesn't exist or permissions)** → proceed normally with extraction + import. No `--overwrite` needed.

## Parsing `--json` output

`carto import --json` emits one JSON object per call. Relevant fields after sync completion:

```json
{
  "status": "success",
  "destination": "demo-bq.migration.stores",
  "rowsImported": 12348,
  "schema": [...],
  "jobId": "ab12...",
  "logs": "..."
}
```

Capture:
- `destination` → `Target FQN` on the manifest entry.
- `rowsImported` → cross-check against the post-import `SELECT COUNT(*)` (in normal cases they match).

If `status` is anything other than `success`, treat it as a failure: `State: failed`, `Failure: <status>: <first 80 chars of logs>`. Continue to the next entry.

## Verification

After a successful import, verify with `carto sql query` (positional form):

```bash
carto sql query "$TARGET_CONNECTION" \
  "SELECT COUNT(*) AS n FROM $TARGET_FQN" \
  --json
```

Compare the returned `n` to the Phase-2 source row count. Tolerance: ±1 row. Mismatch → `State: failed`, `Failure: row count mismatch (source=N, target=M)`.

## Async path (rare)

For files near the 1 GB limit (estimated 0.8–1.0 GB), the sync wait can be long. The agent may pass `--async` to get a job ID immediately:

```bash
JOB_ID=$(carto import --file ./out/<item-id>.parquet \
  --connection "$TARGET_CONNECTION" \
  --destination "$TARGET_FQN" \
  --async --json | jq -r '.jobId')
```

Then poll with `carto import status "$JOB_ID" --json`, or per `carto-import-export-data`'s async pattern. For v1 keep it simple: sync mode by default, async only if the user explicitly requests it or a sync call exceeds a 5-minute timeout.

## Errors that aren't failures

A few CARTO Imports API responses warrant a retry rather than a `failed` state:

- `429 Too Many Requests` — back off 30 s, retry once. Persistent 429 → `State: failed`, `Failure: rate-limited; retry later`.
- `503 Service Unavailable` — back off 60 s, retry once.
- Connection error mid-upload — back off 10 s, retry once.

After retries, treat as `failed` and continue.

## Cleanup

The skill leaves `out/<item-id>.parquet` on disk after a successful import — useful for post-mortem and manual re-imports. Re-runs of the skill don't re-extract these files unless the manifest entry is `failed` or the user passes an explicit `--force-extract` cue. The user is responsible for clearing `out/` when they're done with the migration.
