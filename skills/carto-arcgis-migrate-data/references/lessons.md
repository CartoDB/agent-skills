# Lessons from the field — `carto-arcgis-migrate-data`

Patterns discovered during real migrations. The agent **reads this file before writing any extraction or import script** and follows the documented patterns. New lessons are surfaced via `SESSION_LESSONS.md` in the working directory at end-of-batch and merged here when the user confirms.

The point: every quirky pagination corner case, every auth-expiry surprise, every type-coercion gotcha that bit a previous run — captured once, never re-discovered.

---

## Auth expiry mid-batch

### CARTO session expired

**Symptom**: `carto import --json` or `carto sql query --json` returns an auth error. Typical strings: `Authentication required`, `Token expired`, `401 Unauthorized`, `403 Forbidden`. The CLI exits non-zero.

**Action**: **stop the entire batch**. Subsequent items will all fail until auth refreshes. Surface to the user:

> CARTO authentication expired during migration. Run `carto auth login` then re-invoke the skill — pending and in-progress entries will resume from where they stopped.

Do **not** mark the current item `failed` — leave it `in-progress`. On re-invocation, the manifest precheck and Phase 1's `pending → in-progress` transition handle resumption cleanly.

**Detection in script**: parse `--json` output for `error` / `code: 401` / `code: 403`. Don't rely solely on exit code; CARTO CLI sometimes emits structured errors with exit 0 in older versions.

```python
import subprocess, json

result = subprocess.run(
    ["carto", "import", *flags, "--json"],
    capture_output=True, text=True
)
try:
    payload = json.loads(result.stdout)
    if payload.get("error", {}).get("code") in (401, 403):
        sys.exit("CARTO auth expired — stop batch")
except json.JSONDecodeError:
    pass
```

### ArcGIS token expired

**Symptom**: REST calls return `401`, or a JSON body with `{"error": {"code": 498}}` (token expired) or `{"error": {"code": 499}}` (token required).

**Action**: **stop the current item only** — mark it `failed` with `Failure: arcgis-token-expired`. Continuing the batch is futile if all items use the same token, but if the user has set `ARCGIS_TOKEN` and can refresh between items, the next item starts fresh. **Surface the error and stop the batch by default**; only continue if the user has explicitly requested it.

**Pre-emptive refresh**: ArcGIS tokens default to 60-min TTL but can be shorter. If a batch will plausibly run > 30 minutes (large layers; many items), refresh the token before starting:

```bash
NEW_TOKEN=$(curl -s -X POST "$PORTAL/sharing/rest/generateToken" \
  -d "username=$USERNAME" -d "password=$PASSWORD" \
  -d "expiration=120" -d "f=json" | jq -r '.token')
export ARCGIS_TOKEN=$NEW_TOKEN
```

---

## Pagination quirks

### `exceededTransferLimit` not always reliable

Some services (especially older Map Servers fronting Feature data) don't set `exceededTransferLimit` correctly, or omit it entirely. Belt-and-braces stop condition:

```python
if not page.get("exceededTransferLimit") and len(page["features"]) < num_per_page:
    break
```

### `objectIdField` may be null or missing in metadata

Default to `OBJECTID` (uppercase) when the layer's metadata doesn't specify one. Most services use this name even when not declared:

```python
oid = layer_meta.get("objectIdField") or "OBJECTID"
```

### Pagination skips rows when source is being mutated

Rare in migration scenarios but possible for live portals. Symptom: post-import row count consistently below source count, even though `exceededTransferLimit=false` returned cleanly.

**Mitigation**: snapshot OBJECTID range at start. Capture `max(OBJECTID)` from the first probe, then add `where=OBJECTID<=<max-oid>` to every page query. Rows added during extraction won't get picked up, but rows already present won't be skipped.

### `resultRecordCount` capped silently

A few services cap at 1000 even when `maxRecordCount=2000`. Don't trust the metadata's `maxRecordCount` blindly — start at 2000 and back off to 1000 if the first page returns fewer than requested without setting `exceededTransferLimit`.

---

## Type coercion

### ArcGIS dates are epoch milliseconds

The REST API returns date fields as integer epoch-ms, not ISO 8601:

