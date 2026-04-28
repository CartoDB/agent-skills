---
name: carto-import-export-data
description: Import geospatial files into the data warehouse via CARTO, export results back out, and prepare tilesets for fast map rendering.
license: MIT
---

# carto-import-export-data

Move data **into** the warehouse from local files / URLs (`carto imports`), pull data **out** (`carto activity export` for usage data; warehouse-native unloads for everything else), and **prepare tilesets** for performant map rendering of large geospatial datasets.

## When to use this skill

- The user has a CSV / GeoJSON / Shapefile / GeoParquet file and wants it queryable in the warehouse.
- The user wants to refresh an existing table from a remote URL.
- The user wants to render a 10M+-row spatial dataset on a map (needs tileset preparation).
- The user is bulk-exporting CARTO activity data to disk for offline analysis.

If the user just wants to query a file already in the warehouse, jump to [`carto-query-datawarehouse`](../carto-query-datawarehouse). If they want to discover what's already there, [`carto-explore-datawarehouse`](../carto-explore-datawarehouse).

## Quick reference

```bash
# Import a local file
carto imports create --file ./data.csv \
  --connection carto_dw \
  --destination project.dataset.table

# Import from a URL
carto imports create --url https://example.com/data.geojson \
  --connection carto_dw \
  --destination my_project.demo.regions

# Async (return immediately, poll separately)
carto imports create --file ./big.parquet \
  --connection carto_dw \
  --destination my_project.demo.huge \
  --async

# Overwrite existing table
carto imports create --file ./data.csv \
  --connection carto_dw \
  --destination my_project.demo.t \
  --overwrite
```

## What's in this skill

| Topic | Reference |
|---|---|
| `carto imports create` — flags, formats, size limits, async | [references/imports.md](references/imports.md) |
| Tileset preparation for large maps | [references/tilesets.md](references/tilesets.md) |
| Exporting data: warehouse-native unloads vs `activity export` | [references/exports.md](references/exports.md) |

## Always-on guidance

- **`--connection` is the connection *name*** (from `connections list`), not the warehouse project ID. If you only know the project, run `carto connections list --json` first to find the matching connection.
- **`--destination` is the fully-qualified target name** in the warehouse's syntax: `project.dataset.table` (BigQuery), `DATABASE.SCHEMA.TABLE` (Snowflake), `schema.table` (Postgres/Redshift), `catalog.schema.table` (Databricks).
- **1GB hard limit per file**. For larger files, split or pre-stage to cloud storage and use `--url` to a presigned URL.
- **`--no-autoguessing` skips column type detection** — use it when you've prepared a precise schema and don't want CARTO to second-guess types (especially for columns that look numeric but should stay string, like ZIP codes).
- **Imports are async at the API level**. The CLI defaults to polling-to-completion; pass `--async` to return immediately. The CLI prints a job ID in async mode that you can use to check progress.
- **For tilesets**, the workflow is *import → SQL job to materialize a tileset table → reference the tileset in a map*. The tileset itself is created in the warehouse, not by the CLI.
