# Recipe — load a CARTO Builder map

The shortest possible CARTO + deck.gl app: load a Builder map by ID, render. Works for both vanilla and React. Use this whenever the user has a `cartoMapId`.

See [`fetchmap.md`](../fetchmap.md) for the full reference.

## Vanilla TS

```ts
import { Deck } from '@deck.gl/core';
import { fetchMap } from '@carto/api-client';
import maplibregl from 'maplibre-gl';

const mapInfo = await fetchMap({
  cartoMapId: import.meta.env.VITE_MAP_ID,
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL,
  accessToken: import.meta.env.VITE_API_ACCESS_TOKEN,   // omit for fully public maps
});

const map = new maplibregl.Map({
  container: 'map',
  style: mapInfo.mapStyle.styleUrl,
  interactive: false,
  ...mapInfo.initialViewState,
});

new Deck({
  canvas: 'deck-canvas',
  initialViewState: mapInfo.initialViewState,
  controller: true,
  layers: mapInfo.layers,
  getTooltip: mapInfo.getTooltip,
  onViewStateChange: ({ viewState }) => {
    const { longitude, latitude, zoom, pitch, bearing } = viewState;
    map.jumpTo({ center: [longitude, latitude], zoom, pitch, bearing });
  },
});
```

That's the whole app. ~25 lines.

## React

```tsx
import { useEffect, useState } from 'react';
import DeckGL from '@deck.gl/react';
import { fetchMap, type FetchMapResult } from '@carto/api-client';
import { Map as MaplibreMap } from 'react-map-gl/maplibre';

export default function App() {
  const [info, setInfo] = useState<FetchMapResult | null>(null);

  useEffect(() => {
    fetchMap({
      cartoMapId: import.meta.env.VITE_MAP_ID,
      apiBaseUrl: import.meta.env.VITE_API_BASE_URL,
      accessToken: import.meta.env.VITE_API_ACCESS_TOKEN,
    }).then(setInfo);
  }, []);

  if (!info) return <div className="loading">Loading map…</div>;

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

## `.env`

```bash
VITE_API_BASE_URL=https://gcp-us-east1.api.carto.com
VITE_API_ACCESS_TOKEN=YOUR_SCOPED_API_TOKEN
VITE_MAP_ID=00000000-0000-0000-0000-000000000000
```

For a fully public map, omit `VITE_API_ACCESS_TOKEN` and the `accessToken` arg.

## Auto-refresh

For a live dashboard:

```ts
fetchMap({
  cartoMapId,
  accessToken,
  apiBaseUrl,
  autoRefresh: 60,
  onNewData: (info) => deck.setProps({ layers: info.layers }),
});
```

## Patching layers

`mapInfo.layers` is an array of regular deck.gl layers. You can clone/patch any of them:

```ts
const layers = mapInfo.layers.map((l) =>
  l.id === 'optional-layer' ? l.clone({ visible: false }) : l
);
```

Or add your own layers on top:

```ts
new Deck({
  layers: [
    ...mapInfo.layers,
    new ScatterplotLayer({ id: 'overlay', data: myData, /* ... */ }),
  ],
  /* ... */
});
```

## Auth

Use whatever auth flow the app uses. For private apps, `accessToken` comes from `getTokenSilently()` (see [`auth-private-oauth.md`](../auth-private-oauth.md)).

## Gotchas

- **Wrong region in `apiBaseUrl`** → 404. The map's region must match the URL (`carto auth status` for the user's tenant).
- **Public-but-token-required** is a thing. A map can be share-link-public but still require a (limited-scope) token for the underlying data. Try without a token; if it fails, use a public token.
- **`mapInfo.layers` includes hidden layers.** If the user toggled visibility in Builder, those layers are still in the array with `props.visible: false`. Filter or honor as you prefer.
- **No layer customization API.** The Builder map is the source of truth — to change styling, change it in Builder. For programmatic styling, hand-roll instead.
