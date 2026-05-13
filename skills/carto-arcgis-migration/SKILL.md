---
name: carto-arcgis-migration
description: End-to-end ArcGIS Portal / AGOL → CARTO migration. Triggers when the user wants to migrate ArcGIS content to CARTO, plan a migration, asks "what's in my Portal", names a Portal/AGOL URL, or asks to migrate the datasets / web maps / simple apps. Runs three phases — discover (enumerate items + write MIGRATION_MANIFEST.md), migrate-data (Hosted Feature Layers / Tables → CARTO tables), migrate-maps (Web Maps + simple Dashboards / Web Experiences / Web Mapping Apps → CARTO Builder maps). Default mode is batch; migrated maps are always tagged `From ArcGIS` and created as private.
license: TBD
---

# carto-arcgis-migration

A single skill that takes an ArcGIS Portal / AGOL endpoint and lands its content in CARTO. Three phases, run in order, sharing one source of truth — `MIGRATION_MANIFEST.md` in the working directory:

1. **Discover** — enumerate items, classify, write the manifest. See [`references/discover.md`](references/discover.md).
2. **Migrate data** — Hosted Feature Layers + Hosted Tables → CARTO tables (Datasets section of the manifest). See [`references/migrate-data.md`](references/migrate-data.md).
3. **Migrate maps** — Web Maps + simple Dashboard / Web Experience / Web Mapping Application entries → CARTO Builder maps (Web Maps + Apps sections of the manifest). See [`references/migrate-maps.md`](references/migrate-maps.md).

The manifest accumulates state — every phase updates entries from `pending` → `in-progress` → `done` / `skipped` / `failed`. Re-runs are idempotent: `done` entries are skipped; `failed` entries are retried.

## Prerequisites

- The `carto-skills` plugin (this catalog). The migration phases delegate CARTO-side mechanics — imports, queries, map authoring — to `carto-import-export-data`, `carto-query-datawarehouse`, `carto-explore-datawarehouse`, and `carto-create-builder-maps`.
- Authenticated `carto` CLI (`carto auth login`) with at least one connection in `carto connections list --json`.
- Access to an ArcGIS Portal / AGOL endpoint, plus credentials (or anonymous for fully public AGOL).
- **Python with `geopandas` + `pyarrow`** for GeoParquet extraction in the data phase. `sqlglot` is required by the maps phase for Arcade-to-SQL validation.

## Routing the user's request

Pick the phase from what the user asked for:

| User request                                                              | Phase                                                |
| ------------------------------------------------------------------------- | ---------------------------------------------------- |
| "Migrate my ArcGIS Portal", "what's in my Portal", names a Portal/AGOL URL without naming items | **Discover** ([`references/discover.md`](references/discover.md)) |
| "Migrate the datasets", "migrate all data", names a Hosted Feature Layer / Hosted Table | **Migrate data** ([`references/migrate-data.md`](references/migrate-data.md)) |
| "Migrate the maps", "migrate the simple apps", names a Web Map or simple-app title | **Migrate maps** ([`references/migrate-maps.md`](references/migrate-maps.md)) |
| "Run the whole migration"                                                 | Run all three phases in order, stopping for user review after each |

If the user names a single item, filter the relevant phase to that entry.

## Order matters

- **Discover before any migrate-* phase.** The manifest is the source of truth — the data and maps phases refuse to start without it.
- **Migrate data before migrate maps.** Web Maps and simple apps depend on `Target FQN` resolved on Datasets entries. A Web Map whose layers reference an unmigrated dataset is marked `failed` (`Failure: depends-on-unmigrated-data`) — the maps phase does **not** auto-invoke migrate-data; the user wants explicit visibility into the gap.

## Always-on rules (skill-wide)

- **Pass `--json`** on every `carto` invocation; pass `&f=json` on every ArcGIS REST call.
- **Don't migrate during discovery.** Discovery writes the manifest only. The user reviews before any migrate-* phase runs.
- **Update the manifest on every state transition.** A crash mid-batch must leave the manifest reflecting reality on disk.
- **Never abort a batch on per-item failures**, except CARTO auth expiry (parse `--json` 401/403 → leave the in-progress item alone, stop the batch, ask the user to `carto auth login` and re-invoke).
- **Idempotency.** `done` entries are skipped silently. `failed` entries are retried (`migrate-data` with `--overwrite`; `migrate-maps` title-and-tag precheck).
- **Tag every migrated map `From ArcGIS`**, leave privacy default (private). The tag is the sole signal for the idempotency precheck and customer-side filtering.
- **Capture lessons as you go.** Each migrate-* phase appends non-obvious patterns to `SESSION_LESSONS.md` in the working directory and surfaces it at end of batch. **Never auto-edit the cached skill files** — the references are read-only from the agent's perspective at runtime; the maintainer merges upstream.
- **Consult the relevant `references/*.md` before writing migration code.** Renderer mappings, popup translation, Arcade subset, basemap mapping, dataset config requirements, and the migration-specific "lessons from the field" all live there. Re-discovering documented quirks wastes the user's time.
