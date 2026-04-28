# Workflow JSON Structure

Reference for the shape of a CARTO Workflow JSON bundle.

---

## Top-level structure

```json
{
  "connectionId": "<uuid from carto connections list>",
  "title": "Workflow Title",
  "description": "What this workflow does",
  "config": {
    "schemaVersion": "1.0.0",
    "connectionProvider": "bigquery | snowflake | redshift | postgres | databricksWarehouse | oracle",
    "nodes": [],
    "edges": [],
    "variables": []
  }
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `connectionId` | Yes (for create/verify) | UUID of the CARTO connection — get it via `carto connections list --json` |
| `title` | Yes | Display name |
| `config.schemaVersion` | Yes | Always `"1.0.0"` |
| `config.connectionProvider` | Yes | Must match the connection's provider: `bigquery`, `snowflake`, `redshift`, `postgres`, `databricksWarehouse`, `oracle` |
| `config.nodes` | Yes | Array of workflow components |
| `config.edges` | Yes | Array of connections between nodes |
| `config.variables` | No | Optional array of workflow variables |

The `connectionProvider` value must match the actual provider of the connection used for validation/execution. Mismatches cause SQL generation to use the wrong dialect. Verify with `carto connections list --search <name> --json` (`carto connections get` requires a UUID, not a name).

On `update`, the `config` wrapper is optional — top-level fields like `title` can be patched independently. On `create` it is required and must contain `nodes` and `edges` (empty arrays are OK).

---

## Node structure

```json
{
  "id": "unique-node-id",
  "type": "generic",
  "data": {
    "name": "native.componentname",
    "version": "2",
    "label": "Display Label",
    "inputs": [
      { "name": "source", "type": "Table", "value": "" }
    ],
    "outputs": [
      { "name": "out", "type": "Table" }
    ]
  },
  "position": { "x": 100, "y": 100 }
}
```

- `id` — unique identifier; use descriptive names (`source-accidents`, `filter-type`).
- `type` — always `"generic"` for processing nodes. Source nodes (`native.gettablebyname`) also use `"generic"`.
- `data.name` — component name from the catalog (e.g. `native.buffer`).
- `data.version` — component version as string. Always include — check the component schema for the current version.
- `data.inputs` — array of `{ "name": "...", "type": "...", "value": "..." }` objects. **Not** a key-value params object.
- `data.outputs` — array of `{ "name": "...", "type": "Table" }` objects. Get exact names from the component schema.
- `position` — required. Layout coordinates (left-to-right, ~200px spacing). Every node must have a position.

---

## Edge structure

```json
{
  "id": "edge-source-to-target",
  "source": "source-node-id",
  "target": "target-node-id",
  "sourceHandle": "out",
  "targetHandle": "source"
}
```

Handle names must match the component schema exactly.

---

## Variables

```json
{
  "variables": [
    { "id": "var-1", "name": "distance_meters", "type": "Number", "defaultValue": "1000" }
  ]
}
```

Reference with `{{variable_name}}` syntax inside input values.
