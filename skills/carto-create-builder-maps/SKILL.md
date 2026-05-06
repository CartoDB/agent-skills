---
name: carto-create-builder-maps
description: Author, edit, publish, and validate CARTO Builder maps via the `carto maps` CLI. Use when the user wants to create a map from a natural-language request, edit an existing map (datasets, layers, styling, privacy, popups, widgets, SQL parameters), duplicate one, upload custom marker icons, or wire up an AI agent on a map. Covers the full `carto maps <subcommand>` surface — `list`, `get`, `create`, `update`, `delete`, `publish`, `validate`, `schema`, `agents`, `markers`, `screenshot`, `datasets update`.
license: MIT
---

# carto-create-builder-maps

CARTO Builder is a mapping tool that renders interactive maps from a JSON map configuration. This skill covers the full authoring lifecycle via the CLI: create from natural language, edit datasets / layers / widgets / popups / privacy, publish snapshots for shared viewers, validate offline, and operate via the `carto maps` commands.

For copying maps cross-org (`dev → prod` promotion, customer-segregated org delivery), use [`carto-copy-maps`](../carto-copy-maps).
For ad-hoc spatial SQL exploration, use [`carto-query-datawarehouse`](../carto-query-datawarehouse).

Field shapes, enum values, palette catalogues, and AI-tool catalogues are served by the CLI — **never hardcode or assume them**. Run `carto maps schema [section]` for JSON Schema (generated from the same Zod definitions Tier-1 validation uses), `carto maps agents models` / `mcp-tools` / `core-tools` for AI surfaces, and `carto connections describe <conn> <table>` for dataset metadata. When this doc disagrees with the CLI, the CLI wins.

## References

**Decision / orientation — read first**
- [`references/cartography.md`](references/cartography.md) — cartographic decisions ahead of styling: palette family, scale type, basemap pairing, multi-layer hue separation, anti-patterns. Mandatory reading before writing JSON when styling decisions are in scope.
- [`references/configuration-shape.md`](references/configuration-shape.md) — the JSON skeleton, annotated. `keplerMapConfig` top-level structure + `datasets[]` entries (table / query / tileset / raster) + `mapSettings` rules.
- [`references/examples.md`](references/examples.md) — working templates validated against a live organization: minimal map, H3 aggregation, SQL parameters, widgets gallery. Load when you need a JSON template to start from.

**Per-component — consult on demand while authoring**
- [`references/layers.md`](references/layers.md) — per-layer-type authoring: `tileset` (point / line / polygon / 3D), `h3`, `quadbin`, `heatmapTile`, `clusterTile`, `raster`. Plus colour ranges (palettes / scales / `/stats`) and basemap-aware contrast.
- [`references/widgets.md`](references/widgets.md) — analytical surface: `formula`, `category`, `pie`, `histogram`, `range`, `timeseries`, `table`. Ordering, collapsibility defaults, cross-filtering across datasets.
- [`references/popups.md`](references/popups.md) — `popupSettings` covers two interaction surfaces: tooltip popups (hover / click) AND info panels (docked side panel, click-only). 5-field hover cap, custom HTML templates with inline CSS, what the renderer sanitises out.
- [`references/sql-parameters.md`](references/sql-parameters.md) — `Category`, `DateRange`, `Numeric`, `NumericRange`. `{{paramName}}` placeholder authoring + provider-native dialect translation.
- [`references/basemap.md`](references/basemap.md) — write BOTH `basemapConfig.styleId` AND `mapStyle.styleType` to the same value (the screenshot engine + viewer SSR still read `mapStyle` today). CARTO basemaps / Google Maps / custom basemap catalogue.
- [`references/agent-config.md`](references/agent-config.md) — Agent on a map (opt-in). Organization-status check, model selection, MCP / core tool catalogues, capability-driven activation.

