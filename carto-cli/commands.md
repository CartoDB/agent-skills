# CARTO CLI Command Reference

Complete reference for all CARTO CLI commands.

## Authentication

### auth login
Interactive browser-based login.

```bash
carto auth login [profile]
```

**Options:**
- `--env <env>` - Auth environment: production|staging|local|dedicated-NN (only configure if instructed by support)
- `--organization-name <name>` - Login with SSO to specific organization (required for SSO). Use quotes for spaces.

**Examples:**
```bash
carto auth login
carto auth login production
carto auth login --organization-name "cartodb"    # SSO login
```

### auth logout
Remove stored credentials.

```bash
carto auth logout [profile]
```

### auth status
Show authentication status, tenant, org, user, and available profiles.

```bash
carto auth status [profile]
```

### auth use
Switch default profile.

```bash
carto auth use <profile>
```

### auth whoami
Show current user info.

```bash
carto auth whoami
```

---

## Credentials

### credentials list
List all credentials.

```bash
carto credentials list [type]
```

Types: `tokens`, `spa`, `m2m`, `oauth`

### credentials create token
Create API Access Token.

```bash
carto credentials create token [options]
```

**Options:**
- `--connection <name>` - Connection name
- `--source <table>` - Table/tileset/query source
- `--apis <list>` - Allowed APIs (comma-separated: sql,maps,imports,lds)
- `--referer <url>` - Allowed referer URL

**Example:**
```bash
carto credentials create token --connection carto_dw --source "demo_tables.*" --apis sql,maps
```

### credentials create spa
Create SPA OAuth Client.

```bash
carto credentials create spa [options]
```

**Options:**
- `--title <name>` - Application title
- `--login-uri <url>` - Login initiation URI
- `--callback <url>` - Callback URL
- `--logout-url <url>` - Logout URL
- `--web-origin <url>` - Web origin
- `--allowed-origin <url>` - Allowed origin

**Example:**
```bash
carto credentials create spa --title "My Web App" --callback "https://app.com/callback"
```

### credentials create m2m
Create M2M OAuth Client.

```bash
carto credentials create m2m --title <name>
```

**Example:**
```bash
carto credentials create m2m --title "Backend Service"
```

### credentials get
Get credential details.

```bash
carto credentials get <type> <id>
```

Types: `token`, `spa`, `m2m`, `oauth`

### credentials update
Update credential.

```bash
carto credentials update <type> <id>
```

### credentials delete / revoke
Delete or revoke credential.

```bash
carto credentials delete <type> <id>
carto credentials revoke <type> <id>
```

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
List your workflows.

```bash
carto workflows list [options]
```

**Options:**
- `--orderBy <field>` - Order by field
- `--orderDirection <dir>` - Order direction (ASC/DESC)
- `--pageSize <number>` - Items per page
- `--page <number>` - Page number
- `--search <term>` - Search term
- `--privacy <level>` - Privacy level
- `--tags <json-array>` - Filter by tags

### workflows get
Get workflow details.

```bash
carto workflows get <id> [--client <name>]
```

### workflows update
Update workflow configuration.

```bash
carto workflows update <id> [json]
```

**Options:**
- `--file <path>` - Read JSON from file (or pipe via stdin)

### workflows delete
Delete a workflow.

```bash
carto workflows delete <id>
```

### workflows copy
Copy workflow between profiles.

```bash
carto workflows copy <id> --dest-profile <profile> [options]
```

**Options:**
- `--source-profile <profile>` - Source profile (default: current)
- `--dest-profile <profile>` - Destination profile (required)
- `--connection <name>` - Destination connection name (optional, auto-maps by name)
- `--title <title>` - Override workflow title
- `--skip-source-validation` - Skip validating source table accessibility

### workflows schedule add
Add schedule to workflow.

```bash
carto workflows schedule add <id> --expression <expr> [--connection <name>]
```

### workflows schedule update
Update workflow schedule.

