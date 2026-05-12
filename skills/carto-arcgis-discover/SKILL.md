---
name: carto-arcgis-discover
description: Enumerate ArcGIS Portal / AGOL items, classify each by type, and write MIGRATION_MANIFEST.md so the agent and the user know what to migrate and how. Triggers when the user wants to plan or start a migration from ArcGIS to CARTO, asks "what's in my Portal", or names a Portal/AGOL URL without specifying which items to migrate. Use this BEFORE any other carto-arcgis-* skill.
license: TBD
---

# carto-arcgis-discover

A migration starts here. Given an ArcGIS Portal or ArcGIS Online endpoint plus credentials, this skill walks the agent through enumerating every relevant item, classifying it by type, and writing a markdown manifest that downstream migration skills consume.

The output — `MIGRATION_MANIFEST.md` in the working directory — is the source of truth for the rest of the migration. The agent updates per-item state as later skills run.

## Prerequisites

- The `carto-skills` plugin (`/plugin install carto-skills@carto-agent-skills`). This skill defers all CARTO-side mechanics to it.
- Authenticated `carto` CLI (`carto auth login`) with at least one connection in `carto connections list` — needed for the manifest to record the migration target.
- Access to an ArcGIS Portal or ArcGIS Online endpoint, plus credentials (or anonymous access for fully public AGOL items). See [`references/extraction-tools.md`](references/extraction-tools.md) for auth patterns.

## When to use this skill

- Starting a fresh migration: the user names a Portal/AGOL URL.
- Re-running discovery on the same Portal after content changes — the manifest is regenerated, preserving any items already marked `done`.
- Replanning before a partial migration: the user asks for a manifest filtered to a single user / group / folder.

## Phases

Follow these in order on every run.

### Phase 1 — Connect

1. Confirm the portal URL with the user. Trim trailing slashes; the `/sharing/rest` suffix is implicit.
2. Determine auth: token, username/password, or anonymous (public AGOL only). Read tokens from env (`ARCGIS_TOKEN`) before prompting.
3. Validate with one REST call: `GET <portal>/sharing/rest/portals/self?f=json`. A populated `user` object in the response means auth works.
4. Confirm the CARTO target: the user must name an existing CARTO connection. Run `carto connections list --json` to enumerate. Defer warehouse-target choice to the user; do not auto-pick.

### Phase 2 — Enumerate

