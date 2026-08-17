# User and invitation management

> **Route interactively via MCP `manage_users`** (list, invite, role change, delete-with-handoff) when the server is attached over OAuth. On token sessions `manage_users` is hidden — use the CLI below. The CLI is also the path for scripted/bulk provisioning and headless runs. Same semantics either way; the flags/roles below apply to both.

## Listing users

```bash
carto users list [options]
```

| Flag | Effect |
|---|---|
| `--all` | Fetch all pages. |
| `--page <n>` / `--page-size <n>` | Pagination (default page-size: 100). |
| `--role Builder\|Viewer\|Guest` | Filter by role. |
| `--search <query>` | Match name or email. |
| `--json` | Machine-readable. |

```bash
# Everyone
carto users list --all --json

# Just Builders
carto users list --role Builder --all --json

# Find one user
carto users list --search "alice" --json
```

## User details

```bash
carto users get <user-id|email>
```

Accepts the internal user ID *or* the email. Email is usually easier for an agent to plumb through.

## Inviting users

```bash
carto users invite <email> [--role <role>]
```

`--role` defaults to `Viewer`. Roles:

| Role | Capabilities |
|---|---|
| `Admin` | Full org admin, including user management. |
| `Builder` | Create/edit maps, workflows, connections. |
| `Viewer` | Read-only. |
| `Guest` | Limited read on resources explicitly shared with them. |

Multiple invites — comma-separated or repeated:

```bash
carto users invite alice@x.com,bob@x.com --role Builder
carto users invite alice@x.com bob@x.com --role Builder
```

The invitee receives an email; they accept by clicking the link, which finalizes account creation in the org.

## Pending invitations

```bash
carto users invitations
carto users resend-invitation <token>
carto users cancel-invitation <token>
```

Tokens come from the invitations list output. Re-sending is useful when the original email expired or got filtered.

## Role changes

MCP `manage_users` handles role changes directly over OAuth. The current CLI has **no** `users update-role` subcommand — on a token session or CLI-only host, change roles in the Workspace UI (Settings → Users → change role) or via a direct API call.

## Deleting users

```bash
carto users delete <user-id|email> <receiver-id|email>
```

**Both arguments are required** (MCP `manage_users` delete and the CLI alike). The receiver inherits the departed user's owned resources — CARTO won't orphan them.

```bash
carto users delete alice@x.com bob@x.com
```

If no obvious receiver exists, create a "former-employees" service account and use it as the receiver — keeps resources intact for later audit.

## Common gotchas

- **Inviting an existing user** errors — check the user list first.
- **Pending invites count against quota** in some plans. At user-cap, cancel stale invites to free slots.
- **Email or ID accepted interchangeably** wherever a user is named (get, delete, invite).
- **Audit trail**: `UserCreated` / `UserDeleted` / `UserRoleUpdated` events land in the activity log. To verify an invite became a real account, query `UserCreated` filtered by the invitee's email.
