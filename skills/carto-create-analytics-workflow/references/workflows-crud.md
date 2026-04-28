# `carto workflows` — CRUD reference

## list

```bash
carto workflows list [options]
```

| Flag | Effect |
|---|---|
| `--orderBy <field>` | Sort field. |
| `--orderDirection ASC\|DESC` | Sort direction. |
| `--pageSize <n>` | Items per page. |
| `--page <n>` | Page number. |
| `--search <term>` | Free-text filter. |
| `--privacy <level>` | Filter by privacy. |
| `--tags <json-array>` | Filter by tags (e.g. `'["prod", "etl"]'`). |
| `--json` | Machine-readable. |

Always pass `--json` if an agent will parse it — the human-formatted table omits IDs by default.

## get

```bash
carto workflows get <id> [--client <name>]
```

Returns the full workflow JSON: nodes, edges, parameters, schedule, connection. **This is the input for `update`** — edit the JSON, then write it back.

`--client <name>` filters the response shape for a specific consumer (rarely needed).

## update

```bash
carto workflows update <id> [json]
carto workflows update <id> --file workflow.json
cat workflow.json | carto workflows update <id>
```

The update replaces the entire DAG. Workflow:

```bash
carto workflows get <id> --json > workflow.json
# edit workflow.json
carto workflows update <id> --file workflow.json
```

Don't pass partial JSON — missing nodes get dropped, not preserved.

## delete

```bash
carto workflows delete <id>
```

Confirms with the literal word `delete`. Pass `--yes` or `--json` for non-interactive use.

The workflow is removed from CARTO. **Tables the workflow created in the warehouse are not deleted** — clean those up separately.

## copy

```bash
carto workflows copy <id> --dest-profile <profile> [options]
```

Cross-profile copy. See [copy-promotion.md](copy-promotion.md) for the full lifecycle pattern.

| Flag | Effect |
|---|---|
| `--source-profile <profile>` | Source profile. Default: current. |
| `--dest-profile <profile>` | Destination profile. **Required.** |
| `--connection <name>` | Destination connection. Auto-maps by name if omitted. |
| `--title <title>` | Override workflow title in the destination. |
| `--skip-source-validation` | Don't verify the source tables exist in the destination. |

## DAG JSON shape (high level)

A workflow JSON has three main sections:

```json
{
  "nodes": [
    { "id": "n1", "type": "source",         "params": { "table": "..." } },
    { "id": "n2", "type": "spatial-join",   "params": { ... } },
    { "id": "n3", "type": "save-as-table",  "params": { "destination": "..." } }
  ],
  "edges": [
    { "from": "n1", "to": "n2" },
    { "from": "n2", "to": "n3" }
  ],
  "parameters": [
    { "name": "date_from", "type": "date", "default": "2026-01-01" }
  ]
}
```

Specific node types and their `params` schemas live in CARTO Workflows docs and depend on the spatial extension version installed in the warehouse.
