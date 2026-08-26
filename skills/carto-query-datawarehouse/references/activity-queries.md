# Querying CARTO activity data (CLI-only)

`carto activity query` runs **DuckDB SQL locally** over CARTO-exported activity data — no MCP equivalent. Data is downloaded once into `/tmp/carto-activity-cache/` and then queried in-process, separate from warehouse SQL.

## Prerequisites

- **Plan**: activity-data export requires Enterprise Large+. Other plans get access-denied.
- **DuckDB**: `npm install duckdb` (native module — first install can take 5–10 min and needs a C++ toolchain).

## Basic usage

```bash
carto activity query \
  --start-date 2026-04-01 \
  --end-date   2026-04-28 \
  --sql "SELECT type, COUNT(*) AS n FROM activity GROUP BY type ORDER BY n DESC LIMIT 10"
```

First run downloads data; later runs over the same range reuse the cache. `--no-cache` forces a fresh download; `--json` for machine output.

## Tables (names are case-sensitive)

| Table | Contents |
|---|---|
| `activity` | Event log: `type`, `ts`, `data` (JSON string) |
| `apiUsage` | Daily API usage: `ts`, `user_id`, `metric`, `amount`, `map_id`, `workflow_id`, `quota_usage_weight` |
| `userList` | Users: `user_id`, `email`, `created_at`, `role`, `group_ids` |
| `groupList` | Groups: `group_id`, `group_alias` |

## Common patterns

### Who modified a specific map

```sql duckdb
SELECT u.email, a.type, a.ts
FROM activity a
LEFT JOIN userList u ON json_extract_string(a.data, '$.userId') = u.user_id
WHERE json_extract_string(a.data, '$.mapId') = 'MAP_ID_HERE'
  AND a.type IN ('MapUpdated', 'MapSnapshotCreated')
  AND a.ts >= CURRENT_DATE - INTERVAL '7 days'
ORDER BY a.ts DESC
```

### Most active users (last 7 days)

```sql duckdb
SELECT u.email, u.role, COUNT(*) AS total_events,
       COUNT(DISTINCT DATE(a.ts)) AS active_days
FROM activity a
LEFT JOIN userList u ON json_extract_string(a.data, '$.userId') = u.user_id
WHERE a.ts >= CURRENT_DATE - INTERVAL '7 days'
  AND json_extract_string(a.data, '$.userId') IS NOT NULL
GROUP BY u.email, u.role
ORDER BY total_events DESC
LIMIT 20
```

### Quota consumption by user

```sql duckdb
SELECT u.email,
       SUM(api.amount * api.quota_usage_weight) AS quota_consumed,
       SUM(api.amount) AS total_requests
FROM apiUsage api
LEFT JOIN userList u ON api.user_id = u.user_id
WHERE api.ts >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY u.email
ORDER BY quota_consumed DESC
LIMIT 20
```

### Quota consumption by map (or workflow)

`apiUsage` carries `map_id` and `workflow_id`, so consumption attributes directly to the resource that drove it — no join through `activity` needed. Swap `map_id` for `workflow_id` to rank workflows.

```sql duckdb
SELECT map_id,
       SUM(amount * quota_usage_weight) AS quota_consumed,
       SUM(amount)             AS total_requests,
       COUNT(DISTINCT user_id) AS distinct_users
FROM apiUsage
WHERE map_id IS NOT NULL
  AND ts >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY map_id
ORDER BY quota_consumed DESC
LIMIT 5
```

- Rows with **both** `map_id` and `workflow_id` `NULL` are non-map/non-workflow surfaces (raw SQL API, imports, AI proxy) — not attributable to one resource.
- Public maps accrue quota from anonymous viewers, so those rows have `NULL` `user_id`.
- Break a map down by `metric` to see the driver (Maps API tiling vs. heavier Widgets API vs. AI-agent tokens): add `WHERE map_id = '<id>' GROUP BY metric`.
- Resolve a `map_id` to name/owner with `read_maps` (MCP, `get`) or `carto maps get <map_id>` — both respect map-level ACLs.

## JSON in the `data` column

```sql duckdb
SELECT json_extract_string(data, '$.userId') AS user_id,
       json_extract_string(data, '$.mapId')  AS map_id
FROM activity
WHERE type LIKE 'Map%'
LIMIT 5
```

`json_extract_string(data, '$.field') IS NOT NULL` is the safe filter for events carrying a given attribute.

## Best practices & syntax

- **Always filter by date and `type`** — the data is large and event types are highly selective.
- **Join `userList`** to surface emails instead of opaque IDs; `LIMIT 100` on exploratory queries.
- DuckDB is Postgres-compatible (CTEs, window functions). Note: `INTERVAL '7 days'` (single quotes), `DATE_TRUNC('month', ts)`, cast string→date with `::DATE`.
