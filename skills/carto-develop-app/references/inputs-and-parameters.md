# Inputs — dropdowns, sliders, parameterized SQL

Two ways to push user input into the map:

1. **Local filters** via the `filters` object — best for predicates over a fixed table.
2. **Parameterized SQL** via `vectorQuerySource` (or H3/quadbin `*QuerySource`) — best when you need joins, computed columns, or you want the warehouse to do the work.

Use both together when needed.

## Parameterized SQL

**The placeholder syntax and the `queryParameters` container are both fixed by the provider — pick the pair before you write the query:**

| Provider | Placeholder in `sqlQuery` | `queryParameters` |
|---|---|---|
| BigQuery | `@name` | named dict, keyed by the name |
| Databricks | `:name` | named dict, keyed by the name |
| Postgres, Snowflake, Redshift | `$1`, `$2`, … | positional array, in placeholder order |
| Oracle | `:1`, `:2`, … | positional array, in placeholder order |

Named on a positional provider (or the reverse) is not a stylistic slip — the warehouse can't bind it and the query fails.

BigQuery:

```ts
import { vectorQuerySource } from '@carto/api-client';

const dataSource = vectorQuerySource({
  ...cartoConfig,
  sqlQuery: `
    SELECT s.id, s.geom, s.revenue, s.category
    FROM demo.public.stores s
    JOIN demo.public.regions r ON s.region_id = r.id
    WHERE r.name = @selectedRegion
      AND s.year = @selectedYear
      AND s.revenue BETWEEN @minRevenue AND @maxRevenue
  `,
  queryParameters: {
    selectedRegion: 'NY',
    selectedYear: 2025,
    minRevenue: 0,
    maxRevenue: 1_000_000,
  },
});
```

The same query on Postgres or Snowflake — placeholders numbered, values in an array in that order:

```ts
const dataSource = vectorQuerySource({
  ...cartoConfig,
  sqlQuery: `
    SELECT s.id, s.geom, s.revenue, s.category
    FROM demo.public.stores s
    JOIN demo.public.regions r ON s.region_id = r.id
    WHERE r.name = $1
      AND s.year = $2
      AND s.revenue BETWEEN $3 AND $4
  `,
  queryParameters: ['NY', 2025, 0, 1_000_000],
});
```

Values are typed (string, number, boolean, ISO date string). To re-fetch with new values, re-call the source factory with a new `queryParameters` — the source result is keyed by the full options bag, so different params = different fetch.

The examples below are BigQuery. On a positional provider, swap the placeholders for `$1`, `$2` and the dict for an array.

## Wiring a dropdown (vanilla)

```html
<select id="region">
  <option value="NY">New York</option>
  <option value="CA">California</option>
</select>
```

```ts
let selectedRegion = 'NY';
let dataSource = buildSource(selectedRegion);

document.getElementById('region')!.addEventListener('change', (e) => {
  selectedRegion = (e.target as HTMLSelectElement).value;
  dataSource = buildSource(selectedRegion);
  deck.setProps({ layers: [new VectorTileLayer({ id: 'stores', data: dataSource, /* ... */ })] });
});

function buildSource(region: string) {
  return vectorQuerySource({
    ...cartoConfig,
    sqlQuery: 'SELECT * FROM demo.public.stores WHERE region = @region',
    queryParameters: { region },
  });
}
```

## Wiring a slider with debounce (vanilla)

```html
<input id="rev" type="range" min="0" max="500000" step="1000" />
<output id="rev-out"></output>
```

```ts
let revenueMin = 0;
const onChange = debounce((v: number) => {
  revenueMin = v;
  dataSource = buildSource(revenueMin);
  rebuildLayers();
}, 200);

document.getElementById('rev')!.addEventListener('input', (e) => {
  const v = +(e.target as HTMLInputElement).value;
  document.getElementById('rev-out')!.textContent = String(v);
  onChange(v);
});
```

200 ms is enough for a slider — 300 ms feels laggy on continuous drag.

## React

```tsx
function StorePicker() {
  const [region, setRegion] = useState('NY');
  const [revenueMin, setRevenueMin] = useState(0);

  const dataSource = useMemo(() => vectorQuerySource({
    ...cartoConfig,
    sqlQuery: 'SELECT * FROM demo.public.stores WHERE region = @region AND revenue >= @min',
    queryParameters: { region, min: revenueMin },
  }), [region, revenueMin, accessToken]);

  return (
    <>
      <select value={region} onChange={(e) => setRegion(e.target.value)}>
        <option value="NY">New York</option>
        <option value="CA">California</option>
      </select>
      <input type="range" min={0} max={500_000} step={1000}
             value={revenueMin}
             onChange={(e) => setRevenueMin(+e.target.value)} />
      <DeckGL layers={[new VectorTileLayer({ id: 'stores', data: dataSource })]}
              initialViewState={INITIAL_VIEW_STATE} controller />
    </>
  );
}
```

For a slider, debounce the *re-fetch*, not the input — display the current value immediately, but only rebuild the source after 200 ms of stillness.

## Multi-select

For `IN` lists, the bound value is the array itself. **Both the predicate and the placeholder are dialect-specific** — the placeholder follows the table at the top of this page.

BigQuery — `IN UNNEST(...)`, named:

```sql bigquery
SELECT * FROM demo.public.stores
WHERE category IN UNNEST(@categories)
```

```ts
queryParameters: { categories: ['retail', 'wholesale'] }
```

Databricks — `array_contains(...)`, named with `:`:

```sql databricks
SELECT * FROM demo.public.stores
WHERE array_contains(:categories, category)
```

```ts
queryParameters: { categories: ['retail', 'wholesale'] }
```

Postgres / Redshift — `= ANY(...)`, positional. The array of values holds one entry, and that entry is itself the list:

```sql postgres
SELECT * FROM demo.public.stores
WHERE category = ANY($1)
```

```ts
queryParameters: [['retail', 'wholesale']]
```

Snowflake and Oracle are positional too (`$1` and `:1`). Confirm each warehouse's array-membership predicate via the `carto-query-datawarehouse` skill — different warehouses spell list parameters differently.

## When to use parameterized SQL vs `filters`

| Need | Use |
|---|---|
| Filter on a column already in the source's result | `filters` |
| Join another table, compute a new column, or change the source schema | parameterized SQL |
| User picks one of N pre-defined queries | parameterized SQL or swap the whole `sqlQuery` |
| User drags a slider over a numeric column | `filters` (BETWEEN) — no re-fetch from SQL, faster |

## Gotchas

- **Re-creating the source on every keystroke** is the killer perf bug. Debounce input, then memoize.
- **Named vs positional is the provider's call, not yours.** `@name` is BigQuery and `:name` is Databricks, both with a named dict; Postgres, Snowflake and Redshift take `$1`, `$2` and Oracle `:1`, `:2`, all with a positional array. Copying a BigQuery snippet onto Snowflake is the most common way to get a query that never binds.
- **Don't string-concatenate user input into `sqlQuery`** — that's SQL injection. Always use `queryParameters`.
- **A `vectorQuerySource` with no filters runs the full query** every tile fetch. The warehouse caches well, but watch quotas on big datasets — consider a tileset (`vectorTilesetSource`) for >10M-row read-only datasets.
