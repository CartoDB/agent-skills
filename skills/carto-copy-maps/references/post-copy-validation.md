# Post-copy validation

Don't trust a map copy on the basis that the CLI returned a new ID. Validate the destination explicitly before handing the map URL to anyone.

## Confirm the map exists

```bash
carto maps list --profile prod --search "<map title>" --json
carto maps get <new-map-id> --profile prod --json | jq '{id, title, privacy}'
```

## Verify datasets loaded

A copy can succeed at the API level while datasets fail to resolve in the destination warehouse — usually a connection-mapping mistake.

```bash
carto maps get <new-map-id> --profile prod --json | jq '.datasets'

# Connection names per dataset
carto maps get <new-map-id> --profile prod --json \
  | jq '.datasets[] | {id, connectionName, source}'
```

If a dataset's `connectionName` is `null` or missing, the connection mapping didn't resolve. Fix with another copy specifying `--connection-mapping`, or — for a one-off — `carto maps update <new-map-id>` with a corrected dataset block.

## Verify connections resolve

```bash
# What connections does the destination have?
carto connections list --profile prod --json | jq '[.[].name]'

# What connections does the copied map reference?
carto maps get <new-map-id> --profile prod --json \
  | jq '[.datasets[].connectionName] | unique'
```

Every connection in the second list must appear in the first.

## Verify agent config (if the map has one)

```bash
# Top-level agent block
carto maps get <new-map-id> --profile prod --json | jq '.map.agent'

# Issues that need manual Builder intervention
carto maps get <new-map-id> --profile prod --json | jq '.map.agent.issues'
```

`[]` means the agent migrated cleanly. Anything else points at `UNAVAILABLE_MODEL` / `UNAVAILABLE_TOOL` — see [agent-migration-caveats.md](agent-migration-caveats.md).

## Construct the destination map URL

The URL uses the destination org's tenant domain, **not** a generic workspace URL.

```bash
# Get the tenant for the destination
carto auth status --profile prod
# Look for: Tenant: <tenant>.app.carto.com

# URLs:
# Private (Builder edit view):  https://<tenant>.app.carto.com/builder/<new-map-id>
# Public/shared:                 https://<tenant>.app.carto.com/map/<new-map-id>
```

`<tenant>` is the actual tenant subdomain — never `workspace-<region>.app.carto.com`. See [`../../carto-basics/SKILL.md`](../../carto-basics/SKILL.md) for the URL convention.

## End-to-end smoke

```bash
# 1. Map exists with expected title
carto maps get <new-map-id> --profile prod --json | jq '.title'

# 2. All datasets have a connection
carto maps get <new-map-id> --profile prod --json \
  | jq '[.datasets[] | select(.connectionName == null)] | length'
# Expected: 0

# 3. No agent issues
carto maps get <new-map-id> --profile prod --json \
  | jq '.map.agent.issues // [] | length'
# Expected: 0 (unless the source had agents — then check & fix in Builder)

# 4. Open in browser
echo "https://$(carto auth status --profile prod --json | jq -r '.tenant')/builder/<new-map-id>"
```

If all four pass, the copy is good. Hand the URL over.

## When something's wrong

| Symptom | Likely cause | Fix |
|---|---|---|
| `connection X not found` during copy | Connection name mismatch | `--connection-mapping` (see [cross-profile-copy.md](cross-profile-copy.md)) |
| Datasets present but render errors | Source table not in destination warehouse | Seed the data, or use `--skip-source-validation` and seed later |
| `.map.agent.issues` non-empty | Agent model/tool refs from source | Manual Builder fix (see [agent-migration-caveats.md](agent-migration-caveats.md)) |
| Map URL hits 404 | Wrong tenant — used `workspace-...` instead of actual tenant | Re-derive URL from `auth status --profile prod` |
| Privacy unexpected | `--keep-privacy` interaction | `carto maps update <new-id> '{"privacy": "shared"}'` |
