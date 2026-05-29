# Oracle connection

CARTO connects to Oracle Database (on-prem or OCI) and Oracle Autonomous Database. Oracle Spatial is required for spatial functions — CARTO assumes Spatial is already enabled on the target database.

## Required fields

- **Host** — e.g. `db.example.com`, an OCI VCN endpoint, or the Autonomous Database connection string host.
- **Port** — usually `1521` (TCP) or `2484` (TCPS / TLS).
- **Service name** *or* **SID** — Oracle accepts either; service name is the modern default.
- **Username**, **Password** — Oracle account CARTO uses.
- **Wallet / TLS material** (Autonomous Database) — Autonomous DB requires the client wallet (`cwallet.sso`, `tnsnames.ora`) for mTLS. CARTO accepts the wallet bundle at connection time.
- **Default schema** (optional) — where CARTO writes outputs. Defaults to the connecting user's schema.

## Minimum grants

```sql
CREATE USER carto_user IDENTIFIED BY "...";
GRANT CREATE SESSION TO carto_user;
GRANT SELECT ANY TABLE TO carto_user;                -- or per-table SELECT
GRANT CREATE TABLE TO carto_user;                    -- only if CARTO needs to write
GRANT UNLIMITED TABLESPACE TO carto_user;            -- or a specific quota
```

For read-only access, drop `CREATE TABLE` and `UNLIMITED TABLESPACE` and grant `SELECT` on each table individually.

## Oracle Spatial prerequisite

CARTO calls `SDO_GEOMETRY` functions (`SDO_RELATE`, `SDO_GEOM.SDO_DISTANCE`, etc.). Confirm Spatial is enabled:

```sql
SELECT comp_name, status, version
FROM dba_registry
WHERE comp_name = 'Spatial';
```

If `status` is anything other than `VALID`, the connection will work but spatial SQL will not. Enable Spatial via Oracle's component installer or have a DBA grant the appropriate package access.

## Networking

- **On-prem** — open the listener port to CARTO's published IP allowlist, or terminate through a VPN / PrivateLink path.
- **OCI** — the database must be reachable from the public internet (with IP allowlist) or via a configured private endpoint.
- **Autonomous Database** — uses mTLS via the wallet bundle. No additional firewall changes needed once the wallet is in place.

## Troubleshooting

- **`ORA-12154: TNS:could not resolve the connect identifier specified`** — service name / SID mismatch, or `tnsnames.ora` not picked up. With Autonomous DB, confirm the wallet bundle was uploaded.
- **`ORA-01017: invalid username/password`** — credentials wrong, or the account is locked (`ALTER USER carto_user ACCOUNT UNLOCK`).
- **`ORA-00942: table or view does not exist`** — either the table isn't in the connecting user's schema or `SELECT` hasn't been granted. Fully-qualify as `OWNER.TABLE` and verify with `SELECT * FROM all_tables WHERE table_name = 'X'`.
- **`ORA-13226: interface not supported without a spatial index`** — the target table has `SDO_GEOMETRY` columns but no spatial index. Create one: `CREATE INDEX idx_geom ON my_table (geom) INDEXTYPE IS MDSYS.SPATIAL_INDEX;`.
- **`ORA-29024: Certificate validation failure`** (Autonomous DB) — wallet expired or wrong wallet for the database. Re-download the wallet from the OCI console.

## Caveats inherited downstream

- **Builder dynamic H3 / quadbin aggregation isn't supported on Oracle.** Maps that aggregate on-the-fly need a pre-aggregated tileset upstream (see `carto-create-builder-maps/references/layers.md`).
- **SQL parameters** in Builder map datasets translate to `JSON_TABLE`-based binding on Oracle — handled automatically by the CLI.
