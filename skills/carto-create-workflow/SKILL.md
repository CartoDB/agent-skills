---
name: carto-create-workflow
description: Builds, schedules, and operates analytics DAGs in CARTO Workflows — the no-code/low-code orchestration layer over the data warehouse. Triggers when the user wants to author a workflow, run/edit one, or schedule a DAG. For copying workflows across profiles, see carto-copy-workflows.
license: MIT
---

# carto-create-workflow

CARTO Workflows is a visual DAG builder that compiles to warehouse SQL. Each workflow runs *inside* a connected warehouse — no CARTO compute is involved at execution time. This skill covers the full lifecycle: building the DAG (the bulk of this file) plus operating it via the CLI (CRUD, schedules). Cross-profile copying is owned by [`carto-copy-workflows`](../carto-copy-workflows).

For one-off ad-hoc SQL, use [`carto-query-datawarehouse`](../carto-query-datawarehouse) — workflows are for repeatable, scheduled, multi-step DAGs.

Bundle structure, component schemas, input formats, and gotchas are all served by the CLI — **never hardcode or assume them**. The CLI is the source of truth.

Live introspection commands (use these before reaching for any reference file):

| Command | What it serves |
|---|---|
| `carto workflows schema` | Index of all bundle/DAG schema sections |
| `carto workflows schema bundle` | Top-level bundle shape (id, title, connectionId, config, privacy, tags). `privacy` is a `$ref` — fetch its shape with `carto workflows schema privacy`. Minimal valid form: `"privacy": { "privacy": "private" }` (the inner string is *not* a bare `"private"` — `enums` lists the allowed values for that inner field). |
| `carto workflows schema config` | Full DAG config (schemaVersion, connectionProvider enum, nodes, edges, variables, viewport, useCache, executionSettings, schedule) |
| `carto workflows schema node` | Generic node shape, including `data.version` requirement and `data.title` vs `data.label` |
| `carto workflows schema node.source` | Source/`ReadTable` node shape and the `data.id == data.inputs[0].value` invariant |
| `carto workflows schema node.customsql` | Full customsql node spec |
| `carto workflows schema customsql` | Copy-paste customsql node template (with `version: "2.0.0"`) |
| `carto workflows schema edge` | Edge shape |
| `carto workflows schema handles` | **Edge handle naming reference** — sourceHandle/targetHandle by node type, by operator, by component. Critical for valid edges. |
| `carto workflows schema variable` | Variable (parameter) shape — `{ order, name, type, value, public }` |
| `carto workflows schema schedule` | Declarative schedule metadata fields |
| `carto workflows schema enums` | All valid enums (node types, providers, privacies, schedule frequencies) |
| `carto workflows components list --connection <conn> --json` | Component catalog for the connected warehouse |
| `carto workflows components get <names> --connection <conn> --json` | Per-component `inputs`, `outputs`, `notes` |
| `carto workflows components get <names> --connection <conn> --input-formats --json` | Input-type `format`, `examples`, `pitfalls` |
| `carto workflows --help` | Full command reference, including schedule-expression dialects per engine |

