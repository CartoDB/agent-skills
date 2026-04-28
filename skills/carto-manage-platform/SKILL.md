---
name: carto-manage-platform
description: Administer the CARTO org — users, roles, quotas, activity audit, and bulk resource operations.
license: MIT
---

# carto-manage-platform

Org-level operations: managing users and invitations, monitoring quotas, auditing activity, and superadmin bulk ops on resources. **Most of these commands require Admin or Superadmin role**; non-admin users will see permission errors.

## When to use this skill

- Provisioning or removing team members.
- Auditing who did what (security review, debugging unexpected changes).
- Monitoring API and LDS quota consumption.
- Rotating ownership of orphaned resources after a user leaves.
- Bulk-deleting test resources.

For *querying* activity data interactively (the exploratory side), use [`carto-query-datawarehouse/references/activity-queries.md`](../carto-query-datawarehouse/references/activity-queries.md). This skill is for the operational/admin surface around activity data.

## Quick reference

```bash
# Org overview (users, resources, quotas, AI limits)
carto org stats

# User management
carto users list --all --json
carto users invite alice@example.com --role Builder
carto users get alice@example.com

# Activity audit (Enterprise Large+)
carto activity export \
  --start-date 2026-04-01 --end-date 2026-04-28 \
  --output-dir ./apr-2026

# Superadmin bulk
carto admin list maps --all
carto admin batch-delete
carto admin transfer
```

## What's in this skill

| Topic | Reference |
|---|---|
| `org stats` and quota monitoring | [references/org-and-quotas.md](references/org-and-quotas.md) |
| `users` lifecycle: list, invite, role changes, deletion with handoff | [references/users-and-invites.md](references/users-and-invites.md) |
| `admin` superadmin ops: bulk list, batch delete, resource transfer | [references/admin-bulk-ops.md](references/admin-bulk-ops.md) |
| Activity event-type catalog (150+ events; full reference) | [references/activity-event-reference.md](references/activity-event-reference.md) |
| Advanced activity analyses (success rates, trends, by-category) | [references/advanced-analyses.md](references/advanced-analyses.md) |
| Activity-data troubleshooting (DuckDB install, plan gates, TLS) | [references/activity-troubleshooting.md](references/activity-troubleshooting.md) |

## Always-on guidance

- **Admin permission gates are warehouse-style, not CARTO-style.** Even a CARTO Admin will get "permission denied" from `users delete` if the receiver-id isn't valid. Pass valid emails or user IDs; check via `users get` first.
- **`users delete` requires a receiver** to inherit the deleted user's resources. Without a receiver argument, the command fails. Plan handoff before deletion: `carto users delete <departing-user> <receiving-user>`.
- **Activity export is plan-gated.** Enterprise Large+ only. Lower plans get a 403; surface that politely if the user is on the wrong tier.
- **`org stats` shows what *you* can see**. Some fields (AI limits, billing) only render for Admin/Superadmin. Don't assume the absence of a field means the resource doesn't exist.
- **Bulk operations are irreversible.** `admin batch-delete` deletes the listed resource IDs without further confirmation per item. Double-check the input list, or do a dry-run with `admin list` first.
- **Audit trail comes from `activity` events**, not the CLI return values. To answer "who deleted map X", query the `MapDeleted` events — see the activity-queries reference.
