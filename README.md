# CARTO Agent Skills

A multi-harness skills catalog for the CARTO Geospatial Cloud, modeled on the [MotherDuck agent-skills](https://github.com/motherduckdb/agent-skills) pattern. Wraps the CARTO CLI (and complementary surfaces) so AI agents ship correct, idiomatic CARTO work without re-discovering the platform every session.

## Status: Phase 2a (utility + platform tiers)

This release ships **8 skills** distributed via Claude Code and the Skills CLI. Two further platform skills (`carto-create-builder-maps`, `carto-build-app`) are owned by another PM and intentionally deferred — see [`docs/deferred-skills.md`](docs/deferred-skills.md). Codex/Gemini distribution and watermarking land in subsequent phases — see [`docs/proposal-skills-redesign.md`](docs/proposal-skills-redesign.md) for the full roadmap.

### Utility tier

| Skill | Purpose |
|---|---|
| [`carto-basics`](skills/carto-basics) | First-time setup: install, auth, profiles, global flags. |
| [`carto-connect-datawarehouse`](skills/carto-connect-datawarehouse) | Connect BigQuery / Snowflake / Redshift / Postgres / Databricks. |
| [`carto-query-datawarehouse`](skills/carto-query-datawarehouse) | Spatial SQL with dialect-specific guidance and execution model. |
| [`carto-explore-datawarehouse`](skills/carto-explore-datawarehouse) | Discover schemas, tables, columns, named sources. |

### Platform tier

| Skill | Purpose |
|---|---|
| [`carto-import-export-data`](skills/carto-import-export-data) | Imports, tilesets, and warehouse-native exports. |
| [`carto-create-analytics-workflow`](skills/carto-create-analytics-workflow) | Workflow CRUD, scheduling, dev → prod promotion. |
| [`carto-find-spatial-data`](skills/carto-find-spatial-data) | Discover and subscribe to Data Observatory datasets. |
| [`carto-manage-platform`](skills/carto-manage-platform) | Org admin: users, quotas, activity audit, bulk ops. |

## Installing in Claude Code

```bash
# 1. Add the marketplace (one-time)
/plugin marketplace add CartoDB/carto-agent-skills

# 2. Install the skills bundle
/plugin install carto-skills@carto-agent-skills
```

All eight skills are registered as one bundle (`carto-skills`).

> **⚠ Migrating from v1.x?** The old `carto-cli@carto-agent-skills` and `carto-activity@carto-agent-skills` plugin IDs are **retired**. Re-install as `carto-skills@carto-agent-skills`. See [CHANGELOG.md](CHANGELOG.md).

## Installing via the Skills CLI

```bash
npx skills add CartoDB/carto-agent-skills
```

The Skills CLI reads [`skills/catalog.json`](skills/catalog.json) and registers each skill independently — useful when you want a subset.

## CARTO CLI prerequisite

All skills assume the [CARTO CLI](https://docs.carto.com/carto-user-manual/carto-cli) (`@carto/carto-cli`) is installed:

```bash
npm install -g @carto/carto-cli
carto --version
```

The `carto-basics` skill walks the user through this on first invocation.

## Repo layout

```
skills/                    # one directory per skill; catalog.json registers them
plugins/                   # harness-specific manifests (Claude only — Codex/Gemini in Phase 2b)
.claude-plugin/            # Claude marketplace registration
scripts/                   # validate_skills.py, sync_manifests.py
tests/                     # validate_snippets.py
docs/                      # design + authoring docs
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for the three-tier layering rationale.

## Contributing

1. Read [`docs/skill-authoring.md`](docs/skill-authoring.md).
2. Run `make validate` locally before pushing — CI runs the same checks.
3. Open a PR; review focuses on whether the skill description is targeted enough that agents route correctly to it.

## Resources

- [CARTO CLI documentation](https://docs.carto.com/carto-user-manual/carto-cli)
- [CARTO Platform documentation](https://docs.carto.com/)
- [Redesign proposal](docs/proposal-skills-redesign.md) — design record for the multi-harness restructure
- [MotherDuck agent-skills](https://github.com/motherduckdb/agent-skills) — reference architecture
