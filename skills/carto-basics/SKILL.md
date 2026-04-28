---
name: carto-basics
description: Start here for first-time CARTO CLI use — install, authenticate, switch profiles, understand JSON output and async job patterns.
license: MIT
---

# carto-basics

The `carto` CLI (`@carto/carto-cli`) is the primary way an agent interacts with the CARTO platform. **Use this skill before any other CARTO skill**: it covers installation, authentication, profiles, and the global flags that every other CARTO skill assumes.

## When to use this skill

- Setting up the CLI for the first time on a new machine.
- The user reports authentication errors (`auth status` failures, expired tokens).
- The user wants to switch between organizations or environments.
- A downstream skill needs `--profile`, `--json`, `--token`, or `--base-url` and you don't yet know how those work.

## Quick start

```bash
npm install -g @carto/carto-cli
carto auth login                # opens browser, stores credentials
carto auth status               # confirms tenant, org, user
carto maps list --json          # any command can return JSON
```

Authentication state persists across sessions. `auth status` is the fastest way to confirm the agent has working credentials before doing anything else.

## What's in this skill

| Topic | Reference |
|---|---|
| Installing the CLI (npm, version verification) | [references/installation.md](references/installation.md) |
| Authentication: browser, headless `--no-launch-browser`, API tokens, SSO | [references/authentication.md](references/authentication.md) |
| Profiles: managing multiple orgs / environments | [references/profiles.md](references/profiles.md) |
| Global flags: `--json`, `--debug`, `--yes`, `--token`, `--base-url`, `--profile`, env vars | [references/global-options.md](references/global-options.md) |

## Always-on guidance

- **Always pass `--json`** when you need machine-readable output. CLI text output is for humans and may change.
- **Map URLs** use the tenant domain from `auth status`, not a generic workspace URL. Private maps live at `https://{tenant_domain}/builder/{map_id}`; public/shared maps at `https://{tenant_domain}/map/{map_id}`. Never construct `workspace-{region}.app.carto.com` URLs.
- **Confirmation prompts**: destructive commands like `maps delete` prompt for the literal word "delete". Pass `--yes` (or `--json`) for non-interactive use.
- **Async jobs**: `imports create` and `sql job` poll until completion by default. Pass `--async` (where supported) to return immediately and poll separately.
