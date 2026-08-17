---
name: carto-manage-platform
description: Administer the CARTO org — users, roles, quotas, activity audit, and bulk resource operations.
license: MIT
---

# carto-manage-platform

Org-level operations: managing users and invitations, monitoring quotas, auditing activity, and superadmin bulk ops on resources. **Most of these require Admin or Superadmin role**; non-admin users will see permission errors.

> **Access-path routing.** With the CARTO MCP server attached over OAuth, route interactive single-item admin to MCP: `manage_users` (list/invite/role/delete-with-handoff), `manage_api_access_tokens`, `manage_oauth_clients`, `manage_connections`, `organize_projects`, `admin_carto` / `admin_carto_customizations` (org config + stats), `export_activity_data`, `superadmin_carto_resources` (cross-user resource listing), and `delete` for single-resource removal (`kind: map|workflow|connection|token|oauth_client|project_item`). These admin tools are **hidden on token-authenticated MCP sessions** (read/discovery subset only) — reconnect over OAuth or fall back to the CLI. **Stays CLI:** bulk/scripted deletes (`admin batch-delete`), ownership transfer (`admin transfer`), and local DuckDB analysis over exported activity data. Detection signals: [`carto-basics/references/access-paths.md`](../carto-basics/references/access-paths.md).

## When to use this skill

- Provisioning or removing team members.
- Auditing who did what (security review, debugging unexpected changes).
- Monitoring API and LDS quota consumption.
- Rotating ownership of orphaned resources after a user leaves.
- Bulk-deleting test resources.

For *querying* activity data interactively (the exploratory side), use [`carto-query-datawarehouse/references/activity-queries.md`](../carto-query-datawarehouse/references/activity-queries.md). This skill is for the operational/admin surface around activity data.

## Quick reference

Interactive single-item admin (MCP over OAuth): `manage_users`, `manage_api_access_tokens`, `manage_oauth_clients`, `manage_connections`, `admin_carto`, `delete`. CLI covers everything below and is the fallback on token sessions or headless/scripted runs.

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

# Superadmin bulk (CLI-only)
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

- **Deleting a user requires a receiver** to inherit their resources (maps, workflows, connections) — CARTO won't orphan them. Plan handoff first, then `manage_users` (MCP) or `carto users delete <departing-user> <receiving-user>`. Pass valid emails/IDs; check via `manage_users` / `users get` first or the delete fails with "permission denied".
- **Activity export is plan-gated** to Enterprise Large+. Lower plans get a 403 (MCP `export_activity_data`) or error (CLI); surface it politely rather than working around it.
- **`org stats` / `admin_carto` show what *you* can see** — AI limits and billing render only for Admin/Superadmin. Absence of a field isn't absence of the resource.
- **Bulk deletes are irreversible.** `admin batch-delete` removes listed IDs with no per-item confirmation — verify the list, or dry-run with `admin list` first.
- **Audit trail comes from `activity` events**, not tool return values. To answer "who deleted map X", query the `MapDeleted` events — see the activity references.
