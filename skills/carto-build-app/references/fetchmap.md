# `fetchMap` — load a CARTO Builder map

The fastest path to a working app **when the user already has a Builder map**. `fetchMap` from `@carto/api-client` returns the full map config — layers, basemap, sources, filters, legend settings — and you reconstruct it client-side via the deck.gl `LayerFactory`.

Use this when:
- The user names a `cartoMapId` or links to a Builder map.
- The user wants the app to mirror what they styled in Builder.
- You want legends and tooltips for free, without hand-rolling.

For everything else, hand-roll with [`data-sources.md`](data-sources.md) + [`layers.md`](layers.md).

## Get the map ID

A Builder map URL looks like `https://{tenant}.app.carto.com/builder/{mapId}`. The trailing UUID is `cartoMapId`.

To list maps from the CLI:

```bash
carto maps list --json --mine
```

## Public maps (no auth needed)

If the map is published as public:

```ts
import { fetchMap } from '@carto/api-client';

const mapInfo = await fetchMap({ cartoMapId: '00000000-0000-0000-0000-000000000000' });
```

`mapInfo` contains:
- `initialViewState` — center, zoom, pitch, bearing
- `mapStyle.styleUrl` — the basemap (resolves to a `BASEMAP.*` constant)
- `layers` — pre-built deck.gl layer instances, ready to drop into `Deck`
- `popupSettings` and `getTooltip` — tooltip config baked in

```ts
new Deck({
  canvas: 'deck-canvas',
  initialViewState: mapInfo.initialViewState,
  controller: true,
  layers: mapInfo.layers,
  getTooltip: mapInfo.getTooltip,
});

new maplibregl.Map({
  container: 'map',
  style: mapInfo.mapStyle.styleUrl,
  interactive: false,
  ...mapInfo.initialViewState,
});
```

That's the whole app.

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
      layers={info.layers}
      getTooltip={info.getTooltip}
    >
      <MaplibreMap mapStyle={info.mapStyle.styleUrl} />
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
    deck.setProps({ layers: newInfo.layers });
  },
});
```

## Customizing the result

You don't have to use `mapInfo.layers` as-is — they're regular deck.gl layers, so you can patch:

```ts
const customLayers = mapInfo.layers.map((layer) => {
  if (layer.id === 'stores') {
    return layer.clone({ getFillColor: [255, 0, 0] });
  }
  return layer;
});
```

Or filter:

```ts
const visibleLayers = mapInfo.layers.filter((l) => l.id !== 'optional-layer');
```

## Legend from `fetchMap`

`mapInfo.layers[i].props.legendSettings` carries title, palette, domain. Render the same way as [`legend.md`](legend.md), but read from the layer instead of hard-coding.

## Gotchas

- **`fetchMap` is a one-shot fetch by default.** Layers won't update when the underlying warehouse data changes unless you set `autoRefresh` or re-call.
- **Custom Maps API URL with regional base** — `apiBaseUrl` must match the org that owns the map. Wrong region → 404.
- **`mapInfo.layers` includes ALL layers**, including hidden / optional ones. Check `layer.props.visible` if you want to honor Builder's visibility toggles.
- **No way to *write* a map.** `fetchMap` is read-only. Authoring lives in `carto-create-builder-maps` (deferred).
- **Large maps with many layers** — deck.gl creates a layer per Builder layer. If the map has 30 layers, all 30 spin up at once. Filter `mapInfo.layers` before passing to `Deck` if perf matters.
