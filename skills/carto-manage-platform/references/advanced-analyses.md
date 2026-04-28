# Advanced activity analyses

Curated SQL patterns for the operational/admin questions that come up repeatedly. All run against the four DuckDB-loaded tables (`activity`, `apiUsage`, `userList`, `groupList`) via `carto activity query`.

For schema and basics, see [`../../carto-query-datawarehouse/references/activity-queries.md`](../../carto-query-datawarehouse/references/activity-queries.md).

## User activity by category

```sql duckdb
SELECT
  json_extract_string(data, '$.userId') AS user_id,
  CASE
    WHEN type LIKE 'Map%'        THEN 'Maps'
    WHEN type LIKE 'Workflow%'   THEN 'Workflows'
    WHEN type LIKE 'Connection%' THEN 'Connections'
    WHEN type = 'UserLogins'     THEN 'Authentication'
    ELSE 'Other'
  END AS category,
  COUNT(*) AS events
FROM activity
WHERE ts >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY user_id, category
ORDER BY user_id, events DESC
```

Use to identify primary use case per user — "Alice is 80% workflows, 15% maps, 5% other".

## Most edited maps

```sql duckdb
SELECT
  json_extract_string(data, '$.mapId') AS map_id,
  COUNT(*) AS edit_count,
  COUNT(DISTINCT json_extract_string(data, '$.userId')) AS unique_editors,
  MIN(ts) AS first_edit,
  MAX(ts) AS last_edit
FROM activity
WHERE type IN ('MapUpdated', 'MapSnapshotCreated')
  AND ts >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY map_id
ORDER BY edit_count DESC
LIMIT 20
```

Surfaces the maps under active development — useful before a big platform change to avoid disrupting hot work.

## Workflow success rate

```sql duckdb
SELECT
  json_extract_string(data, '$.workflowId') AS workflow_id,
  COUNT(CASE WHEN type = 'WorkflowRun' THEN 1 END) AS total_runs,
  COUNT(CASE WHEN type = 'WorkflowExecutionComplete' THEN 1 END) AS successful_runs,
  ROUND(100.0
        * COUNT(CASE WHEN type = 'WorkflowExecutionComplete' THEN 1 END)
        / NULLIF(COUNT(CASE WHEN type = 'WorkflowRun' THEN 1 END), 0),
        2) AS success_rate_pct
FROM activity
WHERE type IN ('WorkflowRun', 'WorkflowExecutionComplete')
  AND ts >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY workflow_id
ORDER BY total_runs DESC
```

Surfaces unstable workflows: success_rate_pct < 90 is a good investigation threshold.

## Daily quota usage trends

```sql duckdb
SELECT
  DATE(ts) AS date,
  SUM(amount * quota_usage_weight) AS daily_quota,
  AVG(SUM(amount * quota_usage_weight)) OVER (
    ORDER BY DATE(ts)
    ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
  ) AS seven_day_avg
FROM apiUsage
WHERE ts >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY DATE(ts)
ORDER BY date DESC
```

7-day rolling average smooths the spike-pattern view — useful for capacity planning.

## Connection usage by provider

```sql duckdb
SELECT
  json_extract_string(data, '$.provider') AS provider,
  COUNT(*) AS events,
  COUNT(DISTINCT json_extract_string(data, '$.connectionId')) AS unique_connections,
  COUNT(DISTINCT json_extract_string(data, '$.userId'))       AS unique_users
FROM activity
WHERE json_extract_string(data, '$.provider') IS NOT NULL
  AND ts >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY provider
ORDER BY events DESC
```

Tells you which warehouse engines actually drive your org's traffic — informs CARTO contract negotiation and SE/SA staffing.

## Inactive users

```sql duckdb
SELECT
  u.email,
  u.role,
  MAX(a.ts) AS last_active
FROM userList u
LEFT JOIN activity a
  ON json_extract_string(a.data, '$.userId') = u.user_id
GROUP BY u.email, u.role
HAVING MAX(a.ts) IS NULL
    OR MAX(a.ts) < CURRENT_DATE - INTERVAL '60 days'
ORDER BY last_active NULLS FIRST
```

Surfaces accounts to deprovision. Combine with `users delete <email> <receiver>` (see [users-and-invites.md](users-and-invites.md)) for the cleanup.

## Quota-blocked users

```sql duckdb
SELECT
  json_extract_string(data, '$.userId') AS user_id,
  COUNT(*) AS quota_blocks,
  MAX(ts) AS last_block
FROM activity
WHERE type = 'QuotaUXTriggered'
  AND ts >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY user_id
ORDER BY quota_blocks DESC
LIMIT 20
```

Frequent `QuotaUXTriggered` events indicate users hitting hard limits in normal workflow — escalate to plan upgrade or per-user quota review.

## Connection rotation audit

```sql duckdb
SELECT
  json_extract_string(data, '$.connectionId') AS connection_id,
  json_extract_string(data, '$.userId')       AS rotated_by,
  ts
FROM activity
WHERE type = 'ConnectionUpdated'
  AND ts >= CURRENT_DATE - INTERVAL '90 days'
ORDER BY ts DESC
```

For security audits: who has rotated each connection's credentials, when?
