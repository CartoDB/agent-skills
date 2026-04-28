# Scheduling workflows

```bash
carto workflows schedule add    <id> --expression <expr> [--connection <name>]
carto workflows schedule update <id> --expression <expr> [--connection <name>]
carto workflows schedule remove <id> [--connection <name>]
```

`--connection` is needed when the workflow's connection has multiple scheduling backends (rare); usually the workflow's primary connection is correct and the flag can be omitted.

## Expression syntax — by engine

The schedule executor lives **inside the warehouse**, so the expression dialect is the warehouse's dialect, not CARTO's.

### BigQuery / CARTO DW — natural language

```bash
--expression "every day 08:00"
--expression "every monday 09:00"
--expression "every 2 hours"
--expression "every weekday 18:30"
```

Times are in the warehouse's configured timezone (usually UTC). Confirm in the BQ Console under Scheduled Queries.

### Snowflake / Postgres — standard cron

5-field cron (`minute hour day-of-month month day-of-week`):

```bash
--expression "0 8 * * *"      # 08:00 every day
--expression "0 9 * * 1"      # 09:00 every Monday
--expression "*/15 * * * *"   # every 15 minutes
--expression "0 0 1 * *"      # midnight on the 1st of each month
```

Snowflake's underlying `TASK` engine uses standard cron. Postgres/Redshift schedules go through CARTO's scheduler service which also accepts standard cron.

### Databricks — Quartz cron

6-field Quartz cron (`second minute hour day-of-month month day-of-week`):

```bash
--expression "0 0 8 * * ?"        # 08:00 every day
--expression "0 0 9 ? * MON"      # 09:00 every Monday
--expression "0 0/15 * * * ?"     # every 15 minutes
```

Note Quartz uses `?` (any) where standard cron uses `*` for one of `day-of-month`/`day-of-week`. Databricks SQL Warehouses and Workflows both use Quartz.

## Picking the right expression

If unsure which dialect the workflow's connection uses, run:

```bash
carto workflows get <id> --json | jq '.connection'
```

Then check the connection's provider:

```bash
carto connections get <connection-id> --json | jq '.provider'
```

| Provider | Expression dialect |
|---|---|
| `bigquery`, `cartodw` | natural language |
| `snowflake`, `postgres`, `redshift` | standard cron |
| `databricks` | Quartz cron |

## Add vs. update

`schedule add` errors if a schedule already exists. `schedule update` replaces the existing schedule. To safely set or re-set, prefer `update`:

```bash
carto workflows schedule update <id> --expression "0 8 * * *"
```

## Remove

```bash
carto workflows schedule remove <id>
```

Removes the schedule but keeps the workflow definition — you can run it manually or re-add a schedule later.

## Verifying a schedule fired

Schedule executions emit `WorkflowRun` and `WorkflowExecutionComplete` events into the activity log. Query via:

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

Or see the curated success-rate query in [`../../carto-query-datawarehouse/references/activity-queries.md`](../../carto-query-datawarehouse/references/activity-queries.md).
