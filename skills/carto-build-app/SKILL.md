---
name: carto-build-app
description: Generate a working geospatial app powered by CARTO and deck.gl — basemap, layers (vector / H3 / quadbin / raster / boundary), widgets, filters, legend, inputs, optional chat-with-map agent, and the right auth strategy (public token, OAuth, SSO, or M2M).
license: MIT
---

# carto-build-app

Generate a working CARTO + [deck.gl](https://deck.gl) app from a prompt. Walk four decisions — **app type**, **framework**, **auth model**, **data shape** — then assemble layers, widgets, filters, inputs, a legend, and (optionally) an embedded map agent.

Generated apps follow the [CartoDB/deck.gl-examples](https://github.com/CartoDB/deck.gl-examples) blueprint. Layers come from `@deck.gl/carto`; data sources, widgets, filters, `fetchMap`, and `query()` come from `@carto/api-client`. Sources moved out of `@deck.gl/carto` in v0.4.0 — never import them from there.

## When to use this skill

- The user asks for a "deck.gl app", "CARTO app", "map app", or "spatial dashboard".
- The user has a Builder map ID and wants it as a standalone app → [`fetchmap.md`](references/fetchmap.md).
- The user wants chat-with-map / an AI agent embedded → [`agentic-variant.md`](references/agentic-variant.md).

For *authoring* maps inside CARTO Builder use `carto-create-builder-maps` (deferred). To *migrate* a Builder map across orgs, use [`carto-copy-maps`](../carto-copy-maps).

## Decision flow — ask the user when unclear

1. **Builder map ID supplied?** Yes → [`fetchmap.md`](references/fetchmap.md). Done.
2. **Demo or production?** *Ask if unclear.*
   - Demo / learning → vanilla TS + Vite + MapLibre — [`scaffold-vanilla.md`](references/scaffold-vanilla.md).
   - Production → React (default) — [`scaffold-react.md`](references/scaffold-react.md). Vue / Angular in [`scaffold-vue-angular.md`](references/scaffold-vue-angular.md).
3. **Auth model?** *Ask if unclear.*
   - Public app, public/shared data → API access token — [`auth-public-token.md`](references/auth-public-token.md).
   - Private app, CARTO login → OAuth (Auth0 SPA) — [`auth-private-oauth.md`](references/auth-private-oauth.md).
   - Private app, corporate IdP → OAuth + SSO — [`auth-private-sso.md`](references/auth-private-sso.md).
   - Backend / CI / no human → M2M — [`auth-m2m.md`](references/auth-m2m.md).
4. **Data shape?** Source/layer pair from [`data-sources.md`](references/data-sources.md) + [`layers.md`](references/layers.md): points/lines/polygons → vector; H3 → H3; quadbin → quadbin; surfaces → raster; admin boundaries → boundary. Wire the basemap and view-state sync via [`basemap-and-view.md`](references/basemap-and-view.md).

Then layer in only what was asked for: [widgets](references/widgets.md), [filters](references/filters.md), [inputs](references/inputs-and-parameters.md), [legend](references/legend.md), [SQL/workflows](references/workflows-and-sql.md), [agentic chat](references/agentic-variant.md). Recipes in [`recipes/`](references/recipes/).

## Always-on guidance

- **`apiBaseUrl` is region-scoped** (`https://gcp-us-east1.api.carto.com`, `https://gcp-eu-west1.api.carto.com`, …). Get it from `carto auth status` (tenant domain). Don't hard-code.
- **`connectionName` defaults to `carto_dw`** — confirm via `carto connections list --json`.
- **One `filters` object** is shared between source helpers *and* widget methods. Mutating it triggers re-fetch on both. Details in [`filters.md`](references/filters.md).
- **Debounce viewport spatial filters by ~300 ms** on `onViewStateChange`. Upstream examples all do this.
- **Scope public-app tokens.** A `credentials create token` without `--source`/`--referer` and with all APIs (`sql,maps,imports,lds`) is a foot-gun in a public bundle.
- **Default React for production, vanilla for demos** — but ask if the user hasn't said.
- **CLI invocation.** If `carto` is on `PATH` and `carto auth status` succeeds, run credential / connection commands directly. Otherwise hand the exact command to the user and read JSON back.
