# Workflows and ad-hoc SQL

## Where the analysis lives: workflow, not app SQL

**Any non-trivial analysis belongs in a CARTO Workflow, not inlined as SQL in the app.** Predicting revenue, composite / suitability scores, segmentation, enrichment, multi-step joins, anything with several CTEs or a sequence of transforms — author it with [`carto-create-workflow`](../../carto-create-workflow), then have the app *call* the result. The app stays a thin presentation layer.

Why this is the pattern, not a preference:
- **One source of truth.** The logic is versioned, runnable, schedulable, and reusable in Builder — not buried in a frontend string that drifts.
- **The app can't be trusted with the SQL.** A public-token app ships its SQL to the browser; complex bodies leak business logic and are trivially editable by anyone holding the token. A workflow's compiled procedure runs server-side; the app only passes parameters.
- **Performance.** Heavy work materializes once (or on a schedule) instead of recomputing per page load.

So the rule:

| Situation | Do |
|---|---|
| Complex / multi-step / repeatable analysis | Build a **workflow**; the app reads its output table or calls its procedure. |
| Same analysis driven by an **embedded agent** ("chat with map") | Publish the workflow as an **MCP tool**; the agent invokes it. See [Workflow as an MCP tool](#workflow-as-an-mcp-tool-agent-driven-apps). |
| One-off lookup, KPI card, input validation, dropdown data | Inline `query()` is fine — see below. |
| A `vectorQuerySource` with a `WHERE` / `JOIN` / computed column | Inline SQL on the source is fine — that's not "analysis," it's shaping a read. |

There's no first-class "run a workflow" helper in the client SDK — both the app path and the agent path go through SQL (the compiled procedure) or the workflow's output table. Mechanics below.

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

## Calling a workflow from the app (Workflows API)

Two shapes, depending on whether the workflow runs ahead of time or on demand.

**Static output — read the result table.** If the workflow runs on a schedule (or was run once) and writes a result table, the app is just a normal `vectorQuerySource` / `vectorTableSource` pointed at that table. No "run" call at all. This is the default and the fastest.

```ts
const dataSource = vectorQuerySource({
  ...cartoConfig,
  sqlQuery: 'SELECT * FROM demo.public.workflow_output_stores',
});
```

**On-demand, parameterized — call the compiled procedure.** Enable "API access" on the workflow in the Workflows UI (CLI can't toggle this yet). The workflow compiles to a stored procedure; the app `CALL`s it through the SQL API via `query()`, passing the user's inputs as parameters. Get the exact procedure FQN and `CALL` signature from `carto workflows mcp describe <id>` or the Workflows UI — **don't guess the name** (it's a hash-based identifier in the connection's workspace dataset, not `wf_<title>`).

```ts
await query({
  ...cartoConfig,
  sqlQuery: 'CALL `demo.carto_workspace.wfproc_...`(@region, @threshold)',
  queryParameters: { region: 'NY', threshold: 1000 },
});
```

After the call, re-fetch the source so the map sees the new output (rebuild a fresh `layers` array — see [`layers.md`](layers.md)):

```ts
dataSource = vectorQuerySource({
  ...cartoConfig,
  sqlQuery: 'SELECT * FROM demo.public.workflow_output_stores',
});
deck.setProps({ layers: rebuildLayers(dataSource) });
```

The public token that powers the app must grant **both** the procedure FQN and every table it reads — add them to `--source` at token creation (see [`auth-public-token.md`](auth-public-token.md)). For endpoint format, naming, and async polling, see [Executing Workflows via API](https://docs.carto.com/carto-user-manual/workflows/executing-workflows-via-api); for publishing/compiling the procedure and the exact FQN, [`carto-create-workflow`'s mcp-and-api-publish.md](../../carto-create-workflow/references/mcp-and-api-publish.md).

## Workflow as an MCP tool (agent-driven apps)

When the app has an **embedded agent** ([`agentic-variant.md`](agentic-variant.md)) and that agent needs to run the analysis, don't hand it raw SQL — publish the workflow as an **MCP tool** and register it alongside the agent's other tools. The agent calls it by name with typed inputs; the procedure runs server-side and returns rows. Same compiled procedure as the API path above, just discovered and invoked through MCP instead of a hard-coded `CALL`.

```bash
# In carto-create-workflow: shape the workflow with a native.mcptooloutput
# terminal node + variables scoped to `mcptool`, then:
carto workflows mcp publish <id> --name predict_revenue \
  --description "Predict revenue for a candidate site given catchment inputs"
carto workflows mcp describe <id>     # → tool name, inputs, the CALL signature
```

The agent's tool result is rows; map them to a layer spec (or a new `vectorQuerySource` over the output table) and apply via the agent's `set-deck-state` path. Full publish requirements — the `native.mcptooloutput` node, `mcptool`-scoped variables, per-input descriptions, the `Number → FLOAT64`/`LIMIT` gotcha — are in [`carto-create-workflow`'s mcp-and-api-publish.md](../../carto-create-workflow/references/mcp-and-api-publish.md). Author the workflow first with [`carto-create-workflow`](../../carto-create-workflow).

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
