---
name: carto-activity
description: Query CARTO activity logs and usage data with SQL. For analyzing user behavior, map changes, API usage, and quota monitoring.
---

# CARTO Activity Data Analysis Skill

Query and analyze CARTO activity logs using SQL. Answer questions like "What user modified map X yesterday?" or "Which users consumed the most quota this week?"

**This is a companion skill to `carto-cli`.** Use the main `carto-cli` skill for maps, workflows, and connections management. Use this skill for activity log analysis and usage analytics.

## Quick Start

**Most common workflow:**

```bash
# 1. Authenticate (same as carto-cli skill)
NODE_TLS_REJECT_UNAUTHORIZED=0 carto auth status

# 2. Query activity data (last 30 days)
NODE_TLS_REJECT_UNAUTHORIZED=0 carto activity query \
  --start-date 2024-12-20 \
  --end-date 2025-01-19 \
  --sql "SELECT type, COUNT(*) as count FROM activity GROUP BY type ORDER BY count DESC LIMIT 10"
```

**The first query downloads data, subsequent queries reuse cache.**

---

## Prerequisites

### 1. CARTO CLI Installation

Verify the CLI is installed:

```bash
# If using NPM global install
carto --version

# If using bundled skill version
node /mnt/skills/user/carto-cli/carto.js --version
```

### 2. DuckDB Dependency (Required for Queries)

**CRITICAL:** The `activity query` command requires the DuckDB NPM package.

**Check if installed:**
```bash
# Try running a query - if DuckDB is missing, you'll get a clear error
NODE_TLS_REJECT_UNAUTHORIZED=0 carto activity query \
  --start-date 2025-01-01 \
  --end-date 2025-01-01 \
  --sql "SELECT 1"
```

**If you get "DuckDB is required" error, install it:**
```bash
# Install DuckDB as NPM dependency
npm install duckdb

# Note: DuckDB is a native module and may take several minutes to compile
```

**For the skill environment:**
- If using bundled CLI: DuckDB should already be included
- If using global CLI: Run `npm install duckdb` once

### 3. Authentication

Activity data requires authentication. Use the same auth from `carto-cli` skill:

```bash
# Start auth flow
NODE_TLS_REJECT_UNAUTHORIZED=0 carto auth login --no-launch-browser

# User opens URL and authenticates, then pastes callback:
NODE_TLS_REJECT_UNAUTHORIZED=0 carto auth login --callback "https://carto.com/cli-callback?code=..."

# Verify authentication
NODE_TLS_REJECT_UNAUTHORIZED=0 carto auth status
```

### 4. Enterprise Plan Required

Activity data is available for **Enterprise Large+** plans only. Users on other plans will receive an access denied error.

---

## Understanding Activity Data

CARTO exports activity data into four main tables:

### 1. `activity` - Activity Logs
All events in your organization (map edits, workflow runs, logins, etc.)

**Schema:**
- `type` (STRING) - Event type (e.g., `MapCreated`, `UserLogins`, `WorkflowRun`)
- `ts` (TIMESTAMP) - Event timestamp (UTC)
- `data` (JSON STRING) - Full event payload with all details

### 2. `apiUsage` - API Usage Metrics
Daily API usage aggregated by user and metric.

**Schema:**
- `ts` (TIMESTAMP) - Daily timestamp
- `user_id` (STRING) - User ID (`"public"` = unauthenticated)
- `metric` (STRING) - API method + client combination
- `amount` (NUMBER) - Number of requests
- `quota_usage_weight` (NUMBER) - Weight for quota calculation

### 3. `userList` - Current Users
Current users with roles and group membership.

**Schema:**
- `user_id` (STRING) - Unique user identifier
- `email` (STRING) - User email
- `created_at` (TIMESTAMP) - Account creation date
- `role` (STRING) - `Admin`, `Editor`, or `Viewer`
- `group_ids` (ARRAY) - Group memberships

### 4. `groupList` - Current Groups
Organization groups.

**Schema:**
- `group_id` (STRING) - Group identifier
- `group_alias` (STRING) - Group display name

---

## Query Command

```bash
NODE_TLS_REJECT_UNAUTHORIZED=0 carto activity query \
  --start-date YYYY-MM-DD \
  --end-date YYYY-MM-DD \
  --sql "YOUR SQL QUERY"
```

