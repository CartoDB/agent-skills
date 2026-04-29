# Cross-profile promotion

`carto workflows copy <id> --dest-profile <profile>` moves a workflow definition between profiles (orgs / environments) — the typical use is **dev → prod promotion**. Flag reference is in `carto workflows --help`.

This file documents the lifecycle and the connection resolution behaviour, which aren't in `--help`.

## Lifecycle

```bash
# 1. Confirm both profiles are authenticated
carto auth status

# 2. Inspect the source workflow
carto workflows get <wf-id> --profile dev --json | jq '{id, title, connectionId}'

# 3. Copy to prod (auto-maps connection by name)
carto workflows copy <wf-id> \
  --source-profile dev \
  --dest-profile   prod

# 4. Verify in prod
carto workflows list --profile prod --search "<workflow title>"
```

## Connection resolution

`workflows copy` picks the destination connection in this order:

1. **Auto-mapping by name** (default). If `dev` has connection `carto_dw` *and* `prod` has `carto_dw`, the copy inherits the same name and works without flags.
2. **Explicit `--connection <name>`** forces the copy onto a single named destination connection. Use this when the dev and prod connection names differ.

The single most common failure: dev and prod connection names differ, no `--connection` flag, and the copied workflow points at a non-existent connection. The first run fails with "connection not found".

```bash
carto workflows copy <wf-id> \
  --source-profile dev \
  --dest-profile   prod \
  --connection     carto_dw_prod
```

## `--skip-source-validation`

By default, `workflows copy` validates that source tables referenced by the workflow exist in the destination warehouse — a useful early warning when the prod warehouse hasn't been seeded. Pass `--skip-source-validation` when:

- The destination workflow is intended to populate those tables itself.
- You're staging a workflow before the upstream data is ready.

## Updating a previously-promoted workflow

`workflows copy` always creates a *new* workflow in the destination — there's no in-place update. The recommended pattern:

1. Promote once with `workflows copy` → gets a fresh prod workflow ID.
2. Subsequent updates: in dev, `get` → edit → in prod, `update` (with the prod ID).

The two workflow IDs are independent; CARTO doesn't track lineage between them. Maintain the mapping in your team's docs.
