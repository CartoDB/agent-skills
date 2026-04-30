# Cross-profile workflow copy

`workflows copy` moves a workflow definition from one CARTO profile (org / environment) to another. Mechanical replication — no creation, no agentic decisions.

## Lifecycle

```bash
# 1. Confirm both profiles are authenticated
carto auth status

# 2. Inspect the source workflow
carto workflows get <wf-id> --profile dev --json | jq '{id, name, connection}'

# 3. Copy to prod (auto-maps connections if names match)
carto workflows copy <wf-id> \
  --source-profile dev \
  --dest-profile   prod

# 4. Verify in prod
carto workflows list --profile prod --search "<workflow name>"
```

## Connection re-mapping

The single most common failure: **the dev connection name doesn't match the prod connection name.** Without remapping, the copied workflow points at a connection that doesn't exist in `prod`, and the first run fails with `connection not found`.

Three ways to resolve:

### Auto-mapping by name

Default behavior — if `dev` has `carto_dw` *and* `prod` has `carto_dw`, the copy inherits the same connection name and works.

### Explicit mapping with `--connection-mapping`

When names differ:

```bash
carto workflows copy <wf-id> \
  --source-profile dev \
  --dest-profile   prod \
  --connection-mapping "carto_dw_dev=carto_dw_prod"
```

For workflows touching multiple connections:

```bash
--connection-mapping "src1=dst1,src2=dst2"
```

### Legacy single-connection override (`--connection`)

```bash
carto workflows copy <wf-id> \
  --source-profile dev \
  --dest-profile   prod \
  --connection carto_dw_prod
```

This forces *every* node onto the same destination connection — fine for single-connection workflows but loses fidelity for multi-connection ones. Prefer `--connection-mapping`.

### Resolution order

When CARTO copies a workflow, it picks a destination connection per node in this order:

1. `--connection-mapping` if it specifies the source connection.
2. Auto-mapping by name (a connection named the same in the destination).
3. Legacy `--connection` (forces every node to that connection).

If none match, the copy fails with `connection X not found in destination profile`.

## `--skip-source-validation`

By default, `workflows copy` validates that source tables referenced by the workflow exist in the destination's data warehouse — useful early warning when the prod warehouse hasn't been seeded.

`--skip-source-validation` disables that check. Use when:

- The destination workflow is intended to populate those tables itself.
- You're staging a workflow before the upstream data is ready.

## Title override

```bash
--title "My Workflow (prod)"
```

Useful when the source title contains `"-dev"` you want to strip.

## Preserving privacy

`workflows copy` defaults to copying the source's privacy setting. Pass `--keep-privacy` to be explicit (default: true) or omit for the default.

## Updating a previously-copied workflow

`workflows copy` always creates a *new* workflow in the destination — there's no in-place update. The recommended pattern is:

1. Copy once with `workflows copy` → gets a fresh destination workflow ID.
2. Subsequent updates: in source, `get` → edit → in destination, `update` (with the destination's workflow ID).

The two workflow IDs are independent; CARTO doesn't track lineage between them. Maintain the mapping in your team's docs.
