# Chat-with-map (`@carto/agentic-deckgl`)

For embedding a "chat with this map" panel: the user types natural language, an LLM emits tool calls, and the deck.gl instance updates live (set view state, drop a marker, mask a region, swap a layer).

`@carto/agentic-deckgl` (v0.1.0, [CartoDB/carto-agentic-deckgl](https://github.com/CartoDB/carto-agentic-deckgl)) ships **the agent contract**: Zod tool schemas, a system-prompt builder, and `@deck.gl/json` validators. **It does not ship UI components, hooks, providers, or a backend.** You wire those up.

This is a runtime feature, not a build-time generator. Use it when the user wants chat-with-map, not when they want "an AI to write my app".

## Architecture

```
[browser]                      [your backend]            [LLM provider]
  ┌────────────┐ chat msg     ┌────────────┐  prompt   ┌──────────┐
  │  React UI  ├─────────────▶│  Express   ├──────────▶│ OpenAI / │
  │            │              │  + WS      │           │ Vercel / │
  │  DeckGL    │◀─────────────┤            │◀──────────┤ Google   │
  │  +         │  tool_calls  │  Streams   │  tool_use │  ADK     │
  │  validator │              │  back      │           └──────────┘
  └────────────┘              └────────────┘
```

The library lives in two places: the backend imports it to build the system prompt and tool schemas; the frontend imports it to validate tool calls before executing them via `JSONConverter`.

## Install

```bash
npm install @carto/agentic-deckgl @deck.gl/json zod
```

Peer deps `@deck.gl/json ^9.2.0` and `zod ^4.3.6`.

## Backend (Vercel AI SDK example)

```ts
import { generateText } from 'ai';
import { openai } from '@ai-sdk/openai';
import {
  getToolsRecordForVercelAI,
  buildSystemPrompt,
} from '@carto/agentic-deckgl';

export async function chat(req, res) {
  const { messages, mapState, userContext } = req.body;

  const result = await generateText({
    model: openai('gpt-4.1'),
    system: buildSystemPrompt({ mapState, userContext }),
    messages,
    tools: getToolsRecordForVercelAI(),
    maxSteps: 5,
  });

  res.json({ text: result.text, toolCalls: result.toolCalls });
}
```

The library also ships `getToolsForOpenAIAgents` (OpenAI Agents SDK) and `getToolsForGoogleADK`. Pick the one that matches your backend stack — the reference repo's `examples/backend-*` folders have full setups.

## Frontend tool execution

```ts
import { JSONConverter } from '@deck.gl/json';
import {
  validateToolParams,
  parseToolResponse,
  successResponse,
  errorResponse,
} from '@carto/agentic-deckgl';

const converter = new JSONConverter({ configuration: { /* layer + view registries */ } });

async function executeToolCall(call: { name: string; params: unknown }) {
  const validation = validateToolParams(call.name, call.params);
  if (!validation.success) return errorResponse(validation.error);

  switch (call.name) {
    case 'set-deck-state': {
      const { layers, viewState } = validation.data;
      const deckJson = converter.convert({ layers, viewState });
      deck.setProps(deckJson);
      return successResponse({ applied: true });
    }
    case 'set-marker': {
      const { coordinates, label } = validation.data;
      addMarkerLayer(deck, coordinates, label);
      return successResponse({ applied: true });
    }
    case 'set-mask-layer': {
      const { polygon } = validation.data;
      setMaskLayer(deck, polygon);
      return successResponse({ applied: true });
    }
  }
}
```

The three built-in tools are `set-deck-state`, `set-marker`, `set-mask-layer`. The agent can also be given custom tools — wrap your own Zod schemas alongside.

## System prompt + map state

The agent only knows what you tell it. Pass the current map context every turn:

```ts
import { buildSystemPrompt, type MapState } from '@carto/agentic-deckgl';

const mapState: MapState = {
  viewState: deck.getViewports()[0],
  layers: deck.props.layers.map((l) => ({
    id: l.id,
    type: l.constructor.name,
    visible: l.props.visible,
    props: serializableProps(l.props),
  })),
};

const system = buildSystemPrompt({
  mapState,
  userContext: { user: 'atena', org: 'cartodb' },
});
```

If the agent is hallucinating layer names or making up table references, expand `mapState` to include data source metadata (table names, columns) — `buildSystemPrompt` accepts arbitrary user context.

## Frontend UI shape (React)

```tsx
function ChatPanel({ onApplyTool }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');

  const send = async () => {
    const next = [...messages, { role: 'user', content: input }];
    setMessages(next);
    setInput('');
    const res = await fetch('/api/chat', { method: 'POST', body: JSON.stringify({
      messages: next,
      mapState: getCurrentMapState(),
    })});
    const { text, toolCalls } = await res.json();
    setMessages([...next, { role: 'assistant', content: text }]);
    for (const call of toolCalls ?? []) onApplyTool(call);
  };

  return (
    <div className="chat">
      {messages.map((m, i) => <div key={i} className={m.role}>{m.content}</div>)}
      <input value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && send()} />
    </div>
  );
}
```

Streaming responses (token-by-token) is what the reference backends do — switch from `fetch` + JSON to SSE / WebSocket once the basic shape works.

## Reserved layer IDs

The library reserves layer IDs prefixed with `__` for system layers (markers, masks, agent state). Don't name your own layers `__anything`.

## Backends — pick one

The reference repo ships three:

- **OpenAI Agents SDK** (default) — most polished, requires OpenAI API key.
- **Vercel AI SDK v6** — provider-agnostic (Anthropic, OpenAI, Google), best for production.
- **Google ADK** — for Vertex / Gemini.

Don't build a backend from scratch. Copy one of the reference backends, swap your provider key, deploy.

## Auth

Two layers:
1. **CARTO** — same as the rest of the app (public token / OAuth / SSO / M2M).
2. **LLM provider** — OpenAI / Anthropic / Google API key on the backend, or CARTO AI Proxy (`carto aiproxy info` / `carto aiproxy chat`) which brokers model access through CARTO.

For demos, hard-code the LLM key on a localhost backend. For production, never expose LLM keys to the browser; everything goes through your backend.

## Gotchas

- **v0.1.0 is pre-1.0.** Pin the version; expect breaking changes between minor releases.
- **No UI components.** If you want hooks / providers, use the React reference example as a template, not the bare library.
- **Tool calls without validation will crash deck.gl.** Always run `validateToolParams` first; the LLM gets things wrong.
- **`deck.getViewports()[0]`** returns the current viewport — pass to the agent every turn so it doesn't drift.
- **`@carto/api-client` is not a dep** of the library. CARTO data fetching happens through your normal source helpers; the agent just emits layer specs that point at sources you set up.
- **Don't put the LLM API key in the bundle.** Backend-only. Always.
