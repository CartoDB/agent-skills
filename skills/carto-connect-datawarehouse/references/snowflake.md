# Snowflake connection

## Auth modes

- **Username + password** — simplest; not recommended for shared/automation use.
- **Key-pair (RSA)** — recommended for service accounts; private key stored by CARTO.
- **OAuth** — for federated SSO setups.

## Required fields

- **Account identifier** — e.g. `xy12345.us-east-1` or the newer `org-acct` form. This is *not* the org URL.
- **Username** — Snowflake user that CARTO will operate as.
- **Password** or **private key** depending on auth mode.
- **Default warehouse** — compute warehouse CARTO will run queries on (e.g. `COMPUTE_WH`).
- **Default database** — where CARTO will write tilesets/named sources.
- **Default schema** — within that database.
- **Role** — Snowflake role the user assumes (recommended: dedicated `CARTO_ROLE`).

## Minimum grants

```sql
-- assuming a dedicated role
USE ROLE ACCOUNTADMIN;
CREATE ROLE CARTO_ROLE;
GRANT USAGE ON WAREHOUSE COMPUTE_WH TO ROLE CARTO_ROLE;
GRANT USAGE ON DATABASE MY_DB TO ROLE CARTO_ROLE;
GRANT USAGE ON SCHEMA MY_DB.PUBLIC TO ROLE CARTO_ROLE;
GRANT SELECT ON ALL TABLES IN SCHEMA MY_DB.PUBLIC TO ROLE CARTO_ROLE;

-- if CARTO needs to write back (tilesets, named sources):
GRANT CREATE TABLE ON SCHEMA MY_DB.PUBLIC TO ROLE CARTO_ROLE;
GRANT CREATE VIEW  ON SCHEMA MY_DB.PUBLIC TO ROLE CARTO_ROLE;
```

## Worked example

```bash
carto connections create
# provider = snowflake
# account  = xy12345.us-east-1
# user     = CARTO_USER
# auth     = key-pair (paste private key)
# warehouse = COMPUTE_WH
# database  = ANALYTICS
# schema    = PUBLIC
# role      = CARTO_ROLE

carto connections describe <name> "ANALYTICS.PUBLIC.STORES"
```

## Troubleshooting

- **`Authentication failed`** — account identifier shape is the most common cause. Use the account form Snowflake shows in the URL of the web UI.
- **`Requested role X is not assigned`** — `GRANT ROLE CARTO_ROLE TO USER CARTO_USER`.
- **Spatial queries fail with "function does not exist"** — Snowflake's geospatial functions live in the `GEOGRAPHY`/`GEOMETRY` modules; user needs `USAGE` on the schema housing them (default `PUBLIC`).
