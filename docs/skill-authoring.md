# Authoring a new skill

This guide walks through adding a new skill end-to-end.

## 1. Pick a name and a tier

Naming convention: `carto-<verb>-<object>`. Verb is imperative. Object names the concrete thing (`builder-maps`, `spatial-data`, `datawarehouse`). The name should route on user *intent*, not CARTO product jargon.

Tiers:

- **`utility`** — depends on nothing. Foundational primitive.
- **`platform`** — wraps a CARTO product. Depends only on utility skills.
- **`use-case`** — orchestrates an end-to-end flow. Depends on utility and/or platform skills.

If unsure, default to platform.

## 2. Add the catalog entry

Edit `skills/catalog.json`:

```json
{
  "name": "carto-<verb>-<object>",
  "layer": "platform",
  "dependencies": ["carto-basics", "carto-connect-datawarehouse"],
  "description": "One sentence saying when to use this skill.",
  "path": "skills/carto-<verb>-<object>"
}
```

The `description` is what makes agents route correctly to your skill. Be specific about *when* to use it.

## 3. Create the directory and SKILL.md

```
skills/carto-<verb>-<object>/
  SKILL.md
  references/
    <topic-1>.md
    <topic-2>.md
```

`SKILL.md` frontmatter (mandatory):

```yaml
---
name: carto-<verb>-<object>
description: Same one-liner as the catalog entry.
license: MIT
---
```

Body conventions:

- Lead with **"When to use this skill"** — bulleted list of trigger conditions.
- Then **"Quick reference"** — minimum commands the agent needs to be useful.
- Then a table of `references/*.md` files with one-line summaries.
- End with **"Always-on guidance"** — invariants the agent should never forget for this skill.

Keep SKILL.md under ~5KB. If it grows past that, split content into `references/`.

## 4. Write reference files

Each `references/*.md` file covers one focused topic — a single warehouse engine, a single SQL dialect, a single subcommand family. Reference files are loaded on demand, so they can be deeper.

## 5. Generate the plugin manifest

```bash
make sync          # regenerates plugins/carto-skills-claude/.claude-plugin/plugin.json
```

For the marketplace.json, **manually** add the new skill path to the `skills` array of the `carto-skills` plugin entry. (Marketplace entries carry per-plugin metadata that we don't auto-generate.)

## 6. Run validation locally

```bash
make validate
```

Two scripts run:

- `validate_skills.py` — catalog/filesystem/manifest/layer/reference integrity.
- `validate_snippets.py` — every fenced code block with a language tag must parse.

The snippet validator dispatches by language tag in the fence:

| Tag | Validator |
|---|---|
| `python` | `ast.parse` |
| `bash` / `sh` | `bash -n` |
| `json` | `json.loads` |
| `yaml` | `yaml.safe_load` |
| `sql` | generic `sqlglot.parse` |
| `sql bigquery` / `sql snowflake` / `sql postgres` / `sql redshift` / `sql databricks` / `sql duckdb` | dialect-aware `sqlglot.parse(read=<dialect>)` |
| `ts` / `typescript` | `tsc --noEmit` if available; warning-only otherwise |

Untagged fenced blocks are skipped. Use them sparingly — they don't get linted.

## 7. Open a PR

Reviewers focus on:

- **Description targetedness**: does the description make it clear *when* to route to this skill (not just *what* it does)?
- **Tier honesty**: does the skill actually only depend on the declared tier?
- **Reference splitting**: is depth in `references/`, not SKILL.md?
- **Salvage check** (for Phase 2/3): if your skill maps onto content in `docs/_phase2-salvage/`, you're expected to consume that content rather than re-write it.
