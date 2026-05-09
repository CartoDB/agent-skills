---
name: carto-mcp-server
description: Use when the user wants inline/exploratory map visualization, references a saved CARTO Builder map by name/topic, or wants to preview the result of a CLI map creation without leaving the chat. Covers the CARTO MCP server's view_map (ad-hoc deck.gl declarative), load_builder_map (lightweight preview of a saved map), list_maps, get_column_stats, and discovery tools. Distinct from carto-create-builder-maps (CLI authoring of permanent maps) — this skill handles the inline/explorative path. Triggers on "show me X on a map", "visualize Y", "make a heatmap of Z", "open the <name> map", and post-creation preview flows.
license: MIT
---

# carto-mcp-server

The CARTO MCP Server is the AI integration into the user's CARTO platform — workspace, saved Builder maps, workflows, and connected data warehouses. It exposes tools that render maps **inline in the chat** for exploratory analysis.

This skill is the **routing and workflow** layer for using the MCP server alongside (or instead of) the CARTO CLI. It does NOT duplicate the MCP tool descriptions — for the deck.gl declarative spec, layer-source compatibility, `aggregationExp` rules, etc., **read the `view_map` tool description directly**. Re-deriving any of that here is a drift risk.

## Step 1 — detect what's available

Skills load on user intent, but the actual tools may or may not be attached. Check before routing:

| What | How to detect |
|---|---|
| **MCP server attached** | Tools named `view_map`, `load_builder_map`, `list_maps`, `list_connections`, `search_resources`, `get_column_stats` are in your tool list. |
| **CARTO CLI installed** | `carto --version` succeeds in a shell. |

| Setup | What this skill does |
|---|---|
| **MCP + CLI both available** | Route by intent (next section). |
| **MCP only** | Stay in MCP. CLI parts of this skill don't apply. |
| **CLI only** | Wrong skill — use `carto-create-builder-maps` instead. |
| **Neither** | Tell the user they need to install the CLI (`npm install -g @carto/carto-cli`) or attach the CARTO MCP server in their host. Don't proceed silently. |

If MCP is the right path but its tools aren't present, surface that to the user — don't fall back to a generic visualization widget.

## MCP vs CLI routing

| User intent | Pick |
|---|---|
| "Show me X on a map" / "Visualize Y" — inline, exploratory, throwaway | **MCP** `view_map` (or `load_builder_map` if a saved map matches) |
| "Make a heatmap / cluster of points" — ad-hoc density | **MCP** `view_map` |
| "Color by quantiles / categories" — data-aware styling | **MCP** `view_map` + `get_column_stats` |
| "Open my retail-stores map" / saved map by name | **MCP** `list_maps` → `load_builder_map` |
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

The cartography reference under `carto-create-builder-maps` (`references/cartography.md`) is **Builder-specific** (kepler config) — its JSON shapes do NOT apply to deck.gl declarative specs. For deeper deck.gl declarative cartography (palette choice, scale type, basemap pairing, multi-layer hue separation, anti-patterns), look for a future `carto-cartography-deckgl` skill.

For now, the `view_map` tool description carries the spec rules; this skill only owns the routing and workflow decisions.
