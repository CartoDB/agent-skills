---
name: carto-basics
description: Start here for first-time CARTO use — install the CLI, authenticate, switch profiles, understand JSON output and async job patterns. Also orients on the two parallel access paths into the CARTO platform (CLI for authoring/scripting, MCP server for inline interactions in chat hosts) and which skills cover each.
license: MIT
---

# carto-basics

CARTO is reachable through two parallel access paths, and most agent setups use one or both:

- **CARTO CLI** (`@carto/carto-cli`) — the primary path for authoring, scripting, and headless contexts. Used by most other skills in this catalog.
- **CARTO MCP Server** — a parallel path for inline interactions in chat-based agent hosts (Claude.ai, Claude Desktop, ChatGPT). Renders maps inline, exposes data discovery and saved-Builder-map preview tools, and dynamically registers the user's saved CARTO Workflows as MCP tools when available.

**Use this skill before any other CARTO skill** — it covers installation, authentication, profiles, the global CLI flags every other CARTO skill assumes, and how to detect / route between the two access paths.

## When to use this skill

- Setting up the CLI for the first time on a new machine.
- The user reports authentication errors (`auth status` failures, expired tokens).
- The user wants to switch between organizations or environments.
- A downstream skill needs `--profile`, `--json`, `--token`, or `--base-url` and you don't yet know how those work.

## Preflight — run before any CLI operation

Every CARTO skill assumes a working, authenticated `carto` CLI. Walk these checks before your first CLI call, and **re-run them at the start of each task** — ephemeral sandboxes (e.g. Claude Code Cowork tasks) wipe the CLI between tasks. An attached MCP server, by contrast, persists at the account level (see below).

1. **CLI present?** Run `carto --version`. If `command not found`, **install it yourself** — tell the user you're installing, then do it; never deflect with "run this on your own machine." The npm command plus the `EACCES` / writable-prefix fallback that sandboxes need are in [references/installation.md](references/installation.md).
2. **Authenticated?** Run `carto auth status`. If not, use the headless flow `carto auth login --no-launch-browser` — an agent can't complete a browser OAuth. **Never** open or wait on a browser, and **never** ask the user for an M2M / API token instead ([references/authentication.md](references/authentication.md)).

If install or auth can't complete, **say so and stop** — never silently fall back to Python / SQL / deck.gl or other non-CARTO tooling.

## What's in this skill

| Topic | Reference |
|---|---|
| Installing the CLI (npm, version verification) | [references/installation.md](references/installation.md) |
| Authentication: browser, headless `--no-launch-browser`, API tokens, SSO | [references/authentication.md](references/authentication.md) |
| Profiles: managing multiple orgs / environments | [references/profiles.md](references/profiles.md) |
| Global flags: `--json`, `--debug`, `--yes`, `--token`, `--base-url`, `--profile`, env vars | [references/global-options.md](references/global-options.md) |
| Access paths: CLI vs MCP routing, detection, host support | [references/access-paths.md](references/access-paths.md) |

## Access paths: CLI vs MCP server

The CLI and MCP server serve different intents — some flows chain across both. When an intent maps to MCP but the server isn't attached (or the host doesn't render MCP Apps), surface that; don't silently fall back to a hand-rolled map. The CLI is wiped per task in ephemeral sandboxes; an attached MCP server persists at the account level. Full routing table, detection signals, and host support: [references/access-paths.md](references/access-paths.md).

## Always-on guidance

- **Never silently degrade.** A CARTO request is answered with CARTO tooling. If the CLI can't be installed or authenticated (or a needed MCP route isn't attached), surface the blocker and stop — don't substitute Python, SQL, deck.gl, or other generic geospatial workarounds, and don't ask for an M2M token in place of `carto auth login --no-launch-browser`.
- **Always pass `--json`** when you need machine-readable output. CLI text output is for humans and may change.
- **Map URLs** use the tenant domain from `auth status`, not a generic workspace URL. Private maps live at `https://{tenant_domain}/builder/{map_id}`; public/shared maps at `https://{tenant_domain}/map/{map_id}`. Never construct `workspace-{region}.app.carto.com` URLs.
- **Confirmation prompts**: destructive commands like `maps delete` prompt for the literal word "delete". Pass `--yes` (or `--json`) for non-interactive use.
- **Async jobs**: `imports create` and `sql job` poll until completion by default. Pass `--async` (where supported) to return immediately and poll separately.
