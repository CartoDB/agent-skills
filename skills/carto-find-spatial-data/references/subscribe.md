# Subscribing to a Data Observatory dataset

Subscription **materializes** the dataset into the user's warehouse as a regular table. Once subscribed, querying is just `carto sql query` over a normal warehouse table.

## Subscribing

```bash
carto do subscribe <dataset-id> \
  --connection <connection-name> \
  --destination <fully-qualified-table>
```

Required flags:

- `--connection` — connection name from `connections list`. Determines which warehouse the data lands in.
- `--destination` — target table FQN in the warehouse's syntax. The table is created/overwritten by the subscription.

Optional flags:

- `--overwrite` — overwrite existing destination table.
- `--refresh-schedule <cron>` — auto-refresh schedule (cron / Quartz / natural language depending on engine; same dialect rules as workflow scheduling).
- `--variables <json>` — for parameterized DO datasets (e.g., year selection for ACS data).
- `--json` — machine-readable output.

```bash
# Free dataset, one-time materialization
carto do subscribe usa.census.tracts.acs5_2022 \
  --connection carto_dw \
  --destination my_project.do.acs_tracts_2022

# Premium dataset, monthly refresh
carto do subscribe spatial-ai.poi.us \
  --connection carto_dw \
  --destination my_project.do.poi_us \
  --refresh-schedule "0 0 1 * *"
```

## Subscription cost dimensions

Three places cost can accrue:

1. **CARTO subscription fee** — paid datasets are charged per dataset per period; usually negotiated upfront in the CARTO contract. `carto do get` surfaces the pricing tier.
2. **Warehouse storage** — the materialized table consumes space on the user's warehouse, billed by the warehouse provider. Demographics tables are usually small (≤100 MB per country); mobility/POI tables can be 10–100 GB.
3. **Warehouse compute** — refresh runs spawn warehouse jobs. For frequent refresh schedules, factor this in.

For premium datasets, agents should surface all three to the user before subscribing.

## Refresh

Three refresh patterns:

### One-time

Default if `--refresh-schedule` isn't specified. Data is materialized once. Static datasets (US Census ACS for a fixed year) usually need only this.

### Scheduled

```bash
carto do subscribe <dataset-id> \
  --connection carto_dw \
  --destination my_project.do.poi_us \
  --refresh-schedule "0 0 1 * *"
```

CARTO drives the refresh server-side. The schedule expression follows the warehouse's dialect (see [`../carto-create-analytics-workflow/references/scheduling.md`](../../carto-create-analytics-workflow/references/scheduling.md)).

### Manual

To re-run on demand, re-subscribe with `--overwrite` — same command, replaces the table:

```bash
carto do subscribe <dataset-id> \
  --connection carto_dw \
  --destination my_project.do.poi_us \
  --overwrite
```

## Querying after subscribe

Once subscribed, the destination is just a warehouse table. Use [`carto-query-datawarehouse`](../../carto-query-datawarehouse):

```bash
carto sql query carto_dw \
  "SELECT geoid, total_pop FROM my_project.do.acs_tracts_2022 LIMIT 10"
```

To **enrich** the user's internal data with the DO data, spatial-join in SQL — see the dialect-specific examples in [`../../carto-query-datawarehouse/references/spatial-sql-*.md`](../../carto-query-datawarehouse).

## Unsubscribing

```bash
carto do subscriptions unsubscribe <subscription-id>
```

This stops future refreshes but **does not delete the destination table**. Drop it manually with `carto sql job` if no longer needed.

## Common errors

- **`Dataset not found`** — typo in the ID, or the dataset is regional and not visible from the user's contracted region.
- **`License not available for your org`** — paid dataset; needs to be added to the contract by CARTO sales.
- **`Permission denied`** writing to the destination — connection's credential lacks write permission. Fix in the warehouse-side IAM.
- **`Spatial extension required`** — destination warehouse needs the CARTO spatial extension installed. Admin task; outside this skill.
