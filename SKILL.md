---
name: carto-cli
description: Manage CARTO Geospatial Cloud resources via CLI. Use for maps, workflows, connections, authentication, and admin operations.
---

# CARTO CLI Skill

This skill helps you use the CARTO CLI to manage CARTO Geospatial Cloud Native platform resources including maps, workflows, connections, and credentials.

## IMPORTANT: Required Domain Whitelist

**Before attempting authentication, you MUST whitelist these domains in claude.ai Settings > Features > Skills:**

- `auth.carto.com` - OAuth authentication
- `*.api.carto.com` - API calls
- `*.app.carto.com` - Tenant configuration
- `carto.com` - OAuth callback page

**This is a hard requirement.** Without these domains whitelisted, authentication will fail with network errors like `getaddrinfo EAI_AGAIN`.

**Before starting authentication, always ask the user:**
> "Have you whitelisted the required domains (auth.carto.com, *.api.carto.com, *.app.carto.com, carto.com) in your claude.ai Settings > Features > Skills? Authentication will fail without this."

If the user hasn't whitelisted the domains, **stop and ask them to do so first**. Do not attempt workarounds - the domains must be whitelisted for this skill to work.

## IMPORTANT: TLS Certificate Workaround for Sandbox

**The claude.ai sandbox uses a proxy that causes TLS certificate verification to fail.** You MUST set this environment variable for ALL CLI commands:

```bash
NODE_TLS_REJECT_UNAUTHORIZED=0
```

**Always prefix every carto command with this variable.** Do not wait for TLS errors - use it from the start:

```bash
# Correct - always use this pattern:
NODE_TLS_REJECT_UNAUTHORIZED=0 node /mnt/skills/user/carto-cli/carto.js <command>

# Wrong - will fail with TLS errors:
node /mnt/skills/user/carto-cli/carto.js <command>
```

## Installation Options

### Option 1: NPM (Recommended)

Install globally via NPM for the easiest setup:

```bash
npm install -g @carto/carto-cli

# Verify installation
carto --version
carto --help
```

### Option 2: Bundled CLI (for sandbox)

This skill includes a bundled Node.js script. Use it with Node:

```bash
# The CLI is bundled at the skill path (remember NODE_TLS_REJECT_UNAUTHORIZED=0)
NODE_TLS_REJECT_UNAUTHORIZED=0 node /mnt/skills/user/carto-cli/carto.js --help
NODE_TLS_REJECT_UNAUTHORIZED=0 node /mnt/skills/user/carto-cli/carto.js --version
```

## Authentication

**In claude.ai sandbox**: Use the two-step `--no-launch-browser` flow with TLS workaround:

```bash
# Step 1: Start the auth flow (exits immediately, prints URL)
NODE_TLS_REJECT_UNAUTHORIZED=0 node /mnt/skills/user/carto-cli/carto.js auth login --no-launch-browser

# Step 2: Ask the user to open the URL in their browser and authenticate
# Step 3: User copies the callback URL from the page they land on
#         (Starts with https://carto.com/cli-callback?code=...&state=...)

# Step 4: Complete authentication with the callback URL
NODE_TLS_REJECT_UNAUTHORIZED=0 node /mnt/skills/user/carto-cli/carto.js auth login --callback "https://carto.com/cli-callback?code=...&state=..."

# After authentication, credentials are saved - continue using the TLS workaround for all commands
NODE_TLS_REJECT_UNAUTHORIZED=0 node /mnt/skills/user/carto-cli/carto.js maps list
```

**Alternative**: If you have an API token, you can use it directly:

```bash
export CARTO_API_TOKEN="your-api-token"
node /mnt/skills/user/carto-cli/carto.js maps list
```

Note: API tokens from the Developer section have limited scope. For full access,
use `--no-launch-browser` authentication which provides a complete OAuth token.

**On local machines**: Use browser-based login:

```bash
carto auth login              # Opens browser for OAuth
carto auth status             # Check authentication status
carto auth whoami             # View current user info
```

## Quick Reference

### Maps
```bash
carto maps list                    # List all maps
carto maps list --limit 10         # Paginated list
carto maps get <id>                # Get map details
carto maps get <id> --json         # Get full map JSON
carto maps create <file.json>      # Create map from JSON
carto maps update <id> <file.json> # Update existing map
carto maps delete <id>             # Delete a map
```

**Map URLs**: After creating a map, construct the URL using the tenant domain from `auth status`:
- **Private maps**: `https://{tenant_domain}/builder/{map_id}`
- **Public/shared maps**: `https://{tenant_domain}/map/{map_id}`

Example: If `auth status` shows `Tenant: clausa.app.carto.com` and map ID is `abc123`:
- Private: `https://clausa.app.carto.com/builder/abc123`
- Public: `https://clausa.app.carto.com/map/abc123`

**Do NOT use** `workspace-{region}.app.carto.com` - always use the actual tenant domain.

### Workflows
```bash
carto workflows list               # List all workflows
carto workflows get <id>           # Get workflow details
carto workflows delete <id>        # Delete a workflow
```

### Connections
```bash
carto connections list             # List all connections
carto connections get <id>         # Get connection details
carto connections create <json>    # Create connection
carto connections update <id>      # Update connection
carto connections delete <id>      # Delete connection
```

### Credentials
```bash
carto credentials tokens list      # List API tokens
carto credentials tokens create    # Create new token
carto credentials oauth list       # List OAuth clients
```

## Global Options

All commands support these flags:
- `--json` - Output in JSON format (machine-readable)
- `--token <token>` - Override API token
- `--base-url <url>` - Override API base URL
- `--profile <name>` - Use specific profile from config

## Profiles

Manage multiple CARTO accounts with profiles:

```bash
carto profiles list                # List profiles
carto profiles add <name>          # Add new profile
carto profiles use <name>          # Switch default profile
carto profiles remove <name>       # Remove profile
```

## Related Skills

### Activity Data Analysis (`carto-activity` skill)

For querying activity logs, API usage, and user behavior analytics, use the **`carto-activity` skill**.

**When to use `carto-activity` skill:**
- "What user modified map X yesterday?"
- "Who are my most active users this week?"
- "Show me API quota consumption by user"
- "Which workflows ran today?"
- Any SQL-based analysis of activity logs

**When to use this (`carto-cli`) skill:**
- Maps, workflows, connections management (CRUD operations)
- Authentication and profile management
- Admin operations (batch delete, transfers)
- General CARTO platform operations

**Note:** Both skills share the same authentication - authenticate once with this skill, then use either skill.

## For Detailed Information

- **[COMMANDS.md](COMMANDS.md)** - Complete command reference with all options
- **[MAPS.md](MAPS.md)** - Map JSON structure for create/update operations
- **[activity.md](activity.md)** - Activity data querying and analysis (separate skill)

## Common Workflows

### Export a map configuration
```bash
carto maps get <map-id> --json > my-map.json
```

### Clone a map
```bash
carto maps get <source-id> --json > temp.json
# Edit temp.json to change title
carto maps create temp.json
```

### List all resources as JSON
```bash
carto maps list --json
carto workflows list --json
carto connections list --json
```

### Batch operations (admin)
```bash
carto admin resources list --type map
carto admin resources delete --ids id1,id2,id3
carto admin resources transfer --from user1 --to user2
```
