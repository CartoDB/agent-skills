# Manifest update protocol — state transitions, fields, batch summary

The skill writes to `MIGRATION_MANIFEST.md` after every state change. Crashes mid-batch must leave the manifest reflecting reality on disk.

## State machine for migrate-data

```
pending  ─►  in-progress  ─►  done
                  │
                  ├──►  skipped  (empty source / > 1 GB)
                  └──►  failed   (with Failure: line; retryable on next run)
```

- **pending → in-progress** at the start of Phase 1 (one transition per entry, written immediately).
- **in-progress → done** when import + verification succeed.
- **in-progress → skipped** when the entry is empty (`Reason: empty-source`) or oversized (`Reason: exceeds-1gb-staging-not-implemented`).
- **in-progress → failed** when extraction errors out persistently OR the post-import row count doesn't match.

Re-runs handle states as follows:

- `done` → silently skipped (idempotency precheck confirms the table still matches).
- `skipped` (empty-source) → silently skipped.
- `skipped` (exceeds-1gb-staging-not-implemented) → silently skipped (will resume when the staging-fallback feature ships).
- `failed` → re-attempted. Phase 1 transitions back to `in-progress`; Phase 4 uses `--overwrite`.

## Required fields per state

### Phase 1: `pending → in-progress`

Add only:
- `In-progress at: 2026-05-07T14:32:00Z` (UTC ISO 8601).

### `done`

Add:
- `State: done`
- `Target FQN: <project>.<dataset>.<table>` (warehouse-native syntax)
- `Target rows: <int>` (from the post-import `SELECT COUNT(*)`)
- `Migrated at: 2026-05-07T14:33:12Z` (UTC ISO 8601)

Optional:
- `Notes:` (one or more lines) — `M/Z geometry stripped`, `reprojected from EPSG:<x> to EPSG:4326`, `pre-existing target table matched source count`, etc.

Remove the `In-progress at:` line.

### `skipped`

Add:
- `State: skipped`
- `Reason: empty-source` OR `Reason: exceeds-1gb-staging-not-implemented`

For `exceeds-1gb-staging-not-implemented`, also add:
- `Estimated size: <human-readable>` (e.g. `1.4 GB`)
- `Source rows: <int>` (from the probe)

Remove the `In-progress at:` line.

### `failed`

Add:
- `State: failed`
- `Failure: <one-line summary>` (e.g. `row count mismatch (source=12348, target=12347)`, `429 rate-limited after 1 retry`, `network error after 3 retries`)

Optional:
- `Logs: <relative-path>` — when the failure was a CARTO Imports API error and the agent saved the full `logs` field of the `--json` response somewhere (`out/logs/<item-id>.txt`).

Remove the `In-progress at:` line.

## Idempotency precheck (Phase 1)

Before transitioning a `pending` entry, run the precheck described in [`import-flow.md`](import-flow.md): `carto sql query` against the target FQN.

- **Match** (table exists, row count matches source) → write `State: done` directly with `Notes: pre-existing target table matched source count`. Skip Phases 2–4.
- **Mismatch** (table exists, row count differs) → proceed normally; Phase 4 will use `--overwrite`.
- **No table** → proceed normally; no `--overwrite`.

The precheck is cheap (one SQL query). It's worth running on every batch, especially when the user re-invokes the skill after fixing a `failed` entry.

## Atomic write

Read the manifest into memory, modify the relevant entry, write the whole file back atomically:

```python
from pathlib import Path
import tempfile

manifest = Path("MIGRATION_MANIFEST.md")
text = manifest.read_text()
text = transform(text, item_id, new_state, new_fields)

# Write to a tempfile in the same directory, then rename
tmp = manifest.with_suffix(manifest.suffix + ".tmp")
tmp.write_text(text)
tmp.replace(manifest)
```

Don't open the manifest in append mode and don't write line-by-line — partial writes corrupt the markdown.

## Worked transitions

### Pending → in-progress

```diff
 ### Stores (Hosted Feature Layer)
 - Source: https://services1.arcgis.com/.../Stores/FeatureServer/0
 - Item ID: 4ae23afb1c1248bda1d3
 - Type: Feature Service
-- State: pending
+- State: in-progress
+- In-progress at: 2026-05-07T14:32:00Z
 - Recommended path: carto-arcgis-migrate-data
```

### In-progress → done

```diff
 ### Stores (Hosted Feature Layer)
 - Source: https://services1.arcgis.com/.../Stores/FeatureServer/0
 - Item ID: 4ae23afb1c1248bda1d3
 - Type: Feature Service
-- State: in-progress
-- In-progress at: 2026-05-07T14:32:00Z
+- State: done
 - Recommended path: carto-arcgis-migrate-data
+- Target FQN: demo-bq.migration.stores
+- Target rows: 12348
+- Migrated at: 2026-05-07T14:33:12Z
```

### In-progress → skipped (oversize)

```diff
 ### LargeRoads (Hosted Feature Layer)
 - Source: https://services1.arcgis.com/.../LargeRoads/FeatureServer/0
 - Item ID: 8de4...
 - Type: Feature Service
-- State: in-progress
-- In-progress at: 2026-05-07T14:33:30Z
+- State: skipped
 - Recommended path: carto-arcgis-migrate-data
+- Reason: exceeds-1gb-staging-not-implemented
+- Estimated size: 1.4 GB
+- Source rows: 4823017
```

### In-progress → failed (count mismatch)

```diff
 ### Sales (Hosted Feature Layer)
 - Source: https://services1.arcgis.com/.../Sales/FeatureServer/0
 - Item ID: c2f1...
 - Type: Feature Service
-- State: in-progress
-- In-progress at: 2026-05-07T14:34:10Z
+- State: failed
 - Recommended path: carto-arcgis-migrate-data
+- Failure: row count mismatch (source=8421, target=8420)
```

## Final batch summary (Phase 5)

Print to chat (not the manifest) at the end of every run. Format:

```
Migration of Datasets section complete.

Migrated (2):
  - Stores                              demo-bq.migration.stores              12348 rows
  - SalesRegions                        demo-bq.migration.sales_regions          184 rows

Skipped — empty (1):
  - LegacyContacts                      no rows in source

Skipped — > 1 GB (1):
  - LargeRoads                          1.4 GB est., 4823017 rows
                                        (staging fallback not yet implemented)

Failed (1):
  - Sales                               row count mismatch (source=8421, target=8420)
                                        re-run to retry, or migrate manually

Next step: run the maps migration phase to migrate Web Maps that depend on
the migrated datasets. The manifest now reflects all updated states.
```

If a category is empty, omit its section. The summary should fit on one screen for batches under ~20 items.
