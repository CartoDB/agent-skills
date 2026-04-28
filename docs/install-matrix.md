# Install matrix

Which skills ship via which harness.

| Skill | Tier | Claude Code | Skills CLI | Codex | Gemini |
|---|---|---|---|---|---|
| `carto-basics` | utility | ✅ | ✅ | ⏳ Phase 2 | ⏳ Phase 2 |
| `carto-connect-datawarehouse` | utility | ✅ | ✅ | ⏳ Phase 2 | ⏳ Phase 2 |
| `carto-query-datawarehouse` | utility | ✅ | ✅ | ⏳ Phase 2 | ⏳ Phase 2 |
| `carto-explore-datawarehouse` | utility | ✅ | ✅ | ⏳ Phase 2 | ⏳ Phase 2 |
| `carto-import-export-data` | platform | ⏳ Phase 2 | ⏳ Phase 2 | ⏳ Phase 2 | ⏳ Phase 2 |
| `carto-create-builder-maps` | platform | ⏳ Phase 2 | ⏳ Phase 2 | ⏳ Phase 2 | ⏳ Phase 2 |
| `carto-build-app` | platform | ⏳ Phase 2 | ⏳ Phase 2 | ⏳ Phase 2 | ⏳ Phase 2 |
| `carto-create-analytics-workflow` | platform | ⏳ Phase 2 | ⏳ Phase 2 | ⏳ Phase 2 | ⏳ Phase 2 |
| `carto-find-spatial-data` | platform | ⏳ Phase 2 | ⏳ Phase 2 | ⏳ Phase 2 | ⏳ Phase 2 |
| `carto-manage-platform` | platform | ⏳ Phase 2 | ⏳ Phase 2 | ⏳ Phase 2 | ⏳ Phase 2 |
| `carto-build-spatial-dashboard` | use-case | ⏳ Phase 3 | ⏳ Phase 3 | ⏳ Phase 3 | ⏳ Phase 3 |
| `carto-build-customer-facing-map` | use-case | ⏳ Phase 3 | ⏳ Phase 3 | ⏳ Phase 3 | ⏳ Phase 3 |
| `carto-migrate-to-carto` | use-case | ⏳ Phase 3 | ⏳ Phase 3 | ⏳ Phase 3 | ⏳ Phase 3 |

## Per-harness install

### Claude Code

```bash
/plugin marketplace add CartoDB/carto-agent-skills
/plugin install carto-skills@carto-agent-skills
```

All four utility skills are installed as a single bundle.

### Skills CLI

```bash
npx skills add CartoDB/carto-agent-skills
```

Reads `skills/catalog.json` and registers each skill independently.

### Codex (Phase 2)

Will use a Codex plugin manifest at `plugins/carto-skills/.codex-plugin/plugin.json`. Not yet built.

### Gemini (Phase 2)

Will use a Gemini extension manifest (`gemini-extension.json`) plus per-command TOML files under `commands/carto/`. Not yet built.
