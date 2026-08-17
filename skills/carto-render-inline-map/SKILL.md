---
name: carto-render-inline-map
description: Render an ad-hoc interactive map inline in the chat from a deck.gl declarative spec via the CARTO MCP server's view_map tool. Use whenever the user asks to map, visualize, or show the geographic distribution of points, polygons, hexagons, quadbins, clusters, density (heatmaps), or raster — and the map is exploratory or throwaway, not meant to be saved as a permanent CARTO Builder map. Triggers on "show me X on a map", "visualize Y", "make a heatmap of Z", "render the points/clusters/raster of W". Distinct from carto-create-builder-maps (authoring permanent maps), carto-preview-builder-map (loading an existing saved Builder map), and carto-develop-app (writing a from-scratch deck.gl app in TypeScript / JavaScript).
license: MIT
---

# carto-render-inline-map

Renders an ad-hoc interactive map inline in the chat via the CARTO MCP server's `view_map` tool. The agent emits a `@deck.gl/json` declarative spec; the renderer handles credentials, basemap, and tooltips. The user sees the map without leaving the chat.

**Legend required after every render.** The `view_map` renderer does NOT show an auto-legend. After invoking `view_map`, render a legend through the host's widget surface (e.g., `show_widget` in Claude.ai / Claude Desktop) — that is the ONLY visual transport that works. Chat-message HTML is escaped by every major host's renderer and appears as raw text — DO NOT emit HTML in your chat reply. If the host has no widget tool, fall back to a plain-text legend (markdown bullets with emoji color squares per bucket, hex codes in parentheses). The full HTML template, style rules, and per-helper variants (`colorBins` swatches, `colorContinuous` gradient bar, `colorCategories` per-category, raster ternary-bucket + nodata) live in the `view_map` tool description's LEGEND section. Applies to ad-hoc `view_map` specs ONLY; a saved Builder map loaded inline (see `carto-preview-builder-map`) carries its own Builder-native legend.

**Tool contract.** This skill consumes the `view_map` tool exposed by the CARTO MCP server. The tool's input shape (`deckglProps`), layer-source compatibility, `aggregationExp` requirements, and `@@=` expression-eval restrictions are documented in the tool's own MCP description — read it via the MCP host's tool-inspector or by calling `tools/list`. This skill stays focused on routing, cartography, and the agent's reply; it does NOT duplicate the tool's spec.

This skill assumes the **CARTO MCP server is attached** (the `view_map` tool is in your tool list) AND the **host supports MCP Apps** (interactive widgets — Claude.ai, Claude Desktop, ChatGPT). If either is missing, see "Step 1 — detect what's available" below.

## Step 1 — detect what's available

| Check | How |
|---|---|
| `view_map` is callable | Tool name `view_map` is in your tool list. |
| Host renders MCP Apps | Hosts that DO: Claude.ai, Claude Desktop, ChatGPT. Hosts that DON'T (Gemini CLI, Codex CLI, plain MCP Inspector, current MCPJam) execute the tool but only show a text confirmation — no map widget. |

| Setup | What to do |
|---|---|
| Tool present + host renders | Proceed normally. |
| Tool present + host doesn't render | Tell the user the host can't render maps inline; suggest switching hosts or — where a shell is available — `carto-create-builder-maps` + `carto maps screenshot` for a PNG-based alternative. |
| Tool not present | The MCP server isn't attached. Tell the user; don't fall back to a generic visualization widget. |

## When to pick a different skill

- **Permanent / shareable map** → `carto-create-builder-maps` (`create_map` over MCP, or the `carto maps` CLI). `view_map` specs aren't saved or shareable as URLs; they live in the chat.
- **Open an existing saved map by name/URL/ID** → `carto-preview-builder-map`. That skill resolves the saved map via `read_maps` and renders it inline.
- **Writing a TypeScript/JavaScript app from scratch** → `carto-develop-app`. Different runtime (full deck.gl surface in JS), different cartography rules.

## Discovery flow before composing the spec

Discovery runs through the `explore_data` tool, which groups the methods this skill (and its cartography reference) names bare — `list_connections`, `search`, `list_resources`, `describe`.

1. `explore_data` (`list_connections`) → identify the right connection (often `carto_dw`).
2. `explore_data` (`search` by name, or `list_resources` by FQN) to find the table.
3. **Always fetch column stats via `explore_data` (`describe` in stats mode) for any unfamiliar numeric column you'll bin on** — quantiles, min, max, categories. Skipping this and hardcoding `colorBins` thresholds is the #1 styling failure mode.
4. Compose the `view_map` spec.

## Composition essentials

For the full deck.gl declarative spec — layer-source compatibility, `aggregationExp` rules, `mapStyle` URLs, `@@function` shapes, expression-eval restrictions — read the `view_map` tool description directly. This skill stays focused on routing and cartographic decisions.

For cartographic decisions on the spec (palette, scale, basemap, stroke, drawing order, hierarchy, picking, anti-patterns, worked recipes), read [`references/cartography.md`](references/cartography.md). Mandatory before composing any styled spec.

## Anti-patterns to surface or self-correct

- **Falling back to a generic visualization widget when `view_map` is available.** If the tool is in your list, use it.
- **Hand-building a spec for a saved map referenced by name.** Switch to `carto-preview-builder-map` and resolve it via `read_maps` first.
- **Hardcoded `colorBins` domain values without fetching stats.** Always fetch real percentiles for unfamiliar columns via `explore_data` (`describe`).
- **Mixing tile schemes** (e.g., `vectorTableSource` → `HeatmapTileLayer`). Silent empty render. The `view_map` tool description has the full compatibility matrix.
- **Generic deck.gl layers** (`ScatterplotLayer`, `HexagonLayer`, `GeoJsonLayer`, etc.). The MCP JSON converter only registers CARTO layers — anything else silently produces nothing.
- **Treating an inline preview as a saved/shareable map.** It isn't. If the user wants to keep it, route to `carto-create-builder-maps`.

## Post-creation preview pattern

When the user creates a permanent map via `carto-create-builder-maps` (`create_map` over MCP, or `carto maps create` on the CLI), the response is a `mapId` + Builder URL. The fastest way to verify the result inline is loading the saved map by that ID (see `carto-preview-builder-map`) — NOT a re-rendered ad-hoc spec. Hand off to that skill rather than reconstructing the spec from scratch.
