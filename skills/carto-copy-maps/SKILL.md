---
name: carto-copy-maps
description: Copy maps across CARTO organizations or profiles, with connection mapping and AI-agent reference handling.
license: MIT
---

# carto-copy-maps

`maps copy` duplicates a map across CARTO profiles (orgs / environments). The typical use is **dev → prod promotion**, but the same verb covers cross-org relocation (e.g. delivering a customer map into a customer-segregated org). Copy is **mechanical replication**, not creation — for authoring a new map, use [`carto-create-builder-maps`](../carto-create-builder-maps).

`maps clone` is a sibling verb for **same-org duplication** — handy for branching off a working map without touching it.

## When to use this skill

- The user wants to promote a map from `dev` to `prod` (or any cross-profile copy).
- The user is delivering a customer map into a customer-segregated org.
- The user wants a same-org copy as a starting point for further edits (`maps clone`).
- The copied map shows `UNAVAILABLE_MODEL` or `UNAVAILABLE_TOOL` issues — the agent migration caveats apply.

## Quick reference

```bash
# Cross-profile copy with auto-mapped connections
carto maps copy <map-id> \
  --source-profile dev \
  --dest-profile   prod

# Explicit connection mapping when names differ across orgs
carto maps copy <map-id> \
  --source-profile dev \
  --dest-profile   prod \
  --connection-mapping "dev-bq=prod-bq"

# Same-org clone (e.g. branch off a working map)
carto maps clone <map-id>
carto maps clone <map-id> --title "Copy of Sales Dashboard"

# After copy: check for AI-agent issues that need manual fixing in Builder
carto maps get <new-map-id> --profile prod --json | jq '.map.agent.issues'
```

## What's in this skill

| Topic | Reference |
|---|---|
| Cross-profile copy mechanics: connection mapping, validation, title/privacy, what gets and doesn't get copied | [references/cross-profile-copy.md](references/cross-profile-copy.md) |
| AI-agent migration caveats: `UNAVAILABLE_MODEL`, `UNAVAILABLE_TOOL`, why the CLI can't auto-fix them today, manual Builder steps | [references/agent-migration-caveats.md](references/agent-migration-caveats.md) |
| Post-copy validation: verifying datasets loaded, connections resolved, agent config preserved; constructing destination URLs | [references/post-copy-validation.md](references/post-copy-validation.md) |

## Always-on guidance

- **Always run `connections list` on both sides first.** Most copy failures are connection-name mismatches between profiles. A two-second check up-front avoids a `connection not found` loop.
- **Don't bulk-copy by listing everything**. Enterprise orgs can have hundreds of maps. Always ask the user which specific map IDs (or names — use `--search` to resolve) to copy. Use `--all` only when the user explicitly requests "everything".
- **Maps with AI agents need a deliberate sequence**: copy any workflow(s) the map's agent references **first**, then copy the map. Even so, the agent's `config.tools` will still reference the source's workflow IDs and need a manual fix in Builder. See [references/agent-migration-caveats.md](references/agent-migration-caveats.md).
- **Maps don't carry sharing links, comments, or collaboration state**. The destination map gets a fresh ID; if the user has shared the source publicly, they'll need to re-share the destination.
- **Privacy defaults to copy** unless overridden. Pass `--keep-privacy` to be explicit (default: true).
- For copying **workflows** that the map depends on, use [`carto-copy-workflows`](../carto-copy-workflows). For **same-org transfer between users** (different scenario — ownership change, not duplication), see [`carto-manage-platform/references/admin-bulk-ops.md`](../carto-manage-platform/references/admin-bulk-ops.md).
