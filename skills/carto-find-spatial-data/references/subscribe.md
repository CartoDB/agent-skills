# Subscribing to a Data Observatory dataset

Subscribing gives the organization access to a Data Observatory dataset. Where the user can then use the data depends on their data warehouse, so check which connections they work with before recommending a subscription:

- **CARTO Data Warehouse:** the data is ready to use right after subscribing, in Data Explorer, Workflows and Builder, and in SQL on the `carto_dw` connection.
- **BigQuery:** CARTO hosts the data in BigQuery's US multi-region and shares it with the user's BigQuery connections. To use it in another BigQuery location, an Admin requests a transfer, as below.
- **Snowflake, Databricks, Redshift, PostgreSQL or Oracle:** the data is not in the user's warehouse yet. An Admin requests a transfer in **Settings > Data Observatory**: open the three-dot menu next to the subscription, select **Request transfer** and enter the warehouse's connection details. CARTO's team then delivers the data through that warehouse's own sharing mechanism, such as a private listing in Snowflake or Delta Sharing in Databricks, and the **Available in** column shows the progress. Once it's delivered, the user queries it on their own connection like any other table. See [Accessing your subscriptions from your data warehouse](https://docs.carto.com/carto-user-manual/data-observatory/accessing-your-subscriptions-from-your-data-warehouse).

Some Self-Hosted deployments run without the CARTO Data Warehouse. There the user can browse the catalog, but can't subscribe or use the data in Workflows or Builder directly. Instead, CARTO's team deploys a copy of the data in their warehouse on request.

Subscribe over MCP with `manage_data_observatory_subscriptions` (`method: subscribe|unsubscribe|list`) — this needs an **OAuth** session; on a token-authenticated session the tool is hidden, so use the `carto do` CLI instead. Discovery (`search_data_observatory`) works on either session — see [data-observatory.md](data-observatory.md).

## Subscribing

- **MCP:** `manage_data_observatory_subscriptions` `method: "subscribe"` with `body: { source, filter?, filterColumns? }`. `source` is the dataset id, slug or fully-qualified name.
- **CLI:**

```bash
carto do subscribe <dataset-id>
carto do subscribe <dataset-id> --filter "WHERE country_iso = 'US'"   # Partial subscription
carto do subscribe <dataset-id> --columns "geoid, population, geom"   # Specific columns only
```

Only **public** datasets can be subscribed self-service. Premium datasets need a commercial agreement with CARTO: `get_dataset` / `carto do get` shows the license, and the user should contact data-sales@carto.com.

## Using the data

- **CARTO Data Warehouse:** `carto do subscribe` prints the table to query on `carto_dw`, and `carto do subscriptions --json` lists every subscription with its `tableName` and the warehouses and regions where it's available (`availableIn`). Query it with `execute_query` or `carto sql query carto_dw`.
- **Other warehouses:** once CARTO has delivered the data, query the shared tables on the user's own connection, not through the Data Observatory tabs in Data Explorer, Workflows or Builder.

To **enrich** the user's internal data with DO data, spatial-join in SQL — see the dialect-specific examples in [`carto-query-datawarehouse`](../../carto-query-datawarehouse).

## Unsubscribing

`manage_data_observatory_subscriptions` `method: "unsubscribe"` with the dataset `id`, or `carto do unsubscribe <dataset-id>` (`--yes` skips the confirmation). It needs Admin permissions and can't be undone.

## Common errors

- **`Dataset not found`** — typo in the ID, or the dataset is regional and not visible from the user's contracted region.
- **`License not available for your org`** — paid dataset; needs adding to the contract by CARTO sales.
- **Already subscribed** (HTTP 409): the organization already has the dataset, so use the existing subscription.
- **No CARTO Data Warehouse in the organization**: self-service subscriptions aren't available, which is expected on Self-Hosted deployments set up without it. The user's CARTO team can deploy a copy of the data in their warehouse instead.
