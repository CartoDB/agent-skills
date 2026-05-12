---
name: carto-arcgis-migrate-data
description: Migrate Hosted Feature Layers and Hosted Tables from an ArcGIS Portal/AGOL to CARTO data warehouse tables. Walks the manifest's Datasets section, extracts each pending entry as GeoParquet, imports via `carto imports create`, and updates per-item state. Default mode is batch (all pending Datasets entries in one run); single-item migration is supported by naming a layer or table title. Triggers when the user says "migrate the datasets" or "migrate all data" or names a Hosted Feature Layer / Hosted Table after `carto-arcgis-discover` has run.
license: TBD
---

# carto-arcgis-migrate-data

Takes the Datasets section of `MIGRATION_MANIFEST.md` and lands each pending Hosted Feature Layer / Hosted Table as a table in the user's CARTO connection. **Default mode is batch** — process every pending entry in one invocation. Idempotent: `done` entries are skipped on re-run; `failed` entries are retried with `--overwrite`. Items whose extracted size would exceed the 1 GB CARTO Imports per-file limit are flagged in the final summary and surface for follow-up — they don't abort the batch.

## Prerequisites

- `MIGRATION_MANIFEST.md` exists in the working directory (produced by `carto-arcgis-discover`). The skill reads it and updates entries in place.
- The `carto-skills` plugin (`/plugin install carto-skills@carto-agent-skills`). This skill defers the actual import call to `carto-import-export-data`.
- `carto auth login` already done. The connection named in the manifest's front-matter `target_connection` must appear in `carto connections list --json`.
- **Python with `geopandas` + `pyarrow`** for GeoParquet output. If either is unavailable, the skill stops and asks the user to install them — it does not silently fall back to GeoJSON.

## When to use this skill

- After `carto-arcgis-discover` produces a manifest. Default: process all pending Datasets entries.
- To migrate a single dataset: name the layer/table title from the manifest.
- To re-run after fixing a failed item: previous `done` entries are skipped; `failed` entries are retried (with `--overwrite` to clear partial imports).

## Phases

Follow these in order on every invocation.

### Phase 0 — Read prior lessons

**Before writing any extraction or import script**, open [`references/lessons.md`](references/lessons.md) and follow its patterns. The lessons are seeded from real migrations — pagination quirks that don't appear in any documentation, auth-expiry signals to watch for, type-coercion edge cases, geometry oddities, service-specific gotchas. Ignoring this file causes the same bug to be re-discovered by every migration.

Initialize an empty `SESSION_LESSONS.md` in the working directory. The agent appends to it whenever it encounters a non-obvious pattern during the batch (see Phase 5 and the always-on rule below).

### Phase 1 — Plan the batch

1. Read `MIGRATION_MANIFEST.md`. Collect entries under `## Datasets` with `State: pending` or `State: failed`. If the user named a single layer/table, filter to that entry.
2. Print a one-line plan to chat: N entries to migrate, target connection, target warehouse.
3. For each in-scope entry, transition `State: pending → in-progress` and write the manifest immediately, so a crash mid-batch leaves a recoverable trail.
4. **Idempotency precheck** (per [`references/manifest-update-protocol.md`](references/manifest-update-protocol.md)): for each entry, run `carto sql query` to check whether `Target FQN` already exists with matching row count. If it does, skip back to `done` without re-extracting.

### Phase 2 — Probe each entry

1. **Row count**: `GET <Source>/query?where=1=1&returnCountOnly=true&f=json` → `count`. Empty layers (`count == 0`) → `State: skipped`, `Reason: empty-source`.
2. **Sample-page size**: extract page 1 (`resultRecordCount=2000` or service max), measure on-disk bytes.
3. **Estimate full size**: `est_bytes = (sample_bytes / sample_rows) × total_rows × 1.3` (1.3× safety factor).
4. If `est_bytes > 1 GB`: `State: skipped`, `Reason: exceeds-1gb-staging-not-implemented`, write the manifest, continue to the next entry. Do not abort the batch.

### Phase 3 — Extract to GeoParquet

For each in-scope entry, follow [`references/extraction-recipes.md`](references/extraction-recipes.md):