```python
df["created_date"] = pd.to_datetime(df["created_date"], unit="ms", utc=True)
```

When a date column is `null` in the source it comes through as integer 0 — convert *before* checking for null, or the resulting timestamp lands at 1970-01-01.

### Numeric-looking strings (ZIP, FIPS, phone)

Codes that *look* numeric but should stay strings (US ZIP codes "00501", FIPS codes, phone numbers with leading zeros). Two failure modes:

- Pandas type-inference promotes them to `int64` and drops leading zeros.
- CARTO's autoguessing does the same in the warehouse.

**Fix**: type the column as `string` explicitly before writing Parquet. Parquet preserves dtypes through CARTO's import:

```python
df["zip"] = df["zip"].astype("string")
df["fips"] = df["fips"].astype("string")
```

When in doubt, prefer string for any column whose values share a fixed length and may have leading zeros.

### Boolean fields stored as 0/1

ArcGIS exports booleans as integer 0/1. CARTO will type them as `INT64` after import. If the user wants `BOOL` in the warehouse, cast post-import via `carto sql query` — don't try to flag this at extraction time.

### `null` in numeric columns → NaN → CARTO type drift

Numeric columns with nulls become `float64` in pandas (because NaN forces float). CARTO imports them as float even when the source column was integer. **Fix**: use pandas `Int64` (capital I) nullable integer:

```python
df["count"] = df["count"].astype("Int64")
```

---

## Geometry quirks

### M / Z values silently break 2D operations

If the source is M-aware or Z-aware, GeoPandas will read the geometries with M/Z but most 2D operations strip them inconsistently. Force 2D explicitly:

```python
from shapely import force_2d
gdf["geometry"] = gdf["geometry"].apply(force_2d)
```

Detect: `gdf.geometry.has_z.any()` (`has_m` requires shapely 2.0+).

Record `Notes: M/Z geometry stripped` on the manifest entry when this runs.

### `outSR=4326` rejected silently

Some services ignore `outSR` and return the source's native SRS regardless. Detect by checking `spatialReference.wkid` in the response — not by trusting the parameter:

```python
response_srs = page.get("spatialReference", {}).get("wkid")
if response_srs != 4326:
    gdf = gdf.set_crs(f"EPSG:{response_srs}", allow_override=True).to_crs("EPSG:4326")
    note_on_entry(f"reprojected from EPSG:{response_srs} to EPSG:4326")
```

### Empty / null geometries

GeoParquet doesn't accept `null` geometries by default (the spec allows them but `geopandas.to_parquet` complains). Drop and record:

```python
n_before = len(gdf)
gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty]
n_dropped = n_before - len(gdf)
if n_dropped > 0:
    note_on_entry(f"dropped {n_dropped} empty/null geometries")
```

### Curves / arcs in geometries

ArcGIS feature services can serve true curves (Bezier, arc segments). Shapely densifies them to line segments at read time, but the densification factor matters for fidelity. Default densification is fine for most use cases; if the user complains about visual differences, increase by reading curves with `arcgis-python`'s `to_geojson()` first (which densifies more aggressively) before handing to shapely.

---

## Service-specific gotchas

### `Hosted Feature Layer Views` (filtered/projected views over a parent service)

These look like Feature Services but their `viewSourceServiceItemId` field points to the underlying service. Two options:

