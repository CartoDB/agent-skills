# Recipe — chat-with-map (React + `@carto/agentic-deckgl`)

A React app with a side panel where the user types natural language; the LLM emits deck.gl tool calls; the map updates live.

This is a **runtime** AI integration, not build-time generation. See [`agentic-variant.md`](../agentic-variant.md) for the full reference and architecture.

## Pre-reqs

- React scaffold from [`scaffold-react.md`](../scaffold-react.md).
- One of the reference backends from [CartoDB/carto-agentic-deckgl/examples](https://github.com/CartoDB/carto-agentic-deckgl) running on `http://localhost:3003` (OpenAI Agents / Vercel AI / Google ADK — pick one).
- A scoped public token or OAuth token for CARTO data.

## Install

```bash
npm install @carto/agentic-deckgl @deck.gl/json zod
```

## `src/components/Map.tsx`

```tsx
import { forwardRef, useImperativeHandle, useMemo, useRef, useState } from 'react';
import DeckGL from '@deck.gl/react';
import { JSONConverter } from '@deck.gl/json';
import * as carto from '@deck.gl/carto';
import { BASEMAP } from '@deck.gl/carto';
import { Map as MaplibreMap } from 'react-map-gl/maplibre';

const converter = new JSONConverter({
  configuration: {
    classes: {
      ...carto,         // makes VectorTileLayer, H3TileLayer, etc. addressable by @@type
    },
  },
});

const INITIAL = { longitude: -73.97, latitude: 40.75, zoom: 11, pitch: 0, bearing: 0 };

export type MapHandle = {
  applyDeckState: (spec: { layers: any[]; viewState?: any }) => void;
  getMapState: () => { viewState: any; layers: { id: string; type: string }[] };
};

const Map = forwardRef<MapHandle>((_, ref) => {
  const [viewState, setViewState] = useState(INITIAL);
  const [layers, setLayers] = useState<any[]>([]);
  const layerRefs = useRef<{ id: string; type: string }[]>([]);

  useImperativeHandle(ref, () => ({
    applyDeckState({ layers: spec, viewState: vs }) {
      const built = converter.convert({ layers: spec });
      setLayers(built.layers ?? []);
      layerRefs.current = (spec ?? []).map((l: any) => ({
        id: l.id,
        type: l['@@type'] ?? 'unknown',
      }));
      if (vs) setViewState({ ...viewState, ...vs });
    },
    getMapState() {
      return { viewState, layers: layerRefs.current };
    },
  }));

  return (
    <DeckGL
      viewState={viewState}
      onViewStateChange={({ viewState: v }: any) => setViewState(v)}
      controller
      layers={layers}
    >
      <MaplibreMap mapStyle={BASEMAP.POSITRON} />
    </DeckGL>
  );
});

export default Map;
```

## `src/components/ChatPanel.tsx`

```tsx
import { useState } from 'react';
import { validateToolParams } from '@carto/agentic-deckgl';
import type { MapHandle } from './Map';

type Msg = { role: 'user' | 'assistant'; content: string };

export default function ChatPanel({ mapRef }: { mapRef: React.RefObject<MapHandle> }) {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState('');
  const [pending, setPending] = useState(false);

  const send = async () => {
    if (!input.trim() || !mapRef.current) return;
    const next: Msg[] = [...messages, { role: 'user', content: input }];
    setMessages(next);
    setInput('');
    setPending(true);

    const res = await fetch('http://localhost:3003/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        messages: next,
        mapState: mapRef.current.getMapState(),
      }),
    });
    const { text, toolCalls } = await res.json();
    setMessages((m) => [...m, { role: 'assistant', content: text ?? '' }]);

    for (const call of toolCalls ?? []) {
      const validated = validateToolParams(call.name, call.params);
      if (!validated.success) {
        console.warn('Invalid tool call', call.name, validated.error);
        continue;
      }
      if (call.name === 'set-deck-state') {
        mapRef.current.applyDeckState(validated.data);
      }
      // set-marker, set-mask-layer: see agentic-variant.md
    }
    setPending(false);
  };

  return (
    <aside className="chat">
      <div className="messages">
        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>{m.content}</div>
        ))}
        {pending && <div className="msg assistant">…</div>}
      </div>
      <div className="composer">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && !pending && send()}
          placeholder="Show me population by H3 in California…"
        />
        <button onClick={send} disabled={pending}>Send</button>
      </div>
    </aside>
  );
}
```

## `src/App.tsx`

```tsx
import { useRef } from 'react';
import Map, { type MapHandle } from './components/Map';
import ChatPanel from './components/ChatPanel';

export default function App() {
  const mapRef = useRef<MapHandle>(null);
  return (
    <div className="app">
      <Map ref={mapRef} />
      <ChatPanel mapRef={mapRef} />
    </div>
  );
}
```

## `src/style.css`

```css
.app { position: relative; height: 100vh; display: grid; grid-template-columns: 1fr 360px; }
.chat { background: #fff; border-left: 1px solid #eee; display: flex; flex-direction: column; }
.messages { flex: 1; overflow-y: auto; padding: 12px; }
.msg { padding: 8px 12px; margin: 6px 0; border-radius: 8px; max-width: 80%; }
.msg.user { background: #4080ff; color: #fff; margin-left: auto; }
.msg.assistant { background: #f0f0f0; }
.composer { display: flex; gap: 8px; padding: 12px; border-top: 1px solid #eee; }
.composer input { flex: 1; padding: 8px; border: 1px solid #ccc; border-radius: 6px; }
.composer button { padding: 8px 14px; }
```

## Backend

Don't write the backend. Clone `examples/backend-vercel-ai` (or `backend-openai-agents`, `backend-google-adk`) from the [reference repo](https://github.com/CartoDB/carto-agentic-deckgl), set the LLM API key in `.env`, run on port 3003.

Key elements the backend ships:
- `buildSystemPrompt({ mapState, userContext })` — gives the LLM context.
- `getToolsRecordForVercelAI()` (or equivalent for the chosen SDK) — exposes the three deck.gl tools.
- A streaming endpoint (`/chat` here is a non-streaming demo; real apps stream tokens via SSE).

## Streaming

For prod, swap the `fetch` for SSE / WebSocket. The reference backends include both shapes — it's a 20-line frontend change once you decide.

## Auth

The chat panel doesn't authenticate to CARTO directly — `mapState.layers` describes the layers; the agent emits specs that point at named CARTO sources you set up earlier. CARTO auth is whatever flow the rest of the app uses.

The **LLM key** lives on the backend only — never in `.env` consumed by Vite.

## Gotchas

- **Tool calls without `validateToolParams` will crash deck.gl** when the LLM hallucinates.
- **Stale `mapState`** → the agent suggests layers based on what *was* on the map, not what's there now. Always call `getMapState()` at fire time, not at render time.
- **Reserved IDs** (`__anything`) are used by the library for system layers. Don't collide.
- **Bundle size** — `@deck.gl/json` registers every deck.gl class. For prod, register only the layers you use, not the entire `* as carto`.
