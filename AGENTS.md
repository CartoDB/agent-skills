# Notes for AI agents

Generic guidance for any agent harness that loads this repo's skills (Claude Code, Codex, Gemini CLI, Skills CLI).

## Reading order for a fresh CARTO session

1. **`carto-basics`** — install, authenticate, confirm `auth status` returns OK.
2. **`carto-explore-datawarehouse`** — list connections; if none, head to `carto-connect-datawarehouse`.
3. **`carto-connect-datawarehouse`** — only if a fresh warehouse needs wiring up.
4. **`carto-query-datawarehouse`** — SQL once you know what you're querying.

Each skill's SKILL.md states explicitly when *not* to use it — defer to those signals.

## Reference files

A skill's `references/*.md` files are *not* always loaded. They're linked from the SKILL.md and the agent should read them on demand when the user's question lands in that area. Pulling all references into context up-front wastes tokens.

## Three-tier discipline

- Utility skills are foundational. They have no dependencies on other CARTO skills.
- Don't synthesize behavior across two utility skills as if they were composable — they're orthogonal primitives. Composition is the platform and use-case tiers' job.

## Conventions every skill assumes

- The CLI is installed (`npm install -g @carto/carto-cli`).
- The user is authenticated (`carto auth status` succeeds).
- For machine-parsable output, every command takes `--json`.
- Destructive commands (`delete`, `batch-delete`) require typing `delete` to confirm; pass `--yes` or `--json` for non-interactive use.

