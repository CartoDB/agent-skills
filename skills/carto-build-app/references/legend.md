# Legend

deck.gl doesn't ship a legend component. You build one from the same domain + palette you passed to `colorBins` / `colorCategories`.

## The pattern

1. Name the palette + domain once.
2. Pass them to the layer's color accessor.
3. Pass them to a manual legend renderer.

```ts
import { colorBins } from '@deck.gl/carto';

const REVENUE_DOMAIN = [10_000, 50_000, 100_000, 500_000];
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

## Resolving a palette to colors

`@deck.gl/carto` exposes the CARTOColors palettes as named constants. To turn `'Sunset'` into actual RGB stops:

```ts
import { CARTOColors } from '@deck.gl/carto';
const colors = CARTOColors.Sunset;           // [[r,g,b], [r,g,b], ...]
```

Number of bins = `domain.length + 1` for `colorBins` (values below first edge → first color, between edge i and i+1 → color i+1, above last edge → last color). The palette must have ≥ that many stops; CARTOColors palettes ship in lengths 2–7 — if the palette has fewer than you need, deck.gl interpolates.

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
import { CARTOColors } from '@deck.gl/carto';

function renderLegend({ title, domain, palette }) {
  const colors = CARTOColors[palette];
  const labels = [
    `< ${fmt(domain[0])}`,
    ...domain.slice(0, -1).map((d, i) => `${fmt(d)} – ${fmt(domain[i + 1])}`),
    `≥ ${fmt(domain.at(-1))}`,
  ];
  const root = document.getElementById('legend')!;
  root.innerHTML =
    `<h4>${title}</h4>` +
    labels.map((label, i) => {
      const [r, g, b] = colors[Math.min(i, colors.length - 1)];
      return `<div class="legend-row">
        <span class="legend-swatch" style="background:rgb(${r},${g},${b})"></span>
        <span>${label}</span>
      </div>`;
    }).join('');
}

const fmt = (n: number) => n.toLocaleString();
```

## Manual legend (React)

```tsx
import { CARTOColors } from '@deck.gl/carto';

function Legend({ title, domain, palette }: {
  title: string; domain: number[]; palette: keyof typeof CARTOColors;
}) {
  const colors = CARTOColors[palette];
  const labels = [
    `< ${domain[0].toLocaleString()}`,
    ...domain.slice(0, -1).map((d, i) => `${d.toLocaleString()} – ${domain[i + 1].toLocaleString()}`),
    `≥ ${domain.at(-1)!.toLocaleString()}`,
  ];
  return (
    <div className="legend">
      <h4>{title}</h4>
      {labels.map((label, i) => {
        const [r, g, b] = colors[Math.min(i, colors.length - 1)];
        return (
          <div key={i} className="legend-row">
            <span className="legend-swatch" style={{ background: `rgb(${r},${g},${b})` }} />
            <span>{label}</span>
          </div>
        );
      })}
    </div>
  );
}
```

## Categorical legend (`colorCategories`)

```ts
import { colorCategories, CARTOColors } from '@deck.gl/carto';

const CAT_DOMAIN = ['retail', 'wholesale', 'online'];
const CAT_PALETTE = 'Bold';

new VectorTileLayer({
  /* ... */
  getFillColor: colorCategories({ attr: 'category', domain: CAT_DOMAIN, colors: CAT_PALETTE }),
});

// Legend rows: one per domain entry
const colors = CARTOColors[CAT_PALETTE];
CAT_DOMAIN.forEach((cat, i) => render(cat, colors[i]));
```

## Continuous gradient (raster, heatmap)

For continuous data, render a CSS gradient bar:

```ts
const stops = CARTOColors.Magenta;
const bg = `linear-gradient(to right, ${stops.map(([r,g,b]) => `rgb(${r},${g},${b})`).join(',')})`;
legendBar.style.background = bg;
```

Add min/max labels at either end. For non-linear scales, render explicit tick marks at the same break points the layer uses.

## Loading the legend from a Builder map

`fetchMap` returns layers *plus* `legendSettings` for each layer. If you're using [`fetchmap.md`](fetchmap.md), iterate `mapInfo.layers` and read `legendSettings` directly — don't hand-roll. See the `fetchmap` example in [deck.gl-examples](https://github.com/CartoDB/deck.gl-examples/tree/master/fetchmap).

## Gotchas

- **Bin count off-by-one** — `colorBins` with `domain = [a, b, c]` makes 4 buckets, not 3. Make sure the legend has 4 rows.
- **Palette length < bin count** — deck.gl interpolates colors; the legend should sample those interpolated stops, not just `CARTOColors[palette]`. For up to 7 bins, use a 7-stop palette and skip the math.
- **Hard-coded palette names break refactors.** Define `DOMAIN` and `PALETTE` constants at module scope, share between layer + legend.
- **`getFillColor` callbacks lose closure when serialized.** If you ever pass layers through `Deck.toJSON()` for an agentic flow, use the `colorBins`/`colorCategories` helpers (they serialize cleanly) — never inline `(d) => ...` arrow functions.
