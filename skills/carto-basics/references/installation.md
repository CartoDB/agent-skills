# Installation

## NPM (recommended)

```bash
npm install -g @carto/carto-cli

carto --version
carto --help
```

Requires Node.js 16 or later. The CLI is published as `@carto/carto-cli` on npm.

## Verifying

After install, run:

```bash
carto --version
carto auth status
```

`auth status` will report "Not authenticated" until you log in — that's expected on a fresh install. See [authentication.md](authentication.md).

## Sandboxed/hosted environments — domain whitelisting

Some hosted agent environments (e.g., the claude.ai sandbox) block outbound network calls by default. If you see `getaddrinfo EAI_AGAIN` or generic network errors during `auth login`, the platform is most likely blocking the CARTO endpoints.

Whitelist these domains in the harness's network/permissions settings:

- `auth.carto.com` — OAuth authentication
- `*.api.carto.com` — API calls
- `*.app.carto.com` — Tenant configuration
- `carto.com` — OAuth callback page

If the user is running locally (no sandbox), this section does not apply.

## Upgrading

```bash
npm update -g @carto/carto-cli
carto --version
```

Pin to a specific version when reproducibility matters:

```bash
npm install -g @carto/carto-cli@0.6.0
```
