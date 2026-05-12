# Storymap — guided tour with camera transitions

A **storymap** is an ordered sequence of *steps*, each pinning a camera position, a set of visible layers, and (optionally) narrative text or a legend. The user advances step-by-step; the camera flies between them.

This is a state pattern, not a separate scaffold. Pick the [React scaffold](scaffold-react.md), wire your [data sources](data-sources.md) and [layers](layers.md), then layer this on top.

## When to use

- Prompt cues: "story map", "scrollytelling", "guided tour", "narrative map", "scenes / chapters / slides", "fly through".
- Anything that says "first show X, then zoom into Y, then tilt to show 3D".

If the user wants free exploration, this isn't it — that's a [vanilla map with widgets](recipes/vanilla-points-with-widgets.md).

## Minimal pattern

Three pieces: a `STEPS` config, a current-index in state, and a controlled `viewState` with a transition.

### `src/storymap/steps.ts`

```ts
export type Step = {
  id: string;
  title: string;
  description?: string;
  view: {
    longitude: number;
    latitude: number;
    zoom: number;
    pitch?: number;
    bearing?: number;
  };
  layers: string[];   // layer IDs visible in this step
};

export const STEPS: Step[] = [
  {
    id: 'overview',
    title: 'The whole region',
    description: 'Population by H3 cell across the state.',
    view: { longitude: -99.5, latitude: 31.6, zoom: 6, pitch: 0, bearing: 0 },
    layers: ['boundary', 'pop-h3'],
  },
  {
    id: 'city',
    title: 'Zoom to Houston',
    description: 'Same data, urban scale.',
    view: { longitude: -95.37, latitude: 29.76, zoom: 11, pitch: 30, bearing: 20 },
    layers: ['boundary', 'pop-h3', 'roads'],
  },
  {
    id: 'streetlevel',
    title: 'Street-level 3D',
    view: { longitude: -95.366, latitude: 29.758, zoom: 16, pitch: 60, bearing: 45 },
    layers: ['buildings-3d'],
  },
];
```

### `src/storymap/Storymap.tsx`

```tsx
import { useEffect, useMemo, useState } from 'react';
import DeckGL from '@deck.gl/react';
import { FlyToInterpolator } from '@deck.gl/core';
import { BASEMAP } from '@deck.gl/carto';
import { Map as MaplibreMap } from 'react-map-gl/maplibre';
import { STEPS } from './steps';

export default function Storymap({ allLayers }: { allLayers: any[] }) {
  const [stepIdx, setStepIdx] = useState(0);
  const step = STEPS[stepIdx];

  const [viewState, setViewState] = useState<any>({ ...STEPS[0].view });

  useEffect(() => {
    setViewState((vs: any) => ({
      ...vs,
      ...step.view,
      transitionDuration: 2500,
      transitionInterpolator: new FlyToInterpolator({ curve: 1.1 }),
    }));
  }, [stepIdx]);

  const layers = useMemo(
    () => allLayers.map((l) => l.clone({ visible: step.layers.includes(l.id) })),
    [allLayers, stepIdx],
  );

  const next = () => setStepIdx((i) => Math.min(i + 1, STEPS.length - 1));
  const prev = () => setStepIdx((i) => Math.max(i - 1, 0));

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'ArrowRight') next();
      if (e.key === 'ArrowLeft') prev();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  return (
    <div className="storymap">
      <DeckGL
        viewState={viewState}
        onViewStateChange={({ viewState: v }: any) => setViewState(v)}
        controller
        layers={layers}
      >
        <MaplibreMap mapStyle={BASEMAP.POSITRON} />
      </DeckGL>
      <aside className="panel">
        <h2>{step.title}</h2>
        {step.description && <p>{step.description}</p>}
        <div className="nav">
          <button onClick={prev} disabled={stepIdx === 0}>← Prev</button>
          <span>{stepIdx + 1} / {STEPS.length}</span>
          <button onClick={next} disabled={stepIdx === STEPS.length - 1}>Next →</button>
        </div>
      </aside>
    </div>
  );
}
```

The map owner constructs *all* layers once (with their data sources memoized) and passes them to `<Storymap>`. The component clones each layer per step with `visible: true|false` — tile caches stay warm across transitions, no re-fetch on step change.

## Camera transitions

Two interpolators ship with deck.gl:

- **`FlyToInterpolator`** — great-circle arc with a zoom-out-then-in curve. Default for any geographic move. `curve: 1.1` is the working default; lower (0.8–1.0) for tighter arcs, higher (1.5–2.0) for more dramatic zoom-out.
- **`LinearInterpolator`** — straight lerp on whichever fields you list. Right when you only change `bearing` or `pitch` (orbit / tilt-in-place) and don't want the camera to back out.

```tsx
import { FlyToInterpolator, LinearInterpolator } from '@deck.gl/core';

const flyTo = new FlyToInterpolator({ curve: 1.1, speed: 1.2 });
const orbit  = new LinearInterpolator(['bearing']);
```

Duration: **1500–3000 ms** for chapter-to-chapter; **5000+ ms** for cinematic single-shot reveals; **<1000 ms** feels jumpy for a storymap (use the [recipe scale](recipes/vanilla-points-with-widgets.md) for snappy interactions instead).

