---
name: carto-preview-builder-map
description: Preview an existing saved CARTO Builder map inline in the chat via the CARTO MCP server's load_builder_map tool. Use whenever the user references a saved Builder map — by URL, by ID, or by name (resolved via list_maps first). Renders a lightweight read-only preview (layers, basemap, viewport, popups, legend). Widgets, SQL parameters, map description, and other Builder-only features are NOT included; the user can click "Open in Builder" for the full experience. Triggers on "show me the X map", "open the Y map", "preview the Z map", and post-CLI-creation inline previews of a freshly-created map. Distinct from carto-create-builder-maps (CLI authoring), carto-render-inline-map (ad-hoc deck.gl spec), and carto-develop-app (developer app).
license: MIT
---

# carto-preview-builder-map

Renders a lightweight inline preview of an existing saved CARTO Builder map via the CARTO MCP server's `load_builder_map` tool. The user references the map (by URL, ID, or name); the agent locates it and loads it inline.

**Tool contract.** This skill consumes the `load_builder_map` and `list_maps` tools exposed by the CARTO MCP server. The tools' input shapes and access-control rules (the user must own, be shared on, or have public access to the map) are documented in the tool's own MCP description — read it via the MCP host's tool-inspector or by calling `tools/list`. This skill stays focused on routing, name → ID resolution, and setting expectations on the lightweight preview; it does NOT duplicate the tool's spec.

This skill assumes the **CARTO MCP server is attached** (the `load_builder_map` and `list_maps` tools are in your tool list) AND the **host supports MCP Apps** (Claude.ai, Claude Desktop, ChatGPT). If either is missing, see "Step 1 — detect what's available" below.

## Step 1 — detect what's available

| Check | How |
|---|---|
| `load_builder_map` and `list_maps` are callable | Both tool names appear in your tool list. |
| Host renders MCP Apps | Hosts that DO: Claude.ai, Claude Desktop, ChatGPT. Hosts that DON'T (Gemini CLI, Codex CLI, plain MCP Inspector, current MCPJam) execute the tool but only show a text confirmation — no map widget. |

| Setup | What to do |
|---|---|
| Tools present + host renders | Proceed normally. |
| Tools present + host doesn't render | Tell the user the host can't render maps inline; suggest opening the Builder URL directly. |
| Tools not present | The MCP server isn't attached. Tell the user; don't try to reconstruct the saved map from scratch. |

## Resolution rules (URL / ID / name)

| User input | What to do |
|---|---|
| Builder URL `https://<workspace>.app.carto.com/builder/<mapId>` | Extract `<mapId>` from the URL; call `load_builder_map({ mapId })` directly. |
| Bare UUID | Call `load_builder_map({ mapId })` directly. |
| Name / topic ("the retail-stores map", "my last week's accidents analysis") | Call `list_maps({ search: "<topic>" })` first, then load by ID. See match handling below. |

For name-based lookup, use `mine_only: true` if the user said "my map". Default sort is `updated_at desc` — most recently edited first.

## Match handling (after `list_maps`)

| Result | Action |
|---|---|
| 1 match | `load_builder_map({ mapId: <id> })`. Confirm to the user which map you're loading by name. |
| >1 matches | List names + dates + thumbnails. Ask the user to pick. Don't guess. |
| 0 matches | Tell the user no saved map matches. Offer `carto-render-inline-map` (`view_map`) as an ad-hoc alternative for the same data. |

## Set expectations on the preview (always)

The preview is **lightweight**:
- ✓ Layers, basemap, viewport, popups, legend — exactly as configured in Builder.
- ✗ Widgets, SQL parameters, map description, AI agent configuration, and other Builder-only features are NOT included.
- ⚠ Newer styling fields may render but not yet appear in the legend swatch. Specifically: `lineStyle` (dashed / dotted polygon strokes and lines, Phase 1a of the line-polygon-stroke-styles initiative) draws correctly on the map but the legend may show a solid swatch until the MCP App picks up the meridian-ds geometry-aware-legend bump. Doesn't affect map readability — only the legend symbol.

After loading, tell the user: *"Loaded [name] as a lightweight preview. Widgets, SQL parameters, and the map description aren't included — click 'Open in Builder' in the rendered widget for the full experience."* Set this expectation BEFORE the user asks why the preview looks different from the live Builder map. If the map uses `lineStyle`, add: *"Dashed strokes render correctly; the legend swatch may show solid until the lightweight viewer catches up."*

## Post-CLI-creation preview workflow

When the user creates a permanent map via `carto maps create` (from `carto-create-builder-maps`), the response is a `mapId` + Builder URL. With the MCP server attached, preview inline immediately:

```
# carto maps create returned { mapId: "abc-123", ... }
load_builder_map({ mapId: "abc-123" })
```

This is the fastest authoring loop: edit, save via CLI, preview inline via MCP, repeat. Especially useful for styling iterations.

Caveat: still the lightweight preview. If the user is debugging widgets or SQL parameters, they need the full Builder experience.

## When to pick a different skill

- **Ad-hoc visualization, no saved map exists** → `carto-render-inline-map` (`view_map`).
- **Authoring / editing a permanent map** → `carto-create-builder-maps` (CLI).
- **Building a from-scratch deck.gl app** → `carto-develop-app`.

## Anti-patterns to avoid

- **Reconstructing a saved map via `view_map` instead of `load_builder_map`.** If the user references an existing map, ALWAYS try `list_maps` + `load_builder_map` first. Re-rendering loses fidelity (saved layers, popups, legend) AND it's slower.
- **Skipping `list_maps` when the user references a map by name.** Don't guess the ID. Search first.
- **Promising widgets, SQL parameters, or map description in the preview.** They're not rendered. Set expectations upfront.
- **Picking the most-recent match silently when `list_maps` returns multiple.** Surface the choices and let the user pick.
