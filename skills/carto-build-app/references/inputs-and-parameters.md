# Inputs — dropdowns, sliders, parameterized SQL

Two ways to push user input into the map:

1. **Local filters** via the `filters` object — best for predicates over a fixed table.
2. **Parameterized SQL** via `vectorQuerySource` (or H3/quadbin/boundary `*QuerySource`) — best when you need joins, computed columns, or you want the warehouse to do the work.

Use both together when needed.

## Parameterized SQL

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

Parameters are referenced in SQL with `@name`. Values are typed (string, number, boolean, ISO date string). To re-fetch with new values, re-call the source factory with a new `queryParameters` — the source result is keyed by the full options bag, so different params = different fetch.

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
    <DeckGL layers={[new VectorTileLayer({ id: 'stores', data: dataSource, /* ... */ })]} ... />
  </>
);
```

For a slider, debounce the *re-fetch*, not the input — display the current value immediately, but only rebuild the source after 200 ms of stillness.

## Multi-select

For `IN` lists, build the parameter as an array and use the warehouse's `IN UNNEST(@arr)` or equivalent:

```sql
SELECT * FROM demo.public.stores
WHERE category IN UNNEST(@categories)    -- BigQuery / Snowflake
-- or:
WHERE category = ANY(@categories)        -- Postgres
```

```ts
queryParameters: { categories: ['retail', 'wholesale'] }
```

Confirm dialect-specific syntax via the `carto-query-datawarehouse` skill — different warehouses spell list parameters differently.

## When to use parameterized SQL vs `filters`

| Need | Use |
|---|---|
| Filter on a column already in the source's result | `filters` |
| Join another table, compute a new column, or change the source schema | parameterized SQL |
| User picks one of N pre-defined queries | parameterized SQL or swap the whole `sqlQuery` |
| User drags a slider over a numeric column | `filters` (BETWEEN) — no re-fetch from SQL, faster |

## Gotchas

- **Re-creating the source on every keystroke** is the killer perf bug. Debounce input, then memoize.
- **Parameter names are positional in some dialects** — but `@name` style works on BigQuery, Snowflake, and Postgres via the SQL API. Stick to named.
- **Don't string-concatenate user input into `sqlQuery`** — that's SQL injection. Always use `queryParameters`.
- **A `vectorQuerySource` with no filters runs the full query** every tile fetch. The warehouse caches well, but watch quotas on big datasets — consider a tileset (`vectorTilesetSource`) for >10M-row read-only datasets.
