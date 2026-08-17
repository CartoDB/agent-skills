---
name: carto-render-inline-map
description: Render an ad-hoc interactive map inline in the chat from a deck.gl declarative spec via the CARTO MCP server's view_map tool. Use whenever the user asks to map, visualize, or show the geographic distribution of points, polygons, hexagons, quadbins, clusters, density (heatmaps), or raster — and the map is exploratory or throwaway, not meant to be saved as a permanent CARTO Builder map. Triggers on "show me X on a map", "visualize Y", "make a heatmap of Z", "render the points/clusters/raster of W". Distinct from carto-create-builder-maps (authoring permanent maps), carto-preview-builder-map (loading an existing saved Builder map), and carto-develop-app (writing a from-scratch deck.gl app in TypeScript / JavaScript).
license: MIT
---

# carto-render-inline-map

Renders an ad-hoc interactive map inline in the chat via the CARTO MCP server's `view_map` tool. The agent emits a `@deck.gl/json` declarative spec; the renderer handles credentials, basemap, and tooltips. The user sees the map without leaving the chat.

**Legend required after every render.** The `view_map` renderer does NOT show an auto-legend. After invoking `view_map`, render a legend through the host's widget surface (e.g., `show_widget` in Claude.ai / Claude Desktop) — that is the ONLY visual transport that works. Chat-message HTML is escaped by every major host's renderer and appears as raw text — DO NOT emit HTML in your chat reply. If the host has no widget tool, fall back to a plain-text legend (markdown bullets with emoji color squares per bucket, hex codes in parentheses). The full HTML template, style rules, and per-helper variants (`colorBins` swatches, `colorContinuous` gradient bar, `colorCategories` per-category, raster ternary-bucket + nodata) live in the `view_map` tool description's LEGEND section. Applies to ad-hoc `view_map` specs ONLY; a saved Builder map loaded inline (see `carto-preview-builder-map`) carries its own Builder-native legend.

**Tool contract.** This skill consumes the `view_map` tool exposed by the CARTO MCP server. The tool's input shape (`deckglProps`), layer-source compatibility, `aggregationExp` requirements, and `@@=` expression-eval restrictions are documented in the tool's own MCP description — read it via the MCP host's tool-inspector or by calling `tools/list`. This skill stays focused on routing, cartography, and the agent's reply; it does NOT duplicate the tool's spec.

This skill is **MCP-only**: `view_map` renders inline ONLY on the CARTO MCP server, and ONLY on hosts that support MCP Apps (Claude.ai, Claude Desktop, ChatGPT). There is no CLI equivalent for inline rendering. `view_map` is offered on both OAuth and token MCP sessions.

## Step 1 — detect what's available

For detection signals and host support, see [carto-basics/references/access-paths.md](../carto-basics/references/access-paths.md). Quick check: `view_map` must be in your tool list, and the host must render MCP Apps.

| Setup | What to do |
|---|---|
| `view_map` present + host renders | Proceed normally. |
| `view_map` present + host doesn't render (Gemini CLI, Codex CLI, MCP Inspector, MCPJam — text-only) | Tell the user the host can't render maps inline; suggest switching hosts or — where a shell is available — `carto-create-builder-maps` + `carto maps screenshot` for a PNG. |
| `view_map` not present | The MCP server isn't attached. Tell the user; don't fall back to a generic visualization widget. |

## When to pick a different skill

- **Permanent / shareable map** → `carto-create-builder-maps` (`create_map` over MCP, or the `carto maps` CLI). `view_map` specs aren't saved or shareable as URLs; they live in the chat.
- **Open an existing saved map by name/URL/ID** → `carto-preview-builder-map`. That skill resolves the saved map via `read_maps` and renders it inline.
- **Writing a TypeScript/JavaScript app from scratch** → `carto-develop-app`. Different runtime (full deck.gl surface in JS), different cartography rules.

## Discovery flow before composing the spec

Discovery runs through the **`explore_data`** MCP tool (available on OAuth and token sessions). Its methods are what the cartography reference writes bare as `list_connections`, `search`, `list_resources`, `describe`.

1. `explore_data` (`list_connections`) → identify the right connection (often `carto_dw`).
2. `explore_data` (`search` by name, or `list_resources` by FQN) to find the table.
3. **Always fetch column stats via `explore_data` (`describe`, stats mode) for any unfamiliar numeric column you'll bin on** — quantiles, min, max, categories. Skipping this and hardcoding `colorBins` thresholds is the #1 styling failure mode.
4. Compose the `view_map` spec.

## Composition essentials

For the full deck.gl declarative spec — layer-source compatibility, `aggregationExp` rules, `mapStyle` URLs, `@@function` shapes, expression-eval restrictions — read the `view_map` tool description directly. This skill stays focused on routing and cartographic decisions.

For cartographic decisions on the spec (palette, scale, basemap, stroke, drawing order, hierarchy, picking, anti-patterns, worked recipes), read [`references/cartography.md`](references/cartography.md). Mandatory before composing any styled spec.

## Routing anti-patterns

- **Falling back to a generic visualization widget when `view_map` is available.** If the tool is in your list, use it.
- **Hand-building a spec for a saved map referenced by name.** Switch to `carto-preview-builder-map` and resolve it via `read_maps` first.
- **Treating an inline preview as a saved/shareable map.** It isn't — specs live in the chat. If the user wants to keep it, route to `carto-create-builder-maps`.

(Spec-composition anti-patterns — tile-scheme mismatches, generic layers, hardcoded bins — are in [`references/cartography.md`](references/cartography.md) §9.)

## Post-creation preview

After a permanent map is created via `carto-create-builder-maps` (`create_map` over MCP, or `carto maps create` on the CLI), verify it inline by loading the saved map by its `mapId` (`carto-preview-builder-map`) — NOT a re-rendered ad-hoc spec.
