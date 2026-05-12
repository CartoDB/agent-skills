# Arcade translation — supported subset → SQL / Builder widget

ArcGIS Arcade is a JavaScript-like expression language used in popups, labels, and visual variables. This skill translates a **deliberately narrow subset** automatically; everything else is recorded as `Notes: arcade-skipped: <fragment>` on the manifest entry and dropped from the migrated map.

The supported subset is everything that has a clean, mechanical translation to a SQL derived field or a Builder widget. Conditional logic, cross-feature references, string manipulation, and date math all need human judgment to be useful and are deferred.

## Supported (translate automatically)

### 1. Single attribute reference

```
$feature.AttrName
```

Translation: bind directly to the attribute. In a popup, the popup field already references the column. In a label expression, set `labelField`. In a visualVariable's `valueExpression`, set the corresponding `*Field`.

Detection: regex `^\s*\$feature\.[A-Za-z_][A-Za-z0-9_]*\s*$` on the trimmed expression.

No SQL needed; no widget needed.

### 2. Per-row math on attributes

```
$feature.population / $feature.area
$feature.population / $feature.area * 1000
$feature.A + $feature.B
$feature.revenue - $feature.cost
$feature.x * 2
($feature.a + $feature.b) / 2
```

Translation: SQL expression in a derived field on the layer's source query. Replace every `$feature.X` with `X`, validate with `sqlglot`, emit:

```sql
SELECT *,
       (population / NULLIF(area, 0)) * 1000 AS _density
FROM <migrated_fqn>
```

The synthetic field name (`_density`) is `_` + slug of the `expressionInfos[].title` (or `name` if title is absent). The popup property references the synthetic field.

**Supported operators**: `+`, `-`, `*`, `/`, `%`. Parentheses for grouping.

**Always wrap divisors in `NULLIF(<x>, 0)`** to avoid divide-by-zero crashes on rows where the divisor is zero. The translator does this mechanically when it sees a `/` operator.

**Operator precedence**: standard (multiplication and division before addition and subtraction). `sqlglot` confirms after translation.

Detection: expression contains `$feature.X` references and only uses `+`, `-`, `*`, `/`, `%`, parentheses, whitespace, and numeric literals. No function calls.

### 3. Simple aggregations on a single field

```
Count($feature)
Max($feature.population)
Min($feature.population)
Sum($feature.population)
Average($feature.population)
Mean($feature.population)
```

Translation: not a derived field — these are layer-level aggregates. Translate to a Builder `formula` widget added to `keplerMapConfig.config.widgets[]`:

```json
{
  "type": "formula",
  "title": "<expressionInfo.title or 'Computed'>",
  "dataId": "<layer-data-id>",
  "column": "population",
  "operation": "sum"
}
```

| Arcade function | Builder formula `operation` |
|---|---|
| `Count($feature)` | `count` |
| `Max($feature.X)` | `max` |
| `Min($feature.X)` | `min` |
| `Sum($feature.X)` | `sum` |
| `Average($feature.X)` / `Mean($feature.X)` | `avg` |

