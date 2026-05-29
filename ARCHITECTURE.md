# Architecture

Multi-harness skills catalog. Single source of truth (`skills/catalog.json`) drives validation, plugin manifests, and Skills CLI distribution across Claude Code, Skills CLI, Codex, and Gemini.

## Three-tier layering

Every skill belongs to exactly one tier. Tiers enforce dependency direction.

| Tier | Description |
|---|---|
| **Utility** | Depends on nothing. Foundational primitives. |
| **Platform** | May depend only on utility skills. Wraps a CARTO product surface. |
| **Use-case** | May depend on utility and/or platform skills. Composes end-to-end agent flows. |

> Why "Platform" and not "Workflow"? CARTO Workflows is a product, and one of the platform-tier skills wraps it. Calling the layer "Workflow" would collide with the product name.

`scripts/validate_skills.py` enforces the dependency rules: utility skills declare no dependencies; platform skills may depend only on utility skills; use-case skills may depend on utility ∪ platform.

## Source of truth: `skills/catalog.json`

```json
{
  "skills": [
    {
      "name": "carto-basics",
      "layer": "utility",
      "dependencies": [],
      "description": "...",
      "path": "skills/carto-basics"
    }
  ]
}
```

Layer metadata lives **in catalog.json, not in SKILL.md frontmatter**, so frontmatter stays portable across harnesses that don't know about layering.

## Skill anatomy

```
skills/<skill-name>/
  SKILL.md                 # frontmatter + main guidance, kept small
  references/*.md          # deep-dive content, loaded only when needed
  artifacts/*              # optional dual-language runnable examples (Phase 2+)
```

Frontmatter:
```yaml
---
name: carto-basics
description: One sentence saying when to use this skill.
license: MIT
---
```

## Distribution surfaces

| Harness | Status | Manifest |
|---|---|---|
| **Claude Code** | ✅ | `.claude-plugin/marketplace.json` + `plugins/carto-skills-claude/.claude-plugin/plugin.json` |
| **Skills CLI** | ✅ | reads `skills/catalog.json` directly |
| **Codex** | ✅ | `.codex-plugin/plugin.json` (repo root) |
| **Gemini** | ✅ | `gemini-extension.json` + `commands/carto/*.toml` (one TOML per skill) |

`scripts/sync_manifests.py` regenerates **all four** harness manifests from `catalog.json`. CI runs `validate_skills.py` (read-only) to catch drift, with sync checks for each harness.

## Validation

Two scripts, both wired into CI:

- `scripts/validate_skills.py` — catalog/filesystem/manifest/layer/reference integrity.
- `tests/validate_snippets.py` — lints fenced code blocks per language: Python AST, `bash -n`, `json.loads`, `yaml.safe_load`, `sqlglot.parse(read=<dialect>)`. TypeScript validation is warning-only in Phase 1.

SQL snippet validation is **syntactic only** (per-dialect parse via `sqlglot`). No live warehouse executes the snippets in CI — the goal is to catch obvious dialect/parse mistakes before they ship, not to verify end-to-end correctness.

## Adding a new skill

See [docs/skill-authoring.md](docs/skill-authoring.md).
