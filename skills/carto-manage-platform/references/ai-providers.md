# AI providers (BYOK models)

> **Routing.** AI provider configuration is part of the org settings bundle. Over MCP (OAuth) use `admin_carto` with `method: get_settings` / `diff_settings` / `apply_settings`. On the CLI use `carto admin settings get | diff | apply`. Both call the same endpoint, so anything that works on one works on the other. There is no dedicated `ai providers` tool or command. `get` and `diff` need `read:account`; `apply` needs `admin:account`.

## What you can configure

The `cartoAi` section of the settings bundle is the same thing the Workspace "AI" settings page edits:

- `enabled` — CARTO AI on/off for the org.
- `defaultModel` — org fallback model.
- `features.<feature>.enabled` and `features.<feature>.defaultModel` — per-feature toggles and defaults, for `aiAgentsInBuilder` and `askAIInDataObservatory`. `aiAgentsInBuilder` covers Builder AI Agents **and** the agent configuration assistant that helps users create those agents; one switch, one default model for both. `askAIInDataObservatory` is the AI Assistant in Data Observatory. Defaults are per feature, not one org-wide dropdown. The schema also accepts `aiAssistantInWorkflows` and `aiAssistantInAppStudio`; those features are not generally available and are intentionally not documented here.
- One block per provider: `openai`, `google`, `vertex`, `bedrock`, `snowflake`, `anthropic`, `azure`, `databricks`, `oracle`, `custom`. Each has `enabled`, `models` (list of model ids) and the provider's credential fields **flat on the block**, not nested under a `credentials` key.

Credential fields per provider (secret fields in bold are never returned by `get`; the others are):

| Provider | Fields |
|---|---|
| `anthropic`, `openai` | **`apiKey`**, optional `baseUrl` |
| `google` | **`apiKey`** |
| `vertex` | `vertexProject`, `vertexLocation`, **`vertexCredentials`** (service-account JSON as a string) |
| `bedrock` | `awsAccessKeyId`, **`awsSecretAccessKey`**, `awsRegionName`, optional **`awsSessionToken`** |
| `azure` | `apiBase`, **`apiKey`**, optional `apiVersion` |
| `databricks` | `apiBase`, **`apiKey`** |
| `snowflake` | `apiBase` (required), **`apiKey`** |
| `oracle` | **`ociUser`**, **`ociFingerprint`**, **`ociTenancy`**, **`ociKey`**, `ociRegion` |
| `custom` | **`apiKey`**, `baseUrl` (OpenAI-compatible endpoint) |

## BYOK replaces the CARTO-managed models

As soon as the org has **at least one BYOK model registered**, the CARTO-managed `carto::...` models disappear from the org's model list, for every AI feature. Only the BYOK models are offered until the last BYOK provider is disabled, at which point the managed models come back. Plan for this before adding a provider: every feature default and every existing map agent must point at a BYOK model id, or it fails at chat time.

## Add a provider

Send only the block you are changing. The endpoint is a partial update: other providers, `defaultModel` and the feature defaults are left untouched.

Keep the key out of the shell history and out of any repo: write the payload to a file outside the working tree with restricted permissions, or build it from a prompt.

```bash
# Build the payload without the key touching the shell history
read -s -p "Anthropic API key: " KEY; echo
jq -n --arg k "$KEY" '{cartoAi:{anthropic:{enabled:true,models:["claude-sonnet-5-5"],apiKey:$k}}}' > ~/ai-provider.json
chmod 600 ~/ai-provider.json

# Apply
carto admin settings apply --file ~/ai-provider.json
rm ~/ai-provider.json
```

MCP equivalent: `admin_carto({ method: "apply_settings", bundle: { cartoAi: { anthropic: { enabled: true, models: ["claude-sonnet-5-5"], apiKey: "sk-ant-..." } } } })`. Over MCP the key becomes part of the conversation transcript; prefer the CLI for credentials when that matters.

`diff` prints the new `apiKey` in clear text, so do not run it on a payload with a real key unless the terminal output is private.

