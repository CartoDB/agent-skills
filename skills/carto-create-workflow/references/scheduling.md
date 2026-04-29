# Scheduling workflows

Command surface and schedule-expression dialects per engine are documented in the CLI itself:

```bash
carto workflows --help        # see "Schedule Expression Formats" footer
carto workflows schema schedule
```

This file only covers what the CLI doesn't: behavioural quirks and verification.

## `add` vs. `update`

`carto workflows schedule add` errors if a schedule already exists. `schedule update` replaces the existing schedule. To safely set or re-set, prefer `update` — it's idempotent on existing schedules and creates a new one when none exists.

```bash
carto workflows schedule update <id> --expression "0 8 * * *"
```

## Bundle-level `schedule` does not activate a cron

`config.schedule` (see `carto workflows schema schedule`) is **declarative metadata only**. Adding it to a bundle on `create`/`update` does not register a warehouse cron — the CLI emits a `SCHEDULE_NOT_ACTIVATED` warning. The schedule fires only after running:

```bash
carto workflows schedule add <id> --expression <expr>
```

## Picking the dialect

If unsure which dialect the workflow's connection uses:

```bash
carto workflows get <id> --json | jq '.connectionId' \
  | xargs -I{} carto connections list --json \
  | jq '.[] | select(.id == "{}") | .provider'
```

The provider→dialect mapping is in `carto workflows --help` under "Schedule Expression Formats".

## Verifying a schedule fired

Schedule executions emit `WorkflowRun` and `WorkflowExecutionComplete` events into the activity log:

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
carto workflows schedule remove <id>
```

Removes the schedule but keeps the workflow definition — you can run it manually or re-add a schedule later.
