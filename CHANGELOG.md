# Changelog

## 2.1.0-phase2a — 2026-04-28

Adds the **4 platform-tier skills** that make up the bulk of CARTO's day-to-day operational surface. No breaking changes from 2.0.0.

### Added

- `carto-import-export-data` — imports, tilesets, exports.
- `carto-create-analytics-workflow` — workflow CRUD, scheduling per engine, dev→prod promotion.
- `carto-find-spatial-data` — Data Observatory discovery and subscriptions.
- `carto-manage-platform` — org stats, users/invitations, admin bulk ops, activity event reference.
- `docs/deferred-skills.md` — status of `carto-create-builder-maps` and `carto-build-app` (owned by another PM).
- 18 new reference files across the 4 skills.

### Catalog

Platform-tier dependencies declared and validated:

- `carto-import-export-data` → `carto-basics`, `carto-connect-datawarehouse`, `carto-explore-datawarehouse`.
- `carto-create-analytics-workflow` → `carto-basics`, `carto-connect-datawarehouse`, `carto-query-datawarehouse`.
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

- 6 platform skills (Phase 2): `carto-import-export-data`, `carto-create-builder-maps`, `carto-build-app`, `carto-create-analytics-workflow`, `carto-find-spatial-data`, `carto-manage-platform`.
- 3 use-case skills (Phase 3): `carto-build-spatial-dashboard`, `carto-build-customer-facing-map`, `carto-migrate-to-carto`.
- Codex plugin and Gemini extension distribution.
- `custom_user_agent` watermarking.
