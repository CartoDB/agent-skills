---
name: carto-develop-app
description: Generate a working geospatial app powered by CARTO and deck.gl — basemap, layers (vector / H3 / quadbin / raster), widgets, filters, legend, inputs, optional chat-with-map agent, and the right auth strategy (public token, OAuth, SSO, or M2M).
license: MIT
---

# carto-develop-app

Generate a working CARTO + [deck.gl](https://deck.gl) app from a prompt. Four decisions — **app type**, **framework**, **auth model**, **data shape** — then assemble layers, widgets, filters, inputs, a legend, and (optionally) an embedded map agent.

Apps follow the [CartoDB/deck.gl-examples](https://github.com/CartoDB/deck.gl-examples) blueprint. Layers from `@deck.gl/carto`; data sources, widgets, filters, `fetchMap`, `query()` from `@carto/api-client` (sources left `@deck.gl/carto` in v0.4.0 — don't import them from there).

## When to use

- "deck.gl app", "CARTO app", "map app", "spatial dashboard" — use this skill.
- Builder map ID supplied → [`fetchmap.md`](references/fetchmap.md).
- Storymap / scrollytelling / narrative map / guided tour → [`storymap.md`](references/storymap.md) (composes on top of the React scaffold below).
- Chat-with-map / embedded AI agent → [`agentic-variant.md`](references/agentic-variant.md).
- *Authoring* maps in Builder → [`carto-create-builder-maps`](../carto-create-builder-maps). *Migrating* a Builder map across orgs / profiles → [`cross-profile-copy.md`](../carto-create-builder-maps/references/cross-profile-copy.md).

## Operating mode — autonomous by default

**Generate the env via the CARTO CLI. Don't interview the user.** Pass `--json` and parse.

Run, then write `.env`:

```bash
carto auth status --json                  # → apiBaseUrl (from tenant.domain region)
carto connections list --json             # → connectionName (default: carto_dw)

# One token, ONE grant per source — repeat --connection alongside every --source.
carto credentials create token --json \
  --connection <connectionName> --source <fully.qualified.table.A> \
  --connection <connectionName> --source <fully.qualified.table.B> \
  --apis sql,maps \
  --referers http://localhost:5173,<production-origin>
```

**One token, many grants** — not one token per table. `--connection` and `--source` pair positionally, so repeat `--connection` for every `--source`. Use `--referers` (plural CSV); `--referer` (singular) overwrites if repeated. `--source` also accepts **wildcard patterns** like `carto.shared.CARTO_*` to cover many resources in a single grant (patterns must contain at least two dot-separated segments — `CARTO_*` and `table*` are rejected; bare `*` is still the "all sources" sentinel, not a pattern). Add `--expiration-date 30d` (or an ISO date) for short-lived contexts like demos and keynotes; tokens never expire by default. See [`auth-public-token.md`](references/auth-public-token.md).

Private apps swap the token command for `carto credentials create spa --json` (OAuth) or `carto credentials create m2m --json` (M2M).

If `carto` isn't on `PATH` or `auth status` fails: say so once and stop — print the missing command. Don't fall back to interviewing. Assumes a working CLI ([`carto-basics`](../carto-basics)).

Only ask what the CLI can't answer: **table name** (if not obvious) and ambiguous app-shape choices below.

## Decision flow — only ask when truly ambiguous

1. **Builder map ID supplied?** Yes → [`fetchmap.md`](references/fetchmap.md). Done.
1b. **Storymap shape?** Cues: "story map", "scrollytelling", "guided tour", "scenes/chapters/slides", "fly through". → [`storymap.md`](references/storymap.md). Still pick the React scaffold + sources/layers below; storymap is a state pattern layered on top, not a separate scaffold.
2. **Demo or production?** Default to **vanilla TS + Vite + MapLibre** ([`scaffold-vanilla.md`](references/scaffold-vanilla.md)) unless the prompt says "production", "auth", "deploy", "team", "multi-screen" → React ([`scaffold-react.md`](references/scaffold-react.md)). Vue / Angular only if explicitly named ([`scaffold-vue-angular.md`](references/scaffold-vue-angular.md)).
3. **Auth model?** Pick from prompt cues; ask only if cues conflict.
   - "public" / "share" / "embed" / no login → API access token ([`auth-public-token.md`](references/auth-public-token.md))
   - "private" / "users log in" / "CARTO login" → OAuth SPA ([`auth-private-oauth.md`](references/auth-private-oauth.md))
   - "SSO" / "Okta" / "Azure AD" / "corporate IdP" → OAuth + SSO ([`auth-private-sso.md`](references/auth-private-sso.md))
   - "backend" / "ETL" / "CI" / "scheduled" → M2M ([`auth-m2m.md`](references/auth-m2m.md))
4. **Data shape?** Source/layer pair from [`data-sources.md`](references/data-sources.md) + [`layers.md`](references/layers.md): points/lines/polygons → vector; H3 → H3; quadbin → quadbin; surfaces → raster. Wire the basemap and view-state sync via [`basemap-and-view.md`](references/basemap-and-view.md).

Then layer in only what was asked for: [widgets](references/widgets.md), [filters](references/filters.md), [inputs](references/inputs-and-parameters.md), [legend](references/legend.md), [SQL/workflows](references/workflows-and-sql.md), [agentic chat](references/agentic-variant.md). Recipes in [`recipes/`](references/recipes/).

5. **Visual style?** No style cues → Meridian-inspired default (clean, professional, CARTO-native). Any style cue ("futuristic", "corporate", a named design system) → custom theme matching the user's description. Either way, apply the UX layout principles. See [`design-and-theming.md`](references/design-and-theming.md).

## Always-on guidance

- **`apiBaseUrl`** comes from `carto auth status --json` (`tenant.domain` region). Never hard-code.
- **`connectionName`** defaults to `carto_dw`; confirm via `carto connections list --json`.
- **Public tokens** must always pass `--source` and limit `--apis` to `sql,maps`. Never `imports` / `lds` in a public bundle.
- **One `filters` object** is shared by source helpers *and* widget methods. Mutating it triggers re-fetch on both.
- **Debounce viewport spatial filters ~300 ms** on `onViewStateChange`.
- **Design** — apply the Meridian-inspired default theme unless the user specifies a different aesthetic. UX layout principles (map as hero, panel discipline, progressive disclosure) always apply. See [`design-and-theming.md`](references/design-and-theming.md).
- **Never invent logos.** Only render a logo (CARTO, customer, partner, third-party brand) when the user supplied a verified PNG / JPG / SVG asset or pointed to an official source. No verified asset → ask the user, or use a text wordmark / omit the logo entirely. Do not generate SVG marks, fetch from unverified URLs, or substitute a similar-looking brand. Applies even to well-known brands.
- **End by running the app.** Run `npm install && npm run dev` and report the URL.
