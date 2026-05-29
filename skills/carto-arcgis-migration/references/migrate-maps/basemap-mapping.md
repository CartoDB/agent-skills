# Basemap mapping — Esri basemap → CARTO basemap

ArcGIS Web Maps store the basemap in `baseMap.baseMapLayers[]` plus `baseMap.title`. CARTO Builder uses **two** fields, both required and synced:

- `keplerMapConfig.config.basemapConfig` — `{ type, styleId }`. The `type` is the **provider discriminator**: `"carto"` for the 3 CARTO built-ins, `"google"` for Google variants, `"custom"` for an organization MapLibre style.
- `keplerMapConfig.config.mapStyle` — `{ styleType }`. Mirror of `basemapConfig.styleId`. Tier-1 rejects desync (`carto-cli/src/schemas/crossField/basemapSync.ts`).

`type` matters: setting `type: "carto"` with a Google styleId puts the basemap into a hybrid namespace where neither renderer claims it, the viewer silently falls back, and Tier-1 doesn't catch it. Always pair the `type` to the styleId's provider family.

This file maps Esri's standard basemap titles/IDs to the closest CARTO equivalent. Custom basemaps fall back to `voyager` and are recorded as `Notes: basemap-fallback: <source-name>`. Source-of-truth for canonical styleIds is `carto-create-builder-maps/references/basemap.md`; this document mirrors it.

## Esri basemap → CARTO basemap

| Esri basemap (`baseMap.title` or layer URL pattern) | CARTO `type` | CARTO `styleId` | Notes |
|---|---|---|---|
| `Topographic` / `World_Topo_Map` | `carto` | `voyager` | Closest analogue — labels + terrain |
| `Streets` / `World_Street_Map` | `carto` | `voyager` | Standard street basemap |
| `Streets (Night)` / `World_Street_Map (Night)` | `carto` | `dark-matter` | Dark vector |
| `Light Gray Canvas` / `World_Light_Gray_Base` | `carto` | `positron` | Light minimal canvas |
| `Dark Gray Canvas` / `World_Dark_Gray_Base` | `carto` | `dark-matter` | Dark minimal canvas |
| `Imagery` / `World_Imagery` | `google` | `satellite` | Satellite/aerial imagery — **canonical id is `satellite`, NOT `google-satellite`** |
| `Imagery Hybrid` / `Imagery_with_Labels` / `Imagery_Clarity` | `google` | `hybrid` | Imagery with labels |
| `Terrain with Labels` / `World_Terrain_Base + labels` | `google` | `terrain` | Terrain |
| `Streets` (when explicitly Google-style) | `google` | `roadmap` | Plain Google road map |
| `Oceans` / `World_Ocean_Base` | `carto` | `voyager` | No exact match; voyager closest |
| `OpenStreetMap` | `carto` | `voyager` | OSM-derived |
| `National Geographic` / `NatGeo_World_Map` | `carto` | `voyager` | No exact match |
| `Terrain` / `World_Terrain_Base` (no labels) | `carto` | `voyager` | No exact match |
| `USA Topo Maps` | `carto` | `voyager` | No exact match |
| `Charted Territory` / `Modern Antique` (style) | `carto` | `voyager` | Stylized; no exact match |
| `Mid-Century` / `Newspaper` (style) | `carto` | `positron` | Print-styled; positron closest |
| `Nova` (style) | `carto` | `dark-matter` | Dark-styled |
| Any custom URL or custom `id` not listed | `carto` | `voyager` (fallback) | Record `Notes: basemap-fallback: <source-name>` |

The full set of Google styleIds available in Builder: `roadmap`, `google-positron`, `google-dark-matter`, `google-voyager`, `satellite`, `hybrid`, `terrain`. (The `google-positron` / `google-dark-matter` / `google-voyager` variants are CARTO-style cartography served on Google's tile infrastructure — useful for orgs that want consistent CARTO styling but with Google's labels/place data underneath.)

The mapping favors readability over exact stylistic match. `voyager` is CARTO's general-purpose default; `positron` and `dark-matter` are minimalist canvases optimized for data overlay.

## Setting both fields

Write **both** `basemapConfig` and `mapStyle`. Pair the `type` to the styleId's provider:

```jsonc
// CARTO basemap
{
  "config": {
    "basemapConfig": { "type": "carto", "styleId": "positron" },
    "mapStyle":      { "styleType": "positron" }
  }
}

// Google basemap
{
  "config": {
    "basemapConfig": { "type": "google", "styleId": "satellite" },
    "mapStyle":      { "styleType": "satellite" }
  }
}
```

The Builder UI reads `basemapConfig`; the deck.gl/carto `fetchMap` light screenshot engine and viewer SSR still read `mapStyle.styleType`. Writing only one — or pairing the wrong `type` to the styleId — produces a map that creates cleanly but renders inconsistently.

