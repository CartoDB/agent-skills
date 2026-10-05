# AI providers (BYOK models)

> **Routing.** AI provider configuration is part of the org settings bundle. Over MCP (OAuth, org-admin) use `admin_carto` with `method: get_settings` / `diff_settings` / `apply_settings`. On the CLI use `carto admin settings get | diff | apply`. Both call the same endpoint, so anything that works on one works on the other. There is no dedicated `ai providers` tool or command.

## What you can configure

The `cartoAi` section of the settings bundle is the same thing the Workspace "AI" settings page edits:

- `enabled` — CARTO AI on/off for the org.
- `defaultModel` — org fallback model, e.g. `carto::claude-sonnet-5`.
- `features.aiAgentsInBuilder.defaultModel` and `features.askAIInDataObservatory.defaultModel` — per-feature defaults. Defaults are per feature, not one org-wide dropdown.
- One block per provider: `openai`, `google`, `vertex`, `bedrock`, `snowflake`, `anthropic`, `azure`, `databricks`, `oracle`, `custom`. Each has `enabled`, `models` (list of model ids) and the provider's credential fields **flat on the block**, not nested under a `credentials` key.

Credential fields per provider:

| Provider | Fields |
|---|---|
| `anthropic`, `openai` | `apiKey`, optional `baseUrl` |
| `google` | `apiKey` |
| `vertex` | `vertexProject`, `vertexLocation`, `vertexCredentials` (service-account JSON as a string) |
| `bedrock` | `awsAccessKeyId`, `awsSecretAccessKey`, `awsRegionName`, optional `awsSessionToken` |
| `azure` | `apiBase`, `apiKey`, optional `apiVersion` |
| `databricks` | `apiBase`, `apiKey` |
| `snowflake` | `apiKey`, optional `apiBase` |
| `oracle` | `ociUser`, `ociFingerprint`, `ociTenancy`, `ociKey`, `ociRegion` |
| `custom` | `apiKey`, `baseUrl` (OpenAI-compatible endpoint) |

## Add a provider

Send only the block you are changing. The endpoint is a partial update: other providers, `defaultModel` and the feature defaults are left untouched.

```bash
# Preview first — no writes
echo '{"cartoAi":{"anthropic":{"enabled":true,"models":["claude-sonnet-5-5"],"apiKey":"sk-ant-..."}}}' \
  | carto admin settings diff -

# Apply
echo '{"cartoAi":{"anthropic":{"enabled":true,"models":["claude-sonnet-5-5"],"apiKey":"sk-ant-..."}}}' \
  | carto admin settings apply -
```

MCP equivalent: `admin_carto({ method: "apply_settings", bundle: { cartoAi: { anthropic: { enabled: true, models: ["claude-sonnet-5-5"], apiKey: "sk-ant-..." } } } })`.

The server validates **every model in the list** against the provider with a real completion call before registering it. On success the model appears as a BYOK model for map agents, id `{accountId}::{provider}::{model}` — confirm with `carto maps agents models` or `admin_carto` `method: list_agent_models`.

## Remove or disable a provider

```bash
echo '{"cartoAi":{"anthropic":{"enabled":false,"models":[]}}}' | carto admin settings apply -
```

Check that no map agent uses one of the removed models first (`carto maps list --json`, look at `agent.config.model`). The settings endpoint does not validate that, and an agent pointing at an unregistered model fails at chat time.

## Pitfalls

- **Keys are write-only.** `get_settings` / `settings get` never return credential fields, not even masked. You cannot read a key back, only replace it. A get → edit → apply round trip is therefore safe: it will not overwrite the stored key.
- **An invalid key saves nothing.** The response reports `✓ cartoAi` plus a per-model warning ("rejected during validation and not registered"), and the provider stays disabled with no models. Safe to retry with the right key.
- **The diff shows unchanged keys as `→ undefined`.** That is how the CLI renders fields missing from a partial payload, not a sign they will be wiped.
- **Keep secrets out of files in a repo.** Pipe the JSON from stdin or from a file outside any working tree, and clear the shell history line afterwards.
- **Org-admin only.** Both the MCP methods and the CLI commands need `admin:account`. Token-authenticated MCP sessions do not see `admin_carto` at all; reconnect over OAuth or use the CLI.
