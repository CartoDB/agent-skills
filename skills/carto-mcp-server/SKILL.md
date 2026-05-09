---
name: carto-mcp-server
description: Use when the user wants inline/exploratory map visualization, references a saved CARTO Builder map by name/topic, wants to preview the result of a CLI map creation without leaving the chat, or asks to run a saved analysis the MCP server may have exposed as a Workflow tool (dynamic per account — may or may not be present). Covers the CARTO MCP server's view_map (ad-hoc deck.gl declarative), load_builder_map (lightweight preview of a saved map), list_maps, get_column_stats, discovery tools, and any CARTO Workflows registered as MCP tools (e.g. compute trade areas, find hotspots, enrich with demographics). Distinct from carto-create-builder-maps (CLI authoring of permanent maps). Triggers on "show me X on a map", "visualize Y", "make a heatmap of Z", "open the <name> map", post-creation preview flows, and analytical asks where a matching Workflow tool is available.
license: MIT
---

# carto-mcp-server

The CARTO MCP Server is the AI integration into the user's CARTO platform — workspace, saved Builder maps, and connected data warehouses. It exposes tools that render maps **inline in the chat** for exploratory analysis, and the MCP server may also expose CARTO Workflows as MCP tools to execute saved analyses (see "CARTO Workflows exposed as MCP tools" below).

For the deck.gl declarative spec details — layer-source compatibility, `aggregationExp` rules, `mapStyle`, etc. — read the `view_map` tool description directly. This skill stays focused on routing and workflow recipes.

## Step 1 — detect what's available

Skills load on user intent, but the actual tools may or may not be attached. Check before routing:

| What | How to detect |
|---|---|
| **MCP server attached** | Tools named `view_map`, `load_builder_map`, `list_maps`, `list_connections`, `search_resources`, `get_column_stats` are in your tool list. |
| **CARTO CLI installed** | `carto --version` succeeds in a shell. |
| **Host supports MCP Apps (interactive widgets)** | The host renders MCP UI resources (e.g., Claude.ai, Claude Desktop, ChatGPT). Hosts WITHOUT MCP Apps support (Gemini CLI, Codex CLI, plain MCP Inspector, current MCPJam) execute the tool but only show a text confirmation — no map widget renders inline. |

| Setup | What this skill does |
|---|---|
| **MCP + CLI both available, MCP Apps supported** | Route by intent (next section). Inline preview renders. |
| **MCP + CLI both, MCP Apps NOT supported** | `view_map` / `load_builder_map` will run but produce no visible map. Prefer CLI paths for visualization (`carto maps create` + `carto maps screenshot`); use MCP only for discovery (`list_connections`, `search_resources`, `get_column_stats`) and Workflow execution. Tell the user upfront that the host can't render maps inline. |
| **MCP only, MCP Apps supported** | Stay in MCP. CLI parts don't apply. |
| **MCP only, MCP Apps NOT supported** | Visualization isn't really possible here — surface that to the user, suggest installing the CLI or switching to a host that supports MCP Apps. Discovery and Workflow execution still work. |
| **CLI only** | Wrong skill — use `carto-create-builder-maps` instead. |
| **Neither** | Tell the user they need to install the CLI (`npm install -g @carto/carto-cli`) or attach the CARTO MCP server in their host. Don't proceed silently. |

If MCP is the right path but its tools aren't present (or MCP Apps aren't supported and visualization is the goal), surface that to the user — don't fall back to a generic visualization widget.

## MCP vs CLI routing

| User intent | Pick |
|---|---|
| "Show me X on a map" / "Visualize Y" — inline, exploratory, throwaway | **MCP** `view_map` (or `load_builder_map` if a saved map matches) |
| "Make a heatmap / cluster of points" — ad-hoc density | **MCP** `view_map` |
| "Color by quantiles / categories" — data-aware styling | **MCP** `view_map` + `get_column_stats` |
| "Open my retail-stores map" / saved map by name | **MCP** `list_maps` → `load_builder_map` |
| Run a saved analytical Workflow ("compute trade areas", "find hotspots", "enrich with demographics") | **MCP** if the matching CARTO Workflow is exposed as a tool — see "CARTO Workflows exposed as MCP tools" below |
| "Create a permanent / shareable map" | **CLI** (`carto-create-builder-maps`) |
| "Save / publish / edit a saved map" | **CLI** |
| Headless / scripted authoring | **CLI** |