For easing, deck.gl accepts any `(t: number) => number`. The two reference repos use `Easing.Quadratic.InOut` from `@tweenjs/tween.js` — install only if you want named easings; otherwise a one-liner works:

```ts
const easeInOutQuad = (t: number) => (t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2);
```

## Layer choreography

**Default — visibility toggle.** `layer.clone({ visible })` per step. Sources stay live, tiles stay cached, no flicker.

**Cross-fade.** When you want the old layer to fade out as the new one fades in, drive `opacity` from a step-derived value and remember `updateTriggers`:

```tsx
const opacityFor = (id: string) => (step.layers.includes(id) ? 1 : 0);

new VectorTileLayer({
  id: 'pop-h3',
  data: dataSource,
  opacity: opacityFor('pop-h3'),
  transitions: { opacity: 800 },        // deck.gl built-in attribute transition
  updateTriggers: { opacity: [stepIdx] },
});
```

`transitions` is deck.gl's per-attribute animation hook — much cheaper than swapping layer instances.

**Don't recreate sources per step.** Each `vectorTableSource(...)` call is a new fetch key. If `useMemo` dependencies include `stepIdx`, you re-fetch on every chapter change. Memoize sources on the data identity (table name + auth token), not on the step.

## 3D and Tile3DLayer steps

Pitching to 40°–70° brings 3D buildings, terrain, and Google Photorealistic 3D Tiles to life. The same `FlyToInterpolator` handles `pitch` and `bearing`; just include them in the step's `view`.

```ts
import { Tile3DLayer } from '@deck.gl/geo-layers';

new Tile3DLayer({
  id: 'buildings-3d',
  data: 'https://tile.googleapis.com/v1/3dtiles/root.json?key=...',
  loadOptions: { '3d-tiles': { loadGLTF: true } },
});
```

For "fly through the city" stories, set `pitch: 60`, increase `transitionDuration` to ~4000 ms, and consider `FlyToInterpolator({ curve: 1.4 })` for more drama. The [tiles3d-demo](https://github.com/CartoDB/tiles3d-demo) reference repo is the worked example.

## Navigation UX — three options

**1. Prev/Next + arrow keys** (default). What both reference repos do. Built into the snippet above. Lowest-effort, works everywhere.

**2. Chapter dots** for non-linear jumps:

```tsx
<div className="dots">
  {STEPS.map((s, i) => (
    <button
      key={s.id}
      className={i === stepIdx ? 'on' : ''}
      onClick={() => setStepIdx(i)}
      aria-label={s.title}
    />
  ))}
</div>
```

**3. Scroll-driven (scrollytelling)** — only if explicitly requested. One scroll-section per step, observed with `IntersectionObserver`:

```tsx
useEffect(() => {
  const io = new IntersectionObserver(
    (entries) => {
      const hit = entries.find((e) => e.isIntersecting);
      if (hit) setStepIdx(Number((hit.target as HTMLElement).dataset.idx));
    },
    { threshold: 0.6 },
  );
  document.querySelectorAll('[data-idx]').forEach((el) => io.observe(el));
  return () => io.disconnect();
}, []);
```

Heavier code, more edge cases (mid-transition scroll, mobile inertia). Don't reach for it unless the prompt says "scroll" or names a tool like *Mapbox storytelling* / *scrollama*.

## Optional flourishes

- **Per-step legend.** Reuse [`legend.md`](legend.md); render the legend matching `step.layers[0]`'s color domain.
- **Per-step query.** Pass step-specific `queryParameters` via [`inputs-and-parameters.md`](inputs-and-parameters.md) — useful when "step 2 = same map, filtered to 2024".
- **Orbit on arrival.** `onTransitionEnd` → start a `requestAnimationFrame` loop that increments `bearing` by ~0.1°/frame. Stop when the user advances or interacts.
- **Deep links.** Sync `stepIdx` to `location.hash` (`#step=2`) so a chapter is shareable.

## Prior art

- [CartoDB/cloud-next](https://github.com/CartoDB/cloud-next) — Google Maps + 2.5D tilt + tween-based camera. React + Material UI. Same `slides.js` + React-context pattern.
- [CartoDB/tiles3d-demo](https://github.com/CartoDB/tiles3d-demo) — deck.gl-native + `Tile3DLayer` + a custom `FlyToInterpolator` subclass. Closest to the snippet above.

Both are several deck.gl versions old (8.x). The *pattern* survives version drift; the file layouts won't — copy the idea, not the imports.

## Gotchas

- **`transitionInterpolator` must be a fresh instance** on every `setViewState` call that triggers a transition. deck.gl mutates it internally; reusing one breaks the next transition.
- **Don't memoize sources on `stepIdx`.** Memoize on table name + access token. Sources are the cache key — change them and you re-fetch every chapter.
- **Mixing controlled `viewState` with user pan/zoom**: in `onViewStateChange` you must spread the incoming `viewState` *without* the transition props, or the next `setStepIdx` won't transition (deck.gl thinks the transition is still mid-flight).
- **`IntersectionObserver` mid-transition.** Throttle the callback (≥250 ms) or you'll fire `setStepIdx` while the previous transition is still running. Result: stutter.
- **Reserved layer IDs.** If you later add the [agentic chat panel](agentic-variant.md), don't reuse the `__`-prefixed IDs the library uses for system layers.
