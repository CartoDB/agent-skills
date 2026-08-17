---
name: carto-preview-builder-map
description: Preview an existing saved CARTO Builder map inline in the chat via the CARTO MCP server — resolve the map with read_maps (by name or search), then render it with view_map by map ID. Use whenever the user references a saved Builder map — by URL, by ID, or by name. Renders a lightweight read-only preview (layers, basemap, viewport, popups, legend). Widgets, SQL parameters, map description, and other Builder-only features are NOT included; the user can click "Open in Builder" for the full experience. Triggers on "show me the X map", "open the Y map", "preview the Z map", and inline previews of a freshly-created map. Distinct from carto-create-builder-maps (authoring), carto-render-inline-map (ad-hoc deck.gl spec), and carto-develop-app (developer app).
license: MIT
---

# carto-preview-builder-map

Renders a lightweight inline preview of an existing saved CARTO Builder map via the CARTO MCP server. The user references the map (by URL, ID, or name); the agent resolves it with `read_maps` and loads it inline with `view_map`.

**Tool contract.** This skill consumes the `read_maps` and `view_map` tools exposed by the CARTO MCP server. The tools' input shapes and access-control rules (the user must own, be shared on, or have public access to the map) are documented in the tools' own MCP descriptions — read them via the MCP host's tool-inspector or by calling `tools/list`. This skill stays focused on routing, name → ID resolution, and setting expectations on the lightweight preview; it does NOT duplicate the tools' specs.

This skill is **MCP-only** — there's no CLI equivalent for inline rendering — and needs an MCP-Apps host (Claude.ai, Claude Desktop, ChatGPT). Detection signals and host support: [carto-basics/references/access-paths.md](../carto-basics/references/access-paths.md).

## Step 1 — detect what's available

Both `view_map` and `read_maps` must be in your tool list, and the host must render MCP Apps. **Token vs OAuth:** on a token MCP session `view_map` is offered but `read_maps` is not — loading by explicit URL/ID still works; name-based search needs an OAuth session (or ask the user for the map URL).

| Setup | What to do |
|---|---|
| Tools present + host renders | Proceed normally. |
| Tools present + host doesn't render (Gemini CLI, Codex CLI, MCP Inspector, MCPJam — text-only) | Tell the user the host can't render maps inline; suggest opening the Builder URL directly. |
| `view_map` not present | The MCP server isn't attached. Tell the user; don't try to reconstruct the saved map from scratch. |

## Resolution rules (URL / ID / name)

| User input | What to do |
|---|---|
| Builder URL `https://<workspace>.app.carto.com/builder/<mapId>` | Extract `<mapId>` from the URL; pass it to `view_map` directly. |
| Bare UUID | Pass it to `view_map` directly. |
| Name / topic ("the retail-stores map", "my last week's accidents analysis") | Search with `read_maps` first (by the topic hint), then load by ID. See match handling below. |

For name-based lookup, restrict to the user's own maps if they said "my map". Default sort is `updated_at desc` — most recently edited first.

## Match handling (after `read_maps`)

| Result | Action |
|---|---|
| 1 match | Load it via `view_map` with the matched ID. Confirm to the user which map you're loading by name. |
| >1 matches | List names + dates + thumbnails. Ask the user to pick. Don't guess. |
| 0 matches | Tell the user no saved map matches. Offer `carto-render-inline-map` (an ad-hoc `view_map` spec) as an alternative for the same data. |

## Set expectations on the preview (always)

The preview is **lightweight**:
- ✓ Layers, basemap, viewport, popups, legend — exactly as configured in Builder.
- ✗ Widgets, SQL parameters, map description, AI agent configuration, and other Builder-only features are NOT included.

After loading, tell the user: *"Loaded [name] as a lightweight preview. Widgets, SQL parameters, and the map description aren't included — click 'Open in Builder' in the rendered widget for the full experience."* Set this expectation BEFORE the user asks why the preview looks different from the live Builder map.

## Post-creation preview workflow

After a map is created via `carto-create-builder-maps` (`create_map` over MCP, or `carto maps create` on the CLI), pass the returned `mapId` to `view_map` to preview inline — the fastest edit → save → preview loop for styling iterations. Still the lightweight preview: debugging widgets or SQL parameters needs the full Builder.

## When to pick a different skill

- **Ad-hoc visualization, no saved map exists** → `carto-render-inline-map` (an ad-hoc `view_map` spec).
- **Authoring / editing a permanent map** → `carto-create-builder-maps` (`create_map` / `update_map` over MCP, or the `carto maps` CLI).
- **Building a from-scratch deck.gl app** → `carto-develop-app`.

## Anti-patterns to avoid

- **Reconstructing a saved map from a hand-built deck.gl spec instead of loading it by ID.** If the user references an existing map, ALWAYS resolve via `read_maps` and load the saved map first. Re-rendering loses fidelity (saved layers, popups, legend) AND it's slower.
- **Skipping `read_maps` when the user references a map by name.** Don't guess the ID. Search first.
- **Promising widgets, SQL parameters, or map description in the preview.** They're not rendered. Set expectations upfront.
- **Picking the most-recent match silently when `read_maps` returns multiple.** Surface the choices and let the user pick.
