# Org stats and quotas

## `carto org stats`

```bash
carto org stats [--json]
```

Returns the org-level view of consumption and limits. The exact fields depend on the user's role:

- **Admin / Superadmin**: full picture — users count, resources by type, API quota usage, LDS quota usage, AI feature limits, billing tier.
- **Builder / Editor**: their own usage stats only.
- **Viewer / Guest**: typically minimal (own profile only).

### Typical fields (Admin view)

```json
{
  "org_id": "...",
  "users": { "total": 42, "by_role": { "Admin": 2, "Builder": 30, "Viewer": 10 } },
  "resources": {
    "maps": 158,
    "workflows": 23,
    "connections": 7,
    "tilesets": 12
  },
  "quotas": {
    "api_requests": { "used": 45120, "limit": 1000000, "period": "monthly" },
    "lds_requests": { "used": 1230, "limit": 50000, "period": "monthly" }
  },
  "ai_features": {
    "map_agents_calls": { "used": 487, "limit": 10000 }
  }
}
```

Field set evolves; treat unknown fields as additive. Always pass `--json` to consume programmatically.

## Quota dimensions

CARTO meters several dimensions per org, each with its own limit and reset cadence:

| Quota | What it counts | Reset |
|---|---|---|
| **API requests** | Calls to CARTO Maps API, SQL API, Imports API. | Monthly. |
| **LDS requests** | Location Data Services lookups (geocoding, isolines, routing). | Monthly. |
| **AI feature calls** | Map AI agent and LiteLLM proxy usage. | Monthly. |
| **Active maps / workflows** | Count, not call rate. | Static — counted at any time. |
| **Storage** | Tilesets and CARTO-managed materializations (subscriptions). Warehouse storage is billed separately by the warehouse. | Static. |

`org stats` shows the first four. Storage is reported by the warehouse provider.

## Detecting "near-limit"

A daily check pattern:

```bash
carto org stats --json | jq '
  .quotas
  | to_entries
  | map({
      name: .key,
      pct: (.value.used / .value.limit * 100 | round)
    })
  | map(select(.pct > 80))
'
```

Alerts on quotas above 80%. Wire this into a cron / GitHub Action / monitoring platform of choice.

## Per-user quota attribution

`org stats` is org-wide. To attribute consumption to specific users, query the `apiUsage` table via [`carto-query-datawarehouse/references/activity-queries.md`](../../carto-query-datawarehouse/references/activity-queries.md):

```bash
carto activity query \
  --start-date 2026-04-01 \
  --end-date   2026-04-28 \
  --sql "SELECT u.email,
                SUM(api.amount * api.quota_usage_weight) AS quota_consumed
         FROM apiUsage api
         LEFT JOIN userList u ON api.user_id = u.user_id
         GROUP BY u.email
         ORDER BY quota_consumed DESC
         LIMIT 20"
```

That's how you turn "we hit our quota" into "Alice's daily ETL is consuming 60% of it".

`apiUsage` also carries `map_id` and `workflow_id` columns, so the same table answers
"which map (or workflow) is driving consumption?" — group by `map_id` / `workflow_id`
instead of `user_id`. See [Quota consumption by map](../../carto-query-datawarehouse/references/activity-queries.md) for the pattern.
