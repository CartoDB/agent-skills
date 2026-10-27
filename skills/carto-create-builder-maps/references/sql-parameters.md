# SQL parameters

Let users change a filter and re-query live — Builder renders the parameter as a viewer-side control, the warehouse re-runs the query on each change. Four parameter kinds: `Category`, `DateRange`, `Numeric`, `NumericRange`. The canonical authoring shape is simple:

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
2. `keplerMapConfig.config.sqlParameters[]` — the control itself. Each entry carries its `sqlName` (inside `item`, or inside `start` / `end`) matching the `{{paramName}}` in the source. That placeholder is the whole binding: a parameter reaches a dataset because the dataset's `source` names it. A `dataSources[]` list on the parameter does not establish it — see the note under the kind examples.
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
// DateRange — start + end date pickers. ISO-8601 YYYY-MM-DD only (no relative dates).
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

Run `carto maps schema sqlparameters` for the authoritative discriminated schema. The four kinds at a glance:

| Kind | Source-side syntax | Value shape | Notes |
|---|---|---|---|
| `Category` | `WHERE col IN {{name}}` | `item: { value: [...], sqlName }` + `values: [...]` (picker options) + `selectionMode: "multi"` (default) \| `"single"` | `multi` empty selection filters to zero rows on BigQuery; for `multi` only, the CLI coerces an unset / empty `item.value` to a copy of `values` ("all selected") to prevent silent-blank legends. `single` requires `item.value` of length 1; the top-level `defaultValue` is optional (Builder resolves the effective default as `defaultValue ?? values[0]`) but when present must be a string drawn from `values[]`. Optional `orderBy` (same enum as category widgets). |
| `DateRange` | `WHERE col >= {{from}} AND col <= {{to}}` | `start: { value, sqlName }` + `end: { value, sqlName }` (ISO-8601 `YYYY-MM-DD`, no relative dates) | Builder validates `end >= start` at save. `allowedRange` is **deprecated** — preserved on read but no longer enforced; omit on new maps. |
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

---

