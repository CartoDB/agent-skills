# Deferred skills

One skill from the original Phase 2 scope is **owned by another PM** and intentionally not built in this PR. It will be delivered in a future PR by that owner.

> **Update (2026-04-29):** `carto-create-builder-maps` shipped — see [`skills/carto-create-builder-maps`](../skills/carto-create-builder-maps). The open question about AI Agents (sub-topic vs. sibling skill) was settled in favour of **bundling them as a sub-topic** — the skill covers Builder maps end-to-end including the `agent` block on a map, with detail in [`references/agent-config.md`](../skills/carto-create-builder-maps/references/agent-config.md).

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

- The catalog (`skills/catalog.json`) does **not** list this skill — `validate_skills.py` would fail on missing directories otherwise.
- Salvage content sits in [`_phase2-salvage/`](_phase2-salvage/) untouched, so the owning PM can fold it in without re-deriving the original split.
- The install matrix ([`install-matrix.md`](install-matrix.md)) marks it as ⏳ — same status as Phase 3 use-case skills.
- Two use-case skills (`carto-build-spatial-dashboard`, `carto-build-customer-facing-map`) **depend** on `carto-build-app`; their delivery is gated on this PM's work landing first.
