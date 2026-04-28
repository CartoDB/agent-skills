# CLI commands deferred to Phase 2

> Salvaged from the pre-redesign `carto-cli/commands.md`. These sections describe
> CLI surfaces that belong to Phase 2 platform skills. Kept here so the next PR
> can fold them in without re-deriving the split.

| Section | Target Phase 2 skill |
|---|---|
| Maps | `carto-create-builder-maps` |
| Workflows | `carto-create-analytics-workflow` |
| Imports | `carto-import-export-data` |
| Organization | `carto-manage-platform` |
| Users | `carto-manage-platform` |
| Activity Data (export side) | `carto-manage-platform` |
| AI Features | `carto-create-builder-maps` (agents) / `carto-build-app` (proxy) |
| AI Proxy | `carto-build-app` |
| Admin | `carto-manage-platform` |

---

## Maps

### maps list
List your maps.

```bash
carto maps list [options]
```

**Options:**
- `--all` - Fetch all pages
- `--page <n>` - Page number (default: 1)
- `--page-size <n>` - Items per page (default: 10)
- `--search <query>` - Search maps by text
- `--privacy <level>` - Filter by privacy level
- `--mine` - Show only your maps

**Examples:**
```bash
carto maps list --json
carto maps list --all --search "sales"
carto maps list --mine
carto maps list --page 2 --page-size 20
```

### maps get
Get detailed map information including datasets and connections.

```bash
carto maps get <id>
```

With `--json` flag, returns full map configuration suitable for create/update.

### maps update
Update an existing map with JSON config.

```bash
carto maps update <id> [json]
```

**Options:**
- `--file <path>` - Read JSON from file (or pipe via stdin)

**Examples:**
```bash
carto maps update <id> '{"title":"Updated Title"}'
carto maps update <id> --file map-config.json
cat config.json | carto maps update <id>
```

### maps delete
Delete a map.

```bash
carto maps delete <id>
```

Requires confirmation (type "delete") unless `--yes` or `--json` flag is used.

### maps clone
Clone a map within the same organization.

```bash
carto maps clone <id> [--title <title>]
```

### maps copy
Copy map between profiles (organizations).

```bash
carto maps copy <id> --dest-profile <name> [options]
```

**Options:**
- `--dest-profile <name>` - Destination profile (required)
- `--source-profile <name>` - Source profile (default: current profile)
- `--connection <name>` - Legacy: single connection for all datasets
- `--connection-mapping <m>` - Map connections: "source1=dest1,source2=dest2"
- `--skip-source-validation` - Skip validating table/query accessibility
- `--title <title>` - Override map title
- `--keep-privacy` - Preserve privacy setting (default: true)

**Connection Resolution Order:**
1. Manual mapping (`--connection-mapping`)
2. Auto-map by name (default behavior)
3. Legacy single connection (`--connection`)

**Examples:**
```bash
carto maps copy map123 --dest-profile prod
carto maps copy map123 --dest-profile prod --connection-mapping "dev-bq=prod-bq"
```

---

## Workflows

### workflows list
```bash
carto workflows list [options]
```

**Options:** `--orderBy`, `--orderDirection`, `--pageSize`, `--page`, `--search`, `--privacy`, `--tags <json-array>`

### workflows get
```bash
carto workflows get <id> [--client <name>]
```

### workflows update
```bash
carto workflows update <id> [json]
```

**Options:** `--file <path>`

### workflows delete
```bash
carto workflows delete <id>
```

### workflows copy
```bash
carto workflows copy <id> --dest-profile <profile> [options]
```

**Options:** `--source-profile`, `--dest-profile` (required), `--connection`, `--title`, `--skip-source-validation`

### workflows schedule add / update / remove
```bash
carto workflows schedule add    <id> --expression <expr> [--connection <name>]
carto workflows schedule update <id> --expression <expr> [--connection <name>]
carto workflows schedule remove <id> [--connection <name>]
```

**Schedule Expression Formats:**
- BigQuery/CARTO DW: `"every day 08:00"`, `"every monday 09:00"`, `"every 2 hours"`
- Snowflake/PostgreSQL: `"0 8 * * *"`, `"0 9 * * 1"` (cron)
- Databricks: `"0 0 8 * * ?"`, `"0 0 9 ? * MON"` (quartz cron)

---

## Imports

### imports create
Import geospatial file (waits for completion).

```bash
carto imports create [options]
```

**Options:**
- `--file <path>` - Local file to upload
- `--url <url>` - Remote file URL to import
- `--connection <name>` - Connection name (required)
- `--destination <fqn>` - Target table name (required)
- `--overwrite` - Overwrite existing table
- `--no-autoguessing` - Disable column type detection
- `--async` - Return immediately (don't wait)

**Supported formats:** CSV, GeoJSON, GeoPackage, GeoParquet, KML, KMZ, Shapefile (zip)
**Size limit:** 1GB per file

**Examples:**
```bash
carto imports create --file ./data.csv --connection carto_dw --destination project.dataset.table
carto imports create --url https://example.com/data.geojson --connection bigquery --destination my.table
```

---

## Organization

### org stats
```bash
carto org stats
```
Shows users, resources, quotas, and AI limits (displays available data based on permissions).

---

## Users

### users list / get / invite / invitations / resend-invitation / cancel-invitation / delete

```bash
carto users list [--all] [--page <n>] [--page-size <n>] [--role <Builder|Viewer|Guest>] [--search <query>]
carto users get <user-id|email>
carto users invite <email> [--role <role>]
carto users invitations
carto users resend-invitation <token>
carto users cancel-invitation <token>
carto users delete <user-id|email> <receiver-id|email>
```

Multiple invite emails: comma-separated or multiple arguments.

---

## Activity Data (export side)

### activity export
Export activity data logs (Enterprise Large+ plans).

```bash
carto activity export [options]
```

**Options:**
- `--start-date <date>` (required, ISO format)
- `--end-date <date>` (required)
- `--format <csv|parquet>` (default: csv)
- `--category <activity|apiUsage|userList|groupList>` (default: all)
- `--output-dir <path>` (default: ./activity-data)

Automatically waits for export and downloads files.

> Note: the `activity query` side belongs in `carto-query-datawarehouse` (utility tier).

---

## AI Features

### aifeature aiagent
Chat with map AI agent.

```bash
carto aifeature aiagent <map-id> [message]
```

**Options:**
- `--conversation-id <id>` - Continue existing conversation
- `--file <path>` - Read message from file

Interactive mode if no message provided.

---

## AI Proxy

### aiproxy info / models / chat

```bash
carto aiproxy info
carto aiproxy models
carto aiproxy chat [message] --model <name> [--system <text>] [--temperature <n>] [--max-tokens <n>] [--top-p <n>] [--file <path>]
```

---

## Admin (Superadmin)

```bash
carto admin list <maps|workflows|connections> [--all] [--page <n>] [--page-size <n>] [--search <query>]
carto admin batch-delete
carto admin transfer
```
