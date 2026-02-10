---
name: carto-migration
description: Migrate CARTO maps, workflows, and agent configs between organizations and users. For cross-org copies, bulk migration, connection mapping, and validation.
---

# CARTO Migration Skill

Migrate maps, workflows, and AI agent configurations between CARTO organizations, profiles, and users using the CARTO CLI.

**This is a companion skill to `carto-cli`.** Use the main `carto-cli` skill for general resource management. Use this skill when the task involves moving or duplicating resources across organizations or users.

## IMPORTANT: Always Ask the User First

**Do NOT list all maps or workflows to discover what to migrate.** Enterprise organizations can have hundreds of resources — listing them all is slow, noisy, and unhelpful.

Instead, **always ask the user to provide:**
- The **map IDs** or **map names** they want to migrate
- The **workflow IDs** or **workflow names** they want to migrate
- The **source profile** and **destination profile** names

If the user provides names instead of IDs, use `--search` to find the specific resource:
```bash
carto maps list --search "Fleet Safety" --profile source-org
carto workflows list --search "ETL pipeline" --profile source-org
```

Only use `--all` for bulk migration when the user explicitly requests migrating everything.

## Prerequisites

Before migrating, ensure:

1. **Authentication on both sides** — You need active profiles for both source and destination organizations:
   ```bash
   # Check current profiles
   carto auth status

   # Login to source org (if not already)
   carto auth login source-org

   # Login to destination org
   carto auth login dest-org
   ```

   **Note:** After re-login, `carto auth status --profile <name>` may still show a cached/stale expired token on the first call. Run `carto auth status` (without `--profile`) to see the refreshed state, or verify with a simple command like `carto maps list --profile <name>` to confirm the token is actually valid.

2. **Connection availability** — The destination org must have connections that can access the same data. List connections on both sides:
   ```bash
   carto connections list --profile source-org --json
   carto connections list --profile dest-org --json
   ```

3. **Permissions** — You need at least Builder role in the destination org to create maps/workflows.

---

## Migration Scenarios

### 1. Copy a Map to Another Organization

The simplest cross-org migration. Connections are auto-mapped by name when possible.

```bash
# Auto-map connections by name (recommended)
carto maps copy <map-id> --dest-profile dest-org

# Override the map title in the destination
carto maps copy <map-id> --dest-profile dest-org --title "Production Map"

# Preserve the privacy setting (default: true)
carto maps copy <map-id> --dest-profile dest-org --keep-privacy
```

**What gets copied:** Title, description, privacy, datasets, keplerMapConfig (layers, styles, widgets), and AI agent configuration.

**What does NOT get copied:** Map ID (a new one is generated), sharing links, comments, or collaboration state.

### 2. Copy a Workflow to Another Organization

```bash
# Auto-map connection by name
carto workflows copy <workflow-id> --dest-profile dest-org

# Specify the destination connection explicitly
carto workflows copy <workflow-id> --dest-profile dest-org --connection prod-bigquery

# Override the workflow title
carto workflows copy <workflow-id> --dest-profile dest-org --title "Production ETL"
```

**Note:** Workflow schedules are NOT copied. You must re-add them in the destination:

```bash
# After copying, add schedule to the new workflow
carto workflows schedule add <new-workflow-id> --expression "every day 08:00" --profile dest-org
```

### 3. Clone a Map Within the Same Organization

For duplicating a map without crossing org boundaries:

```bash
carto maps clone <map-id>
carto maps clone <map-id> --title "Copy of Sales Dashboard"
```

### 4. Migrate an AI Agent Configuration Between Maps

Agent configs are embedded in map JSON. To copy an agent config from one map to another:

```bash
# Step 1: Export the source map to get its agent config
carto maps get <source-map-id> --json > source-map.json

# Step 2: Extract the agent block (the "agent" key from the JSON)
# The agent config looks like:
# {
#   "agent": {
#     "enabledForViewer": true,
#     "config": {
#       "model": "account-id::gemini-2.5-flash",
#       "tools": [...],
#       "instructions": "...",
#       ...
#     }
#   }
# }

# Step 3: Apply it to the target map
carto maps update <target-map-id> '{"agent": { ... }}'
# Or from a file:
carto maps update <target-map-id> --file agent-config.json
```

**Important caveats for agent migration:**

- **Agent config location**: The agent config is nested under `.map.agent` in the JSON returned by `carto maps get --json`, not at the top level.
- **Model references** include an account-specific prefix (`"account-id::provider::model-name"`, e.g. `"ac_cb7b9151::anthropic::claude-sonnet-4-5"`). If migrating across organizations, the account ID will differ — verify the model is available in the destination with `carto aiproxy models --profile dest-org`.
- **Tool UUIDs are workflow IDs**: The `config.tools` array references workflow IDs that the agent can invoke. When migrating, you must:
  1. Copy the workflow(s) first to get their new IDs in the destination
  2. Copy the map (agent config comes along)
  3. Update the agent's `config.tools` in the destination map to reference the new workflow IDs
- **Instructions and introduction** (welcome message, starters) are plain text and transfer without issues.

---

## Connection Mapping

When copying maps or workflows across organizations, connections must be resolved in the destination. The CLI resolves connections in this priority order:

### Priority 1: Manual Mapping (most explicit)

Map source connections to destination connections by name:

```bash
carto maps copy <map-id> --dest-profile dest-org \
  --connection-mapping "dev-bigquery=prod-bigquery,dev-snowflake=prod-snowflake"
```

