# CARTO Agent Skills

A catalog of **agent skills** that teach AI coding tools to drive [CARTO](https://carto.com/) — the cloud-native location intelligence platform — correctly: right CLI flags, right SQL dialect, right job-handling patterns, right import shape.

Each skill is a short playbook the agent loads on demand when a user's request matches its domain, so the agent produces idiomatic, working CARTO output the first time.

Works with **Claude Code**, **Skills CLI**, **Codex**, and **Gemini CLI**. All four harnesses load the same skills from a single source of truth: [`skills/catalog.json`](skills/catalog.json).

## Documentation

For installation, authoring, and usage details, see the official documentation:

**[docs.carto.com/carto-for-agents/agent-skills](https://docs.carto.com/carto-for-agents/agent-skills)**

## Skills

Skills are organized in three tiers — pick what's relevant to your work; an agent will route to the right skill automatically based on user intent. See [ARCHITECTURE.md](ARCHITECTURE.md) for the rationale behind the layering.

### Utility — foundational CARTO operations

| Skill | Purpose |
|---|---|
| [`carto-basics`](skills/carto-basics) | First-time setup: install, auth, profiles, global flags. |
| [`carto-connect-datawarehouse`](skills/carto-connect-datawarehouse) | Connect BigQuery / Snowflake / Redshift / Postgres / Databricks / Oracle. |
| [`carto-query-datawarehouse`](skills/carto-query-datawarehouse) | Spatial SQL with dialect-specific guidance. |
| [`carto-explore-datawarehouse`](skills/carto-explore-datawarehouse) | Discover schemas, tables, columns, named sources. |

### Platform — CARTO product surfaces

| Skill | Purpose |
|---|---|
| [`carto-import-export-data`](skills/carto-import-export-data) | Imports, tilesets, and warehouse-native exports. |
| [`carto-create-workflow`](skills/carto-create-workflow) | Build, schedule, operate, and cross-profile-copy analytics DAGs in CARTO Workflows. |
| [`carto-find-spatial-data`](skills/carto-find-spatial-data) | Discover and subscribe to Data Observatory datasets. |
| [`carto-manage-platform`](skills/carto-manage-platform) | Org admin: users, quotas, audit, bulk ops. |
| [`carto-create-builder-maps`](skills/carto-create-builder-maps) | Author maps in CARTO Builder (layers, basemaps, styling, AI Agents) and copy them across orgs / profiles. |
| [`carto-render-inline-map`](skills/carto-render-inline-map) | Render an ad-hoc deck.gl map inline in the chat via the CARTO MCP server. |
| [`carto-preview-builder-map`](skills/carto-preview-builder-map) | Preview an existing saved Builder map inline in the chat. |
| [`carto-develop-app`](skills/carto-develop-app) | Generate from-scratch CARTO + deck.gl apps in TypeScript / JavaScript with auth, layers, widgets, and filters. |

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
| [`carto-arcgis-migration`](skills/carto-arcgis-migration) | End-to-end ArcGIS Portal / AGOL → CARTO migration (discover, migrate data, migrate maps). |

## Support

For bugs, feature requests, and CARTO platform questions, contact [support@carto.com](mailto:support@carto.com). General product documentation is at [docs.carto.com](https://docs.carto.com/).

## License

MIT — see [LICENSE](LICENSE).
