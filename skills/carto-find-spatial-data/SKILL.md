---
name: carto-find-spatial-data
description: Discover and subscribe to external spatial datasets via CARTO Data Observatory and partner catalogs.
license: MIT
---

# carto-find-spatial-data

The **CARTO Data Observatory (DO)** is a catalog of curated external spatial datasets — demographics, points of interest, environmental data, mobility, financial — that you can subscribe to and query from the CARTO Data Warehouse. Instead of the user hunting down a US census shapefile, this skill answers: "what's already curated in the DO that would help here?"

This skill covers **discovery and subscription**. Once subscribed, the dataset is a view in the CARTO Data Warehouse, queryable on the `carto_dw` connection like any other table — see [`carto-query-datawarehouse`](../carto-query-datawarehouse).

> **Access-path routing.** With the CARTO MCP server attached, route discovery through `search_data_observatory` (`method: list_datasets|list_filters|search_variables|get_dataset|sample`) — available even on **token-authenticated** sessions — and subscription management through `manage_data_observatory_subscriptions` (`method: list|subscribe|unsubscribe`), which needs an **OAuth** session. Fall back to the `carto do` CLI when the server isn't attached, for scripted use, or to subscribe from a token session. The evaluation guidance below (coverage, licensing, cadence) applies on every path. Detection signals: [`carto-basics/references/access-paths.md`](../carto-basics/references/access-paths.md).

## When to use this skill

- The user asks for "demographics", "points of interest", "boundaries", "mobility data", "weather", or any other category of *external* spatial data.
- The user has internal data and wants to *enrich* it with external context (e.g. spatial-join their stores against census tracts).
- The user is exploring what's available before committing to a paid subscription.

If the user already has the dataset in their warehouse, jump to [`carto-explore-datawarehouse`](../carto-explore-datawarehouse) instead — DO is for sourcing *new* external data.

## Quick reference

MCP (search available on any session; subscribe needs OAuth):

```
search_data_observatory { method: "list_datasets", keyword: "census", country: "usa" }
search_data_observatory { method: "get_dataset", dataset_id }        # inspect before subscribing
manage_data_observatory_subscriptions { method: "list" }
manage_data_observatory_subscriptions { method: "subscribe", body: { source: dataset_id, filter?, filterColumns? } }
```

CLI fallback (no server / scripted / token-session subscribe):

```bash
carto do search --keyword "census" --country usa --json
carto do get <dataset-id> --json
carto do subscriptions list --json
carto do subscribe <dataset-id>       # prints the view to query on carto_dw
```

## What's in this skill

| Topic | Reference |
|---|---|
| Discovery: searching, filtering, evaluating datasets | [references/data-observatory.md](references/data-observatory.md) |
| Subscribing: public vs premium, the CARTO Data Warehouse view, unsubscribing | [references/subscribe.md](references/subscribe.md) |

## Always-on guidance

- **Free vs paid**: many DO datasets are free (US Census, OpenStreetMap-derived, NaturalEarth). Premium datasets (Spatial.ai, Mastercard, AirSage, etc.) require a CARTO subscription contract — `get_dataset` / `carto do get` shows the licensing and pricing tier.
- **A subscription is a view in the CARTO Data Warehouse**, not a copy in the user's own warehouse. Subscribing needs a CARTO Data Warehouse connection in the organization, and the view is queried on `carto_dw`.
- **Don't recommend a DO dataset without inspecting it first** (`get_dataset` / `carto do get`). Its metadata reveals coverage (US-only, EU-only, global), update cadence (monthly, yearly, real-time), and licensing — all critical to whether it fits the user's question.
- **DO is *external*; named sources are *internal*.** Named sources (covered in [`carto-explore-datawarehouse/references/named-sources.md`](../carto-explore-datawarehouse/references/named-sources.md)) are the user's saved queries; DO is the curated catalog of third-party data. Don't confuse the two.
