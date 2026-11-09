# SQL parameters

Let users change a filter and re-query live: Builder renders the parameter as a viewer-side control, the warehouse re-runs the query on each change. A control is wired in one of two ways:

- **SQL placeholder**: the control fills a `{{paramName}}` in the dataset SQL. Four kinds: `Category`, `DateRange`, `Numeric`, `NumericRange`. Use it when the value has to land inside the query (a threshold, a buffer distance, a weight, an analysis input), and for every numeric control.
- **Source column**: the control names a column of a `table` or `query` dataset and Builder filters that dataset by it, the way a widget does, with no SQL to edit. Two kinds: `SourceCategory` (text column) and `SourceDateRange` (date or timestamp column). See *Source-bound controls* below.

Both wirings sit in the same `sqlParameters[]` array and can share a map. A placeholder control's canonical authoring shape is simple:

**Write `{{paramName}}` in `dataset.source`.** The CLI auto-translates that into whatever the warehouse expects. The SQL around the placeholder is yours and runs on the dataset's connection, so write it in that provider's dialect (quoting, functions, dates, spatial calls). NAMED placeholders: `@paramName` on BigQuery (and the BigQuery-backed `carto` / `carto_dw`, with `UNNEST(...)` for arrays), `:paramName` on `databricksRest` / `databricksWarehouse` and Fabric. POSITIONAL: `$1` / `$2` on Postgres and Redshift, `:1` / `:2` on Oracle, and `?` on Snowflake. The CLI fetches the dataset's connection `provider_id` and picks the right dialect at translate time; a provider outside this list throws instead of writing broken SQL.

