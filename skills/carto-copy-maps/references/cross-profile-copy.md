# Cross-profile map copy

`maps copy` duplicates a map across CARTO profiles. The destination gets a new map ID, fresh per-org metadata, and a fresh share state. Source content (datasets, layers, styles, AI-agent config) transfers; share links, comments, and collaboration state do not.

## Lifecycle

```bash
# 1. Confirm both profiles are authenticated
carto auth status

# 2. Inspect the source map (quick sanity check)
carto maps get <map-id> --profile dev --json \
  | jq '{id, title, privacy, datasetCount: (.datasets | length)}'

# 3. Compare connections (most common failure mode)
carto connections list --profile dev  --json | jq '[.[].name]'
carto connections list --profile prod --json | jq '[.[].name]'

# 4. Copy
carto maps copy <map-id> \
  --source-profile dev \
  --dest-profile   prod

# 5. Verify the copy landed
carto maps list --profile prod --search "<map title>"
```

## What gets copied

- Title, description, privacy
- Datasets (table/query references)
- `keplerMapConfig`: layers, styles, widgets, mapState, mapStyle
- Agent configuration (with caveats — see [agent-migration-caveats.md](agent-migration-caveats.md))

## What does **not** get copied

- The map ID (a new one is generated)
- Public sharing links / share tokens
- Comments
- Collaboration state (collaborators, roles)
- Activity history (the destination starts with a fresh log entry)

## Connection re-mapping

The single most common failure: **connection names differ between profiles**. Without remapping, the copied map's datasets reference connections that don't exist in the destination, and the map renders with errors.

Three ways to resolve:

### Auto-mapping by name (default)

If `dev` has `carto_dw` *and* `prod` has `carto_dw`, the copy inherits the same name and works. **Keep connection names consistent across orgs to make copies trivial.**

### Explicit mapping with `--connection-mapping`

When names differ across orgs:

```bash
carto maps copy <map-id> \
  --source-profile dev \
  --dest-profile   prod \
  --connection-mapping "dev-bigquery=prod-bigquery,dev-snowflake=prod-snowflake"
```

For maps with multiple datasets pointing at multiple connections, list each pair separated by commas.

### Legacy single-connection (`--connection`)

```bash
carto maps copy <map-id> \
  --source-profile dev \
  --dest-profile   prod \
  --connection prod-bigquery
```

This forces every dataset onto a single destination connection. **Only use for single-source maps**; multi-dataset maps will break if datasets need different connections.

### Resolution order

CARTO picks each dataset's destination connection in this order:

1. `--connection-mapping` if it specifies the source connection.
2. Auto-mapping by name.
3. Legacy `--connection` if specified.

If none match, the copy fails with `connection X not found in destination profile`.

## `--skip-source-validation`

By default, `maps copy` validates that each dataset's source table or query is accessible via the destination connection — early warning when the destination warehouse hasn't been seeded.

`--skip-source-validation` disables that check:

```bash
carto maps copy <map-id> \
  --source-profile dev \
  --dest-profile   prod \
  --skip-source-validation
```

Use when the destination data will arrive later (e.g. you're staging the map ahead of an ETL). Resulting map will render dataset errors until the data is available.

## Title and privacy overrides

```bash
# Override the title
carto maps copy <map-id> --dest-profile prod --title "Production Sales Dashboard"

# Be explicit about privacy (default: --keep-privacy true)
carto maps copy <map-id> --dest-profile prod --keep-privacy
```

## Same-org clone

`maps clone` is the same-org variant — duplicates within the current profile, no `--dest-profile`:

```bash
carto maps clone <map-id>
carto maps clone <map-id> --title "Sales Dashboard (experimental)"
```

Useful when you want to branch off a working map for further edits without touching the original. All the copy semantics (what transfers, what doesn't) apply identically.

## Updating a previously-copied map

`maps copy` always creates a *new* map. There's no in-place update. Subsequent edits are independent: the source and destination map IDs have no lineage in CARTO. Maintain the mapping in your team's docs if you need to track which prod map came from which dev map.
