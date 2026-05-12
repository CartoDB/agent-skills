# `MIGRATION_MANIFEST.md` schema

The manifest is a markdown ledger the agent maintains for the duration of a migration. The `discover` skill seeds it; downstream `migrate-*` skills update per-item state and append `Target …` fields as work completes; the `validate` skill reads it to drive parity checks.

Markdown (not YAML / JSON) was chosen so users can review and hand-edit it without tooling, and so agents read/write it natively.

## File location

Always written to `MIGRATION_MANIFEST.md` in the working directory the agent was launched in. Companion sidecar `MIGRATION_INVENTORY.json` (raw `/search` responses) sits alongside it.

## Front matter

```yaml
portal_url: https://demo.arcgis.com/portal
generated_at: 2026-05-06T14:32:00Z
target_connection: demo-bq
target_warehouse: bigquery
discover_scope: org-owned        # or: shared / group:<id> / user:<name> / folder:<name>
```

All five fields are required. `target_warehouse` is read from `carto connections list --json | jq '.[] | select(.name=="<connection>") | .provider'` — never asked of the user.

## Body sections

Sections always appear in this order; section headers are H2. Each section contains H3 entries — one per source item.

```markdown
# Migration Manifest

## Datasets

### Stores (Hosted Feature Layer)
- Source: https://services1.arcgis.com/.../Stores/FeatureServer/0
- Item ID: 4ae23afb1c1248bda1d3...
- Type: Feature Service
- State: pending
- Recommended path: carto-arcgis-migrate-data
- Notes: dynamic-tiled (verify perf after import)

### Sales Regions (Hosted Feature Layer)
- Source: https://services1.arcgis.com/.../SalesRegions/FeatureServer/0
- Item ID: 9bd11a7c3f...
- Type: Feature Service
- State: done
- Recommended path: carto-arcgis-migrate-data
- Target FQN: demo-bq.migration.sales_regions
- Target rows: 184
- Migrated at: 2026-05-06T15:01:22Z

## Web Maps

### Sales Dashboard 2024 (Web Map)
- Source Item ID: c2f...
- Type: Web Map
- State: pending
- Recommended path: carto-arcgis-migrate-maps
- Depends on: Stores, Sales Regions
- Renderer hints: 4 layers (3 exact mapping; 1 dotDensity → fallback)

## Services

### Buffer GP Service
- Source URL: https://server/.../Buffer/GPServer
- Type: Geoprocessing Service
- State: pending
- Recommended path: carto-arcgis-migrate-services
- Notes: 3-step task (buffer → dissolve → write); native-first
- M5+ pattern candidate: carto-pattern-trade-area-analysis

## Apps

### Sales Dashboard (ArcGIS Dashboard)
- Source Item ID: e5a...
- Type: Dashboard
- App profile: 7 widgets detected — 5 in Builder, 2 not available (embedded-content, multi-series serial-chart)
- Max visible widgets: 5
- Routing decision: custom-app
- State: pending
- Recommended path: carto-arcgis-migrate-apps
- Depends on: Sales Dashboard 2024 (Web Map), Stores (data), Sales Regions (data)
- Notes: embedded-content widget not available

### Store Locator Experience (Web Experience)
- Source Item ID: 3f8...
- Type: Web Experience
- App profile: 3 analytical widgets — all in Builder (formula, table, range); plus search, layer list, legend (map controls)
- Max visible widgets: 3
- Routing decision: builder
- Source Web Map: c2f...
- State: pending
- Recommended path: carto-arcgis-migrate-maps
- Depends on: Stores (data)

## Gaps

### Aerial 2023 (Image Service)
- Source URL: https://server/.../Aerial2023/ImageServer
- Item ID: f12...
- Reason: out-of-scope-v1
- Manual notes: requires raster import (BigQuery/Snowflake only)

### Field Survey 2024 (Form)
- Source Item ID: a98...
- Type: Form
- Reason: out-of-scope-v1
```

## Required keys per entry

Every H3 entry has these keys (lines starting with `- <key>: <value>`):

| Key | Source | Notes |
|---|---|---|
| `Source` or `Source Item ID` | item URL or ID | Use `Source` when the item has a service URL (Feature/GP/Map/Image services); use `Source Item ID` when it's a content item without a service URL (Web Map, Dashboard, Web Experience, Form). |
| `Item ID` | item id | Always populated; appears even when `Source` is a URL, so the agent can re-fetch item details. |
| `Type` | item `type` field | Verbatim from `/search`. |
| `State` | state machine | One of `pending` / `in-progress` / `done` / `skipped` / `failed`. |
| `Recommended path` | classifier | The `carto-arcgis-migrate-*` skill, or `gap`. |

## Optional keys (per state)

