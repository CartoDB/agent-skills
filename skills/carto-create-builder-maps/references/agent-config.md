# Agent on the map — `agent` block

Enables the Agent on the map. **Opt-in** — only include this block when the user explicitly asks for an Agent on the map. Organization must have CARTO AI enabled.

**Check organization AI enablement before emitting an agent block:**

```sh
carto maps agents status      # → { enabled, defaultModel, provider config }
```

If `enabled === false`, do NOT emit `agent` in the configuration — tell the user that CARTO AI is not enabled on this organization and skip. The CLI will also soft-strip an `agent` block and warn if it's present in a create/update on an AI-disabled organization, so the create still succeeds without the assistant — but leading with the check avoids authoring dead config.

**You don't have to pick the model.** Omit `agent.config.model` and the CLI auto-fills it with the organization's `defaultModel` from `/settings/carto-ai` (emits a `→ Using organization default model for agent: …` log). Only set `agent.config.model` explicitly when the user asks for a specific provider or model — then `maps agents models` is the catalogue to pick from. If the organization has neither AI enabled nor a `defaultModel`, the CLI surfaces the missing-model error at Tier-1 so you can act.

Full tree required if `config` is included — Kepler's validator is strict.

```jsonc
{
  "agent": {
    "enabledForViewer": false,                      // true = agent also available to viewers
    "config": {
      "model": "ac_7xhfwyml::anthropic::claude-opus-4-5",
      "tools": [],                                   // workflow UUIDs
      "capabilities": {
        "querySources": true                         // allow agent to run SQL against datasets
      },
      "useCase": "One-sentence description of what this agent is for.",
      "instructions": "# Context & constraints\n…\n# Behavior\n…\n# Data definition\n…",
      "introduction": {
        "welcome":  "Hi — I can help you explore this map.",
        "starters": [
          "Show me the top 10 locations by score",
          "Filter to high-risk cells only"
        ]
      }
    }
  }
}
```

### Model string grammar

`<source>::<provider>::<model>`. `source` is `carto` for CARTO-managed models or `ac_xxxxxxxx` (organization account id) for "bring your own key" entries. `provider` is `anthropic` / `openai` / `gemini` / `vertex` / `bedrock` / `azure` / etc. Discover what's enabled on this organization: `carto maps agents models` (pretty) or `--json` (structured). Only strings from that list pass server-side validation — anything else silently falls back to the organization default and surfaces as `agent.issues[]`.

### Tools — `config.tools[]` is **MCP UUIDs only**

`config.tools[]` is a flat array of MCP tool UUIDs (workflows with `mcpTool.enabled === true`). Core Builder and backend tools are *implicit* and context-gated — you do NOT list them here.

| Command | Purpose |
|---|---|
| `carto maps agents mcp-tools [--json]` | List MCP tool UUIDs available on the organization. Empty list ⇒ user must flip the MCP toggle on a workflow first. |
| `carto maps agents core-tools [--json]` | List built-in tools + activation rules + JSON-Schema `parameters` blocks (enough for an external caller to validate arguments). |

**Core-tool activation rules (the agent sees these automatically — no config needed):**

- **Always:** map camera, layer control, filter inspection, marker drop.
- **`capabilities.querySources: true`** unlocks `add_source`, `remove_source`, `execute_query`.
- **Widget-gated:** `get_*_widget` / `filter_*_widget` appear only when a matching widget (formula / category / pie / histogram / timeseries / range) exists in the configuration.
- **SQL-parameter-gated:** `set_sql_parameter_*` appear only when a matching parameter kind exists.
- **Workflow-gated:** `async_workflow_job_*` / `add_source_from_workflows` activate only when `config.tools[]` is non-empty.

> **Implication for authoring.** To give the agent a capability, change the *map shape* — not `agent.config`. "Answer 'top 10 by score'" → include a formula or category widget. "Free-form SQL" → `capabilities.querySources: true`. Don't try to enable tools individually.

### Capabilities & server-computed fields

```jsonc
"capabilities": { "querySources": true }   // SQL + add/remove_source tools
```

`maps get --json` strips `agent.token` and `agent.issues` so the output can be piped straight back into `create` / `update`. Don't resend them.

---

