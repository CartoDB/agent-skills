# Legend

deck.gl doesn't ship a legend component. You build one from the same domain + palette you passed to `colorBins` / `colorCategories`.

`@deck.gl/carto`'s `colorBins` / `colorCategories` accept a palette **name** (`'Sunset'`, `'Bold'`, …). To resolve that name to actual color stops for the legend, install the `cartocolor` package — that's how every example in [CartoDB/deck.gl-examples](https://github.com/CartoDB/deck.gl-examples) does it. Pattern lifted from the `carto-colors` example: `import * as cartoColors from 'cartocolor'; const stops = cartoColors[palette][7]`.

## Install

```bash
npm install cartocolor
```

`cartocolor` returns palettes as **hex strings**, indexed by stop count: `cartoColors['Sunset'][7]` is `string[]` of length 7.

## The pattern

1. Name the palette + domain once.
2. Pass them to the layer's color accessor.
3. Pass them to a manual legend renderer.

```ts
import { colorBins } from '@deck.gl/carto';

const REVENUE_DOMAIN = [10_000, 50_000, 100_000, 500_000];   // 4 edges → 5 buckets
const REVENUE_PALETTE = 'Sunset';

const fillColor = colorBins({
  attr: 'revenue',
  domain: REVENUE_DOMAIN,
  colors: REVENUE_PALETTE,
});

new VectorTileLayer({ id: 'stores', data: dataSource, getFillColor: fillColor });

renderLegend({
  title: 'Revenue (USD)',
  domain: REVENUE_DOMAIN,
  palette: REVENUE_PALETTE,
});
```

## Bucket count

`colorBins` with `domain.length = N` produces `N + 1` buckets:
- below first edge → bucket 0
- between edge `i` and `i+1` → bucket `i+1`
- above last edge → bucket `N`

So `[10_000, 50_000, 100_000, 500_000]` (4 edges) needs **5 swatches** in the legend. `cartocolor` palettes ship in lengths 2–7. Pick the smallest stop count ≥ your bucket count.

## Manual legend (vanilla)

```html
<div id="legend" class="legend"></div>
```

```css
.legend { position: absolute; right: 16px; bottom: 16px; background: #fff; padding: 12px; border-radius: 6px; font: 12px system-ui; box-shadow: 0 2px 8px rgba(0,0,0,.1); }
.legend h4 { margin: 0 0 8px; font-size: 12px; }
.legend-row { display: flex; align-items: center; gap: 8px; margin: 2px 0; }
.legend-swatch { width: 14px; height: 14px; border-radius: 2px; }
```

```ts
import * as cartoColors from 'cartocolor';

function renderLegend({ title, domain, palette }: {
  title: string;
  domain: number[];
  palette: string;
}) {
  const buckets = domain.length + 1;
  const colors: string[] = cartoColors[palette][buckets];
  const labels = [
    `< ${fmt(domain[0])}`,
    ...domain.slice(0, -1).map((d, i) => `${fmt(d)} – ${fmt(domain[i + 1])}`),
    `≥ ${fmt(domain.at(-1)!)}`,
  ];
  const root = document.getElementById('legend')!;
  root.innerHTML =
    `<h4>${title}</h4>` +
    labels.map((label, i) => `
      <div class="legend-row">
        <span class="legend-swatch" style="background:${colors[i]}"></span>
        <span>${label}</span>
      </div>
    `).join('');
}

const fmt = (n: number) => n.toLocaleString();
```

## Manual legend (React)

```tsx
import * as cartoColors from 'cartocolor';

function Legend({ title, domain, palette }: {
  title: string;
  domain: number[];
  palette: string;
}) {
  const buckets = domain.length + 1;
  const colors = cartoColors[palette][buckets] as string[];
  const labels = [
    `< ${domain[0].toLocaleString()}`,
    ...domain.slice(0, -1).map((d, i) => `${d.toLocaleString()} – ${domain[i + 1].toLocaleString()}`),
    `≥ ${domain.at(-1)!.toLocaleString()}`,
  ];
  return (
    <div className="legend">
      <h4>{title}</h4>
      {labels.map((label, i) => (
        <div key={i} className="legend-row">
          <span className="legend-swatch" style={{ background: colors[i] }} />
          <span>{label}</span>
        </div>
      ))}
    </div>
  );
}
```

## Categorical legend (`colorCategories`)

```ts
import { colorCategories } from '@deck.gl/carto';
import * as cartoColors from 'cartocolor';

const CAT_DOMAIN = ['retail', 'wholesale', 'online'];
const CAT_PALETTE = 'Bold';

new VectorTileLayer({
  /* ... */
  getFillColor: colorCategories({ attr: 'category', domain: CAT_DOMAIN, colors: CAT_PALETTE }),
});

const colors = cartoColors[CAT_PALETTE][CAT_DOMAIN.length] as string[];
CAT_DOMAIN.forEach((cat, i) => render(cat, colors[i]));
```

## Continuous gradient (raster, heatmap)

For continuous data, render a CSS gradient bar:

```ts
import * as cartoColors from 'cartocolor';

const stops = cartoColors['Magenta'][7] as string[];
const bg = `linear-gradient(to right, ${stops.join(',')})`;
legendBar.style.background = bg;
```

Add min/max labels at either end. For non-linear scales, render explicit tick marks at the same break points the layer uses.

## TypeScript types

`cartocolor` ships without bundled types. Add a one-liner to `vite-env.d.ts` (or any `.d.ts`) if you hit a type error:

```ts
declare module 'cartocolor';
```

That's exactly what the upstream React/Vue/Angular examples do.

## Loading the legend from a Builder map

`fetchMap` returns layers *plus* `legendSettings` for each layer. If you're using [`fetchmap.md`](fetchmap.md), iterate `mapInfo.layers` and read `legendSettings` directly — don't hand-roll. See the `fetchmap` example in [deck.gl-examples](https://github.com/CartoDB/deck.gl-examples/tree/master/fetchmap).

## Gotchas

- **Bucket count off-by-one** — `colorBins` with `domain = [a, b, c]` (3 edges) makes **4** buckets, not 3. Use `domain.length + 1` for `cartocolor[palette][n]`.
- **Palette stop count** — `cartocolor[palette]` is keyed by stop count (`[2]`, `[3]`, …, `[7]`). Pick the smallest one `≥ bucket count`. If you need >7 buckets, redesign the bins (or pre-interpolate yourself) — most readable legends top out at 7 anyway.
- **Hard-coded palette names break refactors.** Define `DOMAIN` and `PALETTE` constants at module scope, share between layer + legend.
- **`getFillColor` callbacks lose closure when serialized.** If you ever pass layers through `Deck.toJSON()` for an agentic flow, use the `colorBins`/`colorCategories` helpers (they serialize cleanly) — never inline `(d) => ...` arrow functions.
- **`cartocolor` is not re-exported by `@deck.gl/carto`.** Install it directly. There is no `import { CARTOColors } from '@deck.gl/carto'` — that doesn't exist.
