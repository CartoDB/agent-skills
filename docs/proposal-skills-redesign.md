# CARTO Skills System — Concept

**Status:** Proposal — team aligned
**Date:** 2026-04-28

A proposal to redesign this repo into a Claude Code / Codex / Gemini skills catalog for CARTO, modeled on MotherDuck's [agent-skills repo](https://github.com/motherduckdb/agent-skills). The goal is a single, opinionated, multi-harness skill library that wraps the CARTO CLI (and complementary MCP services) so AI agents ship correct, idiomatic CARTO work without re-discovering the platform every session.

---

## 1. Why this, why now

CARTO already exposes most platform capabilities through the CLI (`carto-cli`, v0.6.0) and a growing set of MCP services. Today, agents using those surfaces have to:

- Re-derive auth, profile, and connection conventions every session
- Pick a warehouse dialect and guess at spatial SQL idioms
- Discover product entities (maps, named sources, tilesets, workflows, DO) from scratch
- Compose multi-step workflows (e.g. "load → tile → build map → deploy app") without guidance

A skills catalog encodes the right defaults and orchestration once, then ships across Claude Code, Codex, and Gemini from a single source. MotherDuck has demonstrated the pattern works: 18 skills, 3-tier layering, multi-harness distribution, validated snippets — all from one repo.

## 2. What MotherDuck did (reference)

Three architectural decisions worth copying:

**Three-tier layering, validation-enforced.**
- *Utility* skills depend on nothing (`connect`, `query`, `explore`, `duckdb-sql`, `rest-api`)
- *Workflow* skills depend only on utilities (`load-data`, `model-data`, `share-data`, `create-dive`, `ducklake`, `security-governance`, `pricing-roi`)
- *Use-case* skills orchestrate workflows + utilities (`build-cfa-app`, `build-dashboard`, `build-data-pipeline`, `migrate`, `enable-self-serve`, `partner-delivery`)

A validation script (`scripts/validate_skills.py`) enforces dependencies; use-case skills declare orchestration in their SKILL.md (e.g. *"orchestrates motherduck-explore, motherduck-query, and motherduck-create-dive"*).

**Minimal, consistent skill anatomy.**
```
skills/<skill-name>/
  SKILL.md                 # frontmatter + main guidance (kept small)
  references/*.md          # deep-dive content, loaded only when needed
  artifacts/*.{py,ts}      # optional dual-language runnable examples
```
Frontmatter is portable across harnesses:
```yaml
---
name: skill-id
description: One sentence saying when to use this skill.
license: MIT
---
```

**Multi-harness distribution from one source.**
- Skills CLI: `npx skills add motherduckdb/agent-skills`
- Claude plugin: `plugins/motherduck-skills-claude/.claude-plugin/plugin.json`
- Codex plugin: `plugins/motherduck-skills/.codex-plugin/plugin.json`
- Gemini extension: `gemini-extension.json` + `commands/motherduck/*.toml`

Sync scripts keep manifests aligned. A single change ships to all three harnesses.

**Other conventions worth copying:**
- Snippet validation extracts every fenced code block from `.md` files and runs Python AST / TS syntax / DuckDB SQL execution against them — keeps docs honest
- `custom_user_agent` watermark via env vars `MOTHERDUCK_AGENT_HARNESS` / `MOTHERDUCK_AGENT_LLM` — measurable agent-driven usage in product analytics
- Layer metadata in `skills/catalog.json`, not frontmatter — separates content from structure

## 3. Proposed CARTO catalog (13 skills)

### Naming convention

`carto-<verb>-<object>`. The verb is imperative; the object names the concrete thing being acted on (`datawarehouse`, `builder-maps`, `spatial-data`). Names route on user intent, not CARTO product jargon — an agent thinking "I need demographics" should match `carto-find-spatial-data`, not "data observatory."

### Utility (4) — depend on nothing

| Skill | Description |
|---|---|
| `carto-basics` | Start here for first-time CARTO CLI use: install, authenticate, switch profiles, understand JSON output and async job patterns. |
| `carto-connect-datawarehouse` | Choose and configure the data warehouse engine connection (BigQuery, Snowflake, Redshift, Postgres, Databricks). |
| `carto-query-datawarehouse` | Write spatial SQL against the connected warehouse engine, with dialect-specific guidance and performance defaults. |
| `carto-explore-datawarehouse` | Discover what's in the connected warehouse: schemas, tables, columns, named sources. |

### Workflow (6) — depend on utilities

