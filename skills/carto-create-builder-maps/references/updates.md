# Updates & lifecycle

CRUD operations for an existing map (read → modify → write), the partial-vs-wholesale `keplerMapConfig` rule (the #1 destructive footgun), targeted edits with `keplerChanges`, and the validation levers available pre-create. For starting-from-scratch JSON templates, see `examples.md`.

> Recipes are shown as `carto maps` commands; on MCP substitute `read_maps get` + `read_maps list_datasets` (read — `get` returns the stored record, with no datasets and `privacy` as a string), `update_map` (update / update_dataset / publish), `create_map` (create), `delete` (kind=map). The merge/wipe rules and validation levers below hold on both paths — `update_map` replaces `keplerMapConfig` wholesale exactly as the CLI does. To change part of it without resending it, send `keplerChanges` (see *Change part of the map config* below).

## Recipes

### Duplicate an existing map

The most reliable way to produce a working map — the source configuration is already Builder-shaped, so the partial-layer pitfall doesn't apply.

```sh
# Any map with a working configuration works — swap the title, clear the server-assigned
# top-level fields, and strip the server-computed decorations off every dataset.
carto maps get <source-map-id> --json \
  | jq '.title = "My copy"
        | del(.id, .privacy)
        | .datasets |= map(del(.mapId, .connectionName, .connectionViewerCredentials,
                               .connectionViewerCredentialsAttached, .providerId,
                               .sourceWorkflowId, .sourceWorkflowNodeId,
                               .createdAt, .updatedAt))' \
  > new-map.json

carto maps create < new-map.json
```

On MCP, build the bundle from two reads: `read_maps get` returns the stored record, which has no datasets and carries `privacy` as a string that `create_map` refuses.

1. `read_maps get` (method `get`, `id`): keep `description`, `keplerMapConfig` and `agent`; set a new `title`; leave out `id`, `privacy` and every other field.
2. `read_maps list_datasets` (same `id`): put the array it returns in the bundle as `datasets`. `create_map` accepts it as returned, read-only fields such as `connectionName` and `providerId` included.
3. `create_map` with that bundle. Each new dataset gets a new id and the layers' `dataId` and widgets' `dataSource` are rewritten to it.

Skip step 2 and every layer and widget of the copy points at a dataset of the source map that the new map doesn't have, so it renders nothing.

> **Strip the server-computed dataset fields before re-posting a bundle you read.** `mapId`, `connectionName`, `connectionViewerCredentials`, `connectionViewerCredentialsAttached`, `providerId`, `sourceWorkflowId`, `sourceWorkflowNodeId`, `createdAt` and `updatedAt` are decorations the server adds on read; no write route accepts any of them back, and both create and update reject unknown params outright — one left in is a 400. Pre-flight validation will NOT catch it: the dataset node is deliberately permissive so that round-tripped bundles, which legitimately carry these, still parse. The same strip applies to every `get → edit → update` recipe below.

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
    "capabilities": {"querySources": false},
    "useCase": "Help analysts explore this dataset.",
    "instructions": "# Behavior\nBe concise. Cite column names when summarizing.",
    "introduction": {"welcome":"Hi!","starters":["Top 10 by score","What changed last quarter?"]}
  }
}' current.json > with-agent.json

carto maps update <map-id> --json < with-agent.json
```
When the configuration declares an agent, the create/update verify step re-fetches the map and surfaces any backend `agent.issues` (`MISSING_MODEL` / `UNAVAILABLE_MODEL` / `UNAVAILABLE_TOOL`) as warnings.

Set `querySources` to `true` only when the user asks for SQL, and never on a public map (see `agent-config.md`).

### Change only the agent's model

Send only the new model. The update merges `agent` over the stored one, so `capabilities`, `tools`, `instructions`, `introduction`, `semanticModel` and `enabledForViewer` stay as the user set them.

```sh
carto maps agents models                       # pick the new model id from this list