**Flags:**
- `--start-date` (required) - Start date (ISO format: `2025-01-01`)
- `--end-date` (required) - End date (ISO format: `2025-01-31`)
- `--sql` (required) - DuckDB SQL query
- `--no-cache` (optional) - Force fresh download, ignore cache
- `--json` (optional) - Output as JSON

### Data Caching

**First query:** Downloads and caches data in `/tmp/carto-activity-cache/`
**Subsequent queries:** Reuses cached data for same date range
**Cache key:** `{startDate}_{endDate}_parquet`

**Force fresh download:**
```bash
NODE_TLS_REJECT_UNAUTHORIZED=0 carto activity query \
  --start-date 2025-01-01 \
  --end-date 2025-01-31 \
  --no-cache \
  --sql "SELECT COUNT(*) FROM activity"
```

---

## Common Event Types

When users ask about map activity, workflows, or user actions, reference these event types:

### Maps & Visualization
- `MapCreated`, `MapUpdated`, `MapDeleted` - Map lifecycle
- `MapLoadedEvent` - Map opened in Builder
- `MapPrivacyChanged` - Sharing settings changed
- `DataSourceCreated`, `DataSourceUpdated`, `DataSourceDeleted` - Map data sources

### Workflows
- `WorkflowCreated`, `WorkflowRun`, `WorkflowExecutionComplete` - Workflow lifecycle
- `WorkflowApiExecuted` - Workflow run via API
- `WorkflowScheduleCreated` - Scheduled workflow

### Users & Auth
- `UserLogins` - Login events
- `UserCreated`, `UserDeleted`, `UserRoleUpdated` - User management

### Connections
- `ConnectionCreated`, `ConnectionUpdated`, `ConnectionDeleted` - Connection lifecycle

### Quota Events
- `LdsConsumed` - Location Data Services usage
- `HttpRequestConsumed` - HTTP request quota usage
- `QuotaUXTriggered` - Action blocked by quota limit

**Complete reference (150+ event types):**
https://docs.carto.com/carto-user-manual/settings/activity-data/activity-data-reference

---

## Interactive Query Examples

Use these patterns to answer user questions about their activity data.

### "What user modified map X yesterday?"

```sql
SELECT
  json_extract_string(data, '$.userId') as user_id,
  type,
  ts
FROM activity
WHERE json_extract_string(data, '$.mapId') = 'MAP_ID_HERE'
  AND type IN ('MapUpdated', 'MapSnapshotCreated')
  AND ts >= CURRENT_DATE - INTERVAL '1 day'
ORDER BY ts DESC
```

Then join with `userList` to get email:
```sql
SELECT
  u.email,
  a.type,
  a.ts
FROM activity a
LEFT JOIN userList u ON json_extract_string(a.data, '$.userId') = u.user_id
WHERE json_extract_string(a.data, '$.mapId') = 'MAP_ID_HERE'
  AND a.type IN ('MapUpdated', 'MapSnapshotCreated')
  AND a.ts >= CURRENT_DATE - INTERVAL '1 day'
ORDER BY a.ts DESC
```

### "Who are my most active users this week?"

```sql
SELECT
  u.email,
  u.role,
  COUNT(*) as total_events,
  COUNT(DISTINCT DATE(a.ts)) as active_days
FROM activity a
LEFT JOIN userList u ON json_extract_string(a.data, '$.userId') = u.user_id
WHERE a.ts >= CURRENT_DATE - INTERVAL '7 days'
  AND json_extract_string(a.data, '$.userId') IS NOT NULL
GROUP BY u.email, u.role
ORDER BY total_events DESC
LIMIT 20
```

### "How many maps were created this month?"

```sql
SELECT
  DATE(ts) as date,
  COUNT(*) as maps_created
FROM activity
WHERE type = 'MapCreated'
  AND ts >= DATE_TRUNC('month', CURRENT_DATE)
GROUP BY DATE(ts)
ORDER BY date DESC
```

### "Which workflows ran today?"

```sql
SELECT
  json_extract_string(data, '$.workflowId') as workflow_id,
  COUNT(*) as run_count,
  MIN(ts) as first_run,
  MAX(ts) as last_run
FROM activity
WHERE type IN ('WorkflowRun', 'WorkflowApiExecuted')
  AND ts >= CURRENT_DATE
GROUP BY workflow_id
ORDER BY run_count DESC
```

### "Who consumed the most API quota this week?"