| Skill | Description |
|---|---|
| `carto-import-export-data` | Import files or external tables into the warehouse, export results back out, and prepare tilesets. |
| `carto-create-builder-maps` | Author maps in CARTO Builder: layers, basemaps, styling, sharing, and AI map agents. |
| `carto-build-app` | Build apps that consume CARTO: APIs, named sources, scoped tokens, SDKs, embedding, hosted deployment. |
| `carto-create-analytics-workflow` | Build, schedule, and operate analytics DAGs in the CARTO Workflows product. |
| `carto-find-spatial-data` | Discover external spatial datasets (Data Observatory and partners) and subscribe them into your warehouse. |
| `carto-manage-platform` | Administer the CARTO org: users, roles, quotas, activity logs, bulk resource ops. |

### Use-case (3) — orchestrate utilities + workflows

| Skill | Description |
|---|---|
| `carto-build-spatial-dashboard` | Build an internal spatial analytics dashboard end-to-end, from connection through map. |
| `carto-build-customer-facing-map` | Ship an embedded or public map for external users with token scoping and tenant isolation. |
| `carto-migrate-to-carto` | Plan a migration from a legacy GIS or analytics platform onto CARTO. |

### Why these boundaries

- **Internal vs external data** — `carto-explore-datawarehouse` covers what *you* have connected; `carto-find-spatial-data` covers external datasets you might subscribe. Different mental models, different commands.
- **Builder maps vs apps** — `carto-create-builder-maps` is the no-code map-authoring product; `carto-build-app` is for developers integrating CARTO into their own apps. AI map agents live in `create-builder-maps` because in CARTO, agents *are* maps.
- **Admin separation** — `carto-manage-platform` carves off org-level operations (users, quotas, audit) so the builder/dev skills stay focused on creation.

## 4. Repo layout

Mirror MotherDuck's structure:

```
carto-agents/
  skills/
    carto-basics/
      SKILL.md
      references/
    carto-connect-datawarehouse/
      ...
    (one directory per skill)
    catalog.json                  # layer metadata
  plugins/
    carto-skills-claude/
      .claude-plugin/plugin.json
    carto-skills/                 # Codex
      .codex-plugin/plugin.json
  commands/carto/*.toml           # Gemini extension
  gemini-extension.json
  .claude-plugin/marketplace.json
  scripts/
    validate_skills.py
    _lib/
  tests/
    validate_snippets.py
    _lib/
  docs/
    skill-authoring.md
    install-matrix.md
  CLAUDE.md
  AGENTS.md
  GEMINI.md
  ARCHITECTURE.md
  README.md
```

## 5. Infrastructure decisions

| Decision | Recommendation | Rationale |
|---|---|---|
| Source layout | One repo, multi-harness packaging | Same as MD; single source of truth |
| Distribution | Claude plugin + Codex plugin + Gemini extension + Skills CLI | Match where users actually invoke agents |
| Snippet validation | Adapt MD's harness; extend for CARTO SQL | Validate Python, TS, JSON; SQL validation needs a strategy (see open questions) |
| Watermarking | `custom_user_agent` via `CARTO_AGENT_HARNESS` / `CARTO_AGENT_LLM` | Product analytics on agent-driven usage |
| MCP vs CLI authority | Prefer MCP for read/discovery, CLI for write/admin | Skills shell out to CLI for state changes; MCP gives faster live introspection |
| Layer enforcement | Port MD's `validate_skills.py` | Keeps the layering honest as the catalog grows |
| Naming | `carto-<verb>-<object>` | Routes on user intent, not product jargon |

## 6. Open questions

1. **Spatial SQL scope.** One `carto-query-datawarehouse` skill with sub-references per dialect, or split per-warehouse (BQ GIS / Snowflake / Postgres+PostGIS)? Lean: one skill, references per dialect. Revisit if the SKILL.md grows past ~5KB.
2. **CLI vs MCP authority.** When both are available, which does a skill prefer? Lean: MCP for read, CLI for write — but needs a documented rule.
3. **SQL snippet validation.** MD validates DuckDB SQL by executing in-memory. CARTO can't do that without a live connection. Options: (a) skip SQL validation, (b) maintain a single canonical sandbox warehouse for CI, (c) syntactic-only validation per dialect. Lean: (c) for now, revisit.
4. **AI map agents.** Bundled into `carto-create-builder-maps`, or its own workflow skill? Bundled today, but if map agents become a major investment, they may deserve a dedicated skill.
5. **Customer-facing map vs app.** Use-case skill is named `carto-build-customer-facing-map`, but most external maps ship as full apps. Should it be `carto-build-customer-facing-app`?
6. **Hyphenation.** `datawarehouse` (one word) vs `data-warehouse` (hyphenated). Pick one and apply consistently.
7. **`carto-basics` scope.** Is this CLI-only, or does it cover platform basics too? If platform basics, the description needs tightening so it doesn't always-load.