```bash
carto workflows schedule update <id> --expression <expr> [--connection <name>]
```

### workflows schedule remove
Remove workflow schedule.

```bash
carto workflows schedule remove <id> [--connection <name>]
```

**Schedule Expression Formats:**
- BigQuery/CARTO DW: `"every day 08:00"`, `"every monday 09:00"`, `"every 2 hours"`
- Snowflake/PostgreSQL: `"0 8 * * *"`, `"0 9 * * 1"` (cron)
- Databricks: `"0 0 8 * * ?"`, `"0 0 9 ? * MON"` (quartz cron)

---

## Connections

### connections list
List your connections.

```bash
carto connections list [options]
```

**Options:**
- `--all` - Fetch all pages
- `--page <n>` - Page number (default: 1)
- `--page-size <n>` - Items per page (default: 10)
- `--search <query>` - Search connections by text

### connections get
Get connection details.

```bash
carto connections get <id>
```

### connections browse
Browse connection resources (projects/datasets/tables).

```bash
carto connections browse <name> [path]
```

**Options:**
- `--page <n>` - Page number (default: 1)
- `--page-size <n>` - Items per page (default: 30)

**Examples:**
```bash
carto connections browse carto_dw
carto connections browse carto_dw "carto-demo-data"
carto connections browse carto_dw "carto-demo-data.demo_tables"
```

### connections describe
Get table schema and details.

```bash
carto connections describe <name> <table-path>
```

**Example:**
```bash
carto connections describe carto_dw "carto-demo-data.demo_tables.nyc_collisions"
```

### connections create
Create a new connection.

```bash
carto connections create
```

### connections update
Update connection.

```bash
carto connections update <id>
```

### connections delete
Delete connection.

```bash
carto connections delete <id>
```

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

## SQL

### sql query
Run SQL query and return results.

```bash
carto sql query <connection> [sql]
```

**Options:**
- `--cache` - Use GET with caching (cached 1yr, 1min timeout)
- `--file <path>` - Read SQL from file

Default: POST (no cache, no URL limit, 1min timeout)

**Examples:**
```bash
carto sql query carto_dw "SELECT * FROM dataset.table LIMIT 10"
carto sql query carto_dw "SELECT * FROM dataset.table" --cache
carto sql query carto_dw --file query.sql
echo "SELECT COUNT(*) FROM dataset.table" | carto sql query carto_dw
```

### sql job
Run SQL job (DDL/DML, no results returned).

```bash
carto sql job <connection> [sql]
```

**Options:**
- `--file <path>` - Read SQL from file

Polls until complete, no timeout. SQL can be passed as arg, stdin, or --file.

**Example:**
```bash
carto sql job carto_dw "CREATE TABLE dataset.newtable AS SELECT..."
```

---

## Organization

### org stats
View organization statistics and quotas.

```bash
carto org stats
```

Shows users, resources, quotas, and AI limits (displays available data based on permissions).

---

## Users

### users list
List all users in the organization.

```bash
carto users list [options]
```

**Options:**
- `--all` - Fetch all pages
- `--page <n>` - Page number (default: 1)
- `--page-size <n>` - Items per page (default: 100)
- `--role <role>` - Filter by role (Builder, Viewer, Guest)
- `--search <query>` - Search users by name or email

### users get
Get detailed user information.

```bash
carto users get <user-id|email>
```

Accepts user ID or email address.

### users invite
Invite new users to the organization.

```bash
carto users invite <email> [--role <role>]
```

**Options:**
- `--role <role>` - Role to assign (Builder/Viewer/Guest, default: Viewer)

Multiple emails: comma-separated or multiple arguments.

**Examples:**
```bash
carto users invite user@example.com --role Builder
carto users invite user1@example.com,user2@example.com --role Viewer
```

### users invitations
List pending invitations.

```bash
carto users invitations
```

### users resend-invitation
Resend a pending invitation.