- Migrate the view as-is (preserves the user's filter/projection).
- Migrate the parent service and recreate the view as a SQL view in CARTO via `migrate-services`.

Default: migrate the view. If the parent is also in the manifest and gets migrated separately, dedup catches the overlap and the user can decide.

### Multi-layer Feature Services

A single Feature Service can host multiple layers (`/0`, `/1`, `/2`, ...). The discover skill creates one Datasets entry per layer. Don't try to import them as a bundle — `carto import` is one file per call.

### File-format AGOL items (GeoJson, Shapefile, KML, GeoPackage, …) skip the `/query` probe

**Symptom**: the manifest's Datasets section contains entries whose `Type:` is `GeoJson`, `Shapefile`, `KML`, `GeoPackage`, or `File Geodatabase` (rather than `Feature Service` / `Map Service`). These are static files uploaded to AGOL, not live services — they have **no `/query` endpoint**, so the Phase-2 probe in [`extraction-recipes.md`](extraction-recipes.md) (`SOURCE/query?returnCountOnly=true`) cannot run.

**Action**: see Recipe 3 in `extraction-recipes.md`. Summary:

1. Use the search-result `size` field (already in `MIGRATION_INVENTORY.json` from discover) for the byte-size precheck — no extra request needed.
2. Download the blob from `/sharing/rest/content/items/<id>/data?token=…` once.
3. For zipped Shapefiles (`Type: Shapefile`): unzip to a temp dir, point `geopandas.read_file` at the `.shp` file. Skip macOS `__MACOSX/._*` resource-fork entries — `pyogrio` chokes on them when reading via `vfs=zip://`.
4. For GeoJSON / KML / GeoPackage: `geopandas.read_file` on the downloaded path directly.
5. Row count is derived after the read, not before. The idempotency precheck (target FQN exists with matching count) runs *after* the file is in memory — but extraction is cheap for file-format items (no paged service calls), so this isn't a meaningful cost.

**Detection**: classify by item `type` from the manifest. If it's not a service type, file-format applies.

---

## CARTO platform quirks

### `carto` CLI v0.6.x ships `carto import` (singular), not `carto imports create`

**Symptom**: `carto imports create --file … --connection … --destination …` exits with `Error: unknown command: imports`. The published recipes in upstream `carto-import-export-data/SKILL.md` and (pre-`0.1.5`) this skill's `references/import-flow.md` showed the multi-word form, but the CLI binary in v0.6.x exposes only the singular noun.

**Action**: use `carto import` (no trailing `s`, no `create` subcommand). Same flags work: `--file`, `--url`, `--connection`, `--destination`, `--overwrite`, `--no-autoguessing`, `--async`, `--json`. Async polling is `carto import status <jobId>`.

```bash
carto import \
  --file ./out/<item-id>.parquet \
  --connection "$TARGET_CONNECTION" \
  --destination "$TARGET_FQN" \
  --json
```

**Detection**: `carto --help | grep -E '^\s*import\b'` lists `import` (singular). No `imports` subcommand group exists in v0.6.x.

**General principle**: even the carto-agent-skills recipes can drift from the actually-installed CLI between releases. When the rule "consult `carto-agent-skills` first" produces an `unknown command` error, fall back to `carto <subcommand> --help` once to confirm the noun shape, then continue. This is the *only* time `--help` is allowed — for flag combinations, the carto-skill remains the source of truth.

### `carto sql query` takes `<connection>` positionally, not as `--connection` / `--query` flags

**Symptom**: `carto sql query --connection carto_dw --query "SELECT 1" --json` fails with `Connection not found ... connection_name="--connection"` — the CLI parsed `--connection` as the *value* of the connection positional. Pre-`0.1.5` import-flow recipes here used the flag form; the actual CLI form is positional.

**Action**: pass the connection name and SQL string as positional args, in that order. `--json` flag still works for parseable output.

```bash
# Correct
carto sql query carto_dw "SELECT COUNT(*) FROM \`project.shared.table\`" --json

# Wrong (looks plausible, fails at runtime)
carto sql query --connection carto_dw --query "SELECT 1" --json
```

**Detection**: cross-reference with `carto-query-datawarehouse/SKILL.md` Quick reference — it documents the positional form. The error message above is the runtime smoke-signal.

### `INFORMATION_SCHEMA` is not queryable on `carto_dw`

**Symptom**: any query against `INFORMATION_SCHEMA.*` (or `*.INFORMATION_SCHEMA.SCHEMATA`, `*.INFORMATION_SCHEMA.TABLES`, etc.) on the built-in CARTO Data Warehouse connection (`carto_dw`) returns a permission error. The user-bound token doesn't have access to system metadata.

**Action**: never use `INFORMATION_SCHEMA` to check if a table exists, list datasets, or introspect the warehouse on `carto_dw`. Use direct queries against the target table — `SELECT COUNT(*) FROM <fqn>` fails with a recognizable "table not found" error if the table doesn't exist, which is enough signal for idempotency.

**Default destination dataset on `carto_dw`**: assume a dataset named `shared` exists for ArcGIS imports. Compose the target FQN as:

```
<carto_dw_project>.shared.<table_name>
```

Resolve `<carto_dw_project>` from `carto connections describe carto_dw --json` (the connection metadata exposes the project ID). Don't try `SELECT * FROM INFORMATION_SCHEMA.SCHEMATA` to find the user's datasets — it will fail.

For customer-owned warehouses (BigQuery, Snowflake, Redshift, Postgres, Oracle, Databricks), `INFORMATION_SCHEMA` is usually queryable, but the agent should still default to direct table-existence probes for portability.

---

## Process patterns

### Consult `carto-agent-skills` first — don't trial-and-error CLI flags

**Symptom**: the agent runs `carto --help`, `carto imports create --help`, or guesses flag names, and ends up with outdated, wrong, or under-documented invocations. Wastes turns and produces broken scripts.

**Action**: every CARTO platform interaction has a dedicated skill in [`CartoDB/carto-agent-skills`](https://github.com/CartoDB/carto-agent-skills) with a live, tested recipe. Read the matching skill **before** writing any `carto` invocation:

| Need | Skill |
|---|---|
| `carto imports create` (datasets, tilesets) | `carto-import-export-data` |
| `carto maps *` (Builder maps) | `carto-create-builder-maps` |
| `carto workflows *` (workflows) | `carto-create-workflow` |
| `carto sql query` / `sql job` | `carto-query-datawarehouse` |
| `carto connections list/describe` (warehouse metadata) | `carto-connect-datawarehouse` / `carto-explore-datawarehouse` |
| `carto auth login/status` (auth) | `carto-basics` |

These skills already encode the right flag combinations, JSON-shape conventions, async-job polling, error patterns, and "do silently, don't ask" defaults. They're updated when the CLI changes — the skill is the source of truth, not the CLI's `--help`.

If a recipe seems wrong or out-of-date for what you're observing on disk, the next-best move is `carto <subcommand> --json` and inspect the structured output (most subcommands self-describe) — but only after the relevant carto-skill is consulted.

This is a hard rule for `carto-arcgis-migrate-data`: we don't reimplement CARTO platform mechanics, we delegate. The migration-specific logic (paged ArcGIS extraction, GeoParquet writing, manifest updates) is what lives in *this* skill; everything CARTO-side is borrowed.

---

## How to add a lesson

When the agent encounters a non-obvious quirk during a run, append to `SESSION_LESSONS.md` in the working directory using this template:

```markdown
## <symptom in one line>

**Encountered**: 2026-05-08 during migration of `<item-name>` (item ID `<id>`)
**Source**: `<service URL or item type>`
**Fix**: <what worked>
**Detection**: <how to spot this proactively>
**Code (if applicable)**:
\`\`\`python
...
\`\`\`
```

At end of batch (Phase 5), the agent prints `SESSION_LESSONS.md` and surfaces two follow-up paths. **The agent never edits this file (`references/lessons.md`) directly at runtime** — for plugin end-users, the file lives under `~/.claude/plugins/cache/...` and any write there is overwritten on the next plugin update.

**Maintainer path** (only when the source repo `carto-arcgis-skills` is cloned somewhere writable, e.g. `projects/2026/esri-migration/`):

1. Open the source-repo `references/lessons.md`, append each session lesson under the matching section (Auth expiry / Pagination / Type coercion / Geometry / Service-specific).
2. Bump `version` in `skills/catalog.json` (PATCH for an addition).
3. `make sync && make validate`.
4. Commit + push per `CLAUDE.md`. The next plugin release ships the new lessons; all installs benefit on `/plugin uninstall && /plugin install`.

**End-user path** (plugin installed via marketplace, no source repo locally):

Keep `SESSION_LESSONS.md` in the engagement directory. If a captured pattern is widely useful (likely to bite other migrations), share the file with the skill maintainer — they'll fold it into the upstream `references/lessons.md` and ship it in the next release.

A future improvement (not yet implemented) is a **user-local lessons file** that the agent reads on every run alongside this one, so end-users accumulate per-machine lessons without depending on upstream releases. Until that exists, end-user lessons stay engagement-scoped.
