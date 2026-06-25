# Access paths: CLI vs MCP server

CARTO is reachable through two parallel access paths, and most agent setups use one or both:

- **CARTO CLI** (`@carto/carto-cli`) — the primary path for authoring, scripting, and headless contexts. Used by most other skills in this catalog.
- **CARTO MCP Server** — a parallel path for inline interactions in chat-based agent hosts (Claude.ai, Claude Desktop, ChatGPT). Renders maps inline, exposes data discovery and saved-Builder-map preview tools, and dynamically registers the user's saved CARTO Workflows as MCP tools when available.

The two paths serve different intents. Most agent flows pick one based on what the user is asking for; some flows chain across both.

| User intent | Preferred path | Skill |
|---|---|---|
| Author or edit a permanent CARTO Builder map (CRUD on saved maps, validation, publish) | CLI | `carto-create-builder-maps` |
| Render an ad-hoc, exploratory map inline in chat from a deck.gl declarative spec | MCP (`view_map`) | `carto-render-inline-map` |
| Open / preview an existing saved Builder map by URL, ID, or name | MCP (`load_builder_map` + `list_maps`) | `carto-preview-builder-map` |
| Build a from-scratch CARTO + deck.gl app in TypeScript / JavaScript | CLI to manage the app's credentials and tokens | `carto-develop-app` |
| Discover what's in a connection — schemas, tables, named sources | CLI today; MCP equivalents (`list_connections`, `list_resources`, `search_resources`, `get_column_stats`) when attached | `carto-explore-datawarehouse` |
| Run spatial SQL | CLI today | `carto-query-datawarehouse` |
| Author a Workflow (DAG of analytical components) | CLI today | `carto-create-workflow` |
| Run a saved Workflow as an analytical tool | MCP, when the Workflow is registered as an MCP tool (dynamic per account) | covered ad-hoc by host's tool-list — no dedicated skill yet |
| Geospatial pattern analyses (hotspots, GWR, spatial autocorrelation, etc.) | CLI (Workflows) | `carto-pattern-*` skills |

## How to detect what's available

| What | How |
|---|---|
| **CARTO CLI installed** | `carto --version` succeeds in a shell. |
| **CARTO MCP server attached** | Tools named `view_map`, `load_builder_map`, `list_maps`, `list_connections`, `search_resources`, `get_column_stats` appear in your tool list. |
| **MCP host renders MCP Apps** (interactive widgets) | Claude.ai, Claude Desktop, ChatGPT do. Gemini CLI, Codex CLI, plain MCP Inspector, current MCPJam do not — those execute MCP tools but show only text confirmations, no inline widget. |

If an MCP-route intent is asked but the MCP server isn't attached (or the host doesn't render MCP Apps for visualization), surface that to the user — don't silently fall back to a generic visualization widget or a hand-rolled HTML map.

## Ephemerality — CLI vs MCP persistence

In ephemeral sandboxes (e.g. Claude Code Cowork tasks) the CLI is wiped between tasks, so the install + auth preflight must run again at the start of each task. An attached MCP server, by contrast, persists at the account level and stays available across tasks — but it covers only the intents above, not the full CLI surface that the rest of the catalog drives.
