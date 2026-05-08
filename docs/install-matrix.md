# Install matrix

Which skills ship via which harness.

| Skill | Tier | Claude Code | Skills CLI | Codex | Gemini |
|---|---|---|---|---|---|
| `carto-basics` | utility | ✅ | ✅ | ✅ | ✅ |
| `carto-connect-datawarehouse` | utility | ✅ | ✅ | ✅ | ✅ |
| `carto-query-datawarehouse` | utility | ✅ | ✅ | ✅ | ✅ |
| `carto-explore-datawarehouse` | utility | ✅ | ✅ | ✅ | ✅ |
| `carto-import-export-data` | platform | ✅ | ✅ | ✅ | ✅ |
| `carto-create-workflow` | platform | ✅ | ✅ | ✅ | ✅ |
| `carto-find-spatial-data` | platform | ✅ | ✅ | ✅ | ✅ |
| `carto-manage-platform` | platform | ✅ | ✅ | ✅ | ✅ |
| `carto-copy-maps` | platform | ✅ | ✅ | ✅ | ✅ |
| `carto-copy-workflows` | platform | ✅ | ✅ | ✅ | ✅ |
| `carto-create-builder-maps` | platform | ✅ | ✅ | ✅ | ✅ |
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
| `carto-build-app` | platform | ⏳ deferred | ⏳ deferred | ⏳ deferred | ⏳ deferred |
| `carto-build-spatial-dashboard` | use-case | ⏳ Phase 3 | ⏳ Phase 3 | ⏳ Phase 3 | ⏳ Phase 3 |
| `carto-build-customer-facing-map` | use-case | ⏳ Phase 3 | ⏳ Phase 3 | ⏳ Phase 3 | ⏳ Phase 3 |
| `carto-migrate-to-carto` | use-case | ⏳ Phase 3 | ⏳ Phase 3 | ⏳ Phase 3 | ⏳ Phase 3 |

One platform skill (`carto-build-app`) is owned by another PM — see [deferred-skills.md](deferred-skills.md). The Phase 3 build-oriented use-case skills depend on it, so they wait too.

## Per-harness install

### Claude Code

```bash
/plugin marketplace add CartoDB/carto-agent-skills
/plugin install carto-skills@carto-agent-skills
```

All 21 skills (4 utility + 7 platform + 10 use-case patterns) ship as one bundle. Manifest: [`.claude-plugin/marketplace.json`](../.claude-plugin/marketplace.json) registers the plugin; the plugin manifest at [`plugins/carto-skills-claude/.claude-plugin/plugin.json`](../plugins/carto-skills-claude/.claude-plugin/plugin.json) enumerates the skills.

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

## Source of truth

All four manifests are **generated** from [`skills/catalog.json`](../skills/catalog.json) by [`scripts/sync_manifests.py`](../scripts/sync_manifests.py). Don't hand-edit manifests — edit the catalog and run `make sync`. CI's `validate` step catches any drift.
