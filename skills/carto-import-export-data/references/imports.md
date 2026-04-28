# `carto imports create` reference

```bash
carto imports create [options]
```

## Required flags

- `--connection <name>` — connection name from `connections list`.
- `--destination <fqn>` — target table name in the warehouse's native syntax.
- One of `--file <path>` or `--url <url>` — the source.

## Optional flags

| Flag | Effect |
|---|---|
| `--overwrite` | Overwrite the destination table if it exists. Default: error if table exists. |
| `--no-autoguessing` | Disable column type detection. Use a pre-built schema instead. |
| `--async` | Return immediately, don't wait for the import to finish. Prints the job ID. |
| `--json` | Machine-readable output. |

## Supported formats

CSV, GeoJSON, GeoPackage, GeoParquet, KML, KMZ, Shapefile (must be zipped — `.zip` containing `.shp`, `.shx`, `.dbf`, `.prj`).

## Size limit

**1 GB per file.** This is a CARTO-side limit, not a warehouse limit.

For larger files:

1. Upload the raw file to cloud storage (S3, GCS, Azure Blob).
2. Generate a presigned / signed URL.
3. Run `carto imports create --url <signed-url> --connection ... --destination ...`.

The signed URL must be reachable from CARTO's import workers. CARTO publishes a static IP allowlist for SaaS — verify with support if the bucket is firewalled.

## Examples

### Local CSV

```bash
carto imports create \
  --file ./stores.csv \
  --connection carto_dw \
  --destination my_project.demo.stores
```

### Remote GeoJSON, overwrite

```bash
carto imports create \
  --url https://example.com/regions.geojson \
  --connection carto_dw \
  --destination my_project.demo.regions \
  --overwrite
```

### Async with explicit schema

```bash
carto imports create \
  --file ./events.parquet \
  --connection carto_dw \
  --destination my_project.demo.events \
  --no-autoguessing \
  --async
```

### Shapefile (zipped)

```bash
zip neighborhoods.zip neighborhoods.shp neighborhoods.shx \
                      neighborhoods.dbf neighborhoods.prj
carto imports create \
  --file ./neighborhoods.zip \
  --connection carto_dw \
  --destination my_project.demo.neighborhoods
```

## What CARTO does behind the scenes

1. Uploads the file (or fetches the URL) to a CARTO-managed staging area.
2. Spawns an import job in the warehouse using the connection's credentials.
3. The job parses the source, infers the schema (unless `--no-autoguessing`), creates the destination table, and loads the rows.
4. CARTO records the import in its activity log (visible via `carto activity export`).

Geometries are stored in the warehouse's native spatial type — `GEOGRAPHY` (BigQuery, Snowflake), `GEOMETRY` (Postgres/PostGIS, Redshift, Databricks).

## Common errors

- **`Permission denied`** writing to the destination — the connection's service account lacks `dataEditor` (BQ) / `CREATE TABLE` (others). Fix in the warehouse, not in CARTO.
- **`File too large`** — split the file or stage it as cloud-storage URL.
- **`Unable to detect format`** — pass the file extension explicitly or rename so the extension matches the actual format.
- **`Geometry parsing failed`** — geometry column has invalid WKT/WKB or mixed SRIDs. Pre-clean before import.
