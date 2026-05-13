# Changelog

## 2.5.0 — initial public release

First public release of the CARTO Agent Skills catalog.

22 skills across three layered tiers, distributed to Claude Code, Skills CLI, Codex, and Gemini CLI from a single source-of-truth catalog (`skills/catalog.json`):

**Utility tier** (4 skills) — `carto-basics`, `carto-connect-datawarehouse`, `carto-query-datawarehouse`, `carto-explore-datawarehouse`.

**Platform tier** (8 skills) — `carto-import-export-data`, `carto-create-workflow`, `carto-find-spatial-data`, `carto-manage-platform`, `carto-create-builder-maps`, `carto-render-inline-map`, `carto-preview-builder-map`, `carto-develop-app`.

**Use-case patterns** (10 skills) — `carto-hotspot-analysis`, `carto-spatial-autocorrelation`, `carto-gwr`, `carto-spatial-enrichment`, `carto-trade-area-analysis`, `carto-site-selection`, `carto-territory-planning`, `carto-routing-od-analysis`, `carto-geocoding`, `carto-composite-scoring`.

For the design rationale behind the three-tier layering, see [ARCHITECTURE.md](ARCHITECTURE.md). For broader CARTO-for-agents documentation, see [docs.carto.com/carto-for-agents/agent-skills](https://docs.carto.com/carto-for-agents/agent-skills).