## Detection

Read `baseMap.title` first — most reliable:

```python
title = web_map.get("baseMap", {}).get("title", "")
mapped = TITLE_TO_CARTO.get(title)  # returns (type, styleId)
if mapped:
    return mapped
```

If title is missing, doesn't match, or is localized (e.g. `Imágenes` for Spanish locales), scan `baseMap.baseMapLayers[].url` — these are stable across UI locales:

```python
patterns = {
    # (URL needle): (basemapConfig.type, basemapConfig.styleId)
    "World_Topo_Map":         ("carto",  "voyager"),
    "World_Street_Map":       ("carto",  "voyager"),
    "World_Light_Gray_Base":  ("carto",  "positron"),
    "World_Dark_Gray_Base":   ("carto",  "dark-matter"),
    "World_Imagery":          ("google", "satellite"),
    "Imagery_with_Labels":    ("google", "hybrid"),
    "World_Terrain_Base":     ("carto",  "voyager"),
    "OpenStreetMap":          ("carto",  "voyager"),
}
for layer in web_map.get("baseMap", {}).get("baseMapLayers", []):
    url = layer.get("url", "")
    for needle, mapped in patterns.items():
        if needle in url:
            return mapped
return ("carto", "voyager")  # fallback
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

The override is a styleId — derive the matching `type` from the styleId family:

| styleId | type |
|---|---|
| `positron` / `dark-matter` / `voyager` | `carto` |
| `roadmap` / `satellite` / `hybrid` / `terrain` / `google-positron` / `google-dark-matter` / `google-voyager` | `google` |
| organization-defined custom id | `custom` (also persist `customBaseMaps.customStyle` per `carto-create-builder-maps/references/basemap.md`) |

The skill doesn't validate the override against the org's available basemaps — `carto maps validate` will catch invalid IDs but **will NOT catch a wrong `type`** (see "Verifying Google basemaps render" below).

## Google basemaps

Google basemaps work without an org-level Google Maps API key in current CARTO orgs — earlier guidance to fall back to `voyager` when no key is configured was based on a misdiagnosis. Don't preemptively swap a Google styleId for `voyager`; emit the Google config faithfully and verify it renders.

What you DO need to get right:

1. `basemapConfig.type` MUST be `"google"` for Google styleIds. `type: "carto"` with a Google styleId silently falls back to a CARTO canvas at render time. Tier-1 doesn't catch this.
2. The canonical Google styleIds are 1-word: `roadmap`, `satellite`, `hybrid`, `terrain` — NOT `google-roadmap` / `google-satellite` / etc. Builder typo-falls-back to `positron` for any unknown id, so the wrong styleId also renders silently as the wrong basemap.
3. The `google-positron` / `google-dark-matter` / `google-voyager` variants ARE valid styleIds — those are CARTO cartography served on Google tile infrastructure (different product from the 3 plain CARTO basemaps).

## Verifying Google basemaps render

`carto maps validate` and `carto maps create` accept both shape mistakes (wrong `type`, non-canonical styleId) silently. The only reliable verification step is a screenshot — and only the `full` engine can render Google tiles.

| Engine | Renders Google basemaps? |
|---|---|
| `--render-engine light` (deck.gl/carto `fetchMap`) | NO — MapLibre-only; Google styleIds render as a CARTO/OSM fallback canvas regardless of config |
| `--render-engine full` (Chromium `/viewer` SSR) | YES — uses the workspace-www viewer with Google Maps SDK |

Always run `carto maps screenshot <id> --render-engine full` after migrating a Web Map with a Google basemap, and confirm satellite imagery + the Google logo + an "Imagery © …" attribution appear in the result. If the screenshot shows a CARTO/OSM canvas instead, the `type` or styleId is wrong — fix and re-screenshot.

## Custom basemaps

The user's ArcGIS portal may have organization-specific custom basemaps (a tile service or a published basemap item). Custom basemaps require manual configuration in CARTO (Builder → custom basemap UI) and are out of scope for batch migration. Always fall back to `voyager` and record the source basemap title in `Notes:` so the user can decide whether to create a matching custom basemap manually.

## Validate after composition

After setting the basemap, run `carto maps validate` — Tier-1 catches `basemapConfig.styleId !== mapStyle.styleType` (sync mismatch). It does **NOT** catch a wrong `type` discriminator or a non-canonical styleId. Visual verification via `--render-engine full` is the only authoritative gate for Google basemaps.

If a CARTO styleId this document recommends is rejected by Tier-1, fetch the live list:

```bash
carto maps schema [section]
```

and align the mapping. Then update this document via the lessons-merge flow.