1. Decide enumeration scope with the user: org-owned items (default), shared content, a specific group, a specific user, or a specific folder. Default is "items the authenticated user owns plus shared org content."
2. Page through the source. Pick the tool silently per [`references/extraction-tools.md`](references/extraction-tools.md): `arcgis` Python (`gis.content.search`) when installed; otherwise `curl` + `jq` against `/sharing/rest/search`. Continue paging until `nextStart == -1`.
3. For each item, capture: `id`, `title`, `type`, `typeKeywords`, `owner`, `created`, `modified`, `url` (when present), `size`, `numViews`, and any `dependencies` you can resolve from `relatedItems` or per-type detail calls (e.g. a Web Map's operationalLayers reveal which Feature Services it depends on).
4. Persist the raw responses to a sidecar file `MIGRATION_INVENTORY.json` in the working directory so downstream skills can re-read item details without re-hitting the REST API.

### Phase 3 — Classify

For each item, look up its `type` (and supplementary `typeKeywords` when needed) in [`references/item-types.md`](references/item-types.md). Each type maps to one of:

- A downstream skill: `carto-arcgis-migrate-data`, `carto-arcgis-migrate-maps`, `carto-arcgis-migrate-services`, or `carto-arcgis-migrate-apps`.
- A gap entry, with reason: `out-of-scope-v1`, `no-CARTO-equivalent`, or `manual-only`.
- An unknown-type entry (the type isn't in the reference). Surface these to the user explicitly — they may indicate a customization.

For Dashboard, Web Experience, and Web Mapping Application items, classification has a second step: fetch the item's `data` payload and apply the routing rubric in [`references/app-routing-rubric.md`](references/app-routing-rubric.md). The rubric chooses between `carto-arcgis-migrate-maps` (simple apps absorbed into the embedded Web Map's Builder map) and `carto-arcgis-migrate-apps` (custom apps with widgets Builder doesn't cover or layouts denser than 4 widgets). Record `App profile`, `Max visible widgets`, `Routing decision`, and (for `builder` decisions) `Source Web Map` on the manifest entry per [`references/manifest-format.md`](references/manifest-format.md).

Track inter-item dependencies. A Web Map references Feature Services; an ArcGIS Dashboard references both maps and feature services. Record dependencies on each entry so downstream skills migrate in the right order.

### Phase 4 — Dedup datasets

A single underlying dataset can be exposed through multiple service-type items (Feature Service + Map Service + WFS + OGCFeatureServer pointing at the same rows). Collapse these into one Datasets entry before writing the manifest, so `migrate-data` runs once per logical dataset.

Detection priority (per [`references/manifest-format.md`](references/manifest-format.md) "Dataset deduplication"):

1. **`serviceItemId` cross-reference**: fetch each service's `?f=json` metadata; group items whose `serviceItemId` references the same source item.
2. **URL-path heuristic**: strip the service-type token (`FeatureServer` / `MapServer` / `WFSServer`) and group items with identical remaining paths. Confirm with the user before collapsing unless the match is exact.

For each alias group, pick the canonical entry by preference order: Feature Service > Map Service > WFS > OGCFeatureServer. Move the others into `Source aliases:` on the canonical entry. **Do not duplicate them as separate Service entries** — that's the most common mistake on real portals and produces three migrations of the same data.

When a Web Map / Dashboard / app references a service URL belonging to a collapsed alias, resolve the dependency to the canonical entry's title in `Depends on:` — not the alias URL.

### Phase 5 — Write the manifest

Emit `MIGRATION_MANIFEST.md` in the working directory using the schema in [`references/manifest-format.md`](references/manifest-format.md). Sections (in order): Datasets, Web Maps, Services, Apps, Gaps. Each new entry starts in state `pending`.

If `MIGRATION_MANIFEST.md` already exists, read it first and preserve `state: done` and per-item `Target …` fields for items still present at the source. New items are appended in their section. Items removed at the source are commented out, not deleted.

### Phase 6 — Summarize

Print a short summary in the chat: counts per section, any gaps, dependencies the agent will need to walk during migration. Then stop. Let the user review the manifest before invoking any downstream migration skill.

## Always-on rules

- **Pass `--json`** on every `carto` invocation; pass `&f=json` on every ArcGIS REST call.
- **Inspect silently, don't ask.** Tool selection (`arcgis` Python vs. `curl`+`jq`), pagination details, item-type lookups — all are agent decisions, not user-facing questions.
- **Never invent item ids or types.** All classifications come from the source `/search` response. If a type is unfamiliar, classify as a gap with `unknown type: <type>` and surface to the user.
- **Don't migrate during discovery.** This skill writes the manifest only. The user reviews before the agent invokes downstream skills.
- **Idempotent re-runs.** The manifest accumulates state; re-running discover preserves done/skipped entries for items still at the source.
- **Dedup datasets**: never produce two Datasets entries (or one Datasets entry plus one Service entry) for the same underlying data. Apply Phase 4 detection on every run. The user only wants one CARTO table per logical dataset, regardless of how many ArcGIS items front it.
- **Always inspect apps.** Never route a Dashboard, Web Experience, or Web Mapping Application to `migrate-apps` without first applying the routing rubric and recording an explicit reason — either an unsupported widget or > 4 visible widgets — in `Notes` on the manifest entry. Default to `migrate-maps` whenever the rubric allows. For Web Mapping Application, identify the subtype via `typeKeywords` (`Configurable` / `Instant App` / `WAB2D` / `WAB3D`) before reading the data payload.
- **Stop on auth failure.** If the portal returns 401/403, ask the user for fresh credentials. Do not retry silently.

## When in doubt

- Item type isn't in [`references/item-types.md`](references/item-types.md)? Classify as gap with `unknown type: <type>` and call it out in Phase 5's summary.
- Portal returns >10 K items? Confirm scope with the user before enumerating — they likely want a filtered run.
- A Web Map references a Feature Service that isn't in the user's org? Record it as an external dependency on the map's entry; flag for the user (downstream migrations may fail to resolve it).
