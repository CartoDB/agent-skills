# Notes for Gemini CLI

This file is loaded as context whenever the `carto-skills` extension is active in Gemini CLI (the `contextFileName` field in [`gemini-extension.json`](gemini-extension.json) points here).

## What's installed

22 skills in three layered tiers — see [`skills/catalog.json`](skills/catalog.json) for the source of truth.

**Utility tier** — foundational, no dependencies:

- `carto-basics` — install, auth, profiles, global flags.
- `carto-connect-datawarehouse` — BigQuery / Snowflake / Redshift / Postgres / Databricks connections.
- `carto-query-datawarehouse` — spatial SQL, dialect-specific guidance, execution model.
- `carto-explore-datawarehouse` — schema discovery, named sources.

**Platform tier** — wraps a CARTO product surface:

- `carto-import-export-data` — imports, tilesets, exports.
- `carto-create-workflow` — Workflow CRUD, scheduling, cross-profile copy.
- `carto-find-spatial-data` — Data Observatory discovery and subscription.
- `carto-manage-platform` — org admin, users, quotas, activity audit.
- `carto-create-builder-maps` — author Builder maps (layers, basemaps, styling, AI agents, sharing).
- `carto-render-inline-map` — ad-hoc deck.gl map preview inline in chat (MCP `view_map`).
- `carto-preview-builder-map` — preview an existing saved Builder map inline (MCP `load_builder_map`).
- `carto-develop-app` — generate from-scratch CARTO + deck.gl apps with the right auth strategy.

**Use-case patterns** — compose the platform skills above:

- `carto-hotspot-analysis` — Getis-Ord Gi\*, spacetime hotspots.
- `carto-spatial-autocorrelation` — Moran's I, LISA, HH/HL/LH/LL classification.
- `carto-gwr` — Geographically Weighted Regression.
- `carto-spatial-enrichment` — demographics and spatial-features enrichment.
- `carto-trade-area-analysis` — catchments, isochrones, billboard scoring.
- `carto-site-selection` — site selection, cannibalization, twin-area discovery.
- `carto-territory-planning` — territory balancing and location allocation.
- `carto-routing-od-analysis` — routing, isolines, OD matrices.
- `carto-geocoding` — address-to-coordinate geocoding.
- `carto-composite-scoring` — composite indices, supervised/unsupervised scoring.

## Per-skill commands

Each skill has a Gemini command at `commands/carto/<skill-name>.toml`. Invoke via `/carto:<skill-name>`:

```
/carto:carto-basics                # install/auth questions
/carto:carto-query-datawarehouse   # spatial SQL help
/carto:carto-create-workflow       # workflow authoring
/carto:carto-hotspot-analysis      # hotspot pattern
```

The command reads the skill's `SKILL.md` first, then opens `references/*.md` for depth as needed. Each command stays within its skill's stated scope and surfaces a redirect when the question fits a different skill better.

## Reading order for a fresh CARTO session

1. `/carto:carto-basics` — confirm install + auth.
2. `/carto:carto-explore-datawarehouse` — list connections, see what's there.
3. `/carto:carto-connect-datawarehouse` — only if a fresh warehouse needs wiring up.
4. `/carto:carto-query-datawarehouse` — SQL once you know the data.

Platform and use-case skills layer on top once the utility-tier flow is fluent.

## CLI prerequisite

All skills assume the CARTO CLI is installed:

```bash
npm install -g @carto/carto-cli
carto --version
```

The `carto-basics` skill walks the user through this on first invocation.

## Always-on

- For machine-parseable CLI output, always pass `--json`.
- Destructive commands require typing `delete` to confirm; pass `--yes` (or `--json`) for non-interactive use.
- Skills are layered: utility skills don't depend on each other; platform skills depend only on utility skills; use-case skills may depend on utility and platform skills.

For the full architectural explanation see [`ARCHITECTURE.md`](ARCHITECTURE.md). For broader CARTO-for-agents documentation see [docs.carto.com/carto-for-agents/agent-skills](https://docs.carto.com/carto-for-agents/agent-skills).
