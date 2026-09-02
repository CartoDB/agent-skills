# Install matrix

Which skills ship via which harness.

| Skill | Tier | Claude Code | Skills CLI | Codex | Gemini |
|---|---|---|---|---|---|
| `carto-arcgis-migration` | use-case | ✅ | ✅ | ✅ | ✅ |
| `carto-basics` | utility | ✅ | ✅ | ✅ | ✅ |
| `carto-connect-datawarehouse` | utility | ✅ | ✅ | ✅ | ✅ |
| `carto-query-datawarehouse` | utility | ✅ | ✅ | ✅ | ✅ |
| `carto-explore-datawarehouse` | utility | ✅ | ✅ | ✅ | ✅ |
| `carto-import-export-data` | platform | ✅ | ✅ | ✅ | ✅ |
| `carto-create-workflow` | platform | ✅ | ✅ | ✅ | ✅ |
| `carto-find-spatial-data` | platform | ✅ | ✅ | ✅ | ✅ |
| `carto-manage-platform` | platform | ✅ | ✅ | ✅ | ✅ |
| `carto-create-builder-maps` | platform | ✅ | ✅ | ✅ | ✅ |
| `carto-render-inline-map` | platform | ✅ | ✅ | ✅ | ✅ |
| `carto-preview-builder-map` | platform | ✅ | ✅ | ✅ | ✅ |
| `carto-develop-app` | platform | ✅ | ✅ | ✅ | ✅ |
| `carto-hotspot-analysis` | use-case | ✅ | ✅ | ✅ | ✅ |
| `carto-spatial-autocorrelation` | use-case | ✅ | ✅ | ✅ | ✅ |
| `carto-gwr` | use-case | ✅ | ✅ | ✅ | ✅ |
| `carto-spatial-enrichment` | use-case | ✅ | ✅ | ✅ | ✅ |
| `carto-trade-area-analysis` | use-case | ✅ | ✅ | ✅ | ✅ |
| `carto-site-selection` | use-case | ✅ | ✅ | ✅ | ✅ |
| `carto-territory-planning` | use-case | ✅ | ✅ | ✅ | ✅ |
| `carto-routing-od-analysis` | use-case | ✅ | ✅ | ✅ | ✅ |
| `carto-geocoding` | use-case | ✅ | ✅ | ✅ | ✅ |
| `carto-composite-scoring` | use-case | ✅ | ✅ | ✅ | ✅ |

All 23 skills are available identically across every harness. See [`skills/catalog.json`](../skills/catalog.json) for the source of truth.

## Per-harness install

### Claude Code

```bash
/plugin marketplace add CartoDB/carto-agent-skills
/plugin install carto-skills@carto-agent-skills
```

All 23 skills (4 utility + 8 platform + 11 use-case patterns) ship as one bundle. Manifest: [`.claude-plugin/marketplace.json`](../.claude-plugin/marketplace.json) registers the plugin; the plugin manifest at [`plugins/carto-skills-claude/.claude-plugin/plugin.json`](../plugins/carto-skills-claude/.claude-plugin/plugin.json) enumerates the skills.

### Skills CLI

```bash
npx skills add CartoDB/carto-agent-skills
```

Reads [`skills/catalog.json`](../skills/catalog.json) and registers each skill independently.

### Codex

The Codex plugin manifest lives at the repo root: [`.codex-plugin/plugin.json`](../.codex-plugin/plugin.json). It points at `./skills/` (the same source-of-truth directory) and exposes display metadata via the `interface` block — `displayName`, `defaultPrompt`, `capabilities`, etc.

Install path depends on the Codex client; refer to Codex docs for the per-client `install`/`add` command. The manifest is self-contained.

### Gemini CLI

Two pieces:

- [`gemini-extension.json`](../gemini-extension.json) — extension manifest, points at [`GEMINI.md`](../GEMINI.md) for context.
- [`commands/carto/<skill>.toml`](../commands/carto/) — one command per skill, invoked as `/carto:<skill-name>`.

