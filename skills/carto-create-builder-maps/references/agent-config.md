# Agent on the map — `agent` block

Enables the Agent on the map. **Opt-in** — only include this block when the user explicitly asks for an Agent on the map. Organization must have CARTO AI enabled.

> The `carto maps agents status` / `models` / `mcp-tools` / `core-tools` catalogues are **CLI-only** — no MCP equivalent. On a chat-host MCP session without a shell, you can't run these; emit the `agent` block and let the create/update verify step surface any `agent.issues`, or ask the user to confirm AI is enabled.

**Check organization AI enablement before emitting an agent block:**

```sh
carto maps agents status      # → { enabled, defaultModel, provider config }
```

If `enabled === false`, do NOT emit `agent` in the configuration — tell the user that CARTO AI is not enabled on this organization and skip. Create/update also soft-strips an `agent` block and warns if it's present on an AI-disabled organization, so the create still succeeds without the assistant — but leading with the check avoids authoring dead config.

**`agent.config.model` is required.** A `config` without it is rejected — there is no fallback to the organization's `defaultModel` at authoring time. Look an id up rather than composing one: `maps agents models` is the catalogue of what this organization accepts. If the organization has neither AI enabled nor a `defaultModel`, that surfaces here too, so you can act.

If `config` is included, `model`, `capabilities` and `introduction` are all required — each missing one is its own rejection.

```jsonc
{
  "agent": {
    "enabledForViewer": false,                      // true = agent also available to viewers
    "config": {
      "model": "ac_7xhfwyml::anthropic::claude-opus-4-5",
      "tools": [],                                   // workflow UUIDs
      "capabilities": {
        "querySources": false                        // true = agent can run SQL; never on public maps
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

> **Length limits on the agent block.** `config.useCase` ≤ 500 characters; `config.introduction.welcome` ≤ 300; `config.introduction.starters` ≤ 4 entries, each ≤ 100 characters. Exceeding any of them is a rejection, not a warning — Builder's agent dialog refuses or truncates past these, so a longer bundle saves a map that cannot be rebuilt from the UI. Keep `useCase` to one sentence and move detail into `instructions`, which has no cap.

### Model string grammar

Two id forms are current side by side: **`carto::<model>`** — two parts — for CARTO-hosted models, and **`<account-id>::<provider>::<model>`** — three parts — for "bring your own key" entries, where `<account-id>` is the organization account id (`ac_xxxxxxxx`) and `<provider>` is `anthropic` / `openai` / `gemini` / `vertex` / `bedrock` / `azure` / etc. **Don't compose an id from the parts** — the shape alone doesn't tell you what a tenant accepts. Discover what's enabled on this organization: `carto maps agents models` (pretty) or `--json` (structured). Only strings from that list pass server-side validation — anything else silently falls back to the organization default and surfaces as `agent.issues[]`.

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

> **Implication for authoring.** To give the agent a capability, change the *map shape* — not `agent.config`. "Answer 'top 10 by score'" → include a formula or category widget. "Free-form SQL" → `capabilities.querySources: true`, only when the user asks for it and never on a public map. Don't try to enable tools individually.

### Capabilities & server-computed fields

```jsonc
"capabilities": { "querySources": false }  // true = SQL + add/remove_source tools
```

**Default `querySources` to `false`.** Set it to `true` only when the user asks for the agent to run SQL, and never on a map that is or will be public.

**On an existing agent, keep `capabilities` as they are.** Any change to `agent.config` (swapping the model, editing instructions) resends the whole block, so copy `capabilities` from `maps get` instead of from the example above. See "Change only the agent's model" in `updates.md`.

`maps get --json` strips `agent.token` and `agent.issues` so the output can be piped straight back into `create` / `update`. Don't resend them.

---

