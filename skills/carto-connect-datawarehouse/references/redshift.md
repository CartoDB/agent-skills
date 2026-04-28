# Redshift connection

CARTO supports both Redshift provisioned clusters (RA3) and Redshift Serverless workgroups.

## Auth modes

- **Database username + password** — works for both cluster and serverless.
- **IAM authentication** — short-lived credentials issued by AWS; requires the IAM role pre-set up on the cluster.

## Required fields

- **Host** — cluster endpoint (e.g. `my-cluster.abc123.us-east-1.redshift.amazonaws.com`) or the serverless workgroup endpoint.
- **Port** — usually `5439`.
- **Database** — initial database name.
- **Username** — CARTO operates as this user.
- **Password** (or IAM credentials).
- **Default schema** (optional) — where CARTO writes outputs.

## Minimum grants

```sql
CREATE USER carto_user WITH PASSWORD '...';
GRANT USAGE ON SCHEMA public TO carto_user;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO carto_user;
GRANT CREATE ON SCHEMA public TO carto_user;   -- if writing back
```

For PostGIS-style spatial functions, the cluster needs `CREATE EXTENSION` already applied; this is admin-only and outside CARTO's scope.

## Networking

If the cluster is in a private VPC, the agent must arrange one of:

- A public endpoint on the cluster (security-group rules allowing CARTO's IP range).
- A VPC peering / PrivateLink setup between CARTO and the customer VPC (Enterprise feature).

CARTO publishes a static IP allowlist for SaaS — confirm with CARTO support before opening security groups.

## Troubleshooting

- **`could not connect to server: Connection timed out`** — security group / VPC issue, not credentials.
- **`password authentication failed`** — credentials wrong, or the user has expired (`ALTER USER carto_user PASSWORD '...'`).
- **`permission denied for relation X`** — `GRANT SELECT` on the specific table or schema.