```sql
SELECT
  u.email,
  SUM(api.amount * api.quota_usage_weight) as quota_consumed,
  SUM(api.amount) as total_requests
FROM apiUsage api
LEFT JOIN userList u ON api.user_id = u.user_id
WHERE api.ts >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY u.email
ORDER BY quota_consumed DESC
LIMIT 20
```

### "What connections were created or modified recently?"

```sql
SELECT
  type,
  json_extract_string(data, '$.connectionId') as connection_id,
  json_extract_string(data, '$.provider') as provider,
  json_extract_string(data, '$.userId') as user_id,
  ts
FROM activity
WHERE type IN ('ConnectionCreated', 'ConnectionUpdated')
  AND ts >= CURRENT_DATE - INTERVAL '7 days'
ORDER BY ts DESC
```

### "Show me hourly activity patterns"

```sql
SELECT
  EXTRACT(HOUR FROM ts) as hour_of_day,
  COUNT(*) as events,
  COUNT(DISTINCT json_extract_string(data, '$.userId')) as active_users
FROM activity
WHERE ts >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY EXTRACT(HOUR FROM ts)
ORDER BY hour_of_day
```

---

## Working with JSON Data

The `data` column contains detailed event information in JSON format. Use DuckDB's JSON functions to extract fields:

### Common Patterns

```sql
-- Extract user who performed action
json_extract_string(data, '$.userId')

-- Extract map ID
json_extract_string(data, '$.mapId')

-- Extract workflow ID
json_extract_string(data, '$.workflowId')

-- Extract connection provider
json_extract_string(data, '$.provider')

-- Extract nested fields
json_extract_string(data, '$.map.id')
json_extract_string(data, '$.connection.provider')

-- Check if field exists
json_extract_string(data, '$.fieldName') IS NOT NULL
```

### Example: Extract All Map Edit Details

```sql
SELECT
  type,
  ts,
  json_extract_string(data, '$.userId') as user_id,
  json_extract_string(data, '$.mapId') as map_id,
  json_extract_string(data, '$.privacy') as privacy,
  json_extract_string(data, '$.collaborative') as collaborative
FROM activity
WHERE type IN ('MapCreated', 'MapUpdated', 'MapPrivacyChanged')
  AND ts >= CURRENT_DATE - INTERVAL '7 days'
ORDER BY ts DESC
LIMIT 100
```

---

## Advanced Analysis Examples

### User Activity by Category

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

### Most Edited Maps

```sql
SELECT
  json_extract_string(data, '$.mapId') as map_id,
  COUNT(*) as edit_count,
  COUNT(DISTINCT json_extract_string(data, '$.userId')) as unique_editors,
  MIN(ts) as first_edit,
  MAX(ts) as last_edit
FROM activity
WHERE type IN ('MapUpdated', 'MapSnapshotCreated')
  AND ts >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY map_id
ORDER BY edit_count DESC
LIMIT 20
```

### Workflow Success Rate

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

### Daily Quota Usage Trends

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

### Connection Usage by Provider

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

---

## Export Command (Optional)

To export raw data files instead of querying:

```bash
NODE_TLS_REJECT_UNAUTHORIZED=0 carto activity export \
  --start-date 2025-01-01 \
  --end-date 2025-01-31 \
  --output-dir ./activity-data
```

**Flags:**
- `--start-date` (required) - Start date
- `--end-date` (required) - End date
- `--output-dir` (optional) - Directory for files (default: `./activity-data`)
- `--format` (optional) - `csv` or `parquet` (default: `csv`)
- `--category` (optional) - Specific category: `activity`, `apiUsage`, `userList`, or `groupList`

**Output:** Creates Parquet or CSV files in the specified directory.

---

## Best Practices

### 1. Always Use Date Filters

Queries scan large datasets. Always filter by date:

```sql
-- Good
WHERE ts >= '2025-01-01' AND ts < '2025-02-01'

-- Bad - scans entire dataset
SELECT * FROM activity
```

### 2. Filter by Event Type Early

Event types are highly selective:

```sql
-- Good - filter type first
WHERE type = 'MapCreated'
  AND ts >= CURRENT_DATE - INTERVAL '7 days'

-- Less efficient
WHERE ts >= CURRENT_DATE - INTERVAL '7 days'
  AND type = 'MapCreated'
```

### 3. Join with Users for Readable Output

