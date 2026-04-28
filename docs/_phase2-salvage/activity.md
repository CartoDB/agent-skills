# Activity data — deferred content

> Salvaged from the pre-redesign `carto-activity/SKILL.md`. Target Phase 2 skill:
> `carto-manage-platform`. Query patterns are *not* duplicated here — they live in
> `skills/carto-query-datawarehouse/references/activity-queries.md`.

## Prerequisites (admin/operator concerns)

- **DuckDB**: `activity query` requires the DuckDB NPM package. Install with
  `npm install duckdb`. Native module — compilation can take 5–10 minutes.
  Requires a C++ toolchain (Xcode CLT on macOS, `build-essential` on Linux,
  Visual Studio Build Tools on Windows). Node 16+.
- **Plan gate**: Activity data is available for **Enterprise Large+** plans only.
  Users on other plans get an access-denied error.

## Schema reference

Four tables.

### `activity` — event log
| Column | Type | Notes |
|---|---|---|
| `type` | STRING | Event type (`MapCreated`, `WorkflowRun`, `UserLogins`, …) |
| `ts` | TIMESTAMP | Event timestamp (UTC) |
| `data` | JSON STRING | Full event payload |

### `apiUsage` — daily API usage
| Column | Type | Notes |
|---|---|---|
| `ts` | TIMESTAMP | Daily timestamp |
| `user_id` | STRING | `"public"` for unauthenticated |
| `metric` | STRING | API method + client |
| `amount` | NUMBER | Request count |
| `quota_usage_weight` | NUMBER | Weight for quota calculation |

### `userList` — current users
`user_id`, `email`, `created_at`, `role` (`Admin`/`Editor`/`Viewer`), `group_ids` (ARRAY).

### `groupList` — current groups
`group_id`, `group_alias`.

## Common event types (selected)

**Maps & visualization:** `MapCreated`, `MapUpdated`, `MapDeleted`, `MapLoadedEvent`, `MapPrivacyChanged`, `DataSourceCreated`, `DataSourceUpdated`, `DataSourceDeleted`.
**Workflows:** `WorkflowCreated`, `WorkflowRun`, `WorkflowExecutionComplete`, `WorkflowApiExecuted`, `WorkflowScheduleCreated`.
**Users & auth:** `UserLogins`, `UserCreated`, `UserDeleted`, `UserRoleUpdated`.
**Connections:** `ConnectionCreated`, `ConnectionUpdated`, `ConnectionDeleted`.
**Quota:** `LdsConsumed`, `HttpRequestConsumed`, `QuotaUXTriggered`.

Full reference (150+ events): https://docs.carto.com/carto-user-manual/settings/activity-data/activity-data-reference

## Advanced analyses

(Examples to fold into `carto-manage-platform` references when that skill lands.)

### User activity by category

```sql
SELECT
  json_extract_string(data, '$.userId') as user_id,
  CASE
    WHEN type LIKE 'Map%' THEN 'Maps'
    WHEN type LIKE 'Workflow%' THEN 'Workflows'
    WHEN type LIKE 'Connection%' THEN 'Connections'
    WHEN type = 'UserLogins' THEN 'Authentication'
    ELSE 'Other'
  END as category,
  COUNT(*) as events
FROM activity
WHERE ts >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY user_id, category
ORDER BY user_id, events DESC
```

### Workflow success rate

```sql
SELECT
  json_extract_string(data, '$.workflowId') as workflow_id,
  COUNT(CASE WHEN type = 'WorkflowRun' THEN 1 END) as total_runs,
  COUNT(CASE WHEN type = 'WorkflowExecutionComplete' THEN 1 END) as successful_runs,
  ROUND(100.0 * COUNT(CASE WHEN type = 'WorkflowExecutionComplete' THEN 1 END) /
        NULLIF(COUNT(CASE WHEN type = 'WorkflowRun' THEN 1 END), 0), 2) as success_rate_pct
FROM activity
WHERE type IN ('WorkflowRun', 'WorkflowExecutionComplete')
  AND ts >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY workflow_id
ORDER BY total_runs DESC
```

### Daily quota usage trends

```sql
SELECT
  DATE(ts) as date,
  SUM(amount * quota_usage_weight) as daily_quota,
  AVG(SUM(amount * quota_usage_weight)) OVER (
    ORDER BY DATE(ts)
    ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
  ) as seven_day_avg
FROM apiUsage
WHERE ts >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY DATE(ts)
ORDER BY date DESC
```

### Connection usage by provider

```sql
SELECT
  json_extract_string(data, '$.provider') as provider,
  COUNT(*) as events,
  COUNT(DISTINCT json_extract_string(data, '$.connectionId')) as unique_connections,
  COUNT(DISTINCT json_extract_string(data, '$.userId')) as unique_users
FROM activity
WHERE json_extract_string(data, '$.provider') IS NOT NULL
  AND ts >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY provider
ORDER BY events DESC
```

## Operator-side troubleshooting

- **DuckDB install failures**: native module — verify a C++ toolchain is on the machine before reporting a bug.
- **Auth errors**: covered in `carto-basics/references/authentication.md`.
- **404 / "Access Denied"**: plan gate — confirm the org is Enterprise Large+.

## Resources

- Event reference: https://docs.carto.com/carto-user-manual/settings/activity-data/activity-data-reference
- Query examples: https://docs.carto.com/carto-user-manual/settings/activity-data/activity-data-examples
- DuckDB SQL: https://duckdb.org/docs/sql/introduction
