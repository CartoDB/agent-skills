# Notes for Gemini CLI

This file is loaded as context whenever the `carto-skills` extension is active in Gemini CLI (the `contextFileName` field in [`gemini-extension.json`](gemini-extension.json) points here).

## What's installed

8 skills in two layered tiers — see [`skills/catalog.json`](skills/catalog.json) for the source of truth.

**Utility tier** — foundational, no dependencies:

- `carto-basics` — install, auth, profiles, global flags.
- `carto-connect-datawarehouse` — BigQuery / Snowflake / Redshift / Postgres / Databricks connections.
- `carto-query-datawarehouse` — spatial SQL, dialect-specific guidance, execution model.
- `carto-explore-datawarehouse` — schema discovery, named sources.

**Platform tier** — wraps a CARTO product:

- `carto-import-export-data` — imports, tilesets, exports.
- `carto-create-analytics-workflow` — Workflow CRUD + scheduling + dev→prod.
- `carto-find-spatial-data` — Data Observatory discovery and subscription.
- `carto-manage-platform` — org admin, users, quotas, activity audit.

## Per-skill commands

Each skill has a Gemini command at `commands/carto/<skill-name>.toml`. Invoke via `/carto:<skill-name>`:

```
/carto:carto-basics       # tackle install/auth questions
/carto:carto-query-datawarehouse  # spatial SQL help
/carto:carto-manage-platform      # admin and audit
```

The command reads the skill's `SKILL.md` first, then opens `references/*.md` for depth as needed. All commands stay within their skill's stated scope and surface a redirect when the question fits a different skill better.

## Reading order for a fresh CARTO session

1. `/carto:carto-basics` — confirm install + auth.
2. `/carto:carto-explore-datawarehouse` — list connections, see what's there.
3. `/carto:carto-connect-datawarehouse` — only if a fresh warehouse needs wiring up.
4. `/carto:carto-query-datawarehouse` — SQL once you know the data.

Platform skills layer on top once the utility-tier flow is fluent.

## CLI prerequisite

All skills assume the CARTO CLI is installed:

```bash
npm install -g @carto/carto-cli
carto --version
```

The `carto-basics` skill walks the user through this on first invocation.

## Always-on

- For machine-parseable CLI output, always pass `--json`.
- Destructive commands require typing `delete` to confirm; pass `--yes` (or `--json`) for non-interactive use.
- Skills are layered: utility skills don't depend on each other; platform skills depend on utility skills only. Don't try to compose two utility skills as if they were the same primitive.

For the full architectural explanation see [`ARCHITECTURE.md`](ARCHITECTURE.md).
