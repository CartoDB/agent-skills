# Basemap configuration — `basemapConfig` + `mapStyle`

The basemap lives on **two parallel fields** inside `keplerMapConfig.config`. **Always write both, set them to the same `styleId` / `styleType` value.** Tier-1 rejects desync.

| Field | Status | Read by |
|---|---|---|
| `basemapConfig.styleId` + `visibleLayerGroups` | **Canonical / newer** | Builder editor + viewer (`workspace-www/src/features/builder/state/baseMapsSagas.ts:49-58` reads it first) |
| `mapStyle.styleType` + `visibleLayerGroups` | **Still load-bearing** | Screenshot light engine (deck.gl/carto `fetchMap`), workspace-www `/viewer` SSR, downstream tools using `fetchMap`. Omitting it crashes the screenshot CLI and breaks viewer rendering — verified 2026-04-29 against a live tenant |

**Why both.** `basemapConfig` is the direction of travel — Builder's saga prefers it. But `mapStyle` is what older code paths (deck.gl/carto fetchMap, viewer SSR) still read directly. Omitting `mapStyle` produces a map that creates cleanly (Tier-1 + backend accept it), opens fine in Builder, but blows up the moment anyone screenshots it or the public viewer SSRs it. The fix is one extra line; the failure is invisible until production.

```jsonc
"basemapConfig": { "styleId": "dark-matter" },
"mapStyle":      { "styleType": "dark-matter" }
```

The two values **must match** — Tier-1 (`carto-cli/src/schemas/crossField/basemapSync.ts`) rejects configurations where `basemapConfig.styleId !== mapStyle.styleType` because Builder's editor and the viewer would render different basemaps.

**Canonical ids** (the 10 CARTO built-ins):

| Group | Ids | Notes |
|---|---|---|
| CARTO basemaps | `positron`, `dark-matter`, `voyager` | Always work; no external dependency |
| Google Maps | `roadmap`, `google-positron`, `google-dark-matter`, `google-voyager`, `satellite`, `hybrid`, `terrain` | Require a tenant Google Maps API key |
| Custom basemap | Any tenant-defined id (declared under `customBaseMaps.customStyle.id`) | Persist the full style (a MapLibre `style.json`) at `keplerMapConfig.config.customBaseMaps.customStyle` |

**Common typos the CLI catches.** Tier-1 flags near-misses of canonical ids: `"darkmatter"` → suggests `"dark-matter"`; `"darkMatter"` → same; `"dark_matter"` → same. Builder silently falls back to `positron` on any unknown id, so typos are invisible until someone opens the map.

When in doubt start with `"positron"` — the CARTO basemaps have no tenant dependency and render identically in any environment.

**Custom basemap example** (a MapLibre `style.json` hosted externally):

```jsonc
"basemapConfig": {
  "styleId": "my-custom-basemap",
  "visibleLayerGroups": { "label": true, "road": true }
},
"customBaseMaps": {
  "customStyle": {
    "id": "my-custom-basemap",
    "label": "My brand basemap",
    "url": "https://cdn.example.com/style.json",
    "customAttribution": "© Example Co."
  }
},
"mapStyle": { "styleType": "my-custom-basemap" }
```

**Visible layer groups.** `basemapConfig.visibleLayerGroups` (mirror in `mapStyle`) is a per-group boolean — set any of `land`, `water`, `building`, `road`, `border`, `label` to `true` / `false` to show or hide that group. Omitted groups use the basemap's default visibility. Custom basemaps can declare their own groups under `customBaseMaps.customStyle.layerGroups`.

**Pair the basemap with contrast-appropriate colours:** see [`cartography.md`](cartography.md) §4.4 (dark-basemap considerations) and §5 (basemap pairing) for the light/dark matrix (which fill hex picks + palette names survive on which basemap). A layer colour that works on Positron can vanish on dark-matter and vice versa; the CLI does not auto-adjust — it's agent judgement.

---

