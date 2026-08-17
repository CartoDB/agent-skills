# Importing data

Two paths, same semantics (formats, 1 GB limit, destination syntax, autoguessing all identical):

- **MCP** `import_data` (OAuth session) — `method: "submit"` with `source` (a `url`, or an uploaded/staged `file`), `connection`, `destination`, optional `overwrite`; then `method: "status"` with the returned job id. Hidden on token-authenticated sessions — use the CLI there.
- **CLI** `carto import` — scripted/bulk/headless, or when the MCP server isn't attached.

## Required inputs

- `connection` / `--connection <name>` — connection name (`explore_data` `list_connections`, or `carto connections list`).
- `destination` / `--destination <fqn>` — target table in the warehouse's native syntax.
- A source: a `url` / `--url`, or an uploaded / local `file` / `--file`.

## Optional inputs

| CLI flag | `import_data` | Effect |
|---|---|---|
| `--overwrite` | `overwrite: true` | Replace the destination if it exists. Default: error if it exists. |
| `--no-autoguessing` | — | Disable column type detection; use a pre-built schema. |
| `--async` | (submit returns a job id; poll `status`) | Return immediately instead of polling to completion. |
| `--json` | — | Machine-readable output. |

## Supported formats

CSV, GeoJSON, GeoPackage, GeoParquet, KML, KMZ, Shapefile (must be zipped — `.zip` containing `.shp`, `.shx`, `.dbf`, `.prj`).

## Size limit

**1 GB per file** (CARTO-side, not a warehouse limit). For larger files:

1. Upload the raw file to cloud storage (S3, GCS, Azure Blob).
2. Generate a presigned / signed URL.
3. Import from that URL (`import_data` `source: {url}` or `carto import --url`).

The signed URL must be reachable from CARTO's import workers. CARTO Cloud publishes a static IP allowlist — verify with support if the bucket is firewalled.

## CLI examples

```bash
# Local CSV
carto import --file ./stores.csv --connection carto_dw --destination my_project.demo.stores

# Remote GeoJSON, overwrite
carto import --url https://example.com/regions.geojson \
  --connection carto_dw --destination my_project.demo.regions --overwrite

# Async with explicit schema
carto import --file ./events.parquet --connection carto_dw \
  --destination my_project.demo.events --no-autoguessing --async

# Shapefile (zipped first)
zip neighborhoods.zip neighborhoods.shp neighborhoods.shx neighborhoods.dbf neighborhoods.prj
carto import --file ./neighborhoods.zip --connection carto_dw \
  --destination my_project.demo.neighborhoods
```

## What CARTO does behind the scenes

1. Uploads the file (or fetches the URL) to a CARTO-managed staging area.
2. Spawns an import job in the warehouse using the connection's credentials.
3. Parses the source, infers the schema (unless autoguessing is off), creates the destination table, loads the rows.
4. Records the import in the activity log (see [exports.md](exports.md) → `carto activity export`).

Geometries land in the warehouse's native spatial type — `GEOGRAPHY` (BigQuery, Snowflake), `GEOMETRY` (Postgres/PostGIS, Redshift, Databricks), `SDO_GEOMETRY` (Oracle Spatial).

## Common errors

- **`Permission denied`** on the destination — the connection's service account lacks `dataEditor` (BQ) / `CREATE TABLE` (others). Fix in the warehouse, not in CARTO.
- **`File too large`** — split the file or stage it as a cloud-storage URL.
- **`Unable to detect format`** — pass the file extension explicitly or rename so it matches the actual format.
- **`Geometry parsing failed`** — invalid WKT/WKB or mixed SRIDs in the geometry column. Pre-clean before import.
