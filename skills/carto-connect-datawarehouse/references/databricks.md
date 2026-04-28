# Databricks connection

CARTO connects to **Databricks SQL Warehouses** (formerly SQL Endpoints), not all-purpose clusters. SQL Warehouses are tuned for low-latency interactive querying — exactly what CARTO drives.

## Required fields

- **Workspace URL** — e.g. `https://adb-1234567890123456.7.azuredatabricks.net` or the AWS equivalent.
- **HTTP Path** — copy from the SQL Warehouse "Connection details" tab (looks like `/sql/1.0/warehouses/abc123def456`).
- **Personal Access Token (PAT)** — generated from Databricks user settings; or a service principal token for production.
- **Catalog** — Unity Catalog catalog name.
- **Schema** — within that catalog.

## Minimum permissions (Unity Catalog)

```sql
GRANT USE CATALOG ON CATALOG main TO `carto-sp@example.com`;
GRANT USE SCHEMA  ON SCHEMA main.analytics TO `carto-sp@example.com`;
GRANT SELECT      ON TABLE  main.analytics.* TO `carto-sp@example.com`;

-- write-back (tilesets, named sources):
GRANT CREATE TABLE ON SCHEMA main.analytics TO `carto-sp@example.com`;
GRANT MODIFY        ON SCHEMA main.analytics TO `carto-sp@example.com`;
```

If the workspace is on the legacy Hive metastore (no Unity Catalog), permissions live on the SQL Warehouse and the workspace itself — that path is supported but UC is recommended.

## SQL Warehouse must be running

Connections from CARTO will start the warehouse if it's stopped (auto-stop is fine), but a cold start adds 30–60s latency to the first query. For interactive map building, set the warehouse's auto-stop to a higher value (30 min+) during active sessions.

## Troubleshooting

- **`Token is invalid`** — PAT expired or revoked. Generate a new one and update the connection.
- **`Catalog X not found`** — Unity Catalog not enabled on the workspace, or the SP doesn't have `USE CATALOG`.
- **First query takes >30s** — SQL Warehouse cold start. Subsequent queries are fast.
- **Geospatial functions missing** — Databricks SQL exposes `ST_*` functions natively; ensure the SQL Warehouse runtime is recent enough (Photon / DBR 13+).
