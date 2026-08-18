---
name: carto-connect-datawarehouse
description: Choose and configure the data warehouse engine connection for CARTO (BigQuery, Snowflake, Redshift, Postgres, Databricks, Oracle).
license: MIT
---

# carto-connect-datawarehouse

CARTO runs spatial analytics in the user's own data warehouse. **A connection is the bridge** between CARTO and that warehouse: it carries credentials, target project/database scoping, and sometimes a service account or PAT. Most other CARTO operations (querying, importing, building maps, running workflows) require an existing connection.

| Task | MCP | CLI (fallback) |
|---|---|---|
| List / inspect connections | `explore_data` (`list_connections` on any session; `get_connection` is OAuth-only) | `carto connections list` / `get` |
| Create / update a connection | `manage_connections` (`create`, `update`) — **OAuth session only** | `carto connections create` / `update` |
| Delete a connection | `delete` (kind=connection) — **OAuth session only** | `carto connections delete` |

> **Access-path routing.** With the MCP server attached, list over `explore_data` (`list_connections`); create/update over `manage_connections`; delete over `delete`. On a token session only `list_connections` is available — `get_connection` and the write tools (`manage_connections`, `delete`) need OAuth, so fall back to the `carto connections` CLI. Also use the CLI when the server isn't attached or for scripted setups. The engine-choice guidance and pitfalls below apply on either path. Detection signals: [`carto-basics/references/access-paths.md`](../carto-basics/references/access-paths.md).

## When to use this skill

- The user wants to connect a new warehouse to CARTO.
- The user is debugging a connection (auth failures, missing tables, permission errors).
- A downstream skill needs a connection name and you don't yet know which engine the user has.
- The user is rotating credentials or moving from one project/database to another.

Use [`carto-explore-datawarehouse`](../carto-explore-datawarehouse) once a connection exists and you want to inspect what's inside it.

## Quick lifecycle (CLI)

```bash
carto connections list --json             # what's already connected? (--all, --search "prod")
carto connections get <id>                # detailed view of one connection
carto connections create                  # interactive create
carto connections update <id>             # rotate credentials, change scoping
carto connections delete <id>             # remove (irreversible)
```

List/inspect are non-destructive — run them freely before deciding what to do. **If the user already has a connection, don't push a new one — use the existing one.**

## Choosing an engine

| Engine | When to choose it | Reference |
|---|---|---|
| **BigQuery** | Google Cloud users; CARTO's flagship integration; rich GIS functions native. | [references/bigquery.md](references/bigquery.md) |
| **Snowflake** | Snowflake-shop customers; geospatial via SQL functions and native types. | [references/snowflake.md](references/snowflake.md) |
| **Redshift** | AWS-shop customers on Redshift Serverless or RA3 clusters. | [references/redshift.md](references/redshift.md) |
| **Postgres** | Self-hosted or RDS Postgres with PostGIS; common for small/medium deployments. | [references/postgres.md](references/postgres.md) |
| **Databricks** | Lakehouse / Unity Catalog users; SQL Warehouses for interactive workloads. | [references/databricks.md](references/databricks.md) |
| **Oracle** | Oracle Database with Spatial; on-prem or OCI / Autonomous Database. | [references/oracle.md](references/oracle.md) |

## Common pitfalls

- **Auth-mode mismatch**: BigQuery supports OAuth (interactive) *and* service-account JSON (CI). Pick one consistently per environment; mixing the two breaks shared connections.
- **Region vs project**: Some engines need both an account/project and a region (Snowflake, Redshift). Skipping the region typically yields "endpoint not found" rather than a permissions error.
- **Default database/schema scoping**: CARTO writes tilesets, named sources, and analytics output back into the warehouse. Confirm *which* dataset/schema CARTO may write to before creating the connection.
- **Permissions** for describe and table reads come from the credential CARTO holds, not the user's CARTO role. A CARTO Admin with a low-privilege service account still sees "permission denied" from the warehouse.

## What this skill doesn't cover

- Browsing tables/schemas of an existing connection — [`carto-explore-datawarehouse`](../carto-explore-datawarehouse).
- Running SQL against the warehouse — [`carto-query-datawarehouse`](../carto-query-datawarehouse).
- Importing files into the warehouse — [`carto-import-export-data`](../carto-import-export-data).
