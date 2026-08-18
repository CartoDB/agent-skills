# Access paths: MCP server vs CLI

CARTO is reachable through two parallel access paths, and most agent setups use one or both:

- **CARTO MCP Server** — the primary path for inline, in-conversation work in chat-based agent hosts (Claude.ai, Claude Desktop, ChatGPT, and other MCP clients). When attached, it exposes a broad, consolidated tool surface: exploring connections and data, creating and editing Builder maps, authoring and running Workflows, running SQL, geocoding/routing, import/export, and org admin. Related operations are grouped behind a `method`/`kind` parameter (e.g. `explore_data`, `read_maps`, `manage_connections`). It renders maps inline on hosts that support MCP Apps, and dynamically registers the user's published Workflows as MCP tools. This covers most interactive requests.
- **CARTO CLI** (`@carto/carto-cli`) — the path for scripting, CI/CD, headless contexts, bulk and cross-org operations, deeper administration and auditing (e.g. SQL over usage logs), and the fullest command surface. Used by many platform skills in this catalog, and the fallback whenever the MCP server isn't attached or the host can't render inline widgets.

The two paths serve different intents. Most agent flows pick one based on what the user is asking for and what's available; some flows chain across both. **When the MCP server is attached, prefer it for interactive requests — including creating and editing maps and Workflows; reach for the CLI for scripting, CI/CD, headless runs, bulk or cross-org work, and deeper administration and auditing.**

| User intent | Preferred path when MCP is attached | CLI alternative | Skill |
|---|---|---|---|
| Discover what's in a connection — schemas, tables, named sources | MCP (`explore_data`) | CLI | `carto-explore-datawarehouse` |
| Run spatial SQL | MCP (`execute_query` / `execute_async_query`) | CLI | `carto-query-datawarehouse` |
| Render an ad-hoc, exploratory map inline in chat from a deck.gl declarative spec | MCP (`view_map`) | — (CLI can't render inline) | `carto-render-inline-map` |
| Open / preview an existing saved Builder map by URL, ID, or name | MCP (`read_maps` + `view_map`) | — | `carto-preview-builder-map` |
| Create or edit a permanent CARTO Builder map (CRUD, validation, publish) | MCP (`create_map`, `update_map`, `validate_map`, `read_maps`) | CLI for scripted/bulk authoring and cross-org copy | `carto-create-builder-maps` |
| Author a Workflow (DAG of analytical components) | MCP (`create_workflow`, `validate_workflow`) | CLI for scripted/bulk authoring | `carto-create-workflow` |
| Run a saved Workflow as an analytical tool | MCP (`run_workflow`, or a published Workflow tool) — needs OAuth; a token session can only poll `status` | CLI (token-session fallback for starting a run) | covered ad-hoc by host's tool-list |
| Import / export / transfer data | MCP (`import_data`, `export_data`, `transfer_data`) | CLI | `carto-import-export-data` |
| Org admin — users, credentials, connections, activity | MCP (`manage_users`, `manage_connections`, `manage_api_access_tokens`, …) | CLI | `carto-manage-platform` |
| Build a from-scratch CARTO + deck.gl app in TypeScript / JavaScript | — | CLI to manage the app's credentials and tokens | `carto-develop-app` |
| Geospatial pattern analyses (hotspots, GWR, spatial autocorrelation, etc.) | MCP (`run_workflow`) or CLI (Workflows) | CLI | `carto-pattern-*` skills |

## How to detect what's available

| What | How |
|---|---|
| **CARTO MCP server attached** | CARTO tools appear in your tool list — e.g. `explore_data`, `read_maps`, `view_map`, `create_map`, `run_workflow`, `manage_connections`. (Consolidated names group several operations behind a `method` parameter.) |
| **CARTO CLI installed** | `carto --version` succeeds in a shell. |
| **MCP host renders MCP Apps** (interactive widgets) | Claude.ai, Claude Desktop, ChatGPT do. Gemini CLI, Codex CLI, plain MCP Inspector, current MCPJam do not — those execute MCP tools but show only text confirmations, no inline widget. |

If an MCP-route intent is asked but the MCP server isn't attached (or the host doesn't render MCP Apps for visualization), fall back to the CLI where it applies, or surface the gap — don't silently fall back to a generic visualization widget or a hand-rolled HTML map.

> **Tool availability depends on how the MCP server was authenticated — and, for a token, on its Allowed APIs.** A user signed in over OAuth reaches the full surface over MCP, including map/workflow authoring and admin. A user connected with an API Access Token reaches a read-and-discovery subset whose size depends on the token's Allowed APIs: the **MCP Server** scope alone reaches only `explore_data` (list connections + browse/search resources — **not** `describe`, **not** `get_connection`), `search_data_observatory`, and the two `validate_*` tools. Adding **SQL** unlocks `execute_query` / `execute_async_query` plus `run_workflow`'s `status` only (the agent can poll a run it can't start; starting a run and fetching results need OAuth); **Maps** unlocks `describe`; **LDS** unlocks `geocode` / `route` / `calculate_isolines` / `calculate_od_matrix`; **Imports/Exports** unlock `import_data` / `export_data` / `transfer_data`. Authoring maps and Workflows, and admin, are OAuth-only — so for those, reconnect over OAuth or fall back to the CLI.

## Ephemerality — CLI vs MCP persistence

In ephemeral sandboxes (e.g. Claude Code Cowork tasks) the CLI is wiped between tasks, so the install + auth preflight must run again at the start of each task. An attached MCP server, by contrast, persists at the account level and stays available across tasks.
