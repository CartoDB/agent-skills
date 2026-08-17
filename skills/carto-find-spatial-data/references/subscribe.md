# Subscribing to a Data Observatory dataset

Subscription **materializes** the dataset into the user's warehouse as a regular table. Once subscribed, querying is just a normal warehouse read (`execute_query` / `carto sql query`).

Subscribe over MCP with `manage_data_observatory_subscriptions` (`method: subscribe|unsubscribe|list`) — this needs an **OAuth** session; on a token-authenticated session the tool is hidden, so use the `carto do` CLI instead. Discovery (`search_data_observatory`) works on either session — see [data-observatory.md](data-observatory.md).

## Subscribing

- **MCP:** `manage_data_observatory_subscriptions` `method: "subscribe"` with `dataset_id`, `connection`, `destination`, optional `overwrite`, `refresh_schedule`, `variables`.
- **CLI:**

```bash
carto do subscribe <dataset-id> --connection <connection-name> --destination <fully-qualified-table>
```

Required: `connection` (name from `explore_data` `list_connections` / `carto connections list` — determines which warehouse the data lands in) and `destination` (target table FQN, created/overwritten by the subscription).

Optional:

- `overwrite` / `--overwrite` — overwrite existing destination table.
- `refresh_schedule` / `--refresh-schedule <cron>` — auto-refresh (cron/Quartz/natural-language per engine; same dialect rules as workflow scheduling).
- `variables` / `--variables <json>` — for parameterized DO datasets (e.g. year selection for ACS data).

```bash
# Free dataset, one-time materialization
carto do subscribe usa.census.tracts.acs5_2022 \
  --connection carto_dw --destination my_project.do.acs_tracts_2022

# Premium dataset, monthly refresh
carto do subscribe spatial-ai.poi.us \
  --connection carto_dw --destination my_project.do.poi_us \
  --refresh-schedule "0 0 1 * *"
```

## Subscription cost dimensions

Three places cost can accrue — surface all three before subscribing to a premium dataset:

1. **CARTO subscription fee** — paid datasets are charged per dataset per period, usually negotiated upfront in the CARTO contract. `get_dataset` / `carto do get` surfaces the pricing tier.
2. **Warehouse storage** — the materialized table consumes space on the user's warehouse, billed by the warehouse provider. Demographics tables are usually small (≤100 MB per country); mobility/POI tables can be 10–100 GB.
3. **Warehouse compute** — refresh runs spawn warehouse jobs; factor this in for frequent schedules.

## Refresh

- **One-time** (default, no `refresh_schedule`) — materialized once. Static datasets (ACS for a fixed year) usually need only this.
- **Scheduled** — pass `refresh_schedule` / `--refresh-schedule "0 0 1 * *"`. CARTO drives it server-side; the expression follows the warehouse's dialect (see [`carto-create-workflow/references/scheduling.md`](../../carto-create-workflow/references/scheduling.md)).
- **Manual** — re-subscribe with `overwrite` / `--overwrite` to replace the table on demand.

## Querying after subscribe

The destination is just a warehouse table. Read it with `execute_query`, or:

```bash
carto sql query carto_dw "SELECT geoid, total_pop FROM my_project.do.acs_tracts_2022 LIMIT 10"
```

To **enrich** the user's internal data with DO data, spatial-join in SQL — see the dialect-specific examples in [`carto-query-datawarehouse`](../../carto-query-datawarehouse).

## Unsubscribing

`manage_data_observatory_subscriptions` `method: "unsubscribe"` with the subscription id, or `carto do subscriptions unsubscribe <subscription-id>`. This stops future refreshes but **does not delete the destination table** — drop it manually (`execute_async_query` / `carto sql job`) if no longer needed.

## Common errors

- **`Dataset not found`** — typo in the ID, or the dataset is regional and not visible from the user's contracted region.
- **`License not available for your org`** — paid dataset; needs adding to the contract by CARTO sales.
- **`Permission denied`** on the destination — connection's credential lacks write permission. Fix in warehouse-side IAM.
- **`Spatial extension required`** — destination warehouse needs the CARTO spatial extension installed. Admin task; outside this skill.
