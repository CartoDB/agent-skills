# Basemap + view state

CARTO ships **basemap style URLs** in `@deck.gl/carto`. MapLibre renders them; deck.gl draws on top. The two stay synced through a single `viewState` source of truth.

## CARTO basemaps

```ts
import { BASEMAP } from '@deck.gl/carto';

BASEMAP.POSITRON           // light, default for analytical maps
BASEMAP.DARK_MATTER        // dark
BASEMAP.VOYAGER            // mid-tone, more landmark labels
BASEMAP.POSITRON_NOLABELS  // light, no place names — good when your layer carries labels
BASEMAP.DARK_MATTER_NOLABELS
BASEMAP.VOYAGER_NOLABELS
```

Each constant is a MapLibre style URL pointing at CARTO's CDN. Pass directly to MapLibre:

```ts
new maplibregl.Map({ container: 'map', style: BASEMAP.POSITRON, /* ... */ });
```

## Custom basemaps

If the user needs a custom MapLibre style (corporate branding, satellite, OS data), pass any valid style URL or style spec object:

```ts
new maplibregl.Map({
  container: 'map',
  style: 'https://tiles.example.com/style.json',
});
```

Or use Google Maps / Amazon Location as basemaps — see the `google-basemap` and `amazon-locations` examples in [deck.gl-examples](https://github.com/CartoDB/deck.gl-examples). These don't go through MapLibre at all — they replace it with the provider's SDK.

## View state

`viewState` is the camera. Always start with:

```ts
const INITIAL_VIEW_STATE = {
  longitude: -73.97,
  latitude: 40.75,
  zoom: 12,
  pitch: 0,        // 0 = top-down, up to 60 for tilted
  bearing: 0,      // rotation in degrees
};
```

For 3D extrusions (`H3HexagonLayer`, `getElevation` on polygons), pitch ~45 makes them visible.

## Sync pattern (vanilla / Angular / Vue)

deck.gl owns the controller; MapLibre is a passive follower:

```ts
const deck = new Deck({
  canvas: 'deck-canvas',
  initialViewState: INITIAL_VIEW_STATE,
  controller: true,
  layers: [/* ... */],
  onViewStateChange: ({ viewState }) => {
    const { longitude, latitude, zoom, pitch, bearing } = viewState;
    map.jumpTo({ center: [longitude, latitude], zoom, pitch, bearing });
  },
});
```

Key points:
- MapLibre is created with `interactive: false` — drag/zoom comes from deck.gl.
- `jumpTo` is the right method (not `flyTo`) — instant, no animation, no jitter.
- Don't call `setProps({ viewState })` on the deck instance from the MapLibre side. One-way data flow only.

## Sync pattern (React)

`@deck.gl/react` + `react-map-gl/maplibre` handle this for free:

```tsx
<DeckGL initialViewState={INITIAL_VIEW_STATE} controller layers={layers}>
  <MaplibreMap mapStyle={BASEMAP.POSITRON} />
</DeckGL>
```

The MapLibre child reads `viewState` from deck.gl's context. No manual sync.

For controlled view state (e.g. "fly to selected feature"):

```tsx skip
const [viewState, setViewState] = useState(INITIAL_VIEW_STATE);
<DeckGL viewState={viewState} onViewStateChange={({ viewState }) => setViewState(viewState)} ...>
```

## Tooltip

Most apps want a hover tooltip:

```ts
new Deck({
  /* ... */
  getTooltip: ({ object }) => object && {
    html: `<b>${object.properties.name}</b><br>${object.properties.value}`,
    style: { background: '#fff', padding: '6px 8px', borderRadius: '4px' },
  },
});
```

In React: `<DeckGL getTooltip={...}>`.

## Globe view

For world-scale data:

```ts
import { _GlobeView as GlobeView } from '@deck.gl/core';

new Deck({ views: new GlobeView(), /* ... */ });
```

MapLibre doesn't render globes. For globe view, drop the basemap or use a tiled satellite layer. See the `globe-view` example.

## Gotchas

- **`BASEMAP` constants change occasionally.** Pin `@deck.gl/carto` to a known-working version per app.
- **Don't wrap MapLibre with its own controls** (`scrollZoom`, `dragPan`) — they fight with deck.gl's controller. `interactive: false` disables all of them at once.
- **High-DPI canvases** — the canvas dimensions are set by the browser; don't override `width`/`height` attributes in HTML, only via CSS.
- **Map labels above your layer.** MapLibre labels render below the deck.gl canvas by default. To put labels *on top*, use the `MapboxOverlay` interleaved pattern (see deck.gl docs) — out of scope for v1 of this skill.