## 7. Salvage from existing repo (`CartoDB/carto-agent-skills`)

The existing repo is a 2-skill Claude plugin (last commit 2026-02-10, dormant since). Worth porting:

| Existing asset | Target skill | Value |
|---|---|---|
| `carto-cli/SKILL.md` auth section | `carto-basics` | High — already covers `--no-launch-browser`, profiles, `--json` flag, tenant URL gotcha |
| `carto-cli/maps.md` (16KB) | `carto-create-builder-maps/references/MAP_JSON_REFERENCE.md` | **Highest** — datasets/layers diagram, creation checklist, common mistakes |
| `carto-cli/commands.md` (15KB) | Split into `references/` per skill | Medium — needs reorg by topic |
| `carto-activity/SKILL.md` schema + ~20 SQL examples | `carto-manage-platform/references/` | High — clean port |
| Quick-reference command tables | Distributed by topic across new skills | Medium |
| `README.md` and `marketplace.json` | New repo root | Low — needs full rewrite for multi-harness |

**Drop deliberately:**
- `NODE_TLS_REJECT_UNAUTHORIZED=0` workarounds (claude.ai sandbox-specific, fragile)
- `/mnt/skills/user/carto-cli/carto.js` bundled CLI references (assume `npm install -g @carto/carto-cli`)
- Domain-whitelist instructions repeated per skill (centralize in `carto-basics`)
- Monolithic `carto-cli` skill (splitting is the whole point of the rewrite)

**Net assessment:** existing skills cover ~15% of the new catalog (auth + activity). This is a rewrite-with-salvage, not a refactor. The 11 remaining skills are greenfield.

## 8. Phased rollout

**Phase 1 — Foundation (2 weeks)**
- Stand up repo, port MD's scripts/validate harness
- Ship 4 utility skills (`carto-basics`, `carto-connect-datawarehouse`, `carto-query-datawarehouse`, `carto-explore-datawarehouse`)
- Ship Claude plugin + Skills CLI distribution

**Phase 2 — Workflow surface (3 weeks)**
- Ship 6 workflow skills
- Add Codex + Gemini distribution
- Wire up `custom_user_agent` watermarking
- Internal dogfooding with CARTO solutions team

**Phase 3 — Use-cases + polish (2 weeks)**
- Ship 3 use-case skills
- Snippet validation in CI
- Public release: README, install docs, demo videos

**Phase 4 — Iterate**
- Add skills based on observed agent failures
- Split any workflow skill that grows past ~5KB SKILL.md
- Backfill use-cases as patterns emerge from real usage

## 9. What success looks like

Six months after launch:
- Agents using CARTO ship correct work without manual schema discovery 80%+ of the time
- Public skill catalog distributed across all three major agent harnesses
- Watermarked usage telemetry shows measurable agent-driven CARTO API traffic
- Solutions team's customer-facing map work shortens by ~30% via `carto-build-customer-facing-map`
- Community contribution path documented; first external skill PR merged

---

## Appendix A — Mapping CLI commands to skills

| CLI command | Primary skill | Secondary |
|---|---|---|
| `carto auth *` | `carto-basics` | |
| `carto credentials *` | `carto-build-app` | `carto-manage-platform` |
| `carto connections *` | `carto-connect-datawarehouse` | `carto-explore-datawarehouse` (browse/describe) |
| `carto sql query/job` | `carto-query-datawarehouse` | |
| `carto import/export/transfer` | `carto-import-export-data` | |
| `carto maps *` | `carto-create-builder-maps` | |
| `carto workflows *` | `carto-create-analytics-workflow` | |
| `carto named-sources *` | `carto-build-app` | |
| `carto do *` | `carto-find-spatial-data` | |
| `carto app *` | `carto-build-app` | |
| `carto aifeature/aiproxy` | `carto-create-builder-maps` (agents) / `carto-build-app` (proxy) | |
| `carto org/users/activity` | `carto-manage-platform` | |
| `carto admin *` | `carto-manage-platform` | |

## Appendix B — Reference

- MotherDuck skills repo (reference architecture): https://github.com/motherduckdb/agent-skills
- CARTO CLI: `@carto/carto-cli` on npm
- Existing CARTO skills repo (this repo, pre-redesign): https://github.com/CartoDB/carto-agent-skills
- MD skill anatomy reference: `docs/skill-authoring.md` in motherduckdb/agent-skills
- MD validation harness: `scripts/validate_skills.py` in motherduckdb/agent-skills
