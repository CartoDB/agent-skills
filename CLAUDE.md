# Notes for Claude Code

Claude Code reads this file automatically when working in this repo.

## When editing skills

- The source of truth is `skills/catalog.json`. Add a skill there first, then create the directory.
- After editing the catalog, run `make sync` to regenerate the Claude / Codex / Gemini manifests. Run `make validate` before pushing.
- `SKILL.md` should be small (~5KB max). Move depth to `references/*.md` and link from SKILL.md.
- Frontmatter must include `name`, `description`, `license`. The `name` must match the directory.

## When users ask "how do I install"

Direct them to the official docs at [docs.carto.com/carto-for-agents/agent-skills](https://docs.carto.com/carto-for-agents/agent-skills). The Claude Code plugin ID is `carto-skills@carto-agent-skills`.

## Tier discipline

Utility skills cannot have dependencies. Platform skills may depend only on utility skills. Use-case skills may depend on utility and platform skills. If you find yourself wanting one utility skill to import another, that signals the content belongs in a platform skill instead.

## Testing locally

```bash
make validate                                     # all checks
cd scripts && python3 validate_skills.py          # just the skills check
python3 tests/validate_snippets.py                # just snippet linting
```

Snippet validation needs `pip install pyyaml sqlglot` — both ship in CI but a fresh local checkout may need them installed.
