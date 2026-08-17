# Named sources

A **named source** is a saved, parameterized SQL query stored in CARTO. Maps, apps, and the SQL API consume them as if they were tables, but the underlying SQL can:

- Restrict access to a row-level subset of a base table.
- Pre-aggregate or pre-join to keep map queries fast.
- Accept parameters (e.g. `{{ date_from }}`) supplied at request time.

Named sources are how CARTO apps usually access warehouse data — hitting tables directly is fine for analysis but coarse for production multi-tenant apps.

## When the agent encounters them

- The user says "the X named source" — find it before assuming you must query the raw table.
- A map's data source is a named source — the map JSON shows `type: query` referring to it.
- An app uses a token scoped to specific named sources — then use the named-source name, not a raw table path.

## Finding and inspecting

| Task | MCP (`manage_named_sources`) | CLI fallback |
|---|---|---|
| List / search named sources | method `list` | `carto named-sources list [--search "stores"] --json` |
| Inspect one | method `get` | `carto named-sources get <name-or-id> --json` |

A `get` returns `name`, `id`, `connection` (which warehouse connection it runs against), `query` (the underlying SQL, with `{{ parameter }}` placeholders), and declared `parameters`.

> Creating/updating named sources (`manage_named_sources` `create`/`update`, or `carto named-sources create/update`) is **out of scope for this utility skill** — see [`carto-develop-app`](../../carto-develop-app) when building an app that manages them. This skill only *finds* and *inspects*.

## Named source vs. raw table

| You're looking at | Use |
|---|---|
| Tables / views / tilesets directly in the warehouse | `explore_data` `list_resources` (`connections browse`) |
| Saved CARTO queries layered on top | `manage_named_sources` `list` |

"What's the column list for the X data the dashboard reads?" has two paths:

1. Dashboard reads a **table** → `explore_data` `describe` (`connections describe`).
2. Dashboard reads a **named source** → `manage_named_sources` `get` to see the SQL, then `describe` on the *underlying* table(s) for source columns.

## Parameter placeholders

```sql bigquery
SELECT * FROM `my_project.demo.events`
WHERE event_date >= '{{ date_from }}'
  AND event_date <  '{{ date_to }}'
```

When called from an app or scoped token, `{{ date_from }}` is substituted at runtime. Inspecting the underlying table raw (via `describe`), you don't need to think about parameters — they only matter when the named source is *executed*.
