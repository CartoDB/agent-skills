---
name: carto-create-analytics-workflow
description: Build, schedule, and operate analytics DAGs in CARTO Workflows — the no-code/low-code orchestration layer over the data warehouse.
license: MIT
---

# carto-create-analytics-workflow

CARTO Workflows is a visual DAG builder that compiles to warehouse SQL. Each workflow runs *inside* a connected warehouse — no CARTO compute is involved at execution time. The CLI exposes CRUD, copy-between-orgs, and schedule management.

## When to use this skill

- The user wants to inspect, edit, or delete an existing workflow.
- The user wants to **promote a dev workflow into prod** (cross-profile copy with optional connection re-mapping).
- The user wants to schedule (or unschedule) a workflow.
- The user is debugging why a scheduled run failed.

For one-off ad-hoc SQL, use [`carto-query-datawarehouse`](../carto-query-datawarehouse) (`sql query` / `sql job`) — workflows are for repeatable, scheduled, multi-step DAGs.

## Quick reference

```bash
# List workflows in the current profile
carto workflows list --json

# Detailed view of one workflow (returns the DAG JSON)
carto workflows get <id>

# Update with edited JSON
carto workflows update <id> --file workflow.json

# Promote dev → prod, auto-mapping connections by name
carto workflows copy <id> --source-profile dev --dest-profile prod

# Add a daily schedule
carto workflows schedule add <id> --expression "every day 08:00"

# Remove a schedule
carto workflows schedule remove <id>
```

## What's in this skill

| Topic | Reference |
|---|---|
| `workflows` CRUD: list, get, update, delete, copy | [references/workflows-crud.md](references/workflows-crud.md) |
| Schedules: `add` / `update` / `remove`, expression formats per engine | [references/scheduling.md](references/scheduling.md) |
| Cross-profile promotion (dev → prod) and connection re-mapping | [references/copy-promotion.md](references/copy-promotion.md) |

## Always-on guidance

- **Workflows run on the connection's warehouse.** A workflow with a BigQuery connection cannot use Snowflake-specific SQL. When copying across profiles with different engines, expect to manually fix any dialect-specific nodes.
- **Schedule expression syntax depends on the engine** — natural-language for BQ/CARTO DW (`"every day 08:00"`), cron for Snowflake/Postgres (`"0 8 * * *"`), Quartz cron for Databricks (`"0 0 8 * * ?"`). See [references/scheduling.md](references/scheduling.md). Picking the wrong dialect will fail at schedule-add time.
- **`workflows copy` auto-maps connections by name across profiles.** If `dev` has connection `carto_dw_dev` and `prod` has `carto_dw_prod`, you must pass `--connection-mapping "carto_dw_dev=carto_dw_prod"` — the auto-mapping only matches identical names.
- **Deleting a workflow doesn't delete its outputs.** Tables/views the workflow created in the warehouse persist; clean them up with `carto sql job` if needed.
- **`workflows update` replaces the whole DAG.** There's no per-node patch. Always `get` first, edit, then `update`.
- **Workflow execution status** lives in the activity log (`WorkflowRun`, `WorkflowExecutionComplete` event types). For health monitoring of scheduled workflows, query that log via [`carto-query-datawarehouse`](../carto-query-datawarehouse) — see `references/activity-queries.md` in that skill.
