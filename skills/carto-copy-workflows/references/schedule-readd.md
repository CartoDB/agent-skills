# Schedules don't copy — re-add after copy

`workflows copy` duplicates the workflow definition (nodes, edges, connection refs, parameters) but **drops any schedule**. A copied workflow lands unscheduled in the destination, and you must re-add the schedule explicitly.

## Why

Schedules execute *inside* the destination warehouse, in that warehouse's scheduling engine. Forcing a schedule to copy implicitly would push expressions written for the source warehouse into the destination — sometimes a different engine entirely (BigQuery → Databricks, for example). Better to require a deliberate re-add than to silently mis-schedule.

## Re-adding after copy

```bash
carto workflows schedule add <new-wf-id> \
  --expression "every day 08:00" \
  --profile prod
```

`<new-wf-id>` is the destination's workflow ID, which `workflows copy` returns (or which you find via `carto workflows list --profile prod --search`).

## Pick the right expression dialect for the destination

The expression syntax depends on the **destination** warehouse engine, not the source. If you copied from BigQuery to Snowflake, the source's natural-language schedule won't work in the destination — Snowflake needs cron.

| Destination engine | Expression dialect |
|---|---|
| BigQuery / CARTO DW | natural language: `"every day 08:00"`, `"every 2 hours"` |
| Snowflake / Postgres / Redshift | standard 5-field cron: `"0 8 * * *"` |
| Databricks | Quartz cron (6-field): `"0 0 8 * * ?"` |

For full dialect detail and examples, see [`../../carto-create-workflow/references/scheduling.md`](../../carto-create-workflow/references/scheduling.md) — that skill owns scheduling depth; this skill just calls out the cross-profile-copy gotcha.

## Inspecting before re-adding

If the source workflow had a schedule, check it before copying so you know what to re-create:

```bash
carto workflows get <wf-id> --profile dev --json | jq '.schedule'
```

If the source and destination are the *same engine* (e.g. dev BigQuery → prod BigQuery), the same expression works. If engines differ, translate.

## Verifying the schedule fired

After re-adding, the next run will emit `WorkflowRun` and (on success) `WorkflowExecutionComplete` events into the destination's activity log. Confirm with:

```bash
carto activity query --profile prod \
  --start-date <yesterday> --end-date <today> \
  --sql "SELECT type, ts FROM activity
         WHERE type IN ('WorkflowRun', 'WorkflowExecutionComplete')
           AND json_extract_string(data, '\$.workflowId') = '<new-wf-id>'
         ORDER BY ts DESC LIMIT 10"
```

See [`../../carto-query-datawarehouse/references/activity-queries.md`](../../carto-query-datawarehouse/references/activity-queries.md) for activity-data patterns.