References (only for what the CLI doesn't serve):
- [`references/providers/`](references/providers/) — per-warehouse details (BigQuery, Snowflake, Databricks): identifier quoting, column casing, AT path.
- [`references/scheduling.md`](references/scheduling.md) — `add` vs `update` semantics, bundle-level schedule warning, activity-log verification.

For copying a workflow across profiles (dev → prod, customer-segregated workspaces), use [`carto-copy-workflows`](../carto-copy-workflows).

> **`connectionProvider` must match the connection.** `config.connectionProvider` (enum in `schema enums`) must match the connection's actual provider — mismatches generate the wrong SQL dialect and error at runtime. Look it up with `carto connections list --search <name> --json` (`connections get` requires a UUID).

---

## Development process

**Follow these 6 phases in order for every workflow request.** Do not skip or reorder them.

### Phase 1 — Gather information

1. **Identify data sources.** If the user named tables, note them. Otherwise discover what's available with `carto connections list` and `carto connections describe <connection> "<fqn>"`.
2. **Clarify the goal.** What transformation? What output? What filters/conditions?
3. **Determine the connection.** `carto connections list | head -n 20`. Note its `provider` (`bigquery` / `snowflake` / `databricks`) — you will need it for the next step.
4. **Read the provider reference.**

   <critical-rule id="read-provider-reference">
   Before writing any node, you MUST open `references/providers/<provider>.md` (e.g. `references/providers/bigquery.md`) and read it end-to-end. This is non-negotiable.

   <why>It contains identifier-quoting rules, column-casing behaviour, Analytics Toolbox path, schedule-expression dialect, and customsql `$a`/`$b` placeholder requirements that `validate` cannot catch. These only surface later as `verify-remote` failures or runtime SQL errors, and are the single most common cause of late-stage rework.</why>

   <do-not>Do not skip this step because the next phases look concrete. Do not rely on memory of a previous run — provider files change.</do-not>
   </critical-rule>
5. **Fetch the component catalog.** `carto workflows components list --connection <connection> --json` — your only source of truth for component names.

### Phase 2 — Design the approach

1. **Select components** from the catalog you fetched.
2. **Fetch schemas for every component you plan to use.** `carto workflows components get <name1>,<name2>,<name3> --connection <connection> --json` returns `inputs`, `outputs`, and `notes`. Read the `notes` array carefully — it contains gotchas.
3. **Fetch input type formats.** `carto workflows components get <component1>,<component2> --connection <connection> --input-formats --json` returns `format`, `examples`, and `pitfalls` for each input/output type. Pass **component names** (e.g. `native.buffer`), NOT input-type names.
4. **Design principles:**
   - Preserve identifier and spatial columns throughout.
   - **Prefer native components over `native.customsql`. This is not a soft preference.** See [Native-first rule](#native-first-rule).
   - H3/Quadbin columns work for visualization without geometry extraction.
   - Use standard names for visualization: `geom`, `h3`, `quadbin`.

### Phase 3 — Present plan, surface gaps, confirm

Present the workflow plan (components, data flow, decisions). Then **explicitly enumerate every gap** before building:

- **Unresolved parameters** — thresholds, radii, filter values, time windows, k for k-NN, aggregation columns, output table names, etc.
- **Analytical decisions left to the user** — significance levels, distance metrics, join types, null-handling, dedup keys, CRS, H3/quadbin resolution.
- **Ambiguities in the request** — anything where you had to guess intent.

For each gap, **propose a sensible default with its rationale** (e.g. "p-value threshold: suggest `0.05` — conventional significance level", "buffer distance: suggest `1000m` — matches the city-block scale of the input"), and **ask the user to confirm or override**. Never silently pick a value for a user-facing analytical parameter. **Wait for confirmation** before building.

### Phase 4 — Build the workflow

1. Create the workflow file. Get the bundle/node/edge/variable shapes from `carto workflows schema [section]` (start with `bundle`, then `node`, `node.source`, `node.customsql`, `edge`, `handles`). For customsql nodes, copy the template from `carto workflows schema customsql`.

   If you set the optional top-level `privacy`, it must be an **object**, not a string: `"privacy": { "privacy": "private" }` (the field name nests). Omit the field entirely if you don't need it — `"privacy": "private"` will fail `validate`.

   **Source nodes** (`type: "source"`) — treat `ReadTable` like any other component: fetch its spec with `carto workflows components get ReadTable --connection <conn> --json` to get the canonical `inputs[*].title` and `inputs[*].description`. (`ReadTable` is hidden from `components list` because it's grouped `__internal`, but `get` returns it normally.) Two source-only rules `get` cannot tell you, both from `schema node.source`:
   - The canvas display name lives in `data.label`, NOT `data.title`. Generic nodes use `title`; source nodes use `label`.
   - `data.id` and `data.inputs[0].value` must be the same FQN.
2. **Run `validate` after every write to the file.** It's offline, fast, and catches structural errors immediately:
   ```bash
   carto workflows validate workflow.json --json
   ```
   Treat any save without a passing `validate` as broken — fix before continuing to the next node/edge.

   **`validate` is authoritative.** If a component schema from `components get` disagrees with what `validate` accepts, trust `validate` and adjust the bundle to satisfy it. Do not "fix" the bundle to match the schema if it's already passing validation.
3. **Run `verify` at branch boundaries**, not on every save. It hits the warehouse (slower, requires auth), so reserve it for whole sub-DAGs once their structure validates clean, and once at the end before presenting:
   ```bash
   carto workflows verify-remote workflow.json --connection <connection-name> --json
   ```
   `verify` is what catches column-type mismatches, missing tables, and AT resolution — things `validate` cannot see.
4. Fix errors silently — don't expose implementation details to the user.
5. Iterate until complete, with both `validate` and a final `verify` clean.

### Phase 5 — Present result

Summarize what was built. Confirm validation success. Wait for user confirmation.

### Phase 6 — Upload to CARTO

1. Ask if the user wants to upload.
2. Upload and provide the URL:
   ```bash
   carto workflows create --file workflow.json --verify
   ```
   The connection comes from `connectionId` inside the bundle — no `--connection` flag here.
3. Do NOT auto-execute unless explicitly requested.

---

## Native-first rule

`native.customsql` is the *last* tool to reach for, not the first. Before writing a customsql node, attempt the native chain. Fall back to customsql only if at least one of these is true:

- The native chain would require **more than ~4-5 nodes** to express the same logic.
- A specific operation has **no native equivalent at all** (verified via `carto workflows components list`).
- The expression genuinely needs raw warehouse SQL (e.g., `ST_UNION_AGG`, `LOGICAL_OR`, `ML.PREDICT`, last-N windowing).

Common operations and their native equivalents — try these first:

| If you'd write SQL like… | Use natives |
|---|---|
| `WHERE x = …` / multi-condition filter | `native.where` (predicate), `native.wheresimplified` (UI builder), `native.spatialfilter` (geometry-based match/unmatch split), `native.select` (column projection) |
| `SELECT a, b, c FROM t` (multi-column projection / rename / multi-expression) | `native.select` (one node, free-form SELECT body) |
| `SELECT ..., expr AS c FROM t` (add **one** computed column) | `native.selectexpression` (one column + one expression per node) |
| `GROUP BY k, SUM(x), AVG(y), COUNT(*)` (single key) | `native.groupby` — `groupby` input is a single `Column`, not multi-column. For multi-key grouping use `native.customsql`. |
| `JOIN ... ON a.k = b.k` (any join type) | `native.joinv2` |
| `JOIN ... ON ST_INTERSECTS / ST_CONTAINS / ST_WITHIN` | `native.spatialjoin` |
| `MIN(ST_DISTANCE(a.geom, b.geom))` across two tables | `native.distance` (augments the **main** table in place with `nearest_id` + `nearest_distance` — rename them per source if you chain two `native.distance` nodes for two reference tables) |
| `ST_BUFFER(geom, d)` | `native.buffer` |
| H3 binning / boundary / center / polyfill | `native.h3frompoint`, `native.h3boundary` (output geometry column is named `<h3col>_geo`, e.g. `index_geo` — **not** `geom`), `native.h3center`, `native.h3polyfill` |
| `ORDER BY ... LIMIT n` | `native.orderby` + `native.limit` |
| z-score / standardization | `native.normalize` |
| weighted composite score | `native.spatialcompositeunsupervised` (weighted/PCA), `native.spatialcompositesupervised` (target-driven) |
| Getis-Ord Gi*, GWR, isolines | `native.getisord`, `native.gwr`, `native.isolines` |
| Save final node to a table | `native.saveastable` |

Signals you're reaching for customsql too early — stop and look for a native chain instead:

- The customsql is just a `WHERE` clause, a single `JOIN`, a `GROUP BY` with one or two aggregates, or a column projection.
- It wraps a single warehouse function (`ST_BUFFER`, `H3_FROMGEOGPOINT`, etc.) for which a dedicated native exists.
- Its only purpose is to project/rename/re-cast columns — use `native.select` (free-form SELECT body, one node) for multiple columns; `native.selectexpression` is for adding a single computed column.
- You're chaining customsql outputs through more customsql nodes — chain natives instead.

When customsql is genuinely the right call, the per-warehouse SQL-dialect footguns live in the matching `references/providers/*.md` (BigQuery backticks, Snowflake casing, Databricks identifiers).

---

## Fetching component & input information

**Do not rely on memorized component schemas or input formats.** Always fetch live data from the CLI.

| Command | Purpose |
|---------|---------|
| `carto workflows components list --connection <conn> --json` | List all available components |
| `carto workflows components get <names> --connection <conn> --json` | Component schemas with `inputs`, `outputs`, and `notes` |
| `carto workflows components get <names> --connection <conn> --input-formats --json` | Input type `format`, `examples`, `pitfalls` for the types those components use |

What to look for in the response:

- **Component `notes`** — gotcha strings: non-obvious behavior, deprecated status, output column naming.
- **Input `format`** — prose describing the expected value shape.
- **Input `examples`** — concrete JSON snippets showing correct usage.
- **Input `pitfalls`** — common mistakes, evaluation order, format quirks.
- **Component `version`** — copy verbatim into the authored node's `data.version` (string). Generic nodes without it are flagged OUTDATED in Builder.
- **Input `options` (Selection / Enum)** — the engine matches values **exactly**. Copy each option string verbatim — preserve case, never paraphrase or Title-Case (e.g. spatialjoin's `jointype` accepts `"inner"`, not `"Inner"`).

For values that may evolve over time (component versions, bundle/config defaults, enum option lists), treat the CLI's `components get` / `schema` output as the single source of truth — never hardcode values in your own templates. Specifically:

- **`config.schemaVersion`** — read the current default from `carto workflows schema config --json` → `properties.schemaVersion.default`. Today it's `"1.0.0"` (string), but resolve at author time so future bumps don't require a skill update.

---

## Provider-specific notes

Different warehouses have different SQL dialects, table-naming conventions, and column-casing rules. Always check the matching provider guide:

- [`references/providers/bigquery.md`](references/providers/bigquery.md)
- [`references/providers/snowflake.md`](references/providers/snowflake.md)
- [`references/providers/databricks.md`](references/providers/databricks.md)

Input-type formats (`Table`, `Column`, `ColumnsForJoin`, `SelectColumnAggregation`, etc.) and per-component gotchas (including the "AT components need `verify`, not `validate`" rule) are served by the CLI itself — see [Fetching component & input information](#fetching-component--input-information).

---

## Operating a workflow (after it's built)

Once a workflow exists in CARTO, the CLI exposes CRUD and schedule management. Quick reference:

```bash
# List / inspect
carto workflows list --json
carto workflows get <id>

# Update with edited JSON
carto workflows update <id> --file workflow.json

# Add / remove a schedule
carto workflows schedule add <id> --expression "every day 08:00"
carto workflows schedule remove <id>
```

Always-on guidance:

- **Workflows run on the connection's warehouse.** A workflow with a BigQuery connection cannot use Snowflake-specific SQL.
- **Schedule expression syntax depends on the engine** — natural-language for BQ/CARTO DW (`"every day 08:00"`), cron for Snowflake/Postgres (`"0 8 * * *"`), Quartz cron for Databricks (`"0 0 8 * * ?"`). See [`references/scheduling.md`](references/scheduling.md). Picking the wrong dialect fails at schedule-add time.
- **Copying a workflow across profiles** (dev → prod, customer-segregated workspaces) is owned by [`carto-copy-workflows`](../carto-copy-workflows) — connection mapping and schedule re-add live there.
- **Deleting a workflow doesn't delete its outputs.** Tables/views the workflow created in the warehouse persist; clean them up with `carto sql job` if needed.
- **`workflows update` replaces the whole DAG.** There's no per-node patch. Always `get` first, edit, then `update`.
- **Workflow execution status** lives in the activity log (`WorkflowRun`, `WorkflowExecutionComplete` event types). For health monitoring of scheduled workflows, query that log via [`carto-query-datawarehouse`](../carto-query-datawarehouse) — see `references/activity-queries.md` in that skill.