Use this when connection names differ between organizations.

### Priority 2: Auto-Map by Name (default)

If source and destination orgs have connections with the **same name**, they are matched automatically:

```bash
# If both orgs have a connection named "carto_dw", it maps automatically
carto maps copy <map-id> --dest-profile dest-org
```

This is the recommended approach. Keep connection names consistent across organizations to simplify migration.

### Priority 3: Single Connection Override (legacy)

Force all datasets to use a single connection:

```bash
carto maps copy <map-id> --dest-profile dest-org --connection my-connection
```

Only use this for maps with a single data source. Multi-dataset maps will break if datasets point to different connections.

### Skipping Source Validation

By default, the CLI validates that dataset sources (tables/queries) are accessible via the destination connection. Skip this if you know the data will be available later:

```bash
carto maps copy <map-id> --dest-profile dest-org --skip-source-validation
```

**Warning:** This creates a map that may show errors until the data is accessible. Use with caution.

---

## Bulk Migration

**Only use bulk migration when the user explicitly asks to migrate everything.** For most cases, ask the user which specific maps/workflows to migrate.

### Migrate Multiple Maps by Name

```bash
# Find specific maps by search term
carto maps list --search "dashboard" --json --profile source-org

# Copy each result
carto maps copy <map-id-1> --dest-profile dest-org
carto maps copy <map-id-2> --dest-profile dest-org
```

### Migrate All Maps (only when explicitly requested)

```bash
# Step 1: List all map IDs in the source org
carto maps list --all --json --profile source-org | jq -r '.[].id' > map-ids.txt

# Step 2: Copy each map
while read -r map_id; do
  echo "Copying map: $map_id"
  carto maps copy "$map_id" --dest-profile dest-org
done < map-ids.txt
```

### Migrate All Workflows (only when explicitly requested)

```bash
# Step 1: List all workflow IDs
carto workflows list --all --json --profile source-org | jq -r '.[].id' > workflow-ids.txt

# Step 2: Copy each workflow
while read -r wf_id; do
  echo "Copying workflow: $wf_id"
  carto workflows copy "$wf_id" --dest-profile dest-org
done < workflow-ids.txt
```

---

## Transfer Resources Between Users

For moving ownership of resources within the same organization (requires admin/superadmin):

```bash
# Transfer all resources from one user to another
carto admin transfer

# Delete user and transfer their resources to a receiver
carto users delete <user-id-or-email> <receiver-id-or-email>
```

**Note:** `users delete` requires specifying a receiver who inherits the deleted user's maps, workflows, and other resources.

---

## Post-Migration Validation

After migrating, verify the resources landed correctly:

### Validate Maps

```bash
# List maps in destination to confirm they exist
carto maps list --profile dest-org --search "<map-title>"

# Get the copied map and verify datasets loaded
carto maps get <new-map-id> --profile dest-org --json | jq '.datasets'

# Check that connections resolved correctly
carto maps get <new-map-id> --profile dest-org --json | jq '.datasets[].connectionName'
```

### Validate Workflows

```bash
# Confirm workflow exists in destination
carto workflows list --profile dest-org --search "<workflow-title>"

# Get workflow details
carto workflows get <new-workflow-id> --profile dest-org --json
```

### Validate Agent Configuration

```bash
# Check agent config was preserved
carto maps get <new-map-id> --profile dest-org --json | jq '.agent'
```

### Construct Map URLs

After migration, build the map URL from the destination org's tenant domain:

```bash
# Get the tenant domain for the destination
carto auth status --profile dest-org
# Look for: Tenant: <tenant>.app.carto.com

# Map URLs:
# Private: https://<tenant>.app.carto.com/builder/<new-map-id>
# Public:  https://<tenant>.app.carto.com/map/<new-map-id>
```

---

## Troubleshooting

### "Connection not found" during copy

The destination org doesn't have a connection matching the source. Solutions:
1. Create a connection with the same name in the destination org
2. Use `--connection-mapping` to map to an existing connection
3. Use `--connection` to override with a single connection

### "Source validation failed"

The destination connection can't access the table/query. Solutions:
1. Ensure the destination connection has access to the same data
2. Use `--skip-source-validation` if you'll set up data access later

### Agent not working after migration

- Check that the AI model is available in the destination org (`carto aiproxy models --profile dest-org`)
- Verify tool UUIDs exist in the destination org
- Re-configure tools if they are organization-specific

### Workflow schedule missing after copy

Schedules are not copied. Re-add them:

```bash
carto workflows schedule add <new-id> --expression "every day 08:00" --profile dest-org
```

### Privacy changed after copy

By default `--keep-privacy` is `true`. If privacy was reset, update it:

```bash
carto maps update <new-id> '{"privacy": "shared"}' --profile dest-org
```

---

## Migration Checklist

Use this checklist for a complete migration:

- [ ] Authenticated to both source and destination profiles
- [ ] Compared connections between orgs (`connections list` on both)
- [ ] Prepared connection mapping if names differ
- [ ] Copied maps with `maps copy`
- [ ] Copied workflows with `workflows copy`
- [ ] Re-added workflow schedules in destination
- [ ] Verified maps load correctly (datasets, layers, agent)
- [ ] Verified workflows execute correctly
- [ ] Updated any agent tool references if org-specific
- [ ] Shared map/workflow URLs with stakeholders
