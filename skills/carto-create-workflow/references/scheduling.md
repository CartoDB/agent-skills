# Scheduling workflows

On an OAuth MCP session, scheduling maps to `schedule_workflow` (method=create|update|delete). On the CLI (or a token MCP session) use `carto workflows schedule`. Command surface and per-engine expression dialects are documented in the CLI itself:

```bash
carto workflows --help        # see "Schedule Expression Formats" footer
carto workflows schema schedule
```

This file only covers what live introspection doesn't: behavioural quirks and verification.

## `create` vs. `update`

`create` errors if a schedule already exists; `update` replaces an existing one.

`create` refuses what Builder's scheduler refuses: a workflow that has never run (run it once first; `carto workflows run` records the run), Redshift connections, BigQuery OAuth connections without BigQuery Data Transfer, and connections whose warehouse permissions don't allow scheduled queries.

```bash
carto workflows schedule update <id> --expression "0 8 * * *"
```

## Bundle-level `schedule` does not activate a cron

`config.schedule` (see `carto workflows schema schedule`) is **declarative metadata only**. Adding it to a bundle on `create`/`update` does not register a warehouse cron — the CLI emits a `SCHEDULE_NOT_ACTIVATED` warning. The schedule fires only after running:

```bash
carto workflows schedule create <id> --expression <expr>
```

## Picking the dialect

If unsure which dialect the workflow's connection uses, read the workflow's `connectionId` (`carto workflows get <id> --json` or `read_workflows method=get`), then look up that connection's `provider` (`carto connections list --json` or `explore_data method=list_connections`). The provider→dialect mapping is in `carto workflows --help` under "Schedule Expression Formats".

## Verifying a schedule fired

Schedule executions emit `WorkflowRun` and `WorkflowExecutionComplete` events into the activity log. Querying it uses `carto activity query` (CLI-only — no MCP equivalent):

```bash
carto activity query \
  --start-date $(date -v-7d +%Y-%m-%d) \
  --end-date   $(date +%Y-%m-%d) \
  --sql "SELECT type, ts, json_extract_string(data, '\$.workflowId') as wfid
         FROM activity
         WHERE type IN ('WorkflowRun', 'WorkflowExecutionComplete')
           AND json_extract_string(data, '\$.workflowId') = '<your-id>'
         ORDER BY ts DESC LIMIT 50"
```

For a curated success-rate query, see [`../../carto-query-datawarehouse/references/activity-queries.md`](../../carto-query-datawarehouse/references/activity-queries.md).

## Removing a schedule

```bash
carto workflows schedule delete <id>
```

Deletes the schedule but keeps the workflow definition — you can run it manually or create a schedule again later.
