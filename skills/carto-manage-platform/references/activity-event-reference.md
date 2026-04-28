# Activity event-type reference

CARTO emits 150+ event types into the `activity` table. This reference lists the most operationally important ones grouped by domain.

For the full reference (kept current by CARTO docs):
https://docs.carto.com/carto-user-manual/settings/activity-data/activity-data-reference

## Schema (recap)

The `activity` table:

| Column | Type | Notes |
|---|---|---|
| `type` | STRING | Event type (e.g., `MapCreated`). |
| `ts` | TIMESTAMP | Event time, UTC. |
| `data` | JSON STRING | Event payload — contents vary per type. |

For querying patterns, see [`../../carto-query-datawarehouse/references/activity-queries.md`](../../carto-query-datawarehouse/references/activity-queries.md).

## Maps & visualization

| Event | Triggers |
|---|---|
| `MapCreated` | New map created in Builder or via API. |
| `MapUpdated` | Map definition changed (layers, style, sources). |
| `MapDeleted` | Map removed. |
| `MapLoadedEvent` | Builder UI opened a map. |
| `MapPrivacyChanged` | Privacy / sharing setting changed. |
| `MapSnapshotCreated` | Auto-snapshot from Builder edits. |
| `DataSourceCreated` | Dataset added to a map. |
| `DataSourceUpdated` | Dataset config changed (column mapping, filters). |
| `DataSourceDeleted` | Dataset removed from a map. |

Common payload fields: `mapId`, `userId`, `privacy`, `collaborative`.

## Workflows

| Event | Triggers |
|---|---|
| `WorkflowCreated` | New workflow saved. |
| `WorkflowRun` | Run started (manual or scheduled). |
| `WorkflowExecutionComplete` | Run finished successfully. |
| `WorkflowApiExecuted` | Run kicked off via the public API. |
| `WorkflowScheduleCreated` | Schedule added to workflow. |
| `WorkflowScheduleUpdated` | Schedule changed. |
| `WorkflowScheduleDeleted` | Schedule removed. |
| `WorkflowDeleted` | Workflow deleted. |

Common payload: `workflowId`, `userId`, `connectionId`, `runDuration`.

To compute a success rate: count `WorkflowExecutionComplete` / `WorkflowRun` per `workflowId`.

## Connections

| Event | Triggers |
|---|---|
| `ConnectionCreated` | New connection registered. |
| `ConnectionUpdated` | Credentials or scoping changed. |
| `ConnectionDeleted` | Connection removed. |

Common payload: `connectionId`, `provider` (bigquery/snowflake/postgres/...), `userId`.

## Users & auth

| Event | Triggers |
|---|---|
| `UserLogins` | Login (interactive or token). |
| `UserCreated` | Account created (post-invitation accept). |
| `UserDeleted` | Account removed. |
| `UserRoleUpdated` | Role changed. |
| `UserInvited` | Invitation sent. |

Common payload: `userId`, `email`, `role`, `loginMethod`.

## Imports & data

| Event | Triggers |
|---|---|
| `ImportStarted` | `imports create` job started. |
| `ImportCompleted` | Import finished successfully. |
| `ImportFailed` | Import errored. |

Payload: `connectionId`, `destination`, `sizeBytes`, `errorMessage` (on failure).

## Quotas

| Event | Triggers |
|---|---|
| `LdsConsumed` | LDS lookup billed. |
| `HttpRequestConsumed` | Generic API request billed. |
| `QuotaUXTriggered` | A user's action was blocked because a quota limit was hit. |

`QuotaUXTriggered` is the alarm-bell event — frequent occurrences mean users are hitting limits in normal workflows.

## Credentials

| Event | Triggers |
|---|---|
| `TokenCreated` / `TokenDeleted` | API tokens. |
| `OAuthClientCreated` / `OAuthClientDeleted` | SPA / M2M OAuth clients. |

Useful for security audits — "who created the token currently used in production?"

## Practical lookups

| Question | Filter on |
|---|---|
| Who deleted map X? | `type = 'MapDeleted'` AND `data.mapId = 'X'` |
| Why is Bob hitting his quota? | `type = 'QuotaUXTriggered'` AND `data.userId = 'bob-id'` |
| Did the nightly workflow run? | `type IN ('WorkflowRun', 'WorkflowExecutionComplete')` AND `data.workflowId = ...` |
| Who logged in this week? | `type = 'UserLogins'` AND `ts >= CURRENT_DATE - INTERVAL '7 days'` |
| Was a connection rotated? | `type = 'ConnectionUpdated'` AND `data.connectionId = '...'` |
