# Changelog

## Unreleased

### Added

- `carto-create-builder-maps` — author maps in CARTO Builder: layers, basemaps, styling, sharing, AI Agents on the map. Migrated from `cloud-native-cli-pr/carto-cli/skills/` after end-to-end validation against a live organization. SKILL.md + 11 references covering authoring lifecycle, cartographic decisions (palette, scale, basemap pairing, anti-patterns), per-layer-type guidance, widgets, popups, SQL parameters, basemap, agent-on-the-map block, troubleshooting, and CRUD updates.

### Changed

- Removed `carto-create-builder-maps` from the deferred list (`docs/deferred-skills.md`). The open question about AI Agents (sub-topic vs. sibling skill) was settled in favour of bundling them into `carto-create-builder-maps` via `references/agent-config.md`.
- Skill count: 20 → 21 (4 utility + 7 platform + 10 use-case patterns). Install matrix, README, and plugin manifests updated.

---

## 2.4.0-phase2d — 2026-04-30

Migrates the workflow-builder skill set from the standalone `workflows-assistant-skills` repo into this catalog and adds the use-case (pattern) tier.

### Added

- `carto-create-workflow` — full DAG authoring lifecycle (6-phase process, native-first rule, live CLI fetching, JSON structure, provider notes, pitfalls) plus operating CRUD/scheduling. Replaces the prior `carto-create-analytics-workflow` skill.
- 10 use-case `carto-pattern-*` skills (hotspot, GWR, Moran's I, geocoding, routing, site-selection, territory, trade-area, composite-scoring, spatial-enrichment). Each ships rich trigger-keyword descriptions and bundled `.json` examples.
- Provider-specific customsql footguns and the Snowflake uppercase rule live in `references/providers/*.md` under `carto-create-workflow`.

### Changed

- `carto-create-analytics-workflow` renamed to `carto-create-workflow`. Cross-profile copy content stays owned by `carto-copy-workflows` (introduced in 2.3.0-phase2c).
- `carto workflows verify` references updated to `carto workflows verify-remote` to match the CLI.

### Catalog dependencies for new skills

- `carto-create-workflow` → `carto-basics`, `carto-connect-datawarehouse`, `carto-query-datawarehouse`.
- All `carto-pattern-*` → `carto-create-workflow`.

### Note

This release pairs with the matching `carto` CLI version in https://github.com/CartoDB/cloud-native/pull/24203.

---

## 2.3.0-phase2c — 2026-04-28

Splits **create** and **copy** activities into separate platform skills. Cross-org / cross-profile artifact replication now has its own home, distinct from agentic creation. Lays the groundwork for absorbing PR #2's migration content cleanly.

### Added

- `carto-copy-maps` — cross-org / cross-profile map copy, AI-agent reference caveats (`UNAVAILABLE_MODEL`, `UNAVAILABLE_TOOL`), post-copy validation.
- `carto-copy-workflows` — cross-org / cross-profile workflow copy + schedule re-add (schedules don't transfer).
- 5 new reference files; salvages map-copy content from PR #2 (carto-migration, Feb 2026, by @anamanvil) directly into the copy skills.

### Changed

- `carto-create-analytics-workflow` no longer carries cross-profile-copy content. The `references/copy-promotion.md` file moved to `carto-copy-workflows/references/cross-profile-copy.md`. SKILL.md gains a "see also" pointer.
- `docs/deferred-skills.md` clarifies that copy / agent-migration caveats are *not* the Builder PM's scope — they live in `carto-copy-maps`. The Builder PM only owns map authoring.

### Catalog dependencies for new skills

- `carto-copy-maps` → `carto-basics`, `carto-explore-datawarehouse`.
- `carto-copy-workflows` → `carto-basics`, `carto-explore-datawarehouse`.

### Deferred (no change in this release)

- `carto-promote-between-orgs` use-case skill (multi-resource cross-org orchestration) — revisit when usage signals demand it.
- `carto-create-builder-maps`, `carto-build-app` (still owned by Builder PM).
- Watermarking docs and TS validator hardening — still gated on the CLI-team RFC.

---

## 2.2.0-phase2b — 2026-04-28

Adds **Codex** and **Gemini CLI** distribution alongside the existing Claude Code + Skills CLI surfaces. Same skills, three more harnesses.

### Added

- `.codex-plugin/plugin.json` at repo root — Codex plugin manifest, modeled on MotherDuck's pattern (single-source, `skills` as directory pointer, `interface` block with display metadata and default prompts).
- `gemini-extension.json` at repo root — Gemini CLI extension manifest pointing at `GEMINI.md` for context.
- `commands/carto/<skill>.toml` — one Gemini command per skill (8 total). Invoked as `/carto:<skill-name>`. Each TOML's prompt reads the skill's SKILL.md and references on demand.
- `GEMINI.md` — Gemini-specific context with reading order and per-skill command reference.

### Validator additions

`scripts/validate_skills.py` gained three new checks:

- **Codex plugin sync** — required fields present, version matches catalog, `skills` directory exists.
- **Gemini extension sync** — required fields, version, `contextFileName` resolves.
- **Gemini commands sync** — exactly one TOML per catalog skill; no orphans, no missing.

### Sync logic

`scripts/sync_manifests.py` now generates all four manifests from `skills/catalog.json`: Claude plugin, Codex plugin, Gemini extension, per-skill Gemini TOMLs. Stale TOMLs (skills removed from the catalog) are pruned automatically.

### Deferred

- `custom_user_agent` watermarking → Phase 2c.
- TypeScript snippet validator promoted from warning-only to blocking → Phase 2c.
- `carto-create-builder-maps`, `carto-build-app` (still owned by Builder PM).

---

## 2.1.0-phase2a — 2026-04-28

Adds the **4 platform-tier skills** that make up the bulk of CARTO's day-to-day operational surface. No breaking changes from 2.0.0.

### Added

- `carto-import-export-data` — imports, tilesets, exports.
- `carto-create-workflow` — workflow CRUD, scheduling per engine, dev→prod promotion.
- `carto-find-spatial-data` — Data Observatory discovery and subscriptions.
- `carto-manage-platform` — org stats, users/invitations, admin bulk ops, activity event reference.
- `docs/deferred-skills.md` — status of `carto-create-builder-maps` and `carto-build-app` (owned by another PM).
- 18 new reference files across the 4 skills.

### Catalog

Platform-tier dependencies declared and validated:

- `carto-import-export-data` → `carto-basics`, `carto-connect-datawarehouse`, `carto-explore-datawarehouse`.
- `carto-create-workflow` → `carto-basics`, `carto-connect-datawarehouse`, `carto-query-datawarehouse`.
- `carto-find-spatial-data` → `carto-basics`, `carto-connect-datawarehouse`, `carto-explore-datawarehouse`.
- `carto-manage-platform` → `carto-basics`, `carto-query-datawarehouse`.

### Deferred (no change in this release)

- `carto-create-builder-maps`, `carto-build-app` — owned by Builder PM. Pre-staged content in `docs/_phase2-salvage/` is intact for that PM to pick up.
- Codex plugin and Gemini extension distribution → Phase 2b.
- `custom_user_agent` watermarking → Phase 2c.

---

## 2.0.0-phase1 — 2026-04-28

**Breaking change.** The repo has been restructured into a multi-harness skills catalog modeled on [MotherDuck's agent-skills](https://github.com/motherduckdb/agent-skills). See [`docs/proposal-skills-redesign.md`](docs/proposal-skills-redesign.md) for the design.

### Migration from v1.x

The old plugin IDs are **retired**:

- ❌ `carto-cli@carto-agent-skills` — removed.
- ❌ `carto-activity@carto-agent-skills` — removed.

Replace with the new bundle:

```bash
/plugin install carto-skills@carto-agent-skills
```

The new bundle ships **4 utility skills** that together cover the install/auth/connect/explore/query content from the old `carto-cli` skill, plus the SQL-query patterns from the old `carto-activity` skill.

### Added (Phase 1)

- Three-tier layered skill catalog (utility / platform / use-case).
- 4 utility skills: `carto-basics`, `carto-connect-datawarehouse`, `carto-query-datawarehouse`, `carto-explore-datawarehouse`.
- `skills/catalog.json` as single source of truth.
- `scripts/validate_skills.py` (catalog/manifest/layer/reference integrity).
- `tests/validate_snippets.py` (per-language code-block linting; SQL via `sqlglot`).
- `make validate` and GitHub Actions workflow.
- Skills CLI distribution via `npx skills add`.
- Authoring guide (`docs/skill-authoring.md`) and install matrix (`docs/install-matrix.md`).

### Removed

- Top-level `carto-cli/` and `carto-activity/` skill directories (content salvaged into the new utility skills or staged in `docs/_phase2-salvage/` for Phase 2).
- `NODE_TLS_REJECT_UNAUTHORIZED=0` workarounds (claude.ai sandbox-specific; assume `npm install -g @carto/carto-cli` instead).
- `/mnt/skills/user/carto-cli/carto.js` bundled-CLI references.

### Deferred to Phase 2 / 3

- 6 platform skills (Phase 2): `carto-import-export-data`, `carto-create-builder-maps`, `carto-build-app`, `carto-create-workflow`, `carto-find-spatial-data`, `carto-manage-platform`.
- 3 use-case skills (Phase 3): `carto-build-spatial-dashboard`, `carto-build-customer-facing-map`, `carto-migrate-to-carto`.
- Codex plugin and Gemini extension distribution.
- `custom_user_agent` watermarking.
