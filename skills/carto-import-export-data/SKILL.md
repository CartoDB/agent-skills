---
name: carto-import-export-data
description: Import geospatial files into the data warehouse via CARTO, export results back out, and prepare tilesets for fast map rendering.
license: MIT
---

# carto-import-export-data

Move data **into** the warehouse from local files / URLs, pull data **out**, transfer tables between connections, and **prepare tilesets** for performant rendering of large geospatial datasets.

> **Access-path routing.** With the CARTO MCP server attached (OAuth session), route interactive moves through `import_data`, `export_data`, and `transfer_data` (each `method: submit|status`), and materialize tilesets with `execute_async_query`. Fall back to the `carto import` / `carto sql job` CLI for scripted/bulk loads, headless pipelines, or when the server isn't attached — and note that over a **token-authenticated** MCP session the import/export/transfer tools are hidden (read/discovery subset only), so authoring moves there go via the CLI too. `carto activity export` (usage data → local disk) is CLI-only, no MCP equivalent. Format, size-limit, and destination-syntax guidance below applies on every path. Detection signals: [`carto-basics/references/access-paths.md`](../carto-basics/references/access-paths.md).

## When to use this skill

- The user has a CSV / GeoJSON / Shapefile / GeoParquet file and wants it queryable in the warehouse.
- The user wants to refresh an existing table from a remote URL, or copy a table between connections.
- The user wants to render a 10M+-row spatial dataset on a map (needs tileset preparation).
- The user is bulk-exporting CARTO activity data to disk for offline analysis.

To query a file already in the warehouse, jump to [`carto-query-datawarehouse`](../carto-query-datawarehouse). To discover what's already there, [`carto-explore-datawarehouse`](../carto-explore-datawarehouse).

## Quick reference

MCP (OAuth session) — submit then poll:

```
import_data   { method: "submit", source: {url|file}, connection, destination, overwrite? }
export_data   { method: "submit", ... }   → status with the returned job id
transfer_data { method: "submit", source_connection, destination_connection, ... }
```

CLI fallback (scripted / headless / no server / token session):

```bash
# Import a local file (or --url for a remote source; --async to poll separately; --overwrite to replace)
carto import --file ./data.csv --connection carto_dw --destination project.dataset.table
```

## What's in this skill

| Topic | Reference |
|---|---|
| Importing — `import_data` / `carto import` flags, formats, size limits, async | [references/imports.md](references/imports.md) |
| Tileset preparation for large maps | [references/tilesets.md](references/tilesets.md) |
| Exporting & transferring: warehouse-native unloads, `export_data`/`transfer_data`, `activity export` | [references/exports.md](references/exports.md) |

## Always-on guidance

- **`--connection` / `connection` is the connection *name*** (discover it with `explore_data` `method: list_connections`, or `carto connections list --json`), not the warehouse project ID.
- **`destination` is the fully-qualified target name** in the warehouse's syntax: `project.dataset.table` (BigQuery), `DATABASE.SCHEMA.TABLE` (Snowflake), `schema.table` (Postgres/Redshift), `catalog.schema.table` (Databricks), `SCHEMA.TABLE` (Oracle).
- **1 GB hard limit per file** (CARTO-side, not a warehouse limit). For larger files, pre-stage to cloud storage and import from a presigned URL.
- **Disable autoguessing** (`--no-autoguessing` on the CLI) when you've prepared a precise schema and don't want CARTO to second-guess types — especially numeric-looking columns that should stay string, like ZIP codes.
- **Imports/exports are async at the API level.** MCP `import_data`/`export_data` return a job id — poll with `method: "status"`. The CLI polls to completion by default; pass `--async` to return immediately with a job id.
- **Tilesets** follow *import → materialize tileset table (`execute_async_query` or `carto sql job`) → reference the tileset in a map*. The tileset is created in the warehouse, not by the mover itself.