Always join with `userList` to show emails instead of user IDs:

```sql
SELECT
  u.email,
  a.type,
  COUNT(*) as events
FROM activity a
LEFT JOIN userList u ON json_extract_string(a.data, '$.userId') = u.user_id
GROUP BY u.email, a.type
```

### 4. Use Cache Wisely

- **Reuse cache** for exploratory queries with same date range
- **Use `--no-cache`** when you need fresh data (e.g., checking today's activity)

### 5. Limit Large Result Sets

Always use `LIMIT` for exploratory queries:

```sql
SELECT * FROM activity
WHERE ts >= CURRENT_DATE
ORDER BY ts DESC
LIMIT 100
```

---

## Troubleshooting

### "DuckDB is required" Error

If you see:
```
DuckDB is required for SQL queries but is not installed.
Install it with: npm install duckdb
```

**Fix:**
```bash
# Install DuckDB NPM package
npm install duckdb

# This is a native module - compilation may take 5-10 minutes
# You'll see output like "node-gyp rebuild" during installation
```

**Common installation issues:**
- **Missing build tools:** DuckDB requires C++ compiler
  - macOS: Install Xcode Command Line Tools (`xcode-select --install`)
  - Linux: Install `build-essential` (`apt-get install build-essential`)
  - Windows: Install Visual Studio Build Tools
- **Node version:** Ensure Node.js 16+ is installed (`node --version`)

### Authentication Errors

```bash
# Check auth status
NODE_TLS_REJECT_UNAUTHORIZED=0 carto auth status

# Re-authenticate if needed
NODE_TLS_REJECT_UNAUTHORIZED=0 carto auth login --no-launch-browser
```

### "Access Denied" or 404 Error

Activity data requires **Enterprise Large+** plan. Users on other plans cannot access this feature.

### TLS Certificate Errors

Always include `NODE_TLS_REJECT_UNAUTHORIZED=0`:

```bash
# Correct
NODE_TLS_REJECT_UNAUTHORIZED=0 carto activity query ...

# Wrong - will fail
carto activity query ...
```

### Query Syntax Errors

DuckDB SQL has some differences from PostgreSQL:

- Use `DATE_TRUNC('month', ts)` not `date_trunc('month', ts::date)`
- Use `INTERVAL '7 days'` not `interval '7 days'`
- Table names: `activity`, `apiUsage`, `userList`, `groupList` (case-sensitive)

### Large Downloads

First query for a date range downloads all data (can be several MB). Subsequent queries reuse cache.

**Tip:** Start with smaller date ranges (7 days) for testing, then expand to 30+ days for full analysis.

---

## Common Workflow

```bash
# 1. Verify authentication
NODE_TLS_REJECT_UNAUTHORIZED=0 carto auth status

# 2. Start with overview query (downloads data)
NODE_TLS_REJECT_UNAUTHORIZED=0 carto activity query \
  --start-date 2025-01-01 \
  --end-date 2025-01-31 \
  --sql "SELECT type, COUNT(*) as count FROM activity GROUP BY type ORDER BY count DESC LIMIT 20"

# 3. Drill into specific event type (uses cache)
NODE_TLS_REJECT_UNAUTHORIZED=0 carto activity query \
  --start-date 2025-01-01 \
  --end-date 2025-01-31 \
  --sql "SELECT json_extract_string(data, '$.userId') as user, COUNT(*) FROM activity WHERE type = 'MapCreated' GROUP BY user ORDER BY COUNT(*) DESC"

# 4. Get user details (uses cache)
NODE_TLS_REJECT_UNAUTHORIZED=0 carto activity query \
  --start-date 2025-01-01 \
  --end-date 2025-01-31 \
  --sql "SELECT u.email, COUNT(*) as maps_created FROM activity a LEFT JOIN userList u ON json_extract_string(a.data, '$.userId') = u.user_id WHERE a.type = 'MapCreated' GROUP BY u.email ORDER BY maps_created DESC"
```

---

## Additional Resources

- **Event Reference**: https://docs.carto.com/carto-user-manual/settings/activity-data/activity-data-reference
- **Query Examples**: https://docs.carto.com/carto-user-manual/settings/activity-data/activity-data-examples
- **DuckDB SQL Docs**: https://duckdb.org/docs/sql/introduction

When users ask about specific event types or need schema details, use WebFetch to retrieve the latest documentation.