**Rule of thumb:** MCP for *what does this look like?* CLI for *I want to keep this and share it*.

## Default discovery flow (MCP)

For open questions about the user's data ("what tables do I have", "do we have anything about retail"):

1. `list_connections` → identify the right connection (often `carto_dw`).
2. `search_resources` (by name) or `list_resources` (browse by FQN) to find a table.
3. `get_column_stats` if styling by an unfamiliar column — required before specifying `colorBins` domain values.
4. `view_map` (or `load_builder_map` if a saved map already answers — see next).

Always prefer surfacing the user's existing assets (`list_maps`, their workflows) before generating new visualizations.

## Saved-map workflow (`load_builder_map`)

Triggers when the user references a saved map by name/topic ("show me the retail-stores map", "open my last week's analysis").

1. **Search first.** `list_maps({ search: "<topic>" })`. Use `mine_only: true` if the user said "my map".
2. **Match handling:**
   - 1 match → `load_builder_map({ mapId: <id> })`.
   - >1 matches → list names + dates + thumbnails; ask the user to pick.
   - 0 matches → tell the user; offer `view_map` as an ad-hoc alternative.
3. **Set expectations.** The preview is **lightweight**: layers, basemap, viewport, popups, legend. Widgets, SQL parameters, map description, AI agents, and other Builder-only features are NOT included. Tell the user; they can click **"Open in Builder"** in the rendered widget for the full experience.

## Post-CLI-creation preview workflow

When the user creates a map via `carto maps create` (from `carto-create-builder-maps`), the response is a `mapId` + Builder URL. With MCP attached, preview inline immediately instead of clicking out:

```
# After: carto maps create returns { mapId: "abc-123", ... }
load_builder_map({ mapId: "abc-123" })
```

This is the fastest authoring loop: edit, save via CLI, preview inline via MCP, repeat. Especially useful for styling iterations.

Caveat: still the lightweight preview. If the user is debugging widgets or SQL parameters, they'll need to "Open in Builder" — those won't show inline.

## Workflows-as-MCP-tools

If the user's account has saved workflows published as MCP tools, they appear in your tool list dynamically (one tool per workflow, named after it). Invoke them like any other MCP tool. For long-running async workflows, poll `async_workflow_job_get_status` until done, then fetch via `async_workflow_job_get_results`.

## Anti-patterns to avoid

- **Falling back to a generic visualization widget when MCP is attached.** If `view_map` is in the tool list and the user asks for a map, use it.
- **`view_map` for a saved map referenced by name.** Search via `list_maps` first.
- **Hardcoded `colorBins` domain values without `get_column_stats`.** Always fetch real percentiles for unfamiliar columns.
- **Mixing tile schemes** (e.g., `vectorTableSource` → `HeatmapTileLayer`) — silent empty render. The `view_map` tool description has the full compatibility matrix.
- **Treating the `load_builder_map` preview as full-fidelity Builder.** Always communicate the lightweight nature and the "Open in Builder" path.

## Cartography for `view_map` specs

For cartographic decisions on `view_map` specs (which layer for the story, scale type, palette family, basemap pairing, stroke conventions, drawing order, multi-layer hue separation, picking, anti-patterns, worked recipes), read [`references/cartography.md`](references/cartography.md) in this skill — it's grounded in the actual `@deck.gl/carto` declarative API.

The cartography reference under `carto-create-builder-maps` (`references/cartography.md` there) is **Builder-specific** (kepler config) — its JSON shapes do NOT apply to deck.gl declarative specs. The principles overlap; the encodings don't.
