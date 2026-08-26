---
name: carto-basics
description: Start here for first-time CARTO use. Orients on the two parallel access paths into the CARTO platform — the MCP server (the primary path for inline, in-conversation work in chat hosts, including creating and editing maps and Workflows) and the CLI (for scripting, CI/CD, headless and bulk/cross-org work, and deeper administration and auditing such as usage-log queries) — and which skills cover each. Also covers CLI install, authentication, profiles, JSON output, and async job patterns.
license: MIT
---

# carto-basics

CARTO is reachable through two parallel access paths, and most agent setups use one or both:

- **CARTO MCP Server** — the primary path for inline, in-conversation work in chat-based agent hosts (Claude.ai, Claude Desktop, ChatGPT, and other MCP clients). When attached, it exposes a broad consolidated tool surface: exploring data, creating and editing Builder maps, authoring and running Workflows, running SQL, import/export, and org admin. Renders maps inline on hosts that support MCP Apps, and dynamically registers the user's published Workflows as MCP tools. This covers most interactive requests.
- **CARTO CLI** (`@carto/carto-cli`) — the path for scripting, CI/CD, headless contexts, bulk and cross-org operations, deeper administration and auditing (e.g. SQL over usage logs), and the fullest command surface. Used by many platform skills in this catalog, and the fallback whenever the MCP server isn't attached.

**Use this skill before any other CARTO skill** — it covers how to detect and route between the two access paths, plus CLI installation, authentication, profiles, and the global flags the CLI-driven skills assume.

## When to use this skill

- Setting up the CLI for the first time on a new machine.
- The user reports authentication errors (`auth status` failures, expired tokens).
- The user wants to switch between organizations or environments.
- A downstream skill needs `--profile`, `--json`, `--token`, or `--base-url` and you don't yet know how those work.

## Preflight — run before any CLI operation

Skills that drive the **CLI** assume a working, authenticated `carto` CLI. If the attached **MCP server** already covers the request (exploring data, creating maps, running Workflows in a chat host), you don't need the CLI at all — route through MCP. Run the checks below before your first *CLI* call, and **re-run them at the start of each task** — ephemeral sandboxes (e.g. Claude Code Cowork tasks) wipe the CLI between tasks. An attached MCP server, by contrast, persists at the account level (see below).

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

## Access paths: MCP server vs CLI

The MCP server and CLI serve different intents — some flows chain across both. **When the MCP server is attached, prefer it for interactive requests** (exploring data, creating and editing maps, building and running Workflows); reach for the CLI for scripting, CI/CD, headless runs, bulk or cross-org work, and deeper administration and auditing (e.g. usage-log queries), or when the server isn't attached. When an intent maps to MCP but the server isn't attached (or the host doesn't render MCP Apps), fall back to the CLI where it applies, or surface the gap — don't silently fall back to a hand-rolled map. The CLI is wiped per task in ephemeral sandboxes; an attached MCP server persists at the account level. Full routing table, detection signals, and auth-dependent tool availability: [references/access-paths.md](references/access-paths.md).

## Always-on guidance

- **Never silently degrade.** A CARTO request is answered with CARTO tooling. If the CLI can't be installed or authenticated (or a needed MCP route isn't attached), surface the blocker and stop — don't substitute Python, SQL, deck.gl, or other generic geospatial workarounds, and don't ask for an M2M token in place of `carto auth login --no-launch-browser`.
- **Always pass `--json`** when you need machine-readable output. CLI text output is for humans and may change.
- **Map URLs** use the tenant domain from `auth status`, not a generic workspace URL. Private maps live at `https://{tenant_domain}/builder/{map_id}`; public/shared maps at `https://{tenant_domain}/map/{map_id}`. Never construct `workspace-{region}.app.carto.com` URLs.
- **Confirmation prompts**: destructive commands like `maps delete` prompt for the literal word "delete". Pass `--yes` (or `--json`) for non-interactive use.
- **Async jobs**: `imports create` and `sql job` poll until completion by default. Pass `--async` (where supported) to return immediately and poll separately.
