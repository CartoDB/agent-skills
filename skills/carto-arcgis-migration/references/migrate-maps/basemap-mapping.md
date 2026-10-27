# Basemap mapping — Esri basemap → CARTO basemap

ArcGIS Web Maps store the basemap in `baseMap.baseMapLayers[]` plus `baseMap.title`. CARTO Builder uses **two** fields, both required and synced:

- `keplerMapConfig.config.basemapConfig` — `{ styleId }` (plus the optional `visibleLayerGroups`). `styleId` alone routes the basemap to its provider.
- `keplerMapConfig.config.mapStyle` — `{ styleType }`. Mirror of `basemapConfig.styleId`. Tier-1 rejects desync.

**There is no `type` field.** `basemapConfig` accepts only `styleId` (required) and `visibleLayerGroups`; anything else is dropped. The provider is implied by the id — `satellite` is a Google basemap whether or not you say so. See [`mapconfig-defaults.md`](mapconfig-defaults.md) "`basemapConfig.type` — always omit".

This file maps Esri's standard basemap titles/IDs to the closest CARTO equivalent. Custom basemaps fall back to `voyager` and are recorded as `Notes: basemap-fallback: <source-name>`. Source-of-truth for canonical styleIds is `carto-create-builder-maps/references/basemap.md`; this document mirrors it.

## Esri basemap → CARTO basemap

| Esri basemap (`baseMap.title` or layer URL pattern) | CARTO `styleId` | Notes |
|---|---|---|
| `Topographic` / `World_Topo_Map` | `voyager` | Closest analogue — labels + terrain |
| `Streets` / `World_Street_Map` | `voyager` | Standard street basemap |
| `Streets (Night)` / `World_Street_Map (Night)` | `dark-matter` | Dark vector |
| `Light Gray Canvas` / `World_Light_Gray_Base` | `positron` | Light minimal canvas |
| `Dark Gray Canvas` / `World_Dark_Gray_Base` | `dark-matter` | Dark minimal canvas |
| `Imagery` / `World_Imagery` | `satellite` | Satellite/aerial imagery — **canonical id is `satellite`, NOT `google-satellite`** |
| `Imagery Hybrid` / `Imagery_with_Labels` / `Imagery_Clarity` | `hybrid` | Imagery with labels |
| `Terrain with Labels` / `World_Terrain_Base + labels` | `terrain` | Terrain |
| `Streets` (when explicitly Google-style) | `roadmap` | Plain Google road map |
| `Oceans` / `World_Ocean_Base` | `voyager` | No exact match; voyager closest |
| `OpenStreetMap` | `voyager` | OSM-derived |
| `National Geographic` / `NatGeo_World_Map` | `voyager` | No exact match |
| `Terrain` / `World_Terrain_Base` (no labels) | `voyager` | No exact match |
| `USA Topo Maps` | `voyager` | No exact match |
| `Charted Territory` / `Modern Antique` (style) | `voyager` | Stylized; no exact match |
| `Mid-Century` / `Newspaper` (style) | `positron` | Print-styled; positron closest |
| `Nova` (style) | `dark-matter` | Dark-styled |
| Any custom URL or custom `id` not listed | `voyager` (fallback) | Record `Notes: basemap-fallback: <source-name>` |

The full set of Google styleIds available in Builder: `roadmap`, `google-positron`, `google-dark-matter`, `google-voyager`, `satellite`, `hybrid`, `terrain`, `google-3d`. (The `google-positron` / `google-dark-matter` / `google-voyager` variants are CARTO-style cartography served on Google's tile infrastructure — useful for orgs that want consistent CARTO styling but with Google's labels/place data underneath. `google-3d` is the photorealistic 3D Tiles basemap.)

Those eight plus `positron`, `dark-matter` and `voyager` are the eleven canonical ids. Anything else renders positron unless it is a tenant custom style declared as described under "Custom basemaps".

The mapping favors readability over exact stylistic match. `voyager` is CARTO's general-purpose default; `positron` and `dark-matter` are minimalist canvases optimized for data overlay.

## Setting both fields

Write **both** `basemapConfig` and `mapStyle`, with the same id in each. The shape is identical whatever the provider:

```jsonc
// CARTO basemap
{
  "config": {
    "basemapConfig": { "styleId": "positron" },
    "mapStyle":      { "styleType": "positron" }
  }
}

// Google basemap — same shape, different id
{
  "config": {
    "basemapConfig": { "styleId": "satellite" },
    "mapStyle":      { "styleType": "satellite" }
  }
}
```

The Builder UI reads `basemapConfig`; the deck.gl/carto `fetchMap` light screenshot engine and viewer SSR read `mapStyle.styleType` exclusively. Writing only one — or letting the two ids drift apart — produces a map that creates cleanly but shows a different basemap depending on where it is opened.

## Detection

Read `baseMap.title` first — most reliable:

```python
title = web_map.get("baseMap", {}).get("title", "")
style_id = TITLE_TO_CARTO.get(title)  # returns a styleId
if style_id:
    return style_id
```

