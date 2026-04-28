---
name: carto-explore-datawarehouse
description: Discover what's in the connected warehouse — schemas, tables, columns, and CARTO named sources.
license: MIT
---

# carto-explore-datawarehouse

Before writing SQL or building maps, an agent typically needs to know **what's in the warehouse**. This skill covers two CARTO surfaces for that:

- **`carto connections browse`** — walk the warehouse hierarchy (project → dataset → table).
- **`carto connections describe`** — inspect a specific table's columns and types.

And one CARTO-specific concept:

- **Named sources** — saved, parameterized SQL that maps and apps consume as if they were tables.

## When to use this skill

- You don't know which tables / schemas exist in a connection.
- You need a column list and types before writing SQL or authoring a map.
- The user references "the named source for X" and you need to find it.

If you already know the table and just want to query it, jump straight to [`carto-query-datawarehouse`](../carto-query-datawarehouse).

## Quick reference

```bash
# What connections are registered?
carto connections list --json

# Walk the hierarchy (no path = top level)
carto connections browse <connection-name>

# Drill in
carto connections browse <connection-name> "carto-demo-data"
carto connections browse <connection-name> "carto-demo-data.demo_tables"

# Get columns + types for a specific table
carto connections describe <connection-name> "carto-demo-data.demo_tables.nyc_collisions"
```

The exact path syntax depends on the engine:

| Engine | `browse` path shape |
|---|---|
| BigQuery | `project.dataset.table` |
| Snowflake | `DATABASE.SCHEMA.TABLE` |
| Postgres / Redshift | `schema.table` (no leading project/database) |
| Databricks | `catalog.schema.table` |

## What's in this skill

| Topic | Reference |
|---|---|
| `connections browse` and `connections describe` in detail | [references/connection-browse.md](references/connection-browse.md) |
| Named sources — what they are, how to list and inspect them | [references/named-sources.md](references/named-sources.md) |

## Always-on guidance

- **Browse before you query.** A two-second `connections browse` usually saves a five-minute "table not found" loop.
- **Use `--page-size`** when a dataset has hundreds of tables; the default is 30.
- **`describe` returns column types** — use those types to write correct SQL (e.g. don't `ST_DWithin` against a `STRING` column the user mistakenly named `geom`).
- **Named sources ≠ tables**. They're parameterized queries. Inspect the *underlying* tables before assuming a column you see in the source exists in raw form.
- **`carto-demo-data`** is a public BigQuery dataset CARTO ships — `carto connections browse <bq-connection> "carto-demo-data"` works on any BigQuery connection that has the right IAM, and is a fast way to validate a fresh connection without touching customer data.
