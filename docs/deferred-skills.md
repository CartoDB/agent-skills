# Deferred skills

Two skills from the original Phase 2 scope are **owned by another PM** (Builder team) and intentionally not built in this PR. They will be delivered in a future PR by that owner.

## `carto-create-builder-maps` (deferred)

**Scope.** **Agentic creation** of maps in CARTO Builder: layers, basemaps, styling, sharing, AI map agents (as part of authoring). The agent helps a user *build* a new map.

**Explicitly NOT in scope** (handled elsewhere):

- *Copying* maps across orgs / profiles → owned by `carto-copy-maps` (Phase 2c). The `UNAVAILABLE_MODEL` / `UNAVAILABLE_TOOL` agent caveats live there, not here, because they only matter when copying.
- *Same-org cloning* (`maps clone`) → also `carto-copy-maps`.

**Pre-staged content.** [`docs/_phase2-salvage/maps.md`](_phase2-salvage/maps.md) — 16KB Map JSON reference covering datasets/layers diagram, creation checklist, common mistakes, complete example. Plus the `Maps` and `AI Features` sections of [`commands-deferred.md`](_phase2-salvage/commands-deferred.md), filtered for create-side verbs (`maps update`, `aifeature aiagent`) — `maps copy` and `maps clone` are not in this skill's scope.

**Open question to settle when picked up.** Should AI map agents live as a sub-topic of this skill, or be a separate sibling skill? Original proposal §6 OQ#4. The decision affects discoverability — bundling makes Builder-centric flows cleaner; splitting makes agentic-map flows easier to land on.

**Catalog entry to add when shipping.**

```json
{
  "name": "carto-create-builder-maps",
  "layer": "platform",
  "dependencies": ["carto-basics", "carto-connect-datawarehouse", "carto-explore-datawarehouse"],
  "description": "Author maps in CARTO Builder: layers, basemaps, styling, sharing, and AI map agents.",
  "path": "skills/carto-create-builder-maps"
}
```

## `carto-build-app` (deferred)

**Scope.** Build apps that consume CARTO: APIs, named sources, scoped tokens, SDKs (deck.gl, Maps API, JS/TS), embedding, hosted deployment.

**Pre-staged content.** [`docs/_phase2-salvage/commands-deferred.md`](_phase2-salvage/commands-deferred.md) — `AI Proxy`, plus most of the `Credentials` content from `carto-cli/commands.md` (token / SPA / M2M OAuth client creation). The named-source CRUD surface — `carto named-sources create/update/delete` — also belongs here (utility-tier `carto-explore-datawarehouse` only covers *finding* named sources, not creating them).

**Open question to settle when picked up.** SDK depth — do we cover JS/TS SDK + APIs equally, or front-load the deck.gl + Maps API path? Affects skill size and reference-file split. Original proposal §6 (implicit).

**Catalog entry to add when shipping.**

```json
{
  "name": "carto-build-app",
  "layer": "platform",
  "dependencies": ["carto-basics", "carto-connect-datawarehouse", "carto-explore-datawarehouse"],
  "description": "Build apps that consume CARTO: APIs, named sources, scoped tokens, SDKs, embedding, hosted deployment.",
  "path": "skills/carto-build-app"
}
```

## What "deferred" means in practice

- The catalog (`skills/catalog.json`) does **not** list these skills — `validate_skills.py` would fail on missing directories otherwise.
- Salvage content sits in [`_phase2-salvage/`](_phase2-salvage/) untouched, so the Builder PM can fold it in without re-deriving the original split.
- The install matrix ([`install-matrix.md`](install-matrix.md)) marks both as ⏳ — same status as Phase 3 use-case skills.
- Three use-case skills (`carto-build-spatial-dashboard`, `carto-build-customer-facing-map`, `carto-migrate-to-carto`) **depend** on these two; their delivery is gated on this PM's work landing first.