1. Pick extractor silently: `arcgis` Python + `geopandas` (preferred) or `curl + jq + small Python helper` (fallback).
2. Page through the source with `outSR=4326`, deterministic `orderByFields` (default: the layer's `objectIdField`), `resultRecordCount=2000`. Loop until `exceededTransferLimit=false`.
3. Stream features into a `GeoDataFrame` and write `out/<item-id>.parquet` in the working directory.
4. Tables (no geometry) emit a `DataFrame` Parquet — no geometry column. Otherwise the same flow.

### Phase 4 — Import to CARTO

For each in-scope entry, follow [`references/import-flow.md`](references/import-flow.md):

1. `carto import --file ./out/<item-id>.parquet --connection <target_connection> --destination <fqn> --json` (add `--overwrite` if the entry was `failed` or already had `Target FQN`).
2. Parse `--json` output for the resulting table identifier.
3. **Verify**: `carto sql query <target_connection> "SELECT COUNT(*) FROM <fqn>" --json` and compare to the Phase-2 source count.
4. Match (±1 row tolerance) → `State: done`, set `Target FQN`, `Target rows`, `Migrated at`. Mismatch → `State: failed`, `Failure: row count mismatch (source=N, target=M)`.

### Phase 5 — Final summary + capture lessons

Print a structured summary to chat:

- **Migrated** (count + per-entry table FQNs).
- **Skipped — empty** (entries with no rows).
- **Skipped — > 1 GB** (entries whose extracted size would exceed the per-file limit; staging fallback comes in a later feature).
- **Failed** (entries with `State: failed` after this run; show `Failure:` reason).

Then check `SESSION_LESSONS.md` in the working directory:

- If empty: continue.
- If non-empty: print its contents in chat and surface both follow-up paths to the user — **do not auto-edit the cached skill files**, ever. The skill is loaded read-only from `~/.claude/plugins/cache/...` for end-users; anything written there is lost on the next plugin update.

  Recommended message:

  > Session lessons captured in `SESSION_LESSONS.md` (printed above). Two ways to act on them:
  >
  > - **If you're maintaining this skill locally** (the source repo `carto-arcgis-skills` is cloned somewhere writable): open the source-repo `references/lessons.md`, append the new entries under the matching section, bump `version` in `skills/catalog.json`, run `make sync && make validate`, commit + push per `CLAUDE.md`. The next plugin release ships the new lessons.
  > - **Otherwise** (you installed the published plugin and don't maintain it): keep `SESSION_LESSONS.md` for this engagement. If a pattern is widely useful, share the file with the skill maintainer — they'll fold the pattern into the upstream lessons.

  The agent never touches the source repo or the cached plugin files on its own. The maintainer reviews and applies; the end-user keeps a local artifact.

If `Datasets` is fully resolved (no `pending` left), suggest invoking `carto-arcgis-migrate-maps` next.

## Always-on rules

- **Consult `references/lessons.md` before writing any extraction or import code.** Every quirky pattern documented there saved a previous migration; ignoring them re-discovers the same bug. Pay special attention to the auth-expiry, pagination, type-coercion, and CARTO-platform-quirks sections.
- **Consult `carto-agent-skills` before writing any `carto` invocation.** Every CARTO platform interaction (`carto import`, `carto sql query`, `carto connections describe`, `carto auth status`, …) has a tested recipe in the matching carto-skill. Don't validate flags by `--help` or guesswork — read the skill, follow the recipe. See `references/lessons.md` "Consult carto-agent-skills first" for the per-command mapping. **Recipe drift caveat**: when a skill recipe and the installed CLI disagree (e.g. an `unknown command` error), `carto <subcommand> --help` once to confirm the noun shape, then continue. See `references/lessons.md` "carto CLI v0.6.x ships `carto import` (singular)" for the canonical example.
- **Capture new lessons as you go.** Whenever the agent encounters and works around a non-obvious quirk during the batch (a pagination edge case, an auth-expiry signal, a type-coercion surprise, a geometry oddity), append to `SESSION_LESSONS.md` in the working directory using the template at the bottom of `references/lessons.md`. At end of batch (Phase 5), surface the file to the user with both follow-up paths (maintainer merges upstream; end-user keeps the file). **Never auto-edit the cached skill** — `references/lessons.md` is read-only from the agent's perspective at runtime.
- **Stop the batch on CARTO auth expiry.** `carto import` or `carto sql query` returning a 401/403 (parsed from `--json`) means subsequent calls will all fail. Do not mark the current item `failed`; leave it `in-progress` so the user can resume after `carto auth login`. See `references/lessons.md` "CARTO session expired" for the detection pattern.
- **Pass `--json`** on every `carto` invocation; pass `&f=json` on every ArcGIS REST call.
- **Idempotency.** `done` entries are skipped silently. `failed` entries are retried with `--overwrite`.
- **One file per item.** Write to `out/<item-id>.parquet` so re-runs and post-mortem inspection are easy. Don't share intermediate files across items.
- **Never abort the batch on per-item failures.** Size, network, type mismatches flag the entry and the loop continues. The exceptions are CARTO auth expiry (above) and the user explicitly cancelling.
- **Update the manifest on every state transition.** A crash mid-batch must leave the manifest reflecting reality on disk.
- **WGS84 only.** Always request `outSR=4326`. If the source refuses, reproject locally with `geopandas.to_crs(4326)` and note it on the entry.
- **GeoParquet, not GeoJSON.** Stop and ask the user to install `geopandas`+`pyarrow` if they're missing — don't silently fall back.

## When in doubt

- `geopandas` / `pyarrow` not installed? Stop and ask: `pip install geopandas pyarrow`.
- Source returns M-aware or Z-aware geometries? Strip M/Z (CARTO is 2D by default) and record `Notes: M/Z geometry stripped` on the entry.
- Probe shows `count: 0`? `State: skipped`, `Reason: empty-source`.
- Source rejects `outSR=4326`? Try `outSR=4269` and reproject; record `Notes:` on the entry.
- Estimated size between 0.8 and 1.0 GB? Extract anyway but warn the user — the estimate has a 1.3× safety factor but actual files can still surprise. If post-extraction file size exceeds 1 GB, flip to `State: skipped`, `Reason: exceeds-1gb-staging-not-implemented`, delete the local file.
