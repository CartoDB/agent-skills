# Querying CARTO activity data

`carto activity query` runs **DuckDB SQL locally** over CARTO-exported activity data. It's separate from warehouse SQL — the data is downloaded once into `/tmp/carto-activity-cache/` and then queryable in-process.

## Prerequisites

- **Plan**: Activity data export requires Enterprise Large+. Other plans get an access-denied error.
- **DuckDB**: `npm install duckdb` (native module — first install can take 5–10 min and needs a C++ toolchain).

## Basic usage

```bash
carto activity query \
  --start-date 2026-04-01 \
  --end-date   2026-04-28 \
  --sql "SELECT type, COUNT(*) AS n FROM activity GROUP BY type ORDER BY n DESC LIMIT 10"
```

- First run downloads data; subsequent runs over the same date range reuse the cache.
- Pass `--no-cache` to force a fresh download.
- `--json` for machine output.

## Tables available

| Table | Contents |
|---|---|
| `activity` | Event log: `type`, `ts`, `data` (JSON) |
| `apiUsage` | Daily API usage: `ts`, `user_id`, `metric`, `amount`, `quota_usage_weight` |
| `userList` | Current users: `user_id`, `email`, `created_at`, `role`, `group_ids` |
| `groupList` | Current groups: `group_id`, `group_alias` |

Table names are **case-sensitive** in DuckDB.

## Common patterns

### Who modified a specific map?

```sql duckdb
SELECT
  u.email,
  a.type,
  a.ts
FROM activity a
LEFT JOIN userList u
  ON json_extract_string(a.data, '$.userId') = u.user_id
WHERE json_extract_string(a.data, '$.mapId') = 'MAP_ID_HERE'
  AND a.type IN ('MapUpdated', 'MapSnapshotCreated')
  AND a.ts >= CURRENT_DATE - INTERVAL '7 days'
ORDER BY a.ts DESC
```

### Most active users (last 7 days)

```sql duckdb
SELECT
  u.email,
  u.role,
  COUNT(*) AS total_events,
  COUNT(DISTINCT DATE(a.ts)) AS active_days
FROM activity a
LEFT JOIN userList u
  ON json_extract_string(a.data, '$.userId') = u.user_id
WHERE a.ts >= CURRENT_DATE - INTERVAL '7 days'
  AND json_extract_string(a.data, '$.userId') IS NOT NULL
GROUP BY u.email, u.role
ORDER BY total_events DESC
LIMIT 20
```

### Hourly activity pattern

```sql duckdb
SELECT
  EXTRACT(HOUR FROM ts) AS hour_of_day,
  COUNT(*) AS events,
  COUNT(DISTINCT json_extract_string(data, '$.userId')) AS active_users
FROM activity
WHERE ts >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY EXTRACT(HOUR FROM ts)
ORDER BY hour_of_day
```

### Quota consumption by user

```sql duckdb
SELECT
  u.email,
  SUM(api.amount * api.quota_usage_weight) AS quota_consumed,
  SUM(api.amount) AS total_requests
FROM apiUsage api
LEFT JOIN userList u ON api.user_id = u.user_id
WHERE api.ts >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY u.email
ORDER BY quota_consumed DESC
LIMIT 20
```

## Working with JSON

The `data` column on `activity` is a JSON string. DuckDB extracts:

```sql duckdb
SELECT
  json_extract_string(data, '$.userId')             AS user_id,
  json_extract_string(data, '$.mapId')              AS map_id,
  json_extract_string(data, '$.connection.provider') AS connection_provider
FROM activity
WHERE type LIKE 'Map%'
LIMIT 5
```

`json_extract_string(data, '$.field') IS NOT NULL` is the safe way to filter for events that have a given attribute.

## Best practices

- **Always filter by date**. The data is large; `SELECT * FROM activity` will scan everything in cache.
- **Filter by `type` early**. Event types are highly selective.
- **Join with `userList`** to surface emails instead of opaque user IDs.
- **Reuse cache** for exploratory work over the same date range; pass `--no-cache` only when you need today's data.
- **Limit exploratory output**: `LIMIT 100` on top-level queries.

## DuckDB syntax notes

- `INTERVAL '7 days'` (single quotes), not `interval 7 days`.
- `DATE_TRUNC('month', ts)`, not `date_trunc('month', ts::date)`.
- Cast string→date with `::DATE`.
- Window functions and CTEs are supported (DuckDB is highly Postgres-compatible).
