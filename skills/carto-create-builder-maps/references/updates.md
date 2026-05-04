# Updates & lifecycle

CRUD operations for an existing map (read → modify → write), the partial-vs-wholesale `keplerMapConfig` rule (the #1 destructive footgun), and the validation levers available pre-create. For starting-from-scratch JSON templates, see `examples.md`.

## Recipes

### Duplicate an existing map

The most reliable way to produce a working map — the source configuration is already Builder-shaped, so the partial-layer pitfall doesn't apply.

```sh
# Any map with a working configuration works — just swap title and clear server-assigned fields.
carto maps get <source-map-id> --json \
  | jq '.title = "My copy" | del(.id, .privacy)' \
  > new-map.json

carto maps create < new-map.json
```

### Update the title without touching anything else

```sh
echo '{"title":"Better title"}' \
  | carto maps update <map-id> --json
```
Partial PATCH — kepler config, datasets, privacy are all preserved.

### Add one dataset to an existing map

```sh
# 1. Read current configuration
carto maps get <map-id> --json > current.json

# 2. Append a new dataset (no id → will be created fresh)
jq '.datasets += [{
  "$ref": "extra",
  "type": "table",
  "source": "proj.ds.new_table",
  "connectionId": "<connection-id>",
  "geoColumn": "geom",
  "columns": ["geom"],
  "format": "tilejson",
  "label": "New source"
}]' current.json > updated.json

# 3. Apply — merge mode (default) keeps existing datasets
carto maps update <map-id> --json < updated.json
```

### Replace all datasets (destructive)

```sh
carto maps update <map-id> --datasets-mode replace --json < map.json
```
Any existing dataset not in the input is DELETED. Default is `merge`, which keeps unmentioned ones.

### Enable the Agent on an existing map

```sh
jq '.agent = {
  "enabledForViewer": true,
  "config": {
    "model": "ac_7xhfwyml::anthropic::claude-opus-4-5",
    "tools": [],
    "capabilities": {"querySources": true},
    "useCase": "Help analysts explore this dataset.",
    "instructions": "# Behavior\nBe concise. Cite column names when summarizing.",
    "introduction": {"welcome":"Hi!","starters":["Top 10 by score","What changed last quarter?"]}
  }
}' current.json > with-agent.json

carto maps update <map-id> --json < with-agent.json
```
When the configuration declares an agent, the create/update verify step re-fetches the map and surfaces any backend `agent.issues` (`MISSING_MODEL` / `UNAVAILABLE_MODEL` / `UNAVAILABLE_TOOL`) as warnings.

---


## Partial updates — merge vs. wholesale-replace

**The headline:** **most top-level configuration fields accept partial updates, but `keplerMapConfig` is replaced wholesale.** Sending `{keplerMapConfig: {config: {basemapConfig: {...}}}}` as a "partial update" wipes layers / widgets / sqlParameters / viewport from the server — read the current configuration, modify, and resend the full tree.

| Top-level field on `carto maps update <id>` | Merge behaviour |
|---|---|
| `title` | Partial ✓ — replaces just the title. |
| `description` | Partial ✓ |
| `tags` | Partial ✓ (replaces the whole array, but a partial *configuration* leaves the server's tags alone if you omit `tags`). |
| `collaborative` | Partial ✓ |
| `privacy` | Partial ✓ — applied via a separate endpoint (POST /privacy). Safe to send alone. |
| `agent` | Partial ✓ — patched atomically via PATCH /maps. |
| `datasets` | Partial ✓ by default (merge mode). `--datasets-mode replace` flips to "delete any dataset not mentioned". |
| **`keplerMapConfig`** | **WHOLESALE-REPLACE ✗** — the entire object gets persisted as-is. Agents treating this as partial will wipe server state. |

**Canonical pattern when you need to change anything inside `keplerMapConfig`** (basemap, layers, widgets, viewport, sqlParameters, popups, legend settings, etc.):

```bash
# Read → modify → write the full configuration
carto maps get <id> --json > /tmp/m.json
# edit /tmp/m.json (change basemapConfig, reorder layers, add a widget, whatever)
carto maps update <id> /tmp/m.json
```

The CLI will refuse a partial `keplerMapConfig` update that would wipe existing content. The rejection names the wipes explicitly:

```
✗ This update would wipe content currently on the map because the backend replaces
  `keplerMapConfig` wholesale (it does not merge partials). Detected wipes:
    • Input provides 0 layer(s); server has 4. The wholesale PATCH would drop 4 layer(s).
    • Input omits `keplerMapConfig.config.mapState` while touching other kepler fields — the
      wholesale PATCH would reset the viewport to defaults.

  Fix one of:
    1. Read-modify-write (recommended): ...
    2. If the wipe is intentional, pass --allow-kepler-replace to confirm.
```

**`--allow-kepler-replace`** is the escape hatch for the rare case where an agent legitimately wants to wipe and rewrite. Not a convenience flag — the wipe is the intent.

**Why the CLI doesn't auto-merge:** merging kepler configs is non-trivial (arrays with positional meaning, refs, nested objects, layer-order implications). A CLI-side merge would produce its own class of bugs. The read-modify-write pattern is explicit, debuggable, and matches how Builder's own save path works.

---


## Validation levers

Every create/update runs three checks after writing:

| Check | What it does | Warning code |
|---|---|---|
| **Map configuration JSON** (Tier-1) | `validateBundle` runs before any network call — unknown fields, bad refs, dangling dataIds, etc. | rejected at pre-flight |
| **Sources** | `SELECT … WHERE 1=0` per dataset via the SQL API | `SOURCE_INACCESSIBLE` |
| **Render** | Hits the tilejson endpoint per dataset (what Builder uses) | `DATASET_WONT_RENDER` |
| **Agent** (only if the configuration declares one) | Re-fetches the map and reads `agent.issues` | `AGENT_ISSUE` |

All are non-fatal — they emit warnings into the JSON `warnings[]` array; the create/update itself succeeds. `--dry-run` on update skips them (no writes happened). There is no way to opt out: the checks are cheap and always useful.

---