```bash
carto users resend-invitation <token>
```

### users cancel-invitation
Cancel a pending invitation.

```bash
carto users cancel-invitation <token>
```

### users delete
Delete user and transfer resources.

```bash
carto users delete <user-id|email> <receiver-id|email>
```

Accepts user IDs or email addresses.

---

## Activity Data

### activity export
Export activity data logs (Enterprise Large+ plans).

```bash
carto activity export [options]
```

**Options:**
- `--start-date <date>` - Start date (required, ISO format: 2025-10-01)
- `--end-date <date>` - End date (required, ISO format: 2025-10-07)
- `--format <csv|parquet>` - Export format (default: csv)
- `--category <name>` - Category: activity|apiUsage|userList|groupList (default: all)
- `--output-dir <path>` - Output directory (default: ./activity-data)

Automatically waits for export and downloads files.

### activity query
Query activity data with DuckDB SQL (Enterprise Large+ plans).

```bash
carto activity query [options]
```

**Options:**
- `--start-date <date>` - Start date (required)
- `--end-date <date>` - End date (required)
- `--sql <query>` - DuckDB SQL query (required)
- `--no-cache` - Force fresh download, ignore cache

Auto-downloads if needed, caches in /tmp for reuse.

**Available tables:** activity, apiUsage, userList, groupList
**SQL syntax:** DuckDB - `json_extract_string(data, '$.field')`

**Example:**
```bash
carto activity query --start-date 2025-10-01 --end-date 2025-10-07 --sql "SELECT COUNT(*) FROM activity"
```

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

**Examples:**
```bash
carto aifeature aiagent <map-id> "What are the traffic patterns?"
echo "Analyze data" | carto aifeature aiagent <map-id>
```

---

## AI Proxy

### aiproxy info
Show LiteLLM proxy connection details.

```bash
carto aiproxy info
```

### aiproxy models
List available LLM models.

```bash
carto aiproxy models
```

### aiproxy chat
Direct OpenAI-compatible chat.

```bash
carto aiproxy chat [message] --model <name>
```

**Options:**
- `--model <name>` - Model to use (required, see: aiproxy models)
- `--system <text>` - System prompt
- `--temperature <n>` - Temperature 0-2 (default: 1)
- `--max-tokens <n>` - Max response tokens
- `--top-p <n>` - Top-p sampling (default: 1)
- `--file <path>` - Read message from file

**Example:**
```bash
carto aiproxy chat "Explain quantum physics" --model carto::gemini-2.5-flash
```

---

## Admin (Superadmin)

### admin list
List all resources.

```bash
carto admin list <type> [options]
```

Types: `maps`, `workflows`, `connections`

**Options:**
- `--all` - Fetch all pages
- `--page <n>` - Page number (default: 1)
- `--page-size <n>` - Items per page (default: 10)
- `--search <query>` - Search resources by text

### admin batch-delete
Batch delete resources.

```bash
carto admin batch-delete
```

### admin transfer
Transfer resources between users.

```bash
carto admin transfer
```

---

## Global Options

Available for all commands:

| Option | Description |
|--------|-------------|
| `--json` | Output in JSON format |
| `--debug` | Show request details (method, URL, headers) |
| `--yes`, `-y` | Skip confirmation prompts (for automation) |
| `--token <token>` | Override API token |
| `--base-url <url>` | Override base API URL |
| `--profile <name>` | Use specific profile (default: "default") |
| `--version`, `-v` | Show version |
| `--help`, `-h` | Show help |

**Note:** Deletion commands require typing "delete" to confirm. Use `--yes` or `--json` to skip.

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `CARTO_API_TOKEN` | API token for authentication |
| `CARTO_PROFILE` | Profile to use (overrides current_profile) |
| `CARTO_AUTH_ENV` | Auth environment (only set if instructed by support) |
| `CARTO_AUTH_PORT` | Callback server port for login (default: 3003) |