Add the extension via Gemini CLI's extension command (consult Gemini docs for the install verb on the version installed locally).

### Web upload (Claude.ai, Gemini Enterprise, Claude Skills API)

Some harnesses have no git or marketplace integration and only take a skill through an upload form: Claude.ai (**Customize > Skills > Upload a skill**), Gemini Enterprise (**Upload skill**, Markdown or ZIP), and the Claude Skills API. Each wants **one zip per skill with `SKILL.md` at the archive root**.

Every release publishes those zips as GitHub Release assets. The `latest` URL always points at the newest release, so these links do not change between versions:

```
https://github.com/CartoDB/agent-skills/releases/latest/download/<skill-name>.zip
```

The zips are **not** committed to the repo. `master` is the release: every merge that changes a skill triggers [`.github/workflows/release.yml`](../.github/workflows/release.yml), which runs `make package` ([`scripts/package_skills.py`](../scripts/package_skills.py)) and publishes a release tagged by date (`vYYYY.MM.DD`). No manual tagging or version bump is involved. [`carto-skills-all.zip`](https://github.com/CartoDB/agent-skills/releases/latest/download/carto-skills-all.zip) holds every skill in its own folder for hosts that accept a multi-skill archive; `SHA256SUMS` and `manifest.json` ship alongside for verification.

**Prerequisites.** A use-case skill references utility and platform skills by name. Upload forms take one skill at a time and do not resolve those references, so upload the prerequisites listed below as well (the list is transitive; utility tier first, then platform, then the use-case skill). Zips are self-standing playbooks otherwise; nothing is inlined.

| Skill | Tier | Download | Upload first (prerequisites) |
|---|---|---|---|
| `carto-basics` | utility | [carto-basics.zip](https://github.com/CartoDB/agent-skills/releases/latest/download/carto-basics.zip) | — |
| `carto-connect-datawarehouse` | utility | [carto-connect-datawarehouse.zip](https://github.com/CartoDB/agent-skills/releases/latest/download/carto-connect-datawarehouse.zip) | — |
| `carto-query-datawarehouse` | utility | [carto-query-datawarehouse.zip](https://github.com/CartoDB/agent-skills/releases/latest/download/carto-query-datawarehouse.zip) | — |
| `carto-explore-datawarehouse` | utility | [carto-explore-datawarehouse.zip](https://github.com/CartoDB/agent-skills/releases/latest/download/carto-explore-datawarehouse.zip) | — |
| `carto-import-export-data` | platform | [carto-import-export-data.zip](https://github.com/CartoDB/agent-skills/releases/latest/download/carto-import-export-data.zip) | `carto-basics`, `carto-connect-datawarehouse`, `carto-explore-datawarehouse` |
| `carto-create-workflow` | platform | [carto-create-workflow.zip](https://github.com/CartoDB/agent-skills/releases/latest/download/carto-create-workflow.zip) | `carto-basics`, `carto-connect-datawarehouse`, `carto-query-datawarehouse` |
| `carto-find-spatial-data` | platform | [carto-find-spatial-data.zip](https://github.com/CartoDB/agent-skills/releases/latest/download/carto-find-spatial-data.zip) | `carto-basics`, `carto-connect-datawarehouse`, `carto-explore-datawarehouse` |
| `carto-manage-platform` | platform | [carto-manage-platform.zip](https://github.com/CartoDB/agent-skills/releases/latest/download/carto-manage-platform.zip) | `carto-basics`, `carto-query-datawarehouse` |
| `carto-create-builder-maps` | platform | [carto-create-builder-maps.zip](https://github.com/CartoDB/agent-skills/releases/latest/download/carto-create-builder-maps.zip) | `carto-basics`, `carto-connect-datawarehouse`, `carto-explore-datawarehouse` |
| `carto-render-inline-map` | platform | [carto-render-inline-map.zip](https://github.com/CartoDB/agent-skills/releases/latest/download/carto-render-inline-map.zip) | `carto-basics` |
| `carto-preview-builder-map` | platform | [carto-preview-builder-map.zip](https://github.com/CartoDB/agent-skills/releases/latest/download/carto-preview-builder-map.zip) | `carto-basics` |
| `carto-develop-app` | platform | [carto-develop-app.zip](https://github.com/CartoDB/agent-skills/releases/latest/download/carto-develop-app.zip) | `carto-basics`, `carto-connect-datawarehouse`, `carto-explore-datawarehouse` |
| `carto-hotspot-analysis` | use-case | [carto-hotspot-analysis.zip](https://github.com/CartoDB/agent-skills/releases/latest/download/carto-hotspot-analysis.zip) | `carto-basics`, `carto-connect-datawarehouse`, `carto-query-datawarehouse`, `carto-create-workflow` |
| `carto-spatial-autocorrelation` | use-case | [carto-spatial-autocorrelation.zip](https://github.com/CartoDB/agent-skills/releases/latest/download/carto-spatial-autocorrelation.zip) | `carto-basics`, `carto-connect-datawarehouse`, `carto-query-datawarehouse`, `carto-create-workflow` |
| `carto-gwr` | use-case | [carto-gwr.zip](https://github.com/CartoDB/agent-skills/releases/latest/download/carto-gwr.zip) | `carto-basics`, `carto-connect-datawarehouse`, `carto-query-datawarehouse`, `carto-create-workflow` |
| `carto-spatial-enrichment` | use-case | [carto-spatial-enrichment.zip](https://github.com/CartoDB/agent-skills/releases/latest/download/carto-spatial-enrichment.zip) | `carto-basics`, `carto-connect-datawarehouse`, `carto-query-datawarehouse`, `carto-create-workflow` |
| `carto-trade-area-analysis` | use-case | [carto-trade-area-analysis.zip](https://github.com/CartoDB/agent-skills/releases/latest/download/carto-trade-area-analysis.zip) | `carto-basics`, `carto-connect-datawarehouse`, `carto-query-datawarehouse`, `carto-create-workflow` |
| `carto-site-selection` | use-case | [carto-site-selection.zip](https://github.com/CartoDB/agent-skills/releases/latest/download/carto-site-selection.zip) | `carto-basics`, `carto-connect-datawarehouse`, `carto-query-datawarehouse`, `carto-create-workflow` |
| `carto-territory-planning` | use-case | [carto-territory-planning.zip](https://github.com/CartoDB/agent-skills/releases/latest/download/carto-territory-planning.zip) | `carto-basics`, `carto-connect-datawarehouse`, `carto-query-datawarehouse`, `carto-create-workflow` |
| `carto-routing-od-analysis` | use-case | [carto-routing-od-analysis.zip](https://github.com/CartoDB/agent-skills/releases/latest/download/carto-routing-od-analysis.zip) | `carto-basics`, `carto-connect-datawarehouse`, `carto-query-datawarehouse`, `carto-create-workflow` |
| `carto-geocoding` | use-case | [carto-geocoding.zip](https://github.com/CartoDB/agent-skills/releases/latest/download/carto-geocoding.zip) | `carto-basics`, `carto-connect-datawarehouse`, `carto-query-datawarehouse`, `carto-create-workflow` |
| `carto-composite-scoring` | use-case | [carto-composite-scoring.zip](https://github.com/CartoDB/agent-skills/releases/latest/download/carto-composite-scoring.zip) | `carto-basics`, `carto-connect-datawarehouse`, `carto-query-datawarehouse`, `carto-create-workflow` |
| `carto-arcgis-migration` | use-case | [carto-arcgis-migration.zip](https://github.com/CartoDB/agent-skills/releases/latest/download/carto-arcgis-migration.zip) | — |

## Source of truth

All four manifests are **generated** from [`skills/catalog.json`](../skills/catalog.json) by [`scripts/sync_manifests.py`](../scripts/sync_manifests.py). Don't hand-edit manifests — edit the catalog and run `make sync`. CI's `validate` step catches any drift.
