# Troubleshooting & visual verification

Symptom→fix table for common authoring mistakes, antipatterns to avoid emitting, escape-hatch rules when stuck, and how to visually verify a rendered map without leaving the terminal.

## Symptom→fix

| Symptom | Likely cause | Fix |
|---|---|---|
| `Cannot convert undefined or null to object` red toast on first open | Your `visState.layers[]` is missing `textLabel`, `visualChannels`, or `colorUI` nested defaults | Use the canonical layer shell from [`layers.md`](layers.md) *"Canonical layer shell"*; the minimal shape includes everything Kepler's reducer inspects |
| Map exists but no layers visible in panel | `dataId` in a layer doesn't match any dataset id/`$ref` | Check the ref substitution. Use `carto maps get <id> --json` and look at layer `config.dataId` values |
| `SOURCE_INACCESSIBLE` warning | Connection lost access, or table doesn't exist | Validate the source with `connections describe <conn> <fqn>` first |
| `DATASET_WONT_RENDER` warning | Source exists but columns or geoColumn are wrong | Compare your dataset's `geoColumn` to what `connections describe` reports |
| `AGENT_ISSUE: UNAVAILABLE_MODEL` | Agent config's model id not enabled on this organization | List valid models (`org stats` or inspect an existing agent map) |
| `datasets[*].id must not be set on create` (older CLI) | Was a hard rule before the revamp's `df869e1` fix | Upgrade to ≥0.5.0 — ids from `get --json` are now accepted and mapped to new ids |
| Drag-reordering legend entries in Builder doesn't stick on next open | `sortScaleDomain` short-circuits when `attributeStats` are missing — CLI-created datasets don't ship per-category tilestats, so "sort by value" silently fails. "Sort by alphabetical" works. | Bake the order into the configuration: `colorRange.colorMap` array order for `custom` scale, `visualChannels.colorDomain` for `ordinal`. See `references/cartography.md` §6.1. |

---


## Antipatterns to avoid emitting

1. **Writing a full `keplerMapConfig` from scratch without starting from an example.** The schema is large, Kepler's defaults are strict, and you'll spend more time debugging than if you'd duplicated a similar map.
2. **Partial nested PATCH of `keplerMapConfig`.** Wholesale-replaced — partial input wipes layers / widgets / sqlParameters / viewport. See [`updates.md`](updates.md) *"Partial updates — merge vs. wholesale-replace"* for the read-modify-write pattern.
3. **Inventing colorRange hex lists.** Copy from a real map configuration. The legend uses the `name` + `category` fields to style itself.
4. **Using `label` as an identity key.** Builder allows duplicate labels; the server id is the only stable handle. The CLI matches by id.
5. **Treating `/publish` as a validator.** It isn't. The verify step that runs on every create/update is the validator — read its `warnings[]`.

---


## When in doubt

1. Browse the fixtures: `carto maps list --mine` (or `--all` for the whole account).
2. Grab a similar one: `carto maps get <id> --json > ref.json`.
3. Diff it against what you wanted and adapt. `jq` is your friend.
4. Read the `warnings[]` emitted by create/update before declaring victory.

---


## Visual verification — `carto maps screenshot`

After a create or update, the agent can render the map to PNG and inspect it. This closes the loop on "the JSON validates and the warehouse query works, but does the map look right?" — which Tier-1 + the source/render checks can't answer (palette contrast, layer occlusion, popup contents, label collision).

```bash
carto maps screenshot <mapId> -o /tmp/m.png
carto maps screenshot <mapId> --lat 40.42 --lng -3.70 --zoom 12 -o /tmp/madrid.png
```

**Two render engines — pick by what you need to verify:**

| Engine | Renders | Speed | Use when |
|---|---|---|---|
| `light` (**default**) | Layers + basemap + viewport only | ~8s warm | Verifying layer rendering, palette, contrast, geometry, layer order. The common case. |
| `full` (`--render-engine full`) | Everything: layers + widgets + legends + popups + side panel | ~20s warm | Verifying widget contents/order, legend categories/order, popup field selection, or any UI element the user will interact with. |

If you authored `widgets[]`, `legendSettings`, or `popupSettings` in this turn, **screenshot with `--render-engine full`** before reporting completion — `light` paints only the map surface and won't show whether the widget panel renders the bins you expected, or whether the legend categories landed in the right order. Conversely, when the user only asked for "show me a map of X", `light` is the right call.

**One-time install** (the user will see the missing-Chromium error if they haven't done this): `npx playwright install chromium`. The Chromium binary is ~150 MB; first run is slow because it downloads it. Subsequent runs use a persistent profile at `~/.carto/screenshot-cache` (bypass with `--no-cache`).

The screenshot is also useful as **agent feedback during iteration**: render → inspect the PNG → adjust the configuration → re-render. Faster than asking the user to open Builder for every tweak. Keep `light` for fast iteration; switch to `full` for final verification.