| Key | When | Source |
|---|---|---|
| `Notes` | always | Free text; classifier hints, perf notes, manual-action callouts. For apps with `Routing decision: custom-app`, must include the rule that fired (unsupported widget name, or visible-widget count). |
| `Source aliases` | datasets that have multiple service-type frontages (Feature Service + Map Service + WFS pointing at the same underlying data) | Multi-line bullet list of alternate sources collapsed into this entry. One bullet per alias: service type, URL, item ID. See "Dataset deduplication" below. |
| `Depends on` | when item references others | Comma-separated list of other entries' titles in this manifest. The discover skill resolves dependencies through `Source aliases` — a Web Map referencing a Map Service URL whose data lives under a Feature Service entry depends on the Feature Service entry's title, not the Map Service. |
| `Renderer hints` | maps | Counts that help the user gauge translation completeness. |
| `App profile` | apps (Dashboard, Web Experience, Web Mapping Application) | One-line summary of detected widgets vs. Builder availability. See [`app-routing-rubric.md`](../references/app-routing-rubric.md). |
| `Max visible widgets` | apps | Integer; max widgets visible simultaneously on any single page/layout (excludes map controls). |
| `Routing decision` | apps | `builder` or `custom-app`. Determines `Recommended path` for the app. |
| `Source Web Map` | apps with `Routing decision: builder` | Item ID of the Web Map embedded in the app — the one `migrate-maps` will turn into a Builder map. |
| `Target FQN` | datasets after `done` | Fully-qualified DW table name. |
| `Target URL` | maps / apps after `done` | Builder map URL or app dev/build path. |
| `Target rows` | datasets after `done` | Row count from the post-import `SELECT COUNT(*)`. |
| `Migrated at` | after `done` | ISO 8601 UTC timestamp. |
| `Reason` | gaps | One of `out-of-scope-v1` / `no-CARTO-equivalent` / `manual-only` / `unknown type: <type>`. |
| `M5+ pattern candidate` | gaps that match a `carto-pattern-*` skill | The matching pattern skill name, recorded for future enhancement. |
| `Failure` | when `State: failed` | One-line error summary; details in the run log. |

## Dataset deduplication

Portals frequently expose the same underlying dataset through multiple service-type items: a Feature Service plus a Map Service plus a WFS pointing at the same rows. The discover skill collapses these into **one** Datasets entry — see `SKILL.md` Phase 4 for the detection logic — so `migrate-data` runs once per logical dataset, not once per ArcGIS item.

The canonical entry is whichever item is preferred for extraction: Feature Service > Map Service > WFS > OGC API Features. The other items are recorded under `Source aliases:`:

```markdown
### Stores (Hosted Feature Layer)
- Source: https://services1.arcgis.com/.../Stores/FeatureServer/0
- Item ID: 4ae23afb1c1248bda1d3
- Type: Feature Service
- State: pending
- Recommended path: carto-arcgis-migrate-data
- Source aliases:
  - Map Service: https://server.example.com/.../Stores/MapServer (Item ID: 9bd1...)
  - WFS: https://server.example.com/.../Stores/WFSServer (Item ID: c2f3...)
```

Detection priority:

1. **`serviceItemId` cross-reference** (most reliable). When the agent fetches each service's `?f=json` metadata, the `serviceItemId` field links derived services back to their source. Items sharing a `serviceItemId` are aliases.
2. **URL-path heuristic** (fallback). Strip the service-type token (`FeatureServer` / `MapServer` / `WFSServer`) and compare the remaining URL paths. Same path → likely aliases. The agent should confirm with the user before collapsing in this case unless the match is exact.

Items that don't share a `serviceItemId` and have different URL paths are **not** aliases even if their titles match — title collisions are common.

When a Web Map / Dashboard / app references a service URL that's been collapsed into another entry's aliases, the dependency tracker resolves to the canonical entry. The `Depends on:` field always names the canonical entry, not the alias.

## State machine

```
pending  ──►  in-progress  ──►  done
                  │
                  ├──►  skipped  (user-marked or unsupported)
                  └──►  failed   (with Failure: line; retryable on next run)
```

The `discover` skill only ever writes `pending` (or preserves an existing `done`/`skipped` from a prior run on still-present items). Transitions to `in-progress` / `done` / `failed` come from the migrate-* skills.

## Idempotent re-runs

When `discover` runs against a portal that already has a `MIGRATION_MANIFEST.md`:

1. Read the existing manifest; index entries by `Item ID`.
2. Run a fresh enumeration.
3. For items present in both the new enumeration and the existing manifest:
   - Preserve `State` if it's `done`, `skipped`, or `failed`.
   - Preserve any `Target …` and `Migrated at` fields.
   - Update mutable metadata (`Type`, `Depends on`, `Renderer hints`, `Widget hints`).
4. For items in the new enumeration but not the existing manifest: append as `pending`.
5. For items in the existing manifest but no longer at the source: comment them out (`<!-- removed at source 2026-05-06 -->`) — don't delete history.

## Worked example

A minimal three-item manifest after a fresh discover:

```markdown
---
portal_url: https://demo.arcgis.com/portal
generated_at: 2026-05-06T14:32:00Z
target_connection: demo-bq
target_warehouse: bigquery
discover_scope: org-owned
---

# Migration Manifest

## Datasets

### Stores (Hosted Feature Layer)
- Source: https://services1.arcgis.com/.../Stores/FeatureServer/0
- Item ID: 4ae23afb1c1248bda1d3
- Type: Feature Service
- State: pending
- Recommended path: carto-arcgis-migrate-data

## Web Maps

### Store Locator Map (Web Map)
- Source Item ID: c2f...
- Item ID: c2f...
- Type: Web Map
- State: pending
- Recommended path: carto-arcgis-migrate-maps
- Depends on: Stores

## Gaps

### Aerial 2023 (Image Service)
- Source: https://server/.../Aerial2023/ImageServer
- Item ID: f12...
- Type: Image Service
- State: skipped
- Recommended path: gap
- Reason: out-of-scope-v1
```