**Operate / unstick**
- [`references/updates.md`](references/updates.md) — CRUD lifecycle: recipes, the partial-vs-wholesale `keplerMapConfig` rule (the #1 destructive footgun), `--datasets-mode`, publish chaining, validation levers.
- [`references/troubleshooting.md`](references/troubleshooting.md) — symptom → fix table, antipatterns to avoid emitting, escape-hatches when stuck, visual verification via `carto maps screenshot`.

---

## Authoring process

Follow these phases in order for every "create a map" request. Skipping a phase is the most common cause of *"the map looks broken in Builder"*.

### Phase 1 — Gather context (intake gate)

This phase is a **gate, not a suggestion**. But the order matters: **the data is the only fact that constrains what's even askable**. Asking the user abstract preferences (audience, mode, widgets, sharing) before knowing what's in the table produces generic questions that often don't apply, and makes the user do the agent's job of mapping wishes to columns.

#### Sequence

1. **Goal — one line.** *"What's the map about, and what's the takeaway?"* Don't proceed without an answer; *"just make a map of X"* is fine if X is specific.
2. **Data hint — one line.** *"Where's the data — a table you already have, a demo dataset, or a file to import?"* Resolve to a concrete table FQN before moving on. Demo data: search `carto-demo-data.demo_tables` by topic. File: run `carto imports create` first.
3. **SILENT data inspection.** Before asking anything else:
   - `carto connections describe <conn> <table>` → schema, row count, geom type (point / line / polygon / h3 / quadbin / raster).
   - `carto sql query` for: NULL ratios on candidate `colorField` columns, min/max/p50/p95/p99 on numeric columns relevant to the goal, `COUNT(DISTINCT ...)` on candidate categorical columns to detect cardinality traps, date range on temporal columns.
   - **Cap inspection at one or two queries.** Don't audit every column. Inspect what's relevant to the user's goal.
4. **Questions, NOW data-contingent.** Only ask what the data makes answerable. Examples of *good* data-grounded questions versus *bad* abstract ones:

   | Bad (abstract, asked too early) | Good (data-grounded, asked after inspect) |
   |---|---|
   | *"Want widgets?"* | *"I see `capacity_repd_mwp` (sum to ~13 GW) and `repd_status` (5 categories) — want a capacity total + a status breakdown widget?"* |
   | *"Analytical or cartographic?"* | *"The table has 23 columns including operational date, area, capacity. Strong analytical map territory — propose a histogram of capacity, or stay simple?"* |
   | *"Public or private?"* | (sharing is orthogonal to data; ask cleanly when relevant — never on first turn) |
   | *"Which palette?"* | *"With 265k installations, points will overlap heavily — propose low opacity + uniform colour, or color by capacity (heavy-tailed → log scale)?"* |

   If the data answers a question on its own, **don't ask** — just decide:
   - Geom type → layer type, silently: polygon / line / point → `tileset`; pre-indexed h3 / quadbin → `h3` / `quadbin` directly; raster → `raster`.
   - Viewport → bounding box of the data.
   - NULL ratio on a candidate `colorField` > 25% → switch column or filter `WHERE col IS NOT NULL` silently. See [`cartography.md` §4.5a](references/cartography.md).
5. **Sharing / audience / agent — ask only when triggered.** Don't gate the first map render on these. Default to `private`. Surface them when the user says *"share with the team"*, *"send to my CEO"*, *"add an AI agent"*.

#### Technical preconditions (silent — don't surface unless they fail)

- **Auth status.** Run `carto auth status`. If unauthenticated, ask the user to run `carto auth login` and stop.
- **Organization AI status** (only if the user mentions an Agent on the map). `carto maps agents status` — if `enabled: false`, drop agent plans and tell the user.

#### Time budget

**First-version target: ~30s wall time** from the user's "go" to a working URL. Achievable when the only intake is goal + data hint and the agent inspects silently. The first map still has to look good — cartographic defaults from [`cartography.md`](references/cartography.md) (palette family, scale, basemap pairing, multi-layer hue separation) apply on the first shot; refinement (custom domains, palette swaps, widget tuning) lands on subsequent turns *with the user looking at the result*.

### Phase 2 — Make cartographic decisions

Read [`references/cartography.md`](references/cartography.md) ahead of writing JSON when styling is in scope. State explicit choices before emitting:

- **Layer type** by data character (point / line / polygon / h3 / quadbin / heatmap / cluster / raster).
- **Palette family** (qualitative / sequential / diverging) — pick by narrative + basemap, not reflex.
- **Scale type** — pick by data shape AND meaning, not reflex. Default ladder: bounded with semantic landmarks (0–100 scores, %, ratios) → `quantize` + explicit `colorDomain` matching the natural extent; heavy-tailed across orders of magnitude → `custom` + `uiCustomScaleType: "logarithmic"`; skewed unbounded where viewers care about RANK not magnitude → `quantile` (the genuine use case, not the safe default); categorical-looking integers → cast to STRING + `ordinal`. See `references/cartography.md` §3.2 — `quantile` is NOT the universal safe default; reflex-picking it on bounded scales like ENERGY STAR / age / % is the most common scale-choice error.
- **Basemap** (`positron` light default / `dark-matter` / `voyager` / Google variants / custom).
- **Multi-layer hue separation** when there's more than one layer (palette-family-per-layer, not shades of one ramp).

Skip cartography ahead-of-time only on purely structural work (rename, dataset swap, privacy change, agent-config edit, mapSettings tweaks).

### Phase 3 — Compose the configuration

Reference [`references/configuration-shape.md`](references/configuration-shape.md) for the skeleton. Fill in:

- `datasets[]` — connection, source, geoColumn, type, format. For h3 / quadbin layers see the source-decision rubric (dynamic binning vs pre-built tileset).
- `keplerMapConfig.config.visState.layers[]` — type + visualChannels + visConfig (consult [`layers.md`](references/layers.md)).
- `keplerMapConfig.config.widgets[]` if analytical (consult [`widgets.md`](references/widgets.md)).
- `keplerMapConfig.config.popupSettings.layers` — emit by default for feature-identifying datasets (consult [`popups.md`](references/popups.md)).
- `keplerMapConfig.config.sqlParameters[]` if filterable (consult [`sql-parameters.md`](references/sql-parameters.md)).
- `keplerMapConfig.config.basemapConfig` + `mapStyle` — write both, same value (consult [`basemap.md`](references/basemap.md)).
- `agent` block only if the user explicitly asked AND organization AI is enabled (consult [`agent-config.md`](references/agent-config.md)).

### Phase 4 — Validate offline

```sh
carto maps validate map.json
```

Tier-1 catches shape, types, enum values, cross-references, agent fields, `aggregationExp` coherence, privacy coercion, and the dozen-or-so cross-field rules (canonical visualChannels path, custom-marker pairings, popup hover cap, etc.) — all with zero backend calls. Iterate until clean.

### Phase 5 — Create + verify

```sh
carto maps create < map.json
```

The CLI runs Tier-1 + a `SELECT … WHERE 1=0` source-accessibility probe per dataset BEFORE `POST /maps`, so broken sources never create orphan maps. The probe automatically excludes synthetic `_carto_*` columns and post-aggregation aliases parsed from `aggregationExp`, so legitimate h3 / quadbin / heatmapTile / clusterTile authoring won't trip it. After create, decide whether to run `carto maps screenshot <id>` for visual verification — see the *"Visual verification"* always-on rule below for the decision rubric.

### Phase 6 — Publish (when ready for viewers)

`maps create` writes a private draft. To make a map visible to the user's intended audience:

- Set `privacy` (`shared` with optional `sharingScope: "organization"` or `"specific"` + `userIds` / `groupIds`, OR `public`).
- Run `carto maps publish <id>` to freeze a snapshot for shared / public viewers.
- For chained edit-and-publish: `carto maps update <id> --publish`.

Tell the user *"it's live for viewers"* after a successful publish; otherwise make clear the edits are visible only to them.

---

## Always-on rules

These apply on every task, not just the create flow.

### Lead with intent — hide the plumbing

When asking the Phase 1 intake questions (and on every follow-up turn), **stay in plain language**. Do NOT surface `dataId`, `geoColumn`, `tilejson`, `keplerMapConfig`, `connectionId`, FQN syntax, or layer-type taxonomy on turn 1 — that reads as a spec dump and makes the user do your job. Frame every question in terms the user already has: *"what's the map about"*, *"who reads it"*, *"should viewers be able to filter"*, *"how should it be shared"*. Translate to the JSON in your head; don't ask the user to.

### Do silently, don't ask

- **Auth** — run `carto auth status` before the first API-touching command.
- **Connection UUID + FQN syntax** — once the user names the table, use `carto connections list` and `carto connections describe` to resolve. Don't ask the user to hand-type `project.dataset.table`.
- **Imports — when the user has a file, not a table** — if the user offers a path / URL to a geospatial file (CSV / GeoJSON / GeoPackage / GeoParquet / KML / KMZ / Shapefile-zip, ≤ 1GB), run `carto imports create --file <path>` (or `--url <url>`) `--connection <name> --destination <fqn>` to land it as a warehouse table FIRST, then build the map on the imported table. Defaults: pick a connection from `carto connections list` (prefer the user's primary CARTO Data Warehouse if present), pick a sensible `--destination` FQN that mirrors the file's basename. The command waits for completion by default; pass `--async` only when the user is shipping a multi-GB load they want to background. Don't ask the user to convert formats — the importer handles all 7.
- **Layer type** — infer from dataset shape:
  - line / polygon source → `tileset`.
  - point source, sparse / feature-level (find-this-store, click-to-zoom) → `tileset`.
  - **point source, dense / large (the typical aggregation case) → aggregate to `h3` or `quadbin`** (h3 = hex aesthetic, quadbin = square + zoom-adaptive cell size). This is the right default for "where does X cluster?" / "density of Y" questions on a large point table — quantitative reading, comparable across viewports, no per-row render budget pressure.
  - pre-indexed h3 / quadbin source → `h3` / `quadbin` directly (no aggregationExp needed).
  - band-stored raster → `raster`.
  - **`heatmapTile` and `clusterTile` are NOT silent defaults** — pick them only when the user explicitly asks for *"a heatmap"* / *"clustered points"*, OR when the narrative is specifically pattern-without-numbers (`heatmapTile`) or numbered-bubbles-with-zoom-to-individual (`clusterTile`). For everything else where the data is dense points, default to `h3` / `quadbin` aggregation — they preserve quantitative reading while heatmap blurs it and cluster turns it into bubble counts.

  Only ask the user when the choice between *feature-level* (`tileset`) and *aggregation* (`h3` / `quadbin`) is genuinely ambiguous — e.g. *"individual store locations, or density across the city?"*.
- **Viewport** — centre on the data's bounding box (the CLI computes this during create); don't ask for lat/lng/zoom.
- **Legend & categorical domains** — the CLI fetches `/stats` and populates the legend automatically.
- **`colorField` data-shape probe** — before binding a numeric column to `colorField` (or `sizeField` / `radiusField` / `heightField`), check NULL ratio with a one-line `carto sql query` probe (`SELECT COUNT(*), COUNT(col) FROM source`). If > 25% of rows are NULL the map renders dominantly grey at render time — same family as the categorical-cardinality trap. Two fixes (no need to ask the user): filter `WHERE col IS NOT NULL` in the source SQL, or pick a more-populated column. See `references/cartography.md` §4.5a for the worked example. Skip the probe on round-trips of existing maps (the user already chose the column) and on tiny datasets (< 1k rows — the trap doesn't materialise visibly).
- **Popups — emit by default** when the dataset has feature-identifying columns (`name` / `id` / `address` / `owner` / `timestamp`). End users **cannot consult the source table** — the popup (or, secondarily, a `table` widget) is the ONLY way they can read per-feature attributes. A map without popups and without a table widget shows the user a colour and a position; everything else about the feature is invisible to them. Add hover with 2–4 identifier columns, click with the rest. Skip only on pure pattern maps (heatmap, density h3/quadbin where the read is *aggregate*, not per-feature).
- **Widgets — propose by default for analytical maps**, count by use case (not a fixed number):
  - Pure cartography map: 0 widgets.
  - Operational / "find this feature" map: 1–2 (mostly `table`).
  - Exploratory analytical map: 3–6 (formula + category/pie + histogram + timeseries + range + table).
  - Dashboard map: 6–8. Past ~8 the panel gets crowded.
- **SQL parameters — propose when the source has a natural filter axis** (date range, region, category). Wire `{{paramName}}` placeholders + a `sqlParameters[]` entry + `mapSettings.sqlParameterControls: true`. Skip when the source is static.
- **Description — viewer-facing Markdown.** End users read this in Builder's right-side panel and in share-link previews. Not for authoring notes, agent reasoning, or change history. Use short headings + scannable sections matching the map's narrative — no wall-of-text. When omitted, emit `description: ""` (empty string, never null — null leaks a placeholder); `maps create` auto-fills `""`, `maps update` needs an explicit `""` to clear.

### Opt-in blocks — emit ONLY when the user has explicitly asked

Don't offer them proactively, don't list them in *"what else can I do?"* unless the user is clearly exploring:

| Block | Emit when… |
|---|---|
| `agent` | User asks for an Agent on the map. Run `carto maps agents status` first; drop if disabled. |
| `privacy` (non-private) | User asks to share. Default stays private. |
| `tags` / `description` | User supplies them, or the map is being published externally. |
| `collaborative` | User asks for other org members to edit, not just view. |
| Custom palette / 3D / custom markers | User asks for specific styling, or the default looks wrong. |

### Validate before you write

When you've assembled a map configuration and want an offline sanity check before burning an API call, run `carto maps validate <map.json>`. Same Tier-1 checks as `create` with zero backend calls. Useful when iterating in a loop or handing the JSON to the user.

### Reload Builder after a write

Every write returns as soon as the server accepts the change. Builder loads the map into its in-memory client state once and does not subscribe to server events, so an open `https://<org>/builder/<id>` tab keeps showing stale state until the tab reloads. For remote / external agents (Claude in claude.ai, ChatGPT, MCP clients, anything without local browser access): tell the user. *"Map updated. Reload the Builder tab (Cmd/Ctrl+R) to see changes."*

### Visual verification — `carto maps screenshot`, decided by map shape (no need to ask)

`carto maps screenshot <id>` renders the map to a PNG. Two engines:

- **`light`** (default): @deck.gl/carto `fetchMap` — fast (~3–8 s), no Chromium needed. No widgets / legends / popups (deck layers + basemap only).
- **`full`**: workspace-www `/viewer` in Chromium — feature parity with Builder (~10–20 s); first run downloads ~150 MB Chromium via `npx playwright install chromium`.

**Don't ask the user "want a screenshot?"** — they can't tell whether it's worth the latency. **Decide based on the map's shape**, run it, then **embed the resulting PNG inline in the conversation** so the user sees what landed without leaving chat. The latency cost is real (~5–20 s on top of the create), so use it deliberately, not reflexively.

**Run a screenshot when:**
- The agent just authored a non-trivial map (3+ layers, custom palettes, custom markers, complex widgets, 3D extrusion, custom basemap). Popups don't render on screenshots, so popup-only changes aren't a screenshot trigger.
- The user reports the map looks blank / wrong / off — confirm what's actually rendering before iterating.
- Before publishing publicly — sanity-check the public viewer's render.
- The agent has no other way to see the result (remote / external agents without browser access — Claude in claude.ai, ChatGPT, MCP clients).

**Skip the screenshot when:**
- Simple metadata edit (title / description / privacy / tags).
- Single-dataset rename, column tweak, or other surgical edit on a previously-screenshotted map.
- The user is iterating fast in front of an open Builder tab and can just reload (`Cmd/Ctrl+R`).
- The latency would slow a tight feedback loop and the agent already has high confidence in the output.

**Engine pick:** default to `light` for speed; switch to `full` when the verification depends on widgets or legends (those don't render in `light` — they only show on the Builder/viewer surface that `full` captures). Popups (hover / click / info-panel / custom HTML templates) **don't render on screenshots at all** — neither engine captures them, so don't pick `full` to verify popup output. When in doubt with high stakes (public publish, complex multi-layer): pay the `full`-engine cost.

See [`references/troubleshooting.md`](references/troubleshooting.md) for full screenshot flag reference (`--render-engine`, `--width`, `--height`, `--lat`/`--lng`/`--zoom`, `--hide-overlays`, etc.).

### `keplerMapConfig` is wholesale-replace, not partial-merge

Most top-level fields on `maps update` accept partial patches: `title`, `description`, `tags`, `collaborative`, `privacy`, `agent`, `datasets`. **`keplerMapConfig` does not.** Sending `{keplerMapConfig: {config: {basemapConfig: {...}}}}` as a "partial update" wipes layers / widgets / sqlParameters / viewport. To change anything inside `keplerMapConfig`, use the read-modify-write cycle: `carto maps get <id> --json > /tmp/m.json`, edit, `carto maps update <id> /tmp/m.json`. The CLI rejects wipe-causing partial updates pre-flight; see [`updates.md`](references/updates.md) for the full merge matrix.

### Don't fabricate a map id from a title

If the user refers to a map by name / title rather than UUID:

1. `carto maps list --mine --search "<hint>"` — narrows to the user's own maps matching the hint.
2. **Exactly one match** → use its `id` and confirm before writing.
3. **Multiple matches** → list them with ids + titles, ask which.
4. **Zero matches** → ask if they meant to create a new map.

Never pick a match and write without the user confirming, and never invent a UUID from a title alone.

### Reserve the spec for when the user asks for it

If they say *"show me the JSON"* / *"I'll write it myself"* / *"what's the schema"*, open `carto maps schema` + [`configuration-shape.md`](references/configuration-shape.md). Otherwise keep the conversation about their map, not about ours.

---

## Cheat sheet

**The work is almost always one of three shapes:**

| I want to… | Do this |
|---|---|
| Create a map from a natural-language request (the common path) | Elicit the required inputs from the user (Phase 1), then emit a configuration with just those, `carto maps create < map.json` |
| Edit an existing map — add a dataset, update a layer's style, change privacy, rename, swap basemap, etc. | `carto maps update <id> < partial.json` (partial PATCH; unmentioned fields are preserved — except `keplerMapConfig` which is wholesale-replaced) |
| Duplicate an existing map | `carto maps get <id> --json > map.json`, edit, `carto maps create < map.json` |

> Render + sources + agent checks run automatically on every `create` / `update` and surface as warnings — no separate "validate it will render" step needed.

### Commands you reach for most

```
carto maps list --mine                            # browse what's already there
carto maps get <id> --json                        # read a configuration; pipe back to create/update
carto maps validate [map.json]                    # Tier-1 sanity check, no API calls
carto maps create [map.json]                      # new map from a configuration file
carto maps update <id> [patch.json] [--publish]   # partial update, optional auto-publish
carto maps publish <id>                           # freeze a snapshot for shared/public viewers
carto maps schema [section]                       # JSON Schema reference
carto maps agents status                          # is CARTO AI enabled on this organization?
carto maps screenshot <id>                        # PNG render for visual verification
carto --commands --json                           # full CLI command catalogue (machine-readable)
```

### Inline recipes

**Duplicate an existing map** — most reliable way to produce a working map; the source configuration is already Builder-shaped, so the partial-layer pitfall doesn't apply.

```sh
carto maps get <source-map-id> --json \
  | jq '.title = "My copy" | del(.id, .privacy)' \
  > new-map.json
carto maps create < new-map.json
```

**Update only the title** (partial PATCH):

```sh
echo '{"title":"Better title"}' | carto maps update <map-id> --json
```

**Add one dataset to an existing map** (merge mode keeps existing datasets):

```sh
carto maps get <map-id> --json > current.json
jq '.datasets += [{"$ref":"extra","type":"table","source":"proj.ds.new_table","connectionId":"<conn-id>","geoColumn":"geom","columns":["geom"],"format":"tilejson","label":"New source"}]' current.json > updated.json
carto maps update <map-id> --json < updated.json
```

**Replace all datasets** (destructive — datasets not in the input are deleted):

```sh
carto maps update <map-id> --datasets-mode replace --json < map.json
```

**Update a single dataset's source SQL** (no `keplerMapConfig` wipe risk):

```sh
carto maps datasets update <map-id> <dataset-id> --source "SELECT geom, revenue FROM stores WHERE country = 'ES'"
```

For longer recipes (full JSON bundles), see [`references/examples.md`](references/examples.md).

---

## When in doubt

- **Field unknown / suspect?** `carto maps schema [section]` returns the authoritative JSON Schema.
- **Map renders blank / wrong?** [`references/troubleshooting.md`](references/troubleshooting.md) symptom→fix table.
- **Visual sanity check?** `carto maps screenshot <id>` — PNG render without leaving the terminal.
- **AI agent surfaces?** `carto maps agents status` / `models` / `mcp-tools` / `core-tools`.
- **Stuck after a write?** Tell the user to reload the Builder tab — Builder doesn't subscribe to server events.
