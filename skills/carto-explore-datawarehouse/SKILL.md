---
name: carto-explore-datawarehouse
description: Discover what's in the connected warehouse — schemas, tables, columns, and CARTO named sources.
license: MIT
---

# carto-explore-datawarehouse

Before writing SQL or building maps, an agent usually needs to know **what's in the warehouse**. This skill covers discovery, matched across MCP and CLI:

| Task | MCP (primary) | CLI (fallback) |
|---|---|---|
| List / inspect connections | `explore_data` (`list_connections`, `get_connection`) | `carto connections list` / `get` |
| Walk the hierarchy (project → dataset → table) | `explore_data` (`list_resources`) | `carto connections browse` |
| Full-text find a resource | `explore_data` (`search`) | — |
| Columns + types for a table | `explore_data` (`describe`) | `carto connections describe` |
| Find / inspect a named source | `manage_named_sources` (`list`, `get`) | `carto named-sources list` / `get` |

> **Access-path routing.** `explore_data` works on any attached MCP session, but not all its methods do on a token: `list_connections`, `list_resources`, and `search` need only the **MCP Server** scope, while **`describe` additionally needs the Maps API** on a token session (it's always available over OAuth). `manage_named_sources` is an authoring tool, so it needs an OAuth session (it's hidden on token sessions). Use the `carto connections` / `carto named-sources` CLI when the server isn't attached, when a token lacks the scope for `describe`, or when the exploration is scripted/headless. Detection signals and the full routing table: [`carto-basics/references/access-paths.md`](../carto-basics/references/access-paths.md).

## When to use this skill

- You don't know which tables / schemas exist in a connection.
- You need a column list and types before writing SQL or authoring a map.
- The user references "the named source for X" and you need to find it.

If you already know the table and just want to query it, jump to [`carto-query-datawarehouse`](../carto-query-datawarehouse).

## Path syntax by engine

The path passed to `list_resources` / `describe` (or `connections browse` / `describe`) depends on the engine:

| Engine | Path shape |
|---|---|
| BigQuery | `project.dataset.table` |
| Snowflake | `DATABASE.SCHEMA.TABLE` |
| Postgres / Redshift | `schema.table` (no leading project/database) |
| Databricks | `catalog.schema.table` |

CLI examples:

```bash
carto connections browse <name>                                  # top level
carto connections browse <name> "carto-demo-data.demo_tables"    # drill in
carto connections describe <name> "carto-demo-data.demo_tables.nyc_collisions"
```

## What's in this skill

| Topic | Reference |
|---|---|
| Browsing and describing a connection in detail | [references/connection-browse.md](references/connection-browse.md) |
| Named sources — what they are, how to list and inspect them | [references/named-sources.md](references/named-sources.md) |

## Always-on guidance

- **Browse before you query.** A two-second `list_resources` usually saves a five-minute "table not found" loop.
- **`describe` returns column types** — use them to write correct SQL (e.g. don't `ST_DWithin` against a `STRING` column mistakenly named `geom`).
- **Paginate long lists** — CLI `browse` defaults to `--page-size 30`; bump it for datasets with hundreds of tables.
- **Named sources ≠ tables.** They're parameterized queries — inspect the *underlying* tables before assuming a column you see in the source exists in raw form.
- **`carto-demo-data`** is a public BigQuery dataset CARTO ships — browsing it works on any BigQuery connection with the right IAM, a fast way to validate a fresh connection without touching customer data.
