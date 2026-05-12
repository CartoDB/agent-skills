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

## Quick start

```bash
npm install -g @carto/carto-cli
carto auth login                # opens browser, stores credentials
carto auth status               # confirms tenant, org, user
carto maps list --json          # any command can return JSON
```

Authentication state persists across sessions. `auth status` is the fastest way to confirm the agent has working credentials before doing anything else.

## What's in this skill

| Topic | Reference |
|---|---|
| Installing the CLI (npm, version verification) | [references/installation.md](references/installation.md) |
| Authentication: browser, headless `--no-launch-browser`, API tokens, SSO | [references/authentication.md](references/authentication.md) |
| Profiles: managing multiple orgs / environments | [references/profiles.md](references/profiles.md) |
| Global flags: `--json`, `--debug`, `--yes`, `--token`, `--base-url`, `--profile`, env vars | [references/global-options.md](references/global-options.md) |

## Access paths: CLI vs MCP server

The two paths serve different intents. Most agent flows pick one based on what the user is asking for; some flows chain across both.

| User intent | Preferred path | Skill |
|---|---|---|
| Author or edit a permanent CARTO Builder map (CRUD on saved maps, validation, publish) | CLI | `carto-create-builder-maps` |
| Render an ad-hoc, exploratory map inline in chat from a deck.gl declarative spec | MCP (`view_map`) | `carto-render-inline-map` |
| Open / preview an existing saved Builder map by URL, ID, or name | MCP (`load_builder_map` + `list_maps`) | `carto-preview-builder-map` |
| Build a from-scratch CARTO + deck.gl app in TypeScript / JavaScript | (developer code) | `carto-develop-app` |
| Discover what's in a connection — schemas, tables, named sources | CLI today; MCP equivalents (`list_connections`, `list_resources`, `search_resources`, `get_column_stats`) when attached | `carto-explore-datawarehouse` (CLI) — MCP-aware refactor pending |
| Run spatial SQL | CLI today | `carto-query-datawarehouse` (CLI) — MCP-aware refactor pending |
| Author a Workflow (DAG of analytical components) | CLI today | `carto-create-workflow` (CLI) — MCP-aware refactor pending |
| Run a saved Workflow as an analytical tool | MCP, when the Workflow is registered as an MCP tool (dynamic per account) | covered ad-hoc by host's tool-list — no dedicated skill yet |
| Geospatial pattern analyses (hotspots, GWR, spatial autocorrelation, etc.) | CLI (Workflows) | `carto-pattern-*` skills |

### How to detect what's available

| What | How |
|---|---|
| **CARTO CLI installed** | `carto --version` succeeds in a shell. |
| **CARTO MCP server attached** | Tools named `view_map`, `load_builder_map`, `list_maps`, `list_connections`, `search_resources`, `get_column_stats` appear in your tool list. |
| **MCP host renders MCP Apps** (interactive widgets) | Claude.ai, Claude Desktop, ChatGPT do. Gemini CLI, Codex CLI, plain MCP Inspector, current MCPJam do not — those execute MCP tools but show only text confirmations, no inline widget. |

If an MCP-route intent is asked but the MCP server isn't attached (or the host doesn't render MCP Apps for visualization), surface that to the user — don't silently fall back to a generic visualization widget or a hand-rolled HTML map.

### Why this orientation lives here

The catalog's existing CLI-action skills (`carto-explore-datawarehouse`, `carto-query-datawarehouse`, `carto-create-workflow`, etc.) are CLI-only today. As they become mode-aware (per-skill MCP/CLI routing internal to each skill), this orientation table will narrow — eventually each skill picks its own access path internally and `carto-basics` carries only the meta-orientation. Until then, this section is the routing source of truth.

## Always-on guidance

- **Always pass `--json`** when you need machine-readable output. CLI text output is for humans and may change.
- **Map URLs** use the tenant domain from `auth status`, not a generic workspace URL. Private maps live at `https://{tenant_domain}/builder/{map_id}`; public/shared maps at `https://{tenant_domain}/map/{map_id}`. Never construct `workspace-{region}.app.carto.com` URLs.
- **Confirmation prompts**: destructive commands like `maps delete` prompt for the literal word "delete". Pass `--yes` (or `--json`) for non-interactive use.
- **Async jobs**: `imports create` and `sql job` poll until completion by default. Pass `--async` (where supported) to return immediately and poll separately.
