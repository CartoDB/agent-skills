# CARTO Agent Skills

AI agents that know how to use [CARTO](https://carto.com/) — the cloud-native location intelligence platform — correctly. This repository ships a catalog of **agent skills** that teach AI coding tools to drive the CARTO CLI and platform fluently, without re-discovering the API every session.

Works with **[Claude Code](#claude-code)**, **[Skills CLI](#skills-cli)**, **[Codex](#codex)**, and **[Gemini CLI](#gemini-cli)**.

## Why agent skills?

Generic LLMs know *about* CARTO but make small mistakes when actually driving it: wrong CLI flags, outdated SQL dialects, missing async-job handling, the wrong import shape for a tileset. Each skill in this repo is a short playbook the agent loads on demand when a user's request matches the skill's domain — so the agent ships idiomatic, working CARTO output the first time.

## Prerequisites

- A **[CARTO account](https://carto.com/signup)** with access to a workspace.
- **Node.js 18+** and the **[CARTO CLI](https://docs.carto.com/carto-user-manual/carto-cli)**:
  ```bash
  npm install -g @carto/carto-cli
  carto --version
  ```
- One of the supported AI agent harnesses (Claude Code, Skills CLI, Codex, or Gemini CLI).

The `carto-basics` skill walks first-time users through CLI install, login, and profile setup.

## Installation

### Claude Code

```bash
# 1. Add the marketplace (one-time)
/plugin marketplace add CartoDB/carto-agent-skills

# 2. Install the skills bundle
/plugin install carto-skills@carto-agent-skills
```

All skills are registered as a single bundle (`carto-skills`).

### Skills CLI

```bash
npx skills add CartoDB/carto-agent-skills
```

The Skills CLI reads [`skills/catalog.json`](skills/catalog.json) and registers each skill independently — useful when you want a subset.

### Codex

The Codex plugin manifest is [`.codex-plugin/plugin.json`](.codex-plugin/plugin.json) at the repo root. Install it with your Codex client's extension command (refer to Codex docs for the verb on your version).

### Gemini CLI

The Gemini extension manifest is [`gemini-extension.json`](gemini-extension.json), with one command per skill under [`commands/carto/`](commands/carto/). After install, invoke a skill via `/carto:<skill-name>` — for example `/carto:carto-basics`.

For the full per-harness picture, see [`docs/install-matrix.md`](docs/install-matrix.md).

## What's included

Skills are organized in three tiers. Pick what's relevant to your work; an agent will route to the right skill automatically based on user intent.

### Utility — basic CARTO operations

| Skill | Purpose |
|---|---|
| [`carto-basics`](skills/carto-basics) | First-time setup: install, auth, profiles, global flags. |
| [`carto-connect-datawarehouse`](skills/carto-connect-datawarehouse) | Connect BigQuery / Snowflake / Redshift / Postgres / Databricks / Oracle. |
| [`carto-explore-datawarehouse`](skills/carto-explore-datawarehouse) | Discover schemas, tables, columns, named sources. |
| [`carto-query-datawarehouse`](skills/carto-query-datawarehouse) | Run SQL: `sql query` vs `sql job`, caching — and dispatch to the per-engine spatial-SQL skill below. |

#### Per-engine spatial SQL (Analytics Toolbox)

Engine-specific skills that teach the agent CARTO's Analytics Toolbox per warehouse — AT modules shipped, type-system quirks, and spatial-index patterns. The dispatcher above routes here based on the connection's provider.

| Skill | Purpose |
|---|---|
| [`carto-spatial-sql-bigquery`](skills/carto-spatial-sql-bigquery) | AT flagship — every module ships. GEOGRAPHY-only type system, STRING H3, INT64 quadbin. |
| [`carto-spatial-sql-snowflake`](skills/carto-spatial-sql-snowflake) | Most AT modules. GEOGRAPHY vs GEOMETRY split. Native App + manual install. |
| [`carto-spatial-sql-databricks`](skills/carto-spatial-sql-databricks) | Narrow AT (enrichment + LDS + quadbin + statistics). H3 / ST_* come from Databricks-native, not CARTO. Beta. |
| [`carto-spatial-sql-postgres`](skills/carto-spatial-sql-postgres) | Thin AT (h3, quadbin, tiler). PostGIS for everything else. `plv8` required for H3. |
| [`carto-spatial-sql-redshift`](skills/carto-spatial-sql-redshift) | AT minus standalone H3 — use quadbin. Sort-key / dist-style for spatial joins. |
| [`carto-spatial-sql-oracle`](skills/carto-spatial-sql-oracle) | **No AT today.** Connection target only. Steers to native `SDO_GEOMETRY` / `SDO_*`. |

### Platform — CARTO product surfaces

| Skill | Purpose |
|---|---|
| [`carto-import-export-data`](skills/carto-import-export-data) | Imports, tilesets, and warehouse-native exports. |
| [`carto-create-workflow`](skills/carto-create-workflow) | Build, schedule, and operate analytics DAGs in CARTO Workflows. |
| [`carto-copy-workflows`](skills/carto-copy-workflows) | Cross-org / cross-profile workflow copy. |
| [`carto-find-spatial-data`](skills/carto-find-spatial-data) | Discover and subscribe to Data Observatory datasets. |
| [`carto-manage-platform`](skills/carto-manage-platform) | Org admin: users, quotas, audit, bulk ops. |
| [`carto-create-builder-maps`](skills/carto-create-builder-maps) | Author maps in CARTO Builder: layers, basemaps, styling, AI Agents. |
| [`carto-copy-maps`](skills/carto-copy-maps) | Cross-org / cross-profile map copy and validation. |

### Use-case patterns — common spatial analyses

Recipe skills that compose the platform skills above. Each carries trigger keywords so the agent routes on user intent (e.g. "find hotspots in this dataset" → `carto-hotspot-analysis`).

| Skill | Purpose |
|---|---|
| [`carto-hotspot-analysis`](skills/carto-hotspot-analysis) | Getis-Ord Gi\* hotspots and spacetime hotspots. |
| [`carto-spatial-autocorrelation`](skills/carto-spatial-autocorrelation) | Moran's I, LISA, HH/HL/LH/LL classification. |
| [`carto-gwr`](skills/carto-gwr) | Geographically Weighted Regression. |
| [`carto-spatial-enrichment`](skills/carto-spatial-enrichment) | Demographics and spatial-features enrichment. |
| [`carto-trade-area-analysis`](skills/carto-trade-area-analysis) | Catchment areas, isochrones, billboard scoring. |
| [`carto-site-selection`](skills/carto-site-selection) | Site selection, cannibalization, twin-area discovery. |
| [`carto-territory-planning`](skills/carto-territory-planning) | Territory balancing and location allocation. |
| [`carto-routing-od-analysis`](skills/carto-routing-od-analysis) | Routing, isolines, OD matrices. |
| [`carto-geocoding`](skills/carto-geocoding) | Address-to-coordinate geocoding. |
| [`carto-composite-scoring`](skills/carto-composite-scoring) | Composite indices, supervised/unsupervised scoring. |

See [ARCHITECTURE.md](ARCHITECTURE.md) for the rationale behind the three-tier layering.

## How it works

Skills run **locally** inside your AI agent. When a skill is triggered, the agent reads the skill's instructions and uses the CARTO CLI on your machine to act on your behalf — authenticating with your local CARTO profile and operating against the warehouses you've already connected. No data leaves your environment via this repository; everything flows through the CARTO CLI you control.

## Repository layout

```
skills/                    # one directory per skill; catalog.json registers them
.claude-plugin/            # Claude marketplace registration
plugins/                   # Claude plugin manifest
.codex-plugin/             # Codex plugin manifest
gemini-extension.json      # Gemini extension manifest
commands/carto/            # one TOML per skill (Gemini)
scripts/                   # validate_skills.py, sync_manifests.py
docs/                      # authoring + install matrix
```

All four harness manifests are generated from `skills/catalog.json` by `scripts/sync_manifests.py`.

## Support

For bugs, feature requests, and CARTO platform questions, contact [support@carto.com](mailto:support@carto.com). General product documentation is at [docs.carto.com](https://docs.carto.com/).

## License

MIT — see [LICENSE](LICENSE).
