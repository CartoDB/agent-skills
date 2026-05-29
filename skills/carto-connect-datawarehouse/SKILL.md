---
name: carto-connect-datawarehouse
description: Choose and configure the data warehouse engine connection for CARTO (BigQuery, Snowflake, Redshift, Postgres, Databricks, Oracle).
license: MIT
---

# carto-connect-datawarehouse

CARTO runs spatial analytics in the user's own data warehouse. **A connection is the bridge** between CARTO and that warehouse: it carries credentials, target project/database scoping, and sometimes a service account or PAT. Most other CARTO operations (querying, importing, building maps, running workflows) require an existing connection.

## When to use this skill

- The user wants to connect a new warehouse to CARTO.
- The user is debugging a connection (auth failures, missing tables, permission errors).
- A downstream skill needs a connection name and you don't yet know which engine the user has.
- The user is rotating credentials or moving from one project/database to another.

Use [`carto-explore-datawarehouse`](../carto-explore-datawarehouse) once a connection exists and you want to inspect what's inside it.

## Quick lifecycle

```bash
carto connections list --json             # what's already connected?
carto connections get <id>                # detailed view of one connection
carto connections create                  # interactive create
carto connections update <id>             # rotate credentials, change scoping
carto connections delete <id>             # remove (irreversible)
```

`connections list` and `connections get` are non-destructive — agents should run them freely before deciding what to do.

## Choosing an engine

| Engine | When to choose it | Reference |
|---|---|---|
| **BigQuery** | Google Cloud users; CARTO's flagship integration; rich GIS functions native. | [references/bigquery.md](references/bigquery.md) |
| **Snowflake** | Snowflake-shop customers; geospatial via SQL functions and Snowflake-native types. | [references/snowflake.md](references/snowflake.md) |
| **Redshift** | AWS-shop customers on Redshift Serverless or RA3 clusters. | [references/redshift.md](references/redshift.md) |
| **Postgres** | Self-hosted or RDS Postgres with PostGIS; common for small/medium deployments. | [references/postgres.md](references/postgres.md) |
| **Databricks** | Lakehouse / Unity Catalog users; SQL Warehouses recommended for interactive workloads. | [references/databricks.md](references/databricks.md) |
| **Oracle** | Oracle Database with Spatial; on-prem or OCI / Autonomous Database deployments. | [references/oracle.md](references/oracle.md) |

> If the user already has a connection (`connections list` returns at least one), don't push a new one — use the existing one.

## Listing options

```bash
carto connections list                    # default page (10)
carto connections list --all              # all pages
carto connections list --search "prod"    # filter by name
carto connections list --json             # machine-readable
```

## Common pitfalls

- **Auth-mode mismatch**: BigQuery supports OAuth (interactive) *and* service-account JSON (CI). Pick one consistently per environment; mixing the two breaks shared connections.
- **Region vs project**: Some engines need both an account/project and a region (Snowflake, Redshift). Skipping the region typically yields "endpoint not found" rather than a permissions error.
- **Default database/schema scoping**: CARTO can write tilesets, named sources, and analytics output back into the warehouse. Confirm with the user *which* dataset/schema CARTO is allowed to write to before creating the connection.
- **Permissions** for `connections describe` and table reads come from the credential CARTO holds, not from the user's CARTO role. A CARTO Admin with a low-privilege service account will still see "permission denied" from the warehouse.

## What this skill doesn't cover

- Browsing tables/schemas of an existing connection — that's [`carto-explore-datawarehouse`](../carto-explore-datawarehouse).
- Running SQL against the warehouse — that's [`carto-query-datawarehouse`](../carto-query-datawarehouse).
- Importing files into the warehouse — that's [`carto-import-export-data`](../carto-import-export-data).
