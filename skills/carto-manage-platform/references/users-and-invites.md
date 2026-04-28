# User and invitation management

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

There's no dedicated `users update-role` subcommand in the current CLI. Two routes:

1. **Workspace UI** — Settings → Users → click user → change role.
2. **API** — direct API call (out of scope for this skill).

If `carto users update` lands in a future CLI version, prefer it.

## Deleting users

```bash
carto users delete <user-id|email> <receiver-id|email>
```

**Both arguments are required.** The receiver inherits the departed user's owned resources (maps, workflows, connections). CARTO won't orphan resources.

```bash
carto users delete alice@x.com bob@x.com
```

If no obvious receiver exists, create a "former-employees" service account and use it as the receiver — keeps resources intact for later audit.

## Common gotchas

- **Inviting an existing user** errors. Check `users list --search` first.
- **Pending invites count against quota** in some plans. If you're at user-cap, cancel stale invites to free slots.
- **Email-vs-ID inconsistency** — `users get alice@x.com` works; `users delete <numeric-id> <email>` works too. The CLI accepts either.
- **Audit trail**: `UserCreated`, `UserDeleted`, `UserRoleUpdated` events land in the activity log. To verify an invite turned into a real account, query for `UserCreated` events filtered by the invitee's email.
