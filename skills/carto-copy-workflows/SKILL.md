---
name: carto-copy-workflows
description: Copy CARTO Workflows across organizations or profiles, with connection mapping and schedule re-add.
license: MIT
---

# carto-copy-workflows

`workflows copy` duplicates a workflow definition from one CARTO profile (org / environment) to another. The typical use is **dev → prod promotion**, but the same verb covers same-tier relocation (e.g. moving a customer workflow into a customer-segregated org). Copy is **mechanical replication**, not creation — for authoring a workflow from scratch use [`carto-create-analytics-workflow`](../carto-create-analytics-workflow).

## When to use this skill

- The user wants to promote a workflow from `dev` to `prod` (or any cross-profile copy).
- The user is moving a workflow into a customer's segregated org.
- The user copied a workflow and the first run failed with "connection not found" — connection mapping went wrong.
- Schedules are missing on the destination after copying — they don't transfer.

## Quick reference

```bash
# Auto-map connections by name (dev and prod both have e.g. carto_dw)
carto workflows copy <wf-id> \
  --source-profile dev \
  --dest-profile   prod

# Explicit connection mapping when names differ
carto workflows copy <wf-id> \
  --source-profile dev \
  --dest-profile   prod \
  --connection-mapping "carto_dw_dev=carto_dw_prod"

# Re-add the schedule (schedules don't copy)
carto workflows schedule add <new-wf-id> \
  --expression "every day 08:00" \
  --profile prod
```

## What's in this skill

| Topic | Reference |
|---|---|
| Cross-profile copy mechanics: connection mapping, validation flags, title/privacy | [references/cross-profile-copy.md](references/cross-profile-copy.md) |
| Schedules don't transfer — how to re-add them after copy | [references/schedule-readd.md](references/schedule-readd.md) |

## Always-on guidance

- **Always run `connections list` on both source and destination first.** The single most common failure mode is a connection-name mismatch between profiles. A two-second check up-front avoids a "connection not found" loop.
- **`workflows copy` always creates a new workflow** in the destination — there's no in-place update. Subsequent edits are independent: edit in dev, `update` separately in prod with the prod workflow ID.
- **Schedules don't copy.** Use `workflows schedule add` after the copy. The expression syntax depends on the destination's warehouse engine — see [references/schedule-readd.md](references/schedule-readd.md).
- **Workflow execution status** lives in the activity log (`WorkflowRun`, `WorkflowExecutionComplete`). Verify a copied workflow ran via [`carto-query-datawarehouse/references/activity-queries.md`](../carto-query-datawarehouse/references/activity-queries.md).
- For copying **maps** (with their AI-agent caveats), use [`carto-copy-maps`](../carto-copy-maps). For copying maps that depend on workflows, copy the workflow **first** so the map's tool references can be resolved manually in Builder.
