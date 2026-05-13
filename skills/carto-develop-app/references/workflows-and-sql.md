# Workflows and ad-hoc SQL

Two ways to run SQL from a CARTO app:

1. **`query()`** from `@carto/api-client` — execute arbitrary SQL, get rows back. For one-off lookups, KPI cards, or as the basis of a `vectorQuerySource`.
2. **A workflow run as SQL** — workflows compile to SQL stored procedures. Call the procedure via `query()` to get its output table, then visualize.

There's no first-class "run a workflow" helper in the client SDK. You always go through SQL.

## `query()` — run SQL

```ts
import { query } from '@carto/api-client';

const result = await query({
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL,
  accessToken,
  connectionName: import.meta.env.VITE_CONNECTION_NAME,
  sqlQuery: 'SELECT COUNT(*) AS n FROM demo.public.stores WHERE region = @region',
  queryParameters: { region: 'NY' },
});

console.log(result.rows);     // [{ n: 12345 }]
```

Rows shape depends on the query. Use this for:
- Counters and KPIs that don't fit a widget model.
- Validating user input ("does this code exist?").
- Pre-flight checks before swapping a layer.
- Loading a small lookup table for a dropdown.

For visualizations, prefer `vectorQuerySource` (see [`data-sources.md`](data-sources.md)) — it's tile-aware and integrates with widgets.

## Aborting

```ts
const controller = new AbortController();
const result = await query({
  apiBaseUrl,
  accessToken,
  connectionName,
  sqlQuery: 'SELECT * FROM ...',
  signal: controller.signal,
});
// later: controller.abort();
```

Always wire abort signals when calls might race (typing in a search box, panning the map).

## Calling a Workflow's output

A workflow saved in CARTO Builder can be exposed as an HTTP endpoint or as a stored procedure. The simplest path from a deck.gl app: read the workflow's output table directly.

```ts
const dataSource = vectorQuerySource({
  ...cartoConfig,
  sqlQuery: 'SELECT * FROM demo.public.workflow_output_stores',
});
```

If the workflow is parameterized and you want to **run it on demand** from the app:

```sql
-- Workflows compile to stored procedures named `wf_<workflow_id>(...)`
CALL `demo.public.wf_aggregate_stores`(@region, @threshold);
```

Trigger via `query()`:

```ts
await query({
  ...cartoConfig,
  sqlQuery: 'CALL `demo.public.wf_aggregate_stores`(@region, @threshold)',
  queryParameters: { region: 'NY', threshold: 1000 },
});
```

After the call, re-fetch the source so the map sees the new output:

```ts
dataSource = vectorQuerySource({
  ...cartoConfig,
  sqlQuery: 'SELECT * FROM demo.public.workflow_output_stores',
});
deck.setProps({ layers: rebuildLayers(dataSource) });
```

For Workflow API specifics — endpoint format, naming, async polling — see the [Executing Workflows via API](https://docs.carto.com/carto-user-manual/workflows/executing-workflows-via-api) guide. The CLI surface is in [`carto-create-workflow`](../../carto-create-workflow).

## Async / long-running queries

`query()` waits for the SQL API to return. For genuinely long jobs (minutes), consider:
- Materializing the result into a table on a schedule (workflow + `schedule add`), then point a `vectorQuerySource` at the materialized table — the app stays fast.
- Or fire the long query from a backend M2M client ([`auth-m2m.md`](auth-m2m.md)) and have the app poll a small status table.

Don't hold a UI loading state for >10 s; the user assumes it's broken.

## React

```tsx
const [stats, setStats] = useState<{ total: number } | null>(null);

useEffect(() => {
  let cancelled = false;
  query({
    apiBaseUrl: import.meta.env.VITE_API_BASE_URL,
    accessToken,
    connectionName: import.meta.env.VITE_CONNECTION_NAME,
    sqlQuery: 'SELECT SUM(revenue) AS total FROM demo.public.stores WHERE region = @region',
    queryParameters: { region },
  }).then(({ rows }) => {
    if (!cancelled) setStats({ total: rows[0].total });
  });
  return () => { cancelled = true; };
}, [region, accessToken]);
```

## Gotchas

- **`query()` returns rows, not tiles.** It's not a layer source. Don't pass it to `data:` on a layer.
- **Result size limits.** The SQL API caps response rows (varies by warehouse). Page in SQL with `LIMIT/OFFSET` or aggregate before returning.
- **Don't run unbounded SQL from a public app token.** Even with `--apis sql`, scope `--source` to specific tables. Without scoping, anyone with the bundled token can run any query.
- **Workflow output tables can be replaced atomically** by the workflow run — but there's a window during the swap where reads can fail. Retry once on transient errors.
- **Procedure invocation syntax is dialect-specific** — `CALL` works on BigQuery, Snowflake, Databricks; Postgres uses `CALL` for procedures and `SELECT` for functions. Confirm via `carto-query-datawarehouse`.
