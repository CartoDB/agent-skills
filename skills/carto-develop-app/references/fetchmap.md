# `fetchMap` — load a CARTO Builder map

The fastest path to a working app **when the user already has a Builder map**. `fetchMap` from `@carto/api-client` returns the full map config — layers, basemap, sources, filters, legend settings — and you reconstruct it client-side via the deck.gl `LayerFactory`.

Use this when:
- The user names a `cartoMapId` or links to a Builder map.
- The user wants the app to mirror what they styled in Builder.
- You want the legend and popup configuration to come from the map rather than from hand-rolled constants.

For everything else, hand-roll with [`data-sources.md`](data-sources.md) + [`layers.md`](layers.md).

## Get the map ID

A Builder map URL looks like `https://{tenant}.app.carto.com/builder/{mapId}`. The trailing UUID is `cartoMapId`.

To find the ID: `carto maps list --json --mine` on the CLI, or `read_maps` (method `list`) over an attached MCP session.

## Public maps (no auth needed)

If the map is published as public:

```ts
import { fetchMap } from '@carto/api-client';

const mapInfo = await fetchMap({ cartoMapId: '00000000-0000-0000-0000-000000000000' });
```

`mapInfo` contains:
- `initialViewState` — center, zoom, pitch, bearing
- `basemap.props.style` — the basemap style, ready to hand to MapLibre
- `layers` — layer *descriptors* (`{ type, props, filters, scales }`), not deck.gl instances; `LayerFactory` turns each into a layer
- `popupSettings` — the popup config the author set in Builder

```ts
import { LayerFactory } from '@deck.gl/carto';

new Deck({
  canvas: 'deck-canvas',
  initialViewState: mapInfo.initialViewState,
  controller: true,
  layers: mapInfo.layers.map(LayerFactory),
});

new maplibregl.Map({
  container: 'map',
  style: mapInfo.basemap.props.style,
  interactive: false,
  ...mapInfo.initialViewState,
});
```

That's the whole app.

`@deck.gl/carto` also exports its own `fetchMap`, a thin wrapper that runs `LayerFactory` for you and hands back `layers` as deck.gl instances. Import from there instead when you don't need the descriptors.

## Private maps (auth required)

```ts
const mapInfo = await fetchMap({
  cartoMapId: '00000000-0000-0000-0000-000000000000',
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL,
  accessToken,
});
```

`accessToken` comes from whichever auth flow the app uses ([public token](auth-public-token.md) / [OAuth](auth-private-oauth.md) / [SSO](auth-private-sso.md)).

## React

```tsx
import { useEffect, useState } from 'react';
import DeckGL from '@deck.gl/react';
import { LayerFactory } from '@deck.gl/carto';
import { fetchMap, type FetchMapResult } from '@carto/api-client';
import { Map as MaplibreMap } from 'react-map-gl/maplibre';

export default function BuilderMap({ mapId, accessToken }: { mapId: string; accessToken: string }) {
  const [info, setInfo] = useState<FetchMapResult | null>(null);

  useEffect(() => {
    fetchMap({ cartoMapId: mapId, apiBaseUrl: import.meta.env.VITE_API_BASE_URL, accessToken })
      .then(setInfo);
  }, [mapId, accessToken]);

  if (!info) return <div>Loading map…</div>;

  return (
    <DeckGL
      initialViewState={info.initialViewState}
      controller
      layers={info.layers.map(LayerFactory)}
    >
      <MaplibreMap mapStyle={info.basemap.props.style} />
    </DeckGL>
  );
}
```

## Auto-refresh

`fetchMap` accepts an `autoRefresh` option (in seconds) — useful when underlying data updates frequently:

```ts
fetchMap({
  cartoMapId,
  accessToken,
  apiBaseUrl,
  autoRefresh: 60,             // re-fetch + rebuild layers every 60 s
  onNewData: (newInfo) => {
    deck.setProps({ layers: newInfo.layers.map(LayerFactory) });
  },
});
```

## Customizing the result

You don't have to use `mapInfo.layers` as-is — patch the descriptor's `props` before handing it to `LayerFactory`:

```ts
const customLayers = mapInfo.layers.map((d) =>
  d.props.id === 'stores'
    ? LayerFactory({ ...d, props: { ...d.props, getFillColor: [255, 0, 0] } })
    : LayerFactory(d)
);
```

Or filter:

```ts
const visibleLayers = mapInfo.layers
  .filter((d) => d.props.id !== 'optional-layer')
  .map(LayerFactory);
```

## Legend from `fetchMap`

Each descriptor carries the scales that drove its styling, at `mapInfo.layers[i].scales` — one entry per styled channel (`fillColor`, `lineColor`, `pointRadius`, …), each with `{ type, field, domain, range }`. That is the palette and the breaks; render as in [`legend.md`](legend.md) instead of hard-coding them. The author's legend *presentation* — which layers show, entry labels, sort order — is separate, at `mapInfo.legendSettings`, keyed by layer id.

## Gotchas

- **`fetchMap` is a one-shot fetch by default.** Layers won't update when the underlying warehouse data changes unless you set `autoRefresh` or re-call.
- **Custom Maps API URL with regional base** — `apiBaseUrl` must match the org that owns the map. Wrong region → 404.
- **`mapInfo.layers` includes ALL layers**, including hidden / optional ones. Check `descriptor.props.visible` if you want to honor Builder's visibility toggles.
- **No way to *write* a map.** `fetchMap` is read-only. Authoring lives in [`carto-create-builder-maps`](../../carto-create-builder-maps).
- **Large maps with many layers** — deck.gl creates a layer per Builder layer. If the map has 30 layers, all 30 spin up at once. Filter `mapInfo.layers` before passing to `Deck` if perf matters.