When `Count($feature)` is used (no field argument), set `column: null` (or whatever Builder's row-count convention is — fetch live via `carto maps schema widgets.formula`).

These widgets count toward Builder's recommended 6-8 widget panel density. If the source map already has many widgets via other paths (e.g. lots of `expressionInfos[]`), surface a Note about widget density.

Detection: regex `^\s*(Count|Max|Min|Sum|Average|Mean)\s*\(\s*(\$feature(\.\w+)?)\s*\)\s*$` (case-insensitive on the function name).

## Deferred (skip with Note)

Any expression matching these patterns is skipped with `Notes: arcade-skipped: <truncated-fragment>` (truncate to first 80 chars):

- **Conditional logic**: `IIf(...)`, `Iif(...)`, `If(...)`, `When(...)`, `if/else` blocks, ternary forms.
- **Cross-feature references**: `FeatureSetByName($map, "...")`, `Filter(featureSet, "...")`, `Intersects(...)`, `Within(...)`.
- **String functions**: `Concatenate`, `Upper`, `Lower`, `Trim`, `Split`, `Replace`, `Find`, `Mid`, `Left`, `Right`, `TextFormatNumber`.
- **Date functions**: `Date(...)`, `DateAdd`, `DateDiff`, `Now()`, `Today()`, `ToLocal`, `ToUTC`, `Year`, `Month`, `Day`.
- **Type conversions**: `Number(...)`, `Text(...)`, `Boolean(...)`, `Date(...)`.
- **Variable assignment**: `var x = ...; return ...`
- **Loops**: `for`, `while`.
- **Function definitions and lambdas**.
- **Combined aggregations**: `Sum(pop) / Count($feature)`, `Max(...) - Min(...)` — combinations are out of scope; skip + note.
- **Anything else** not in the "Supported" section above.

## Validation

Every translated SQL fragment is validated with `sqlglot` against the target warehouse's dialect (read `target_warehouse` from the manifest front-matter):

```python
import sqlglot

dialect_map = {
    "bigquery": "bigquery",
    "snowflake": "snowflake",
    "redshift": "redshift",
    "postgres": "postgres",
    "databricks": "databricks",
    "oracle": "oracle",
}
dialect = dialect_map.get(target_warehouse, "bigquery")

try:
    sqlglot.parse_one(sql_expression, dialect=dialect)
except sqlglot.errors.ParseError as e:
    note_arcade_skipped(expression_info, reason=f"sqlglot rejected: {e}")
    continue
```

If `sqlglot` rejects the output, treat the expression as untranslatable (skip + note) rather than emitting broken SQL into the layer source.

If `sqlglot` isn't installed (`pip install sqlglot` not run), the agent skips client-side validation and relies on `carto maps validate` at compose time. Surface a one-line warning at start: *"sqlglot not installed — Arcade translations will be validated server-side only."*

## Translation flow per expression

```
For each Arcade expression in popupInfo / labelingInfo / visualVariables:
  trim whitespace
  if matches single-attribute pattern:
      → bind to attribute directly
  elif matches per-row-math pattern (only +-*/% on $feature.X with parens/literals):
      → emit derived SQL field; validate with sqlglot
  elif matches aggregation pattern (Count/Max/Min/Sum/Average/Mean of one $feature[.X]):
      → emit Builder formula widget added to widgets[]
  else:
      → record arcade-skipped: <truncated-expression> in Notes
      → fall back to plain field reference if there's an obvious one
        (e.g. when the expressionInfo's title matches a real field name)
```

## Worked example: end-to-end on a popup with three expressions

Source `expressionInfos[]`:

```json
[
  { "name": "expr1", "title": "Density",   "expression": "$feature.pop / $feature.area * 1000" },
  { "name": "expr2", "title": "Avg Pop",   "expression": "Average($feature.pop)" },
  { "name": "expr3", "title": "Status",    "expression": "IIf($feature.x > 100, 'High', 'Low')" }
]
```

Outcome:

| Expression | Outcome |
|---|---|
| `expr1` | Derived SQL field `_density` in layer source query: `(pop / NULLIF(area, 0)) * 1000`. Popup property `_density` of type number. |
| `expr2` | Builder `formula` widget `{title: "Avg Pop", operation: "avg", column: "pop", dataId: <layer-id>}` added to `widgets[]`. |
| `expr3` | `Notes: arcade-skipped: expressionInfos[expr3]: IIf($feature.x > 100, 'High', 'Low')`. Popup omits this expression's contribution. |

## Source-query composition

When one or more per-row-math expressions translate to derived fields, the layer's source query becomes a `query` (not `table`) in the kepler `datasets[]` entry. Compose:

```sql
SELECT *,
       (pop / NULLIF(area, 0)) * 1000 AS _density,
       (revenue - cost) AS _profit
FROM <migrated_fqn>
```

Reference this query as the layer's `source` in the kepler dataset config:

```json
{
  "$ref": "<layer-data-id>",
  "type": "query",
  "source": "SELECT *, (pop / NULLIF(area, 0)) * 1000 AS _density FROM `demo-bq.shared.populations`",
  "connectionId": "<conn-id>",
  "format": "tilejson"
}
```

If the layer has no Arcade expressions to translate, leave the dataset as `type: "table"` referencing the migrated FQN directly — simpler and faster to render.

## When in doubt

- Translation produces SQL that `carto maps validate` rejects after composition? Skip + note. Don't try to fix the SQL by hand.
- Multiple aggregations referenced from one popup expression (`Sum(pop) / Count($feature)`)? Skip + note.
- The expression's `title` is empty? Use the `name` field as the widget title; fall back to `"Computed"` if both are empty.
- An aggregation references a field NOT in the layer (typo or removed)? `sqlglot` won't catch this — `carto maps validate` will. Skip + note when the validator rejects.
- Two `expressionInfos[]` resolve to the same synthetic name (`_density` x 2)? Append `_2`, `_3` to subsequent ones.
