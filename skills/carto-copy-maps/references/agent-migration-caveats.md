# AI-agent migration caveats

`maps copy` carries the source map's AI agent configuration along with the rest of the map JSON. **Most of the agent config transfers cleanly** — `instructions`, `introduction`, `enabledForViewer`, conversation starters, etc. are plain text and survive intact.

What **doesn't** transfer cleanly:

- `config.model` — encodes the source org's account ID. Becomes invalid in the destination.
- `config.tools` — references workflow IDs from the source org. Even if you copy the workflow first, the *new* workflow ID isn't auto-substituted.

These two issues surface as `.map.agent.issues` entries on the destination map after the copy. **The CLI today cannot fix them** — they require manual intervention in Builder.

## Inspecting issues after copy

```bash
carto maps get <new-map-id> --profile prod --json | jq '.map.agent.issues'
```

Expected output for a clean copy: `[]`. Anything in the array points at a manual fix needed in Builder.

## `UNAVAILABLE_MODEL`

The agent's model is stored as `"<account-id>::<provider>::<model-name>"`, e.g. `"ac_cb7b9151::anthropic::claude-sonnet-4-5"`. After copy, the account-ID prefix still references the **source** org. The destination org doesn't recognize that account ID and reports the model as unavailable.

```json
{ "issue": "UNAVAILABLE_MODEL" }
```

**Manual fix.** Open the copied map in Builder in the destination org. Open the agent panel and select an available model. The provider + model-name part (`anthropic::claude-sonnet-4-5`) is portable; you're effectively just re-binding to the destination's account ID.

> The CLI gap that prevents auto-fixing this is tracked separately on the CLI team's backlog (see also Ana Manzanares's findings from PR #2). Possible future fixes: auto-swap account-ID prefix during copy; `--model` flag override on `maps copy`; `maps update` support for agent config.

## `UNAVAILABLE_TOOL`

The agent's `config.tools` array references workflow IDs (the agent invokes them as tools). After copy, those IDs still point at the **source** org's workflows. Even if you ran `carto-copy-workflows` for those workflows first — getting fresh IDs in the destination — the agent still references the old IDs.

```json
{ "issue": "UNAVAILABLE_TOOL", "toolId": "ed642f16-7718-4e3d-ad41-ec854a9b4854" }
```

**Manual fix.** Open the map in Builder in the destination org. Open the agent panel; remove the tool reference; re-add the destination workflow as a tool. The tool prompt/parameters pre-set in the source agent are not preserved across this re-add — capture them before the swap if non-default.

> Same CLI gap. A future `--tool-mapping "old-wf-id=new-wf-id"` flag on `maps copy` would close this end-to-end automation hole.

## Recommended sequence for maps with agents

1. **Copy the workflow(s) the agent references first**, using [`carto-copy-workflows`](../../carto-copy-workflows). Note each new workflow ID — you'll need them for the manual tool re-binding.
2. **Copy the map** with `carto maps copy`. The agent config comes along automatically.
3. **Inspect issues**:
   ```bash
   carto maps get <new-map-id> --profile prod --json | jq '.map.agent.issues'
   ```
4. **Fix in Builder** — open the destination map, agent panel:
   - Re-select an available model (resolves `UNAVAILABLE_MODEL`).
   - Re-bind each tool to the corresponding new workflow ID (resolves `UNAVAILABLE_TOOL`).
5. **Verify** — chat with the agent in the destination. Confirm the tools execute successfully (i.e., they actually invoke the destination workflows, not error out).

## Why this is in carto-copy-maps, not carto-create-builder-maps

These caveats apply only when a map is copied across orgs — they don't surface when an agent is creating a fresh map from scratch. Splitting `copy` from `create` puts the gotcha where it's discoverable: an agent doing copy work hits this skill; an agent doing creation doesn't.

## What instruction text *does* transfer cleanly

For the record, these pieces of agent config are plain text and survive a copy without issue:

- `enabledForViewer`
- `config.instructions`
- `config.introduction` (welcome message)
- Conversation starters

So a copied map's agent **looks** right at first glance. It only fails when invoked, because the model and tool references are dangling. Always check `.map.agent.issues` post-copy; never assume a clean copy because the rest of the map renders.
