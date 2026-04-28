# Install matrix

Which skills ship via which harness.

| Skill | Tier | Claude Code | Skills CLI | Codex | Gemini |
|---|---|---|---|---|---|
| `carto-basics` | utility | ✅ | ✅ | ⏳ Phase 2b | ⏳ Phase 2b |
| `carto-connect-datawarehouse` | utility | ✅ | ✅ | ⏳ Phase 2b | ⏳ Phase 2b |
| `carto-query-datawarehouse` | utility | ✅ | ✅ | ⏳ Phase 2b | ⏳ Phase 2b |
| `carto-explore-datawarehouse` | utility | ✅ | ✅ | ⏳ Phase 2b | ⏳ Phase 2b |
| `carto-import-export-data` | platform | ✅ | ✅ | ⏳ Phase 2b | ⏳ Phase 2b |
| `carto-create-analytics-workflow` | platform | ✅ | ✅ | ⏳ Phase 2b | ⏳ Phase 2b |
| `carto-find-spatial-data` | platform | ✅ | ✅ | ⏳ Phase 2b | ⏳ Phase 2b |
| `carto-manage-platform` | platform | ✅ | ✅ | ⏳ Phase 2b | ⏳ Phase 2b |
| `carto-create-builder-maps` | platform | ⏳ deferred | ⏳ deferred | ⏳ deferred | ⏳ deferred |
| `carto-build-app` | platform | ⏳ deferred | ⏳ deferred | ⏳ deferred | ⏳ deferred |
| `carto-build-spatial-dashboard` | use-case | ⏳ Phase 3 | ⏳ Phase 3 | ⏳ Phase 3 | ⏳ Phase 3 |
| `carto-build-customer-facing-map` | use-case | ⏳ Phase 3 | ⏳ Phase 3 | ⏳ Phase 3 | ⏳ Phase 3 |
| `carto-migrate-to-carto` | use-case | ⏳ Phase 3 | ⏳ Phase 3 | ⏳ Phase 3 | ⏳ Phase 3 |

Two platform skills (`carto-create-builder-maps`, `carto-build-app`) are owned by another PM and intentionally deferred — see [deferred-skills.md](deferred-skills.md). The Phase 3 use-case skills depend on those, so they wait too.

## Per-harness install

### Claude Code

```bash
/plugin marketplace add CartoDB/carto-agent-skills
/plugin install carto-skills@carto-agent-skills
```

All 8 skills (4 utility + 4 platform) ship as one bundle.

### Skills CLI

```bash
npx skills add CartoDB/carto-agent-skills
```

Reads `skills/catalog.json` and registers each skill independently.

### Codex (Phase 2b)

Will use a Codex plugin manifest at `plugins/carto-skills/.codex-plugin/plugin.json`. Drafted from MotherDuck's pattern. Not yet built.

### Gemini (Phase 2b)

Will use a Gemini extension manifest (`gemini-extension.json`) plus per-skill TOML files under `commands/carto/<skill>.toml` (one file per skill). Not yet built.