The server validates **every model in the `models` list** against the provider with a real completion call before registering it. On success the model appears as a BYOK model, id `{accountId}::{provider}::{model}` — confirm with `carto maps agents models` or `admin_carto` `method: list_agent_models`.

### What happens when validation fails

- **Always send `models` together with a new key.** Validation only runs on the models in the payload. A key sent without `models` is stored with no check at all, so a typo in a rotated key goes unnoticed until the first chat fails.
- **New provider, every model rejected:** nothing is saved, the provider stays disabled. Safe to retry.
- **Existing provider, every model rejected:** the previous configuration is kept, the new key and models are discarded.
- **Some models rejected:** the provider is saved with the models that passed.
- The rest of the same payload (`enabled`, `features.*.defaultModel`) is saved regardless.
- The CLI prints `✓ cartoAi` plus one warning line per rejected model, and exits 0 even when every model failed. In scripts, parse the output or the `warnings` field in `--json` mode.

## Enable CARTO AI and set per-feature defaults

`enabled`, `defaultModel` and `features` are writable in the same partial update, so a full provisioning run is one call:

```bash
jq -n --arg k "$KEY" '{cartoAi:{
  enabled: true,
  anthropic: {enabled: true, models: ["claude-sonnet-5-5"], apiKey: $k},
  features: {
    aiAgentsInBuilder:      {enabled: true, defaultModel: "ac_xxxx::anthropic::claude-sonnet-5-5"},
    askAIInDataObservatory: {enabled: true, defaultModel: "ac_xxxx::anthropic::claude-sonnet-5-5"}
  }
}}' > ~/ai-provider.json
carto admin settings apply --file ~/ai-provider.json
```

### Enable or disable individual AI features

Each feature takes its own `enabled` and `defaultModel`; send any subset, the rest are untouched. A disabled feature is enforced server-side (the AI API answers 403 for it), and the org-level `cartoAi.enabled` must be true for any feature switch to take effect.

```bash
echo '{"cartoAi":{"features":{"askAIInDataObservatory":{"enabled":false}}}}' | carto admin settings apply -
```

`defaultModel` and `features.*.defaultModel` take the full model id as listed by `maps agents models` (`carto::...` for CARTO-managed, `{accountId}::{provider}::{model}` for BYOK). **The server does not validate these ids**: a typo or a removed model is accepted and only fails at chat time, so copy the id from the models list. A feature default only preselects the model for new agents; existing map agents keep their own `agent.config.model`.

## Remove or disable a provider

```bash
echo '{"cartoAi":{"anthropic":{"enabled":false}}}' | carto admin settings apply -
```

**Disabling a provider deletes its credentials.** Re-enabling it later requires sending the key again, otherwise the request fails with "Missing or invalid credentials".

Before disabling, check that no map agent uses one of its models (`carto maps list --all --json`, look at `agent.config.model`) and that no feature default points at them. Neither is validated by the settings endpoint; an agent or feature pointing at an unregistered model fails at chat time. If this was the last BYOK provider, the CARTO-managed models become available again.

## Pitfalls

- **Secrets are write-only, the rest is readable.** `get` omits the secret fields marked in the table above and returns everything else (`baseUrl`, `apiBase`, `apiVersion`, `vertexProject`, `vertexLocation`, `awsAccessKeyId`, `awsRegionName`, `ociRegion`). You cannot read a key back, only replace it.
- **A full get → apply round trip is safe for keys but not free.** Stored keys are kept, but every model in the bundle is re-validated with real calls, and the `defaultModel` that `get` fills in is pinned explicitly.
- **The diff shows `→ undefined` for keys missing from your payload.** Those are left untouched by the partial update, not wiped.
- **Self-Hosted: the CARTO AI prerequisites must be deployed first.** Enabling CARTO AI or any provider fails with "The AI service backend is not configured" until the AI Proxy is set up, see [Configure CARTO AI prerequisites](https://docs.carto.com/carto-self-hosted/configuration/ai-features/configure-carto-ai-prerequisites).
- **Token-authenticated MCP sessions do not see `admin_carto` at all.** Reconnect over OAuth or use the CLI.