**What ends up persisted** (what you'll see on a configuration read back via `get --json`):
- **`dataset.source`** — the *parsed* form, provider-native. `SELECT * FROM t WHERE agency IN UNNEST(@agency)` on BigQuery.
- **`dataset.queryTemplate`** — the original with `{{agency}}`. Builder reads this when it shows the query in its SQL panel.
- **`dataset.queryParameters`** — the initial bound values. The **container** is decided by the provider, NOT by the parameter kind: a named dict keyed by `sqlName` on the named-placeholder providers (BigQuery, `databricksRest` / `databricksWarehouse`), a positional array on the others (Postgres, Snowflake, Redshift, Oracle), ordered to match the placeholders. The **value inside** is what follows the parameter kind: a list for `Category`, a scalar for `DateRange` / `Numeric` / `NumericRange`. Postgres stores the `Category` list as a raw array; Snowflake, Redshift and Oracle store it as a JSON string.
  - BigQuery / `databricksRest` / `databricksWarehouse`: `{"agency": ["HPD","DSNY"], "date_from": "2022-01-01"}`
  - Postgres: `[["HPD","DSNY"], "2022-01-01"]`
  - Snowflake / Redshift / Oracle: `["[\"HPD\",\"DSNY\"]", "2022-01-01"]`

**What you have to set** to make the parameter *appear* to the user:
1. `keplerMapConfig.config.mapSettings.sqlParameterControls: true` — shows the parameters bar to viewers of the shared or public map. Editors always see it. Builder sets it to `true` when an Editor creates the first parameter.
2. `keplerMapConfig.config.sqlParameters[]`: the control itself. Each placeholder entry carries its `sqlName` (inside `item`, or inside `start` / `end`) matching the `{{paramName}}` in the source. That placeholder is the whole binding: a parameter reaches a dataset because the dataset's `source` names it. A `dataSources[]` list on the parameter does not establish it; see the note under the kind examples.
3. Order — SQL parameters appear in the parameters bar above the map, and the `sqlParameters[]` array order is their order in the bar, left to right. There is no index field: to reorder, reorder the array. Put the most-used parameters first, because they stay visible when the bar overflows and the rest scroll behind arrows. Builder writes the same array back when an Editor drags a parameter, so carry the order through on every update.

**Authoring → persistence example (BigQuery).**

What you write:
```jsonc
"datasets": [{
  "source": "SELECT * FROM t WHERE agency IN {{agency}}",
  "queryTemplate": null,                // let the CLI derive it
  "queryParameters": null,              // let the CLI derive it
  "connectionId": "<conn-id>"
}]
```

What the CLI persists after `maps create`/`maps update`:
```jsonc
{
  "source":         "SELECT * FROM t WHERE agency IN UNNEST(@agency)",
  "queryTemplate":  "SELECT * FROM t WHERE agency IN {{agency}}",
  "queryParameters": { "agency": ["HPD", "DSNY"] }
}
```

> **Gotcha:** if you explicitly set both `source` with `{{...}}` AND `queryTemplate` with `{{...}}`, older CLI versions short-circuited and left the placeholder in `source` unparsed — tiles 400'd. Fixed from 0.5.x onwards: the CLI always re-parses when `{{}}` is present in `source`. The safe authoring habit is to **leave `queryTemplate` and `queryParameters` null** when you put a placeholder in `source`.

### Parameter kind examples

Minimal valid `keplerMapConfig.config.sqlParameters[]` entry per kind. Run `carto maps schema sqlparameters` for the full discriminated schema. Each entry needs `id`, `name` (user-visible), `type`, plus a kind-specific value shape.

> **Don't author `dataSources[]`.** Builder maintains it as a cache of *which datasets use this parameter*, and rebuilds it from the live datasets on every read — matching on the query template, not on the stored ids. So it decides nothing: a stale or missing entry changes no behaviour, which is also why validation deliberately leaves it alone rather than blocking a round-trip over it. The binding is the `{{placeholder}}` in `dataset.source`. Omit it when authoring; leave it untouched when you're round-tripping a bundle that already carries it.

```jsonc
// Category — pick from a list (multi or single selection).
// Source-side: WHERE col IN {{agency}}
{
  "id": "p-agency",
  "name": "Agency",
  "type": "Category",
  "values": ["NYPD", "HPD", "DSNY", "DOT", "DEP"],     // picker options
  "item": { "value": ["NYPD"], "sqlName": "agency" },  // default selection
  "selectionMode": "multi",                            // "multi" (default) | "single"
  "orderBy": "frequency_desc"                          // optional — same enum as category widgets
}
```

```jsonc
// DateRange: start + end date pickers. ISO-8601 YYYY-MM-DD; a live range goes in `default` (see Default dates).
// Source-side: WHERE col >= {{date_from}} AND col <= {{date_to}}
{
  "id": "p-date",
  "name": "Date",
  "type": "DateRange",
  "start": { "value": "2024-01-01", "sqlName": "date_from" },
  "end":   { "value": "2024-12-31", "sqlName": "date_to" }
}
// Builder validates end >= start at save time.
// `allowedRange` is DEPRECATED — preserved on read but not enforced; omit on new maps.
```

```jsonc
// Numeric — single-value scalar picker.
// Source-side: WHERE col = {{weight}}
{
  "id": "p-weight",
  "name": "Weight threshold",
  "type": "Numeric",
  "item": { "value": 0.5, "sqlName": "weight" },
  "defaultValue": 0.5,
  "min": 0, "max": 1, "step": 0.05
}
```

```jsonc
// NumericRange — two-handle slider on a numeric range.
// Source-side: WHERE col BETWEEN {{score_from}} AND {{score_to}}
{
  "id": "p-score",
  "name": "Score range",
  "type": "NumericRange",
  "start": { "value": 10,  "sqlName": "score_from" },
  "end":   { "value": 100, "sqlName": "score_to" },
  "min": 0, "max": 100, "step": 1
}
```

### Parameter types — reference table

Run `carto maps schema sqlparameters` for the authoritative discriminated schema. The four placeholder kinds at a glance (the two source-bound kinds are under *Source-bound controls*):

| Kind | Source-side syntax | Value shape | Notes |
|---|---|---|---|
| `Category` | `WHERE col IN {{name}}` | `item: { value: [...], sqlName }` + `values: [...]` (picker options) + `selectionMode: "multi"` (default) \| `"single"` | `multi` empty selection filters to zero rows on BigQuery; for `multi` only, the CLI coerces an unset / empty `item.value` to a copy of `values` ("all selected") to prevent silent-blank legends. `single` requires `item.value` of length 1; the top-level `defaultValue` is optional (Builder resolves the effective default as `defaultValue ?? values[0]`) but when present must be a string drawn from `values[]`. Optional `orderBy` (same enum as category widgets). |
| `DateRange` | `WHERE col >= {{from}} AND col <= {{to}}` | `start: { value, sqlName }` + `end: { value, sqlName }` (ISO-8601 `YYYY-MM-DD`; a live range goes in `default`, see *Default dates*) | Builder validates `end >= start` at save. `allowedRange` is **deprecated**, preserved on read but no longer enforced; omit on new maps. |
| `Numeric` | `WHERE col = {{name}}` | scalar `value` + `sqlName` + top-level `defaultValue`, `min`, `max`, optional `step` | Single value picker. |
| `NumericRange` | `WHERE col BETWEEN {{from}} AND {{to}}` | `start` / `end`, each `{ value, sqlName }`, + required top-level `min` / `max` and optional `step` bounding both ends | Range slider. |

### Tier-1 rules

- **`sqlName` format** must match `/^[a-zA-Z_][a-zA-Z0-9_]*$/` (same regex as Builder).
- **`sqlName` unique per map** — two parameters with the same `sqlName` collide at runtime. Tier-1 rejects.
- **`Category` `values[]` is not capped by Tier-1.** Builder's editor fetches at most 1000 values, and a long list is still a poor picker (wide `IN (…)` lists also strain query limits). If the column genuinely has >1000 distinct values, **don't ship a Category picker** — pick the most common N (`orderBy: "frequency_desc"` mirrors Builder's default), or give the viewer a `Numeric` / `NumericRange` / `DateRange` parameter.
- **Providers** — BigQuery (incl. `carto` / `carto_dw`), Snowflake, Postgres, Redshift, Databricks (`databricksRest`, `databricksWarehouse`), Oracle and Fabric. Any other provider throws `Unsupported provider for SQL parameter substitution`.
- **Orphaned placeholders** — `{{foo}}` in a `dataset.source` with no matching parameter throws `Invalid sql parameter placeholder` at parse time.
- **Unreferenced parameters** — a parameter that no dataset references is carried through (useful for "defined but not yet wired" configs).
- **`id` unique per map** — two parameters with the same `id` are rejected; parameters are keyed by id when edited or reordered.
- **`Category` values are strings.** `values[]` and `item.value` hold strings, and the warehouse receives a list of strings (cast to `text[]` on Postgres, `VARCHAR2` on Oracle). Filtering a numeric column with `IN {{name}}` fails on type; cast the column to a string in the SQL.
- **`Category` `values[]` must not be empty** — Builder will not save a picker with nothing to choose.
- **`Numeric` needs `defaultValue`**, and for `Numeric` / `NumericRange` `max` must exceed `min`.
- **Write the placeholder bare.** A `Category` placeholder already expands to a list on every provider, so `IN {{name}}` is the only form: `IN UNNEST({{name}})` becomes a double `UNNEST` on BigQuery, and `IN ({{name}})` or `= {{name}}` break too. Never quote a placeholder (`'{{name}}'` is still replaced, inside the string), and never pad it (`{{ name }}` is not trimmed, so it matches no parameter).
- **Comments are stripped** from the persisted `source` when it carries placeholders; `queryTemplate` keeps the original.

### Source-bound controls: `SourceCategory`, `SourceDateRange`

A source-bound control is wired to a column instead of a placeholder. Use it when the control only narrows the rows of a `table` or `query` dataset by a text or date column. Builder reads the column's values itself, so the dataset SQL stays untouched and the editor writes no `{{placeholder}}`.

```json
{
  "id": "c-state",
  "name": "State",
  "type": "SourceCategory",
  "binding": { "datasetId": "$ref:crashes", "column": "state" },
  "selectionMode": "multi",
  "orderBy": "frequency_desc"
}
```

```json
{
  "id": "c-date",
  "name": "Crash date",
  "type": "SourceDateRange",
  "binding": { "datasetId": "$ref:crashes", "column": "crash_ts" },
  "default": { "kind": "relative", "direction": "last", "count": 30, "unit": "day", "anchor": "data" }
}
```

- **`binding`** is required: `{ "datasetId", "column" }`, both non-empty strings. Declare the dataset once with `"$ref": "crashes"` and write `"$ref:crashes"` as the `datasetId` on create, as layers do; use the real dataset id when editing a map that exists. A `$ref:` that names no dataset in the bundle is rejected.
- **Nothing else wires it.** A source-bound entry has no `item`, `values`, `start`, `end` or `sqlName`, and validation rejects them. The reverse holds too: `binding` on a `Category`, `DateRange`, `Numeric` or `NumericRange` entry is rejected. There is no source-bound `Numeric` or `NumericRange`.
- **The bound dataset** is a `table` or `query` dataset; a `tileset` or `raster` cannot be bound. The column must exist in it, as a text column for `SourceCategory` and a date or timestamp column for `SourceDateRange`. Otherwise Builder lists the control as not configured and applies no filter from it.
- **What it writes.** Nothing in the dataset: `source`, `queryTemplate` and `queryParameters` stay as authored. The control's state lives on its own entry, and Builder composes it into the filters it sends with each request for that dataset, like a widget filter: `IN` on the column for a text selection (`NOT IN` for an `{ "except": [...] }` selection), and a range from the start of the first day to the end of the last day (UTC) for dates. Layers on that dataset load filtered, and controls bound to the same dataset narrow each other's value lists.
- **Values are live.** A text control reads its values from the column, so there is no `values` list to author, new values appear on their own, and the 1,000-value cap of the placeholder `Category` does not apply.

`SourceCategory` fields, all optional beyond `binding`:

| Field | Meaning |
|---|---|
| `selection` | What is selected: `"all"`, a list of strings (a `null` entry is the rows with no value), or `{ "except": [...] }` for "all but these" (multi only). Omit it for "nothing narrowed". A `single` control holds one value at most, never `"all"` or `except`. |
| `selectionMode` | `"multi"` (default) or `"single"`. |
| `defaultValue` | A string, single-select only: the value used while `selection` is unset. A single-select with neither takes the first value in `orderBy` order when it loads; Builder does not save that pick. A multi-select with no selection starts on all values. |
| `orderBy` | `frequency_desc` (default), `frequency_asc`, `alphabetical_asc` or `alphabetical_desc`. Unlike the placeholder `Category`, there is no `added_asc` or `added_desc`. |

`SourceDateRange` fields, all optional beyond `binding`: `default` (see *Default dates*) and `selection`, a `{ "start", "end" }` window or `"all"`. With neither, the control applies no filter and opens on the first to the last day of the data.

> **Feature flag.** Builder shows and applies source-bound controls only for organizations that have the `BuilderSourceLinkedControls` flag (`2026-src-link-param-controls`) on. Validation and `create` / `update` do not check it: with the flag off the map saves and Builder applies no filter from these controls. The CLI validates against the schema it was built with, so `carto maps schema sqlparameters` shows whether the installed CLI knows `SourceCategory` and `SourceDateRange`.

### Default dates

A date control, in either wiring, can carry a `default`: the rule that says what the map opens on and what Reset returns to. The rule is stored as a rule and never as resolved dates, so "last 14 days" still reads that way a month later. When you read a map and write it back, keep the rule; do not replace it with the two dates it resolves to today.

| `default` | Window | `SourceDateRange` | `DateRange` |
|---|---|---|---|
| `{ "kind": "all" }` | Every date; applies no filter | yes | no |
| `{ "kind": "fixed", "start": "2024-01-01", "end": "2024-03-31" }` | The typed pair | yes | yes |
| `{ "kind": "relative", "direction": "last", "count": 30, "unit": "day", "anchor": "today" }` | The last N units ending on the anchor day | anchor `today` or `data` | anchor `today` |
| `{ "kind": "relative", "direction": "next", "count": 3, "unit": "month", "anchor": "today" }` | The next N units starting today | yes | yes |
| `{ "kind": "from", "start": "2021-06-01", "anchor": "today" }` | From the fixed date to the anchor day | anchor `today` or `data` | anchor `today` |

- **Anchors.** `today` is the viewer's local date, recalculated on every open. `data` is the last day with data in the bound column, so it exists only on `SourceDateRange`, and `next` has no `data` anchor. A `from` whose anchor day falls before its `start` resolves to that one day.
- **`count` is bounded by its unit**: a whole number from 1 to 365 for `day`, 1 to 120 for `month`, 1 to 50 for `year`. There is no `week` unit. Zero, negatives, decimals and larger numbers are rejected on validate, and Builder shows a relative default outside these bounds as not configured.
- **Arithmetic is calendar-aware and inclusive.** "Last 30 days" ending 2 Sep is 4 Aug to 2 Sep. When a month or year shift lands on a day the target month lacks, the window starts on the next day that exists.
- **Dates** are real calendar dates written `YYYY-MM-DD`, year 1000 or later, and a `start` is never after its `end`.
- **`selection` outranks `default`.** It is the window the control currently opens on (the editor picked it over a live default); omit it to follow the rule. Reset returns to the rule.
- **A rule is applied as written.** If "last 30 days ending today" reaches past the last row of the data, the empty tail shows no rows; it is not shortened.
- **Calendar limits.** A `SourceDateRange` calendar spans the first to the last day of the column, stretched to include the resolved default, so everything Reset returns is pickable. A placeholder `DateRange` calendar stays open.
- **Placeholder `DateRange`.** `start` and `end` stay required, and without a `default` they are the default, as before. With a `relative` or `from` rule, write them as the window the rule resolves to today: Builder and `fetchMap` use the window of `selection` when it is set, otherwise the rule resolved again on every open, in place of `start` and `end`. A `DateRange` cannot use `all` or the `data` anchor, and cannot have `selection: "all"`.

### URL keys and agent tools

Viewers can share a filtered map by URL. With the `BuilderSourceLinkedControls` flag on, every control, in both wirings, uses `control_<id>`: a date range adds `_start` and `_end` (`control_<id>_start=2024-01-01`); a text selection of "all but these" uses `control_<id>_except`, and a selection that includes the rows with no value adds `control_<id>_null=1`. A source-bound date control at all dates travels as `control_<id>=all`. `param_<sqlName>` keeps working for placeholder controls. A control at its published state stays out of the URL, so a live default the viewer never touched keeps rolling.

In a map's AI agent, `get_control_text_values`, `get_control_date_bounds` and `get_control_numeric_bounds` read what a control offers, and `set_control_text`, `set_control_date_range`, `set_control_numeric` and `set_control_numeric_range` change it. The text and date tools cover both wirings (source-bound controls with the flag on).

---

