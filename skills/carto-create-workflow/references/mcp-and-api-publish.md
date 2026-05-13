# Publishing a workflow as an MCP tool or callable API endpoint

The same compiled stored procedure powers both surfaces:

- **MCP**: agent-facing. Discovered via the workflow's `mcpTool` block; invoked through an MCP client.
- **API**: programmatic-caller-facing. Same procedure FQN, called via the CARTO SQL API with an API access token.

> **API publishing is not yet available via CLI.** Today only `mcp publish` is wired up. To enable API access, toggle "Enable API access" in the Builder UI on the workflow — the CLI can then *call* the resulting procedure (see [Calling the procedure via API](#calling-the-procedure-via-api)), but cannot enable, disable, or describe the API endpoint itself.

CLI surface (full flag list in `carto workflows mcp publish --help`):

```bash
carto workflows mcp publish <id> [--name <s>] [--description <s>] [--output-description <s>]
carto workflows mcp unpublish <id>
carto workflows mcp describe <id>
carto workflows mcp list
```

`mcp publish` is one-shot end-to-end: it compiles the workflow into a stored procedure (`wfproc_mcptool_<wfHash>` in `<billing>.carto_workspace`), creates that procedure on the warehouse, and PATCHes the full MCP metadata onto the workflow. After it returns, an agent can invoke the tool against real data — no Builder UI step required. The same procedure is callable directly via SQL API for non-agent code paths (see [Calling the procedure via API](#calling-the-procedure-via-api) below).

## Bundle requirements

The workflow must be **MCP-shaped** before publishing — `mcp publish` exits with an error otherwise. Three things:

1. **Terminal `native.mcptooloutput` node** fed by at least one upstream node. Marks the workflow's output. Fetch its spec with `carto workflows components get native.mcptooloutput --connection <conn> --json` — the `mode` input takes `"sync"` (procedure SELECTs the temp result) or `"async"` (job metadata returned).
2. **At least one variable in `config.variables[]` with `mcptool` in `scopes[]`.** These become the tool's inputs. Each variable's `value` is the default the procedure uses when an agent omits that parameter.
3. **A connection on the workflow** (`connectionId`). Required for procedure compilation.

## Authoring per-input descriptions

The agent-facing descriptions (tool description, output description, **per-input descriptions**) are read from `config.mcpTool.draft` in the bundle. Authoring them upfront in the bundle is the most ergonomic path — there's no per-input CLI flag.

```json
{
  "mcpTool": {
    "draft": {
      "name": "canonical_tool_name",
      "description": "Top-level description shown to the agent.",
      "inputs": {
        "varname": { "description": "What this parameter means and example values." }
      },
      "output": { "description": "Shape and column meanings of the returned rows." }
    }
  }
}
```

`--name`, `--description`, and `--output-description` flags override their respective draft fields at publish time.

## Referencing variables from a node's `value`

The substitution syntax depends on the input's type:

- **`StringSql` inputs** (e.g. `native.customsql.sql`, `native.selectexpression.expression`, `native.where.expression`): bare `@<varname>`. Example: `ST_DISTANCE(geom, ST_GEOGPOINT(@lon, @lat))`.
- **Non-`StringSql` inputs with `allowExpressions: true`** (e.g. `Number`, `String`, `GeoJsonDraw` typed inputs on natives like `native.pointfromstaticlatlon`, `native.drawcustomgeographies`): wrap the reference in double braces, `{{@<varname>}}`. Example: `"value": "{{@lon}}"` on a `Number`-typed `lon` input.

Mixing the two forms — e.g. bare `@lon` on a `Number` input — fails offline `validate` with `Expected number, received string`. Check each component's input definition (`carto workflows components get <name> --connection <conn> --json`) for `allowExpressions` to confirm a non-StringSql input can take a variable reference at all.

## Type gotcha: `Number` variables map to `FLOAT64`

Workflow variable types are restricted to `Number | String | GeoJsonDraw` (see `carto workflows schema variable`). `Number` becomes `FLOAT64` in the compiled BigQuery procedure, which means **plain `LIMIT @k` fails at call time** — BigQuery's `LIMIT` requires an INT64 literal or query parameter, and won't accept `CAST(@k AS INT64)` either.

Use `QUALIFY` instead of `LIMIT` when the bound is a workflow variable:

```
SELECT *
FROM `$a`
QUALIFY ROW_NUMBER() OVER (ORDER BY distance_m ASC) <= CAST(@k AS INT64)
ORDER BY distance_m ASC
```

Same constraint applies to anywhere BigQuery requires INT64 (e.g. `OFFSET`, array indexing) when the value comes from a `Number` variable.

## Verifying

After `mcp publish`, three things should hold:

```bash
# 1. Tool metadata is populated.
carto workflows mcp describe <id>
#    → non-empty Inputs, Output method=POST, Procedure block with a CALL statement.

# 2. The stored procedure exists in the warehouse.
carto sql query <conn> "SELECT routine_name FROM \`<billing>.carto_workspace.INFORMATION_SCHEMA.ROUTINES\` WHERE routine_name = 'wfproc_mcptool_<wfHash>'"
#    → 1 row. wfHash = sha1(workflowId)[:16].

# 3. Calling the procedure with concrete values returns the expected rows.
carto sql query <conn> "CALL \`<billing>.carto_workspace.wfproc_mcptool_<wfHash>\`(<args>)"
```

If step 2 returns 0 rows, the publish silently failed compilation — re-run with `--debug` and inspect.

## Calling the procedure via API

The compiled procedure is a regular BigQuery (or Snowflake/Databricks) stored procedure. Any caller with a CARTO API access token can invoke it through the SQL API:

```bash
TOKEN=...   # API access token from `carto credentials create token`
CONN=...    # connection name (e.g. acme-bq)
WFHASH=...  # sha1(workflowId)[:16] — find via `mcp describe` or INFORMATION_SCHEMA.ROUTINES
BILLING=... # billing project / database for the connection

curl -X POST "https://gcp-us-east1.api.carto.com/v3/sql/${CONN}/query" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "q": "CALL `'"${BILLING}"'.carto_workspace.wfproc_mcptool_'"${WFHASH}"'`(@lat,@lon)",
    "queryParameters": { "lat": 40.4168, "lon": -3.7038 }
  }'
```

Token creation:

```bash
carto credentials create token \
  --connection <conn> \
  --source "<billing>.carto_workspace.wfproc_mcptool_<wfHash>,<source-table-fqn(s)>" \
  --apis sql
```

The token's `--source` grant must include the procedure FQN **and** every table the procedure body reads from. Wildcards (`<billing>.<dataset>.*`) are accepted at creation time but, in practice, may not be honoured at SQL-API call time depending on tenant configuration — when in doubt, list the exact FQNs. If a fresh token returns `403 You don't have permissions to read this resource` even on `SELECT 1`, the issue is the token itself (or tenant-level token-acceptance policy), not the grant list — surface this back to the workflow author rather than re-scoping endlessly.

The `mcp describe <id>` output includes the full canonical CALL statement and the procedure FQN, so it is the authoritative source for `WFHASH` and the exact `q` body.

## Other flags

- **`--draft-only`** — flips `enabled`/`name`/`description` only; skips procedure compile. Tool appears published but is **not callable**. Useful when staging metadata before the warehouse is ready, or for testing CLI flows without warehouse round-trips.
- **`--file <path>`** — escape hatch that PATCHes the file's JSON as the full `mcpTool` block, skipping compilation. Only useful when applying a hand-crafted block (e.g., copying the published metadata from another workflow).

## Operating notes

- **Tool names must be unique within the org.** If a name is taken, the server appends `_1`, `_2`, etc. — pass `--name` explicitly to control this.
- **Republishing recompiles.** Editing the customsql body and re-running `mcp publish` will `CREATE OR REPLACE PROCEDURE` on the warehouse. Idempotent.
- **`unpublish` keeps metadata.** Re-publishing later is fast — the draft and procedure metadata are preserved; only `enabled` flips back to true.