echo '{"agent": {"config": {"model": "<model-id-from-the-list>"}}}' > agent-only.json
carto maps update <map-id> --json < agent-only.json
carto maps publish <map-id>                    # published agents keep the old model until republished
```

On MCP, the same applies to `update_map`: send `{ "agent": { "config": { "model": "…" } } }`. The same works for any other agent field. To clear one, send `""` or `[]`.

---


## Partial updates — merge vs. wholesale-replace

When a change doesn't touch `keplerMapConfig` — a title, description, sharing or agent change — leave `keplerMapConfig` out entirely: the other top-level fields merge on their own. Resending a 5 KB config for a title change only adds ways to fail.

**The headline:** **most top-level configuration fields accept partial updates, but `keplerMapConfig` is replaced wholesale.** Sending `{keplerMapConfig: {config: {basemapConfig: {...}}}}` as a "partial update" wipes layers / widgets / sqlParameters / viewport from the server. To change part of it, send only the edits with `keplerChanges`; to rebuild it, read the current configuration, modify, and resend the full tree.

| Top-level field on `carto maps update <id>` | Merge behaviour |
|---|---|
| `title` | Partial ✓ — replaces just the title. |
| `description` | Partial ✓ |
| `tags` | Partial ✓ (replaces the whole array, but a partial *configuration* leaves the server's tags alone if you omit `tags`). |
| `collaborative` | Partial ✓ |
| `privacy` | **Replaces sharing ✗** — applied via a separate endpoint (POST /privacy). Omit it to keep the current sharing. Any block you send rewrites it: a `policies` array (preferred) becomes the full grant list, `{"policies": []}` or `{"privacy": "private"}` revokes every share and public link. Send one form, not both; a block with both is rejected. The first share publishes the map, and making it private unpublishes it. |
| `agent` | Partial ✓ — merged over the stored agent key by key, inside `capabilities` and `introduction` too; omitted keys keep their value, `""` / `[]` clear one. |
| `datasets` | Partial ✓ by default (merge mode). `--datasets-mode replace` flips to "delete any dataset not mentioned". |
| **`keplerMapConfig`** | **WHOLESALE-REPLACE ✗** — the entire object gets persisted as-is. Agents treating this as partial will wipe server state. To edit part of it, leave it out and send `keplerChanges`. |

### Change part of the map config: `keplerChanges`

For a small change to a map that already exists (an opacity, a color, a widget title, one more widget, a popup field), send only the edits. The server reads the stored `keplerMapConfig`, applies the edits in order, and saves the result through the same validation and wipe guard as a whole config. Everything you don't name goes back as stored, including `popupSettings`, `legendSettings`, `mapSettings` and `layerGrouping`, which a hand-rebuilt config loses without a warning. On a large map it is also much faster than resending the whole config, which is slow and can time out.

On MCP, `update_map` with method `update`. Leave `bundle.keplerMapConfig` out; `bundle` itself is optional:

```json
{
  "method": "update",
  "id": "<map-id>",
  "keplerChanges": [
    { "path": "config.visState.layers[id=<layer-id>].config.visConfig.opacity", "value": 0.5 },
    { "path": "config.visState.layers[id=<layer-id>].config", "merge": { "label": "Stores 2026", "isVisible": true } },
    { "path": "config.widgets[-]", "value": { "id": "w-total", "type": "formula", "title": "Total revenue", "column": "revenue", "operation": "sum", "formatter": "DECIMAL_CURRENCY", "dataSource": "<dataset-id>", "global": false } }
  ]
}
```

On the CLI, `--changes` takes the same array, inline or as a file path. The bundle becomes optional and must not carry `keplerMapConfig`; pass it as the positional argument or `--file`, because stdin is not read with `--changes`:

```sh
carto maps update <map-id> --changes '[{"path":"config.visState.layers[id=<layer-id>].config.visConfig.opacity","value":0.5}]' --json
carto maps update <map-id> '{"title":"Retail 2026"}' --changes ./edits.json --json
```

> `--changes` ships in the CLI release after 0.15.0. `carto maps update --help` lists it when your CLI has it. On an older CLI, upgrade or use read-modify-write below.

**Each item is one of three:**

| Item | What it does |
|---|---|
| `{ "path", "value" }` | Sets the key at `path`, or adds it. On an object it replaces the whole object and drops every key you didn't send. |
| `{ "path", "merge": { ... } }` | Sets some keys of an existing object and keeps the rest. One level deep: an object inside `merge` replaces that key whole. |
| `{ "path", "remove": true }` | Removes the key or the array element. |

**Paths:**

- Dot-separated keys from the `keplerMapConfig` root. Every path starts with `config`.
- An array element is addressed by its id, `[id=...]`, or by position, `[n]`. Prefer ids: positions shift after a remove in the same call.
- `[-]` as the last segment appends `value` to the array.
- A key that holds a dot goes in quotes: `config.popupSettings.layers["a.b"]`.
- In `layerGrouping` a layer entry is matched by its `layerId`. `popupSettings.layers` and `legendSettings.layers` are keyed by layer id.

**What is refused, and what is not:**

- An `[id=...]` that matches nothing, or more than one element, is refused, and the error lists the ids that are there. Read the ids from the map (`read_maps get` / `carto maps get <id> --json`) instead of guessing them.
- An element found by `[id=...]` keeps that id. To replace it with a different one, remove it and append the new one.
- Appending an element whose id the list already has is refused.
- Every segment before the last must exist. The exception is an append to `config.widgets`, `config.sqlParameters` or `config.layerGrouping`, which creates the list when the map doesn't have it yet.
- Removing a layer, widget or SQL parameter still needs `allowKeplerReplace` / `--allow-kepler-replace`, the same as with a whole config.
- **A misspelt key at the end of a path is not caught: it is saved as a new key.** Take field names from the schema (`validate_map` method `schema` / `carto maps schema <section>`), never from memory.
- At most 200 changes per call.

**A new layer needs two changes:** append it to `config.visState.layers`, and append `{ "type": "layer", "layerId": "<new-layer-id>" }` to `config.layerGrouping`. `[-]` puts it last in the tree, which is the bottom of the stack. To place it anywhere else, set `config.layerGrouping` with `value`, the whole tree in the new order.

**Which way to send a change:**

| Change | Send |
|---|---|
| Part of the map config on an existing map: a style, a widget, a popup, a SQL parameter, the viewport | `keplerChanges` / `--changes` |
| Title, description, tags, agent, sharing | A partial bundle with no `keplerMapConfig` |
| A dataset's SQL, columns or aggregation | `update_map` method `update_dataset` / `carto maps datasets update` |
| A rebuild of most of the config, or a copy of another map | The whole config, read-modify-write below |

**Whole-config pattern, for a rebuild of `keplerMapConfig`** (or on a CLI that doesn't have `--changes` yet):

```bash
# Read → modify → write the full configuration
carto maps get <id> --json > /tmp/m.json
# edit /tmp/m.json (change basemapConfig, reorder layers, add a widget, whatever)
carto maps update <id> /tmp/m.json
```

**Reordering layers on an existing map means reordering `config.layerGrouping`**, not just `visState.layers` — Builder writes that tree on every save and it owns the render order (first entry on top). A new layer that isn't added to the tree renders at the bottom. See `references/layers.md` → *"Layer groups"*.

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

**The guard does not cover every field.** It counts layers, widgets and sqlParameters, so replacing one layer with another (same count) passes unflagged, and flags a missing `config`, `visState` or `mapState`. It also flags the basemap when other kepler fields are set: an update that sends neither `basemapConfig` nor `mapStyle` (it would reset the basemap to the default), and one that sends `mapStyle` without the map's stored `basemapConfig` (it would drop the stored style and visible layer groups). Re-send what the map has stored to keep it: its `basemapConfig`, or its `mapStyle` on a map that has no `basemapConfig`. Everything else under `config` — `popupSettings`, `legendSettings`, `mapSettings`, `layerGrouping`, `customBaseMaps`, `uiState` — is replaced with whatever the input carries, and its loss is reported by nothing. `widgetsPanelLayout` is flagged only when the stored layout is not the default; dropping it from an update otherwise silently returns a two-column or floating widgets panel to the default (1 column, docked). Read-modify-write is what protects them.

**Why the CLI doesn't auto-merge:** merging kepler configs is non-trivial (arrays with positional meaning, refs, nested objects, layer-order implications). A CLI-side merge would produce its own class of bugs. The read-modify-write pattern is explicit, debuggable, and matches how Builder's own save path works.

---


**Publish once.** On MCP, `update_map` takes a `publish` option that publishes after a successful write. Use it on the write that finishes the change; call the separate publish method only to publish without a change. Never both for one edit.

## Validation levers

**When a write is refused,** fix what the error details say and try again, three attempts at most. If the third is refused too, stop and report what was refused and why, instead of looping on the same bundle.

Every create/update runs these checks:

| Check | What it does | Warning code |
|---|---|---|
| **Map configuration JSON** (Tier-1) | `validateBundle` runs before any network call — unknown fields, bad refs, dangling dataIds, etc. | rejected at pre-flight |
| **Sources** (before writing) | `SELECT … WHERE 1=0` per dataset via the SQL API | `SOURCE_INACCESSIBLE` / `COLUMN_NOT_FOUND` |
| **Render** | Hits the tilejson endpoint per dataset (what Builder uses); new datasets are checked before writing | `DATASET_WONT_RENDER` |
| **Agent** (only if the configuration declares one) | Re-fetches the map and reads `agent.issues` | `AGENT_ISSUE` |

Not all are non-fatal. Tier-1 issues reject the write. A `SOURCE_INACCESSIBLE` or `COLUMN_NOT_FOUND` warning that carries a `detail` rejects it too, and so does a tile server 4xx on a brand-new dataset. The rest land in the JSON `warnings[]` array and the create/update succeeds. `--dry-run` on update runs Tier-1 only: it skips the source dry-run, the render and agent checks, and the `keplerMapConfig` wipe guard, so a clean dry run does not promise the real update will pass. There is no way to opt out: the checks are cheap and always useful.

---

