# CARTO CLI - Agent Migration Issues

Findings from real-world migration testing: copying map "Identify Urban Transport Deserts" with agent + workflow from `agentic-gis-demos` to `dedicated-07` using CARTO CLI v0.1.2.

## Context

When migrating a map that has an AI agent configured, the CLI copies the agent config automatically via `maps copy`. However, the agent config contains org-specific references (model account ID, workflow/tool IDs) that become invalid in the destination org. The CLI currently cannot fix these — they must be corrected manually in Builder.

---

## Issue 1: Agent tool references not remapped during maps copy

**Current behavior:**
- User copies a workflow with `carto workflows copy` → gets a new workflow ID in the destination
- User copies a map with `carto maps copy` → agent config comes along, but `config.tools` still references the old (source org) workflow ID
- The copied map shows `{"issue": "UNAVAILABLE_TOOL", "toolId": "<old-workflow-id>"}` in `.map.agent.issues`
- User must open Builder to manually re-link the tool to the copied workflow

**Expected behavior:**
The CLI should remap tool references when copying a map. Possible approaches:
1. **`--tool-mapping` flag**: Similar to `--connection-mapping`, allow explicit remapping: `carto maps copy <id> --dest-profile prod --tool-mapping "old-wf-id=new-wf-id"`
2. **Automatic cascade**: If `maps copy` detects that agent tools are workflow IDs that exist in the source org, automatically copy those workflows and remap the references in one operation
3. **Post-copy prompt**: After detecting `UNAVAILABLE_TOOL`, suggest the correct new workflow ID if a workflow with the same name exists in the destination

**Test case:**
```bash
# Step 1: Copy workflow
carto workflows copy ed642f16-7718-4e3d-ad41-ec854a9b4854 \
  --source-profile agentic-gis-demos --dest-profile dedicated-07
# Returns: new workflow ID c8c6f8f9-d2a9-457a-ac37-4ad5c04798bb

# Step 2: Copy map (agent tools still reference old workflow ID)
carto maps copy 81e54890-a6fd-455b-9ae5-8a8f12d0a1d1 \
  --source-profile agentic-gis-demos --dest-profile dedicated-07 --skip-source-validation

# Step 3: Check issues
carto maps get <new-map-id> --profile dedicated-07 --json | jq '.map.agent.issues'
# Returns: [{"issue": "UNAVAILABLE_TOOL", "toolId": "ed642f16-..."}]
```

---

## Issue 2: Agent model reference not updated for destination org

**Current behavior:**
- Agent model is stored as `"account-id::provider::model-name"` (e.g. `"ac_cb7b9151::anthropic::claude-sonnet-4-5"`)
- After `maps copy`, the model still references the source org's account ID
- The copied map shows `{"issue": "UNAVAILABLE_MODEL"}` in `.map.agent.issues`
- User must open Builder to manually select an available model

**Expected behavior:**
The CLI should update the account ID prefix to match the destination org. Possible approaches:
1. **Auto-swap account ID**: Replace the account ID prefix with the destination org's account ID, keeping `provider::model-name` unchanged
2. **`--model` flag**: Allow overriding the model during copy: `carto maps copy <id> --dest-profile prod --model "ac_dest::anthropic::claude-sonnet-4-5"`
3. **Model availability check + fallback**: Query available models in destination, auto-map if the same provider::model-name is available, warn if not

**Test case:**
```bash
# Source map agent model:
# "ac_cb7b9151::anthropic::claude-sonnet-4-5"

# After maps copy to dedicated-07:
carto maps get <new-map-id> --profile dedicated-07 --json | jq '.map.agent.config.model'
# Returns: "ac_cb7b9151::anthropic::claude-sonnet-4-5" (still source org account ID)

carto maps get <new-map-id> --profile dedicated-07 --json | jq '.map.agent.issues'
# Returns: [{"issue": "UNAVAILABLE_MODEL"}]
```

---

## Issue 3: No CLI support for updating agent config on existing maps

**Current behavior:**
- `carto maps update` can update map metadata (title, description, privacy, keplerMapConfig)
- There is no way to update agent config fields (model, tools, instructions) via the CLI
- Fixing `UNAVAILABLE_MODEL` and `UNAVAILABLE_TOOL` requires opening Builder

**Expected behavior:**
`carto maps update` should support updating agent configuration:
```bash
# Update agent model
carto maps update <map-id> '{"agent": {"config": {"model": "ac_neworg::anthropic::claude-sonnet-4-5"}}}'

# Update agent tools
carto maps update <map-id> '{"agent": {"config": {"tools": ["new-workflow-id"]}}}'
```

---

## Summary

| Issue | Severity | Current workaround |
|-------|----------|-------------------|
| Tool references not remapped | High | Manual fix in Builder |
| Model account ID not swapped | High | Manual fix in Builder |
| Cannot update agent via CLI | Medium | Manual fix in Builder |

All three issues break the "fully automated migration" workflow. An agent-aware map with workflows currently requires manual post-migration steps in Builder, which defeats the purpose of CLI-based migration for CI/CD and automation scenarios.
