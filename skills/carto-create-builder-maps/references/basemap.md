# Basemap configuration — `basemapConfig` + `mapStyle`

The basemap lives on **two parallel fields** inside `keplerMapConfig.config`. **Always write both, set them to the same `styleId` / `styleType` value.** Tier-1 rejects desync.

| Field | Status | Read by |
|---|---|---|
| `basemapConfig.styleId` + `visibleLayerGroups` | **Canonical / newer** | Builder editor + viewer (`workspace-www/src/features/builder/state/baseMapsSagas.ts:49-58` reads it first) |
| `mapStyle.styleType` + `visibleLayerGroups` | **Still load-bearing** | Screenshot light engine (deck.gl/carto `fetchMap`), workspace-www `/viewer` SSR, downstream tools using `fetchMap`. Omitting it crashes the screenshot CLI and breaks viewer rendering — verified 2026-04-29 against a live organization |

**Why both.** `basemapConfig` is the direction of travel — Builder's saga prefers it. But `mapStyle` is what older code paths (deck.gl/carto fetchMap, viewer SSR) still read directly. Omitting `mapStyle` produces a map that creates cleanly (Tier-1 + backend accept it), opens fine in Builder, but blows up the moment anyone screenshots it or the public viewer SSRs it. The fix is one extra line; the failure is invisible until production.

```jsonc
"basemapConfig": { "styleId": "dark-matter" },
"mapStyle":      { "styleType": "dark-matter" }
```

The two values **must match** — Tier-1 (`carto-cli/src/schemas/crossField/basemapSync.ts`) rejects configurations where `basemapConfig.styleId !== mapStyle.styleType` because Builder's editor and the viewer would render different basemaps.

**Canonical ids** (the 11 CARTO built-ins):

| Group | Ids | Notes |
|---|---|---|
| CARTO basemaps | `positron`, `dark-matter`, `voyager` | Always work; no external dependency |
| Google Maps | `roadmap`, `google-positron`, `google-dark-matter`, `google-voyager`, `satellite`, `hybrid`, `terrain`, `google-3d` | All require a tenant Google Maps API key. `google-3d` is the photorealistic 3D Tiles basemap — pair with `mapState.pitch > 0` (e.g. 45°) to actually see the buildings. |
| Custom basemap | `custom:<accountBasemapId>` — the `custom:` prefix is **mandatory** and must match `customBaseMaps.customStyle.id` exactly | Persist the full style (a MapLibre `style.json`) at `keplerMapConfig.config.customBaseMaps.customStyle` |

> **The Google id namespace is inconsistent — don't extrapolate.** Some Google ids carry a `google-` prefix (`google-positron`, `google-dark-matter`, `google-voyager`, `google-3d`), others don't (`roadmap`, `satellite`, `hybrid`, `terrain`). The most common LLM hallucination here is generalising the prefix — emitting `"google-satellite"` / `"google-hybrid"` / `"google-roadmap"` because the prefixed ids are visible. **Those ids do not exist.** Builder falls back silently to `positron` on any unknown id, so the failure is invisible until a viewer opens the map. When in doubt: copy from this table verbatim, don't reconstruct.

> **Persisted shape is just `{styleId, visibleLayerGroups?}` — no `type` field.** The `type` discriminator (`gmaps` / `carto` / `custom`) lives only on Builder's in-memory `BuilderBasemapStyle` after the loader resolves the styleId against `defaultMapStyles[]`. Don't emit `{type: "google", styleId: "satellite"}` or `{type: "carto", styleId: "google-satellite"}` into the saved map — both are wrong; the correct shape is `{styleId: "satellite"}`. (`customBaseMaps.customStyle` is the exception and *does* carry a required `type` — see the custom-basemap example below.)

**Common typos the CLI catches.** Tier-1 flags near-misses of canonical ids: `"darkmatter"` → suggests `"dark-matter"`; `"darkMatter"` → same; `"dark_matter"` → same; `"google3d"` → suggests `"google-3d"`. Builder silently falls back to `positron` on any unknown id, so typos are invisible until someone opens the map.

When in doubt start with `"positron"` — the CARTO basemaps have no organization dependency and render identically in any environment.

**Custom basemap example** (a MapLibre `style.json` hosted externally):

```jsonc
"basemapConfig": {
  "styleId": "custom:my-brand-basemap",          // the `custom:` prefix is mandatory
  "visibleLayerGroups": { "land": true, "water": true, "building": true,
                          "road": true, "border": false, "label": true }
},
"customBaseMaps": {
  "customStyle": {
    "type": "custom",                            // required
    "id": "custom:my-brand-basemap",             // must equal basemapConfig.styleId
    "label": "My brand basemap",
    "url": "https://cdn.example.com/style.json",
    "customAttribution": "© Example Co."
  }
},
"mapStyle": { "styleType": "custom:my-brand-basemap" }
```

> **The `custom:` prefix is the switch.** It is what makes Builder consult `customBaseMaps.customStyle` at all. An unprefixed id — `"my-brand-basemap"` — never matches the built-in style table either, so Builder and fetchMap skip the custom lookup and silently render `positron`. The near-miss check cannot detect this (an unprefixed custom id is indistinguishable from a tenant id it has no way to know), so get it right yourself.

**Visible layer groups.** `basemapConfig.visibleLayerGroups` (mirror in `mapStyle`) is a per-group boolean over `land`, `water`, `building`, `road`, `border`, `label`. **Emit all six keys, or omit the field entirely.** The record is consumed as-is with no merge against the defaults, so an omitted key reads as falsy and *hides* that group — a partial record is not "accept the defaults for the rest". Worse, the two readers disagree on a partial one: Builder hides the absent groups, while fetchMap viewers skip filtering altogether when no value is `false`, so the same bundle renders differently in Builder and in an embed. Omitting the whole field is the safe way to take the defaults (label, road, building, water, land visible; border hidden).

`customStyle.layerGroups` is inert — omit it. Builder rebuilds layer groups from the built-in style table by id, which a `custom:`-prefixed id never matches, so nothing written there is read. Layer-group toggles only do anything on the CARTO MapLibre styles.

**Pair the basemap with contrast-appropriate colours:** see [`cartography.md`](cartography.md) §4.4 (dark-basemap considerations) and §5 (basemap pairing) for the light/dark matrix (which fill hex picks + palette names survive on which basemap). A layer colour that works on Positron can vanish on dark-matter and vice versa; the CLI does not auto-adjust — it's agent judgement.

---