If title is missing, doesn't match, or is localized (e.g. `Imágenes` for Spanish locales), scan `baseMap.baseMapLayers[].url` — these are stable across UI locales:

```python
patterns = {
    # (URL needle): basemapConfig.styleId
    "World_Topo_Map":         "voyager",
    "World_Street_Map":       "voyager",
    "World_Light_Gray_Base":  "positron",
    "World_Dark_Gray_Base":   "dark-matter",
    "World_Imagery":          "satellite",
    "Imagery_with_Labels":    "hybrid",
    "World_Terrain_Base":     "voyager",
    "OpenStreetMap":          "voyager",
}
for layer in web_map.get("baseMap", {}).get("baseMapLayers", []):
    url = layer.get("url", "")
    for needle, style_id in patterns.items():
        if needle in url:
            return style_id
return "voyager"  # fallback
```

When falling back, record `Notes: basemap-fallback: <baseMap.title or first layer URL>` on the manifest entry.

## User override

If the manifest entry has a `Basemap override:` field set by the user before invoking the skill, respect that override and skip the auto-mapping:

```markdown
### Sales Dashboard 2024 (Web Map)
- Source Item ID: c2f...
- ...
- Basemap override: positron
```

The override is a styleId — write it into `basemapConfig.styleId` and mirror it into `mapStyle.styleType`. Nothing else is derived from it: there is no provider field to keep in step.

An override naming an organization-defined custom style needs the `custom:` prefix and a matching `customBaseMaps.customStyle` entry — see "Custom basemaps" below.

The skill doesn't validate the override against the org's available basemaps. `carto maps validate` flags an id that is a near-miss of a canonical one (`darkmatter` → `dark-matter`), but it cannot tell a genuine tenant custom id from a typo'd one.

## Google basemaps

Google basemaps work without an org-level Google Maps API key in current CARTO orgs — earlier guidance to fall back to `voyager` when no key is configured was based on a misdiagnosis. Don't preemptively swap a Google styleId for `voyager`; emit the Google config faithfully and verify it renders.

What you DO need to get right:

1. The canonical Google styleIds are 1-word: `roadmap`, `satellite`, `hybrid`, `terrain` — NOT `google-roadmap` / `google-satellite` / etc. Builder falls back to `positron` for any unknown id, so the wrong styleId renders silently as the wrong basemap.
2. The `google-positron` / `google-dark-matter` / `google-voyager` variants ARE valid styleIds — those are CARTO cartography served on Google tile infrastructure (different product from the 3 plain CARTO basemaps).
3. The id is the only thing to get right. There is no provider field to pair it with.

## Verifying Google basemaps render

`carto maps validate` flags a styleId that is a near-miss of a canonical one, but an id that resembles nothing canonical passes and renders positron. The only reliable verification step is a screenshot — and only the `full` engine can render Google tiles.

| Engine | Renders Google basemaps? |
|---|---|
| `--render-engine light` (deck.gl/carto `fetchMap`) | NO — MapLibre-only; Google styleIds render as a CARTO/OSM fallback canvas regardless of config |
| `--render-engine full` (Chromium `/viewer` SSR) | YES — uses the workspace-www viewer with Google Maps SDK |

Always run `carto maps screenshot <id> --render-engine full` after migrating a Web Map with a Google basemap, and confirm satellite imagery + the Google logo + an "Imagery © …" attribution appear in the result. If the screenshot shows a CARTO/OSM canvas instead, the styleId is wrong — fix and re-screenshot.

## Custom basemaps

The user's ArcGIS portal may have organization-specific custom basemaps (a tile service or a published basemap item). Custom basemaps require manual configuration in CARTO (Builder → custom basemap UI) and are out of scope for batch migration. Always fall back to `voyager` and record the source basemap title in `Notes:` so the user can decide whether to create a matching custom basemap manually.

If the user has already set one up and overrides the basemap to it, the reference has two halves that must agree: `basemapConfig.styleId` is the account basemap id **prefixed** `custom:` (e.g. `custom:<accountBasemapId>`), and `keplerMapConfig.config.customBaseMaps.customStyle.id` holds that same string. The prefix is the switch — without it Builder and fetchMap skip the custom lookup and fall back to positron, and no validation can tell an unprefixed custom id from a typo. The style's own configuration belongs in `customBaseMaps.customStyle`, not in `basemapConfig`, which takes nothing beyond `styleId` and `visibleLayerGroups`.

## Validate after composition

After setting the basemap, run `carto maps validate` — Tier-1 catches `basemapConfig.styleId !== mapStyle.styleType` (sync mismatch) and flags a styleId that is a near-miss of a canonical value, with the suggestion. It cannot detect an unprefixed custom id. Visual verification via `--render-engine full` is the only authoritative gate for Google basemaps.

If a CARTO styleId this document recommends is rejected by Tier-1, fetch the live list:

```bash
carto maps schema kepler --json   # then look under config.basemapConfig.styleId
carto maps schema mapstyle --json
```

and align the mapping. Then update this document via the lessons-merge flow.
