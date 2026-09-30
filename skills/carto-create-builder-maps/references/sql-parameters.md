# SQL parameters

Let users change a filter and re-query live — Builder renders the parameter as a viewer-side control, the warehouse re-runs the query on each change. Four parameter kinds: `Category`, `DateRange`, `Numeric`, `NumericRange`. The canonical authoring shape is simple:

**Write `{{paramName}}` in `dataset.source`.** The CLI auto-translates that into whatever the warehouse expects. Only two providers use a NAMED placeholder — `@paramName` on BigQuery (with `UNNEST(...)` for arrays) and `:paramName` on Databricks. Every other provider is POSITIONAL: `$1` / `$2` on Postgres and Snowflake, `:1` / `:2` on Oracle. The CLI fetches the dataset's connection `provider_id` and picks the right dialect at translate time.

**What ends up persisted** (what you'll see on a configuration read back via `get --json`):
- **`dataset.source`** — the *parsed* form, provider-native. `SELECT * FROM t WHERE agency IN UNNEST(@agency)` on BigQuery.
- **`dataset.queryTemplate`** — the original with `{{agency}}`. Builder reads this when it shows the query in its SQL panel.
- **`dataset.queryParameters`** — the initial bound values. The **container** is decided by the provider, NOT by the parameter kind: a named dict keyed by `sqlName` on BigQuery and Databricks (the two with named placeholders), a positional array on every other provider (Postgres, Snowflake, Redshift, Oracle), ordered to match `$1`/`$2` or `:1`/`:2`. The **value inside** is what follows the parameter kind: an array for `Category`, a scalar for `DateRange` / `Numeric` / `NumericRange`.
  - BigQuery / Databricks: `{"agency": ["HPD","DSNY"], "date_from": "2022-01-01"}`
  - Postgres / Snowflake / Redshift / Oracle: `[["HPD","DSNY"], "2022-01-01"]`

**What you have to set** to make the parameter *appear* to the user:
1. `keplerMapConfig.config.mapSettings.sqlParameterControls: true` — without this, the control is hidden.
2. `keplerMapConfig.config.sqlParameters[]` — the control itself. Each entry carries its `sqlName` (inside `item`, or inside `start` / `end`) matching the `{{paramName}}` in the source. That placeholder is the whole binding: a parameter reaches a dataset because the dataset's `source` names it. A `dataSources[]` list on the parameter does not establish it — see the note under the kind examples.
3. Optional — `keplerMapConfig.config.uiState`: `controlsPaneOpen: true` opens the right-hand controls pane on load, and `controlsPaneTab: "parameters"` selects the SQL-parameters tab rather than the widgets one.

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
| `Category` | `WHERE col IN {{name}}` | `item: { value: [...], sqlName }` + `values: [...]` (picker options, **capped at 1000** — see Tier-1 rules) + `selectionMode: "multi"` (default) \| `"single"` | `multi` empty selection filters to zero rows on BigQuery; CLI coerces an unset / empty `item.value` to a copy of `values` ("all selected") to prevent silent-blank legends. `single` requires `item.value` of length 1; the top-level `defaultValue` is optional (Builder resolves the effective default as `defaultValue ?? values[0]`) but when present must be a string drawn from `values[]`. Optional `orderBy` (same enum as category widgets). |
| `DateRange` | `WHERE col >= {{from}} AND col <= {{to}}` | `start: { value, sqlName }` + `end: { value, sqlName }` (ISO-8601 `YYYY-MM-DD`, no relative dates) | Builder validates `end >= start` at save. `allowedRange` is **deprecated** — preserved on read but no longer enforced; omit on new maps. |
| `Numeric` | `WHERE col = {{name}}` | scalar `value` + `sqlName` + top-level `defaultValue`, `min`, `max`, optional `step` | Single value picker. |
| `NumericRange` | `WHERE col BETWEEN {{from}} AND {{to}}` | `start` / `end`, each `{ value, sqlName }`, + required top-level `min` / `max` and optional `step` bounding both ends | Range slider. |

### Tier-1 rules

- **`sqlName` format** must match `/^[a-zA-Z_][a-zA-Z0-9_]*$/` (same regex as Builder).
- **`sqlName` unique per map** — two parameters with the same `sqlName` collide at runtime. Tier-1 rejects.
- **`Category` `values[]` capped at 1000** — same ceiling Builder's UI applies (`DEFAULT_MAX_NUMBER_OF_CATEGORIES` in `CategoryValuesFromDataSource.tsx`). The cap is both UX (the multi-select picker doesn't virtualise above ~1k items, so a 50k-value list is unusable) and runtime (tile requests embed the selected list in `WHERE col IN (…)` — wide IN-lists blow past the warehouse's parameter / query-length limits). If the underlying column genuinely has >1000 distinct values, **don't ship a Category picker** — pick the most common N (`orderBy: "frequency_desc"` mirrors Builder's default), or give the viewer a `Numeric` / `NumericRange` / `DateRange` parameter (free-form input, no enumeration). The cap is on what the editor configures, not on warehouse cardinality.
- **Providers** — BigQuery, Snowflake, Postgres, Redshift, Databricks, Oracle all supported.
- **Orphaned placeholders** — `{{foo}}` in a `dataset.source` with no matching parameter throws `Invalid sql parameter placeholder` at parse time.
- **Unreferenced parameters** — a parameter that no dataset references is carried through (useful for "defined but not yet wired" configs).

---

