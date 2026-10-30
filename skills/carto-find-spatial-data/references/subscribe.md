# Subscribing to a Data Observatory dataset

Subscribing gives the organization a **BigQuery view of the dataset in the CARTO Data Warehouse**, in a dataset named after the organization's account id (on CARTO SaaS, `` `carto-data`.<account-id>.<view-name> ``). Querying it is a normal read on the `carto_dw` connection (`execute_query` / `carto sql query carto_dw`). Subscribing needs a CARTO Data Warehouse connection in the organization.

Subscribe over MCP with `manage_data_observatory_subscriptions` (`method: subscribe|unsubscribe|list`) — this needs an **OAuth** session; on a token-authenticated session the tool is hidden, so use the `carto do` CLI instead. Discovery (`search_data_observatory`) works on either session — see [data-observatory.md](data-observatory.md).

## Subscribing

- **MCP:** `manage_data_observatory_subscriptions` `method: "subscribe"` with `body: { source, filter?, filterColumns? }`. `source` is the dataset id, slug or fully-qualified name.
- **CLI:**

```bash
carto do subscribe <dataset-id>
carto do subscribe <dataset-id> --filter "WHERE country_iso = 'US'"   # Partial subscription
carto do subscribe <dataset-id> --columns "geoid, population, geom"   # Specific columns only
```

The CLI prints the view to query; with `--json` it returns it as `qualifiedView`.

Only **public** datasets can be subscribed self-service. Premium datasets need a commercial agreement with CARTO: `get_dataset` / `carto do get` shows the license, and the CLI points the user to data-sales@carto.com.

## Querying after subscribe

Read the view with `execute_query` on `carto_dw`, or:

```bash
carto sql query carto_dw "SELECT * FROM \`carto-data\`.<account-id>.<view-name> LIMIT 10"
```

To **enrich** the user's internal data with DO data, spatial-join in SQL — see the dialect-specific examples in [`carto-query-datawarehouse`](../../carto-query-datawarehouse).

## Unsubscribing

`manage_data_observatory_subscriptions` `method: "unsubscribe"` with the dataset `id`, or `carto do unsubscribe <dataset-id>` (`--yes` skips the confirmation). It needs Admin permissions and can't be undone.

## Common errors

- **`Dataset not found`** — typo in the ID, or the dataset is regional and not visible from the user's contracted region.
- **`License not available for your org`** — paid dataset; needs adding to the contract by CARTO sales.
- **Already subscribed** (HTTP 409): the organization already has the dataset, so query the existing view.
- **No CARTO Data Warehouse connection**: Data Observatory subscriptions need one, and the organization's Admin or CARTO support has to set it up.
