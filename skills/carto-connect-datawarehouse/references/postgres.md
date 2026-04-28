# Postgres / PostGIS connection

CARTO connects to any Postgres reachable over the network. PostGIS is required for spatial functions; CARTO assumes it's already installed (`CREATE EXTENSION postgis;`).

## Required fields

- **Host** — e.g. `db.example.com` or an RDS endpoint.
- **Port** — usually `5432`.
- **Database** — Postgres database name.
- **Username**, **Password** — Postgres role CARTO uses.
- **SSL mode** (recommended `require`) — most managed Postgres providers require TLS.
- **Default schema** (optional).

## Minimum grants

```sql
CREATE ROLE carto_user LOGIN PASSWORD '...';
GRANT USAGE ON SCHEMA public TO carto_user;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO carto_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO carto_user;
GRANT CREATE ON SCHEMA public TO carto_user;   -- only if CARTO needs to write
```

## PostGIS prerequisite

```sql
CREATE EXTENSION IF NOT EXISTS postgis;
SELECT PostGIS_Full_Version();
```

If `PostGIS_Full_Version()` fails, the connection will work but spatial SQL will not. Install PostGIS before creating the CARTO connection.

## Networking

- **RDS / Cloud SQL / managed**: open the security group / authorized networks to CARTO's published IPs.
- **Self-hosted**: a public endpoint or a VPN / PrivateLink path.

## Troubleshooting

- **`SSL connection required`** — many managed providers (RDS, Heroku) reject non-SSL connections; set SSL mode to `require`.
- **`relation X does not exist`** — schema-search-path; either fully qualify (`my_schema.X`) or set `search_path` on the CARTO role: `ALTER ROLE carto_user SET search_path = my_schema, public;`.
- **`function st_intersects(...) does not exist`** — PostGIS not installed or installed in a different schema; ensure `public` (or the relevant schema) is on `search_path`.
