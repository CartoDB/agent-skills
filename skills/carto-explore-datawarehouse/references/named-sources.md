# Named sources

A **named source** is a saved, parameterized SQL query stored in CARTO. Maps, apps, and the SQL API consume them as if they were tables, but the underlying SQL can:

- Restrict access to a row-level subset of a base table.
- Pre-aggregate or pre-join to keep map queries fast.
- Accept parameters (e.g. `{{ date_from }}`) that the consuming app supplies at request time.

Named sources are how CARTO apps usually access warehouse data — directly hitting tables is fine for analysis but coarse for production multi-tenant apps.

## When the agent encounters them

- The user says "the X named source" — find it before assuming you need to query the raw table.
- A map's data source is a named source — when inspecting the map JSON you'll see `type: query` referring to a named source.
- An app uses a token scoped to specific named sources — in that case the agent must use the named source name, not a raw table path.

> Named-source CRUD (`carto named-sources create/update/delete`) is **out of scope for this utility skill** — that's part of [`carto-build-app`](#) (Phase 2). This skill only covers *finding* and *inspecting* existing named sources.

## Listing named sources

```bash
carto named-sources list --json
carto named-sources list --search "stores" --json
```

## Inspecting a single named source

```bash
carto named-sources get <name-or-id> --json
```

The JSON includes:
- `name`, `id`
- `connection` — which warehouse connection it runs against
- `query` — the underlying SQL (with `{{ parameter }}` placeholders if any)
- `parameters` — declared parameter names and types

## Distinguishing named sources from `connections browse` output

| You're looking at | Use |
|---|---|
| Tables / views / tilesets directly in the warehouse | `connections browse` |
| Saved CARTO queries layered on top | `named-sources list` |

A typical question like "what's the column list for the X data the dashboard reads?" has two paths:

1. The dashboard reads a **table** → `connections describe <conn> "<path>"`.
2. The dashboard reads a **named source** → `named-sources get <name>` to see the SQL, then `connections describe` on the *underlying* table(s) to see source columns.

## Parameter placeholders

```sql bigquery
SELECT * FROM `my_project.demo.events`
WHERE event_date >= '{{ date_from }}'
  AND event_date <  '{{ date_to }}'
```

When called from an app or a scoped token, `{{ date_from }}` is substituted at runtime. When inspecting raw — e.g. through `connections describe` on the underlying table — you don't need to think about parameters; they only matter when the named source is being *executed*.
