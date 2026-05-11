# Design & Theming

Two modes — infer from the prompt, never ask:

1. **Default** — no style cues → Meridian-inspired baseline (clean, professional, CARTO-native).
2. **Custom** — any style cue ("futuristic", "corporate green", a named DS like "shadcn") → build the described aesthetic from scratch. Still apply the UX principles below.

---

## UX layout principles (always apply)

- **Map is the hero.** Full viewport. Chrome (panels, widgets, legend) floats on top or docks to a side.
- **Panel discipline.** One primary side panel, collapsible. Don't scatter controls across all edges.
- **Progressive disclosure.** Most important stat/widget first; secondaries behind scroll or accordion.
- **Responsive.** Panels collapse on narrow viewports. No fixed pixel widths for layout containers.
- **Touch targets ≥ 44 px.** Space between interactive elements ≥ 8px.
- **WCAG AA contrast.** 4.5:1 body text, 3:1 large text and UI components.
- **Loading states.** Skeleton or spinner for async data. Never blank.
- **Tooltip restraint.** 3–5 fields max on hover; format numbers and dates.

---

## Default theme — Meridian tokens

Derived from CARTO's Meridian design system (`@carto/react-ui` theme), scaled down for map dashboards. The scaffolds' `style.css` already wire these as CSS custom properties.

### Colors

| Token | Hex | Usage |
|---|---|---|
| `--color-primary` | `#036FE2` | Buttons, active states, links |
| `--color-primary-light` | `#358BE7` | Hover |
| `--color-primary-dark` | `#024D9E` | Pressed, dark accents |
| `--color-primary-bg` | `#EAF2FC` | Selected rows, badges |
| `--color-secondary` | `#47DB99` | Success, secondary actions |
| `--color-error` | `#C1300B` | Errors, destructive |
| `--color-warning` | `#F29E02` | Warnings |
| `--color-bg` | `#F8F9F9` | Page background |
| `--color-surface` | `#FFFFFF` | Cards, panels |
| `--color-text` | `#2C3032` | Primary text (warm near-black) |
| `--color-text-secondary` | `#6F777C` | Muted text |
| `--color-border` | `#E1E3E4` | Dividers, input borders |
| `--color-nav` | `#162945` | App bar (Navy Blue) |

### Typography

Font: `Inter`, system-ui fallback. Mono: `Overpass Mono`. Weights: 400 regular, 500 medium, 600 bold (Meridian uses 600, not 700).

| Element | Size | Weight |
|---|---|---|
| Page title | 24px | 600 |
| Section heading | 18px | 500 |
| Body | 14px | 400 |
| Caption / labels | 12px | 400 |
| Button | 13px | 500 |

### Spacing, shape, shadow

- **Grid:** 8px base. Use multiples: 4 · 8 · 12 · 16 · 24 · 32 · 48.
- **Radius:** 4px (inputs) · 8px (buttons, panels) · 12px (modals).
- **Shadows** (warm, keyed to `#2C3032`): `sm` for cards, `md` for floating panels/legends, `lg` for tooltips/dropdowns.
- **Transitions:** 150ms color/opacity, 200ms transform.

### Data viz colors

Use CARTOColors palettes for `colorBins`/`colorCategories` — they're perceptually calibrated and colorblind-safe. Don't reuse UI palette for data encoding.

- Sequential: `Sunset`, `Teal`, `BluGrn`, `Emrld`
- Diverging: `TealRose`, `Temps`, `Geyser`
- Categorical: `Bold`, `Vivid`, `Safe`

### Dark basemap adjustment

When using DARK_MATTER, flip surface tokens: `--color-bg: #1A1D21`, `--color-surface: #242830`, `--color-text: #E1E3E4`, `--color-border: #3A3F47`. Use a `.theme-dark` class or `prefers-color-scheme`.

---

## Custom theme mode

Drop Meridian tokens. Build a coherent visual language from the user's description:

1. Extract: font mood, color mood, shape language, effects.
2. Define 5–7 CSS custom properties (primary, bg, surface, text, accent, error).
3. Pick a matching type stack.
4. Set radius/shadow/spacing to fit the aesthetic.
5. Apply consistently — one visual language per app.

CARTOColors for data viz still apply regardless of theme (perceptual quality > aesthetic matching).

**Examples** — "futuristic AI terminal": mono font, dark bg, neon accent, sharp corners, glow effects. "Corporate green": clean sans, forest green primary, warm grays, 4px radius. "Use shadcn/ui": follow that DS's component conventions, still use CARTOColors for maps.

---

## Implementation rules

- **CSS custom properties** on `:root`. Works with plain CSS, Tailwind, CSS-in-JS.
- **No CSS framework or component library** unless the user asks.
- **Google Fonts** with `display=swap`. Inter for default; match the aesthetic for custom.
- **Don't animate layout shifts.** Only animate color, opacity, transform.
- **Never invent logos or brand marks.** Inventing a logo means making one up — generating SVG, hand-drawing a wordmark in CSS, fetching an unverified URL, or substituting a similar-looking brand. Only render a logo when one of these is true: (a) the user supplied a verified PNG / JPG / SVG asset, (b) the asset already exists in the repo, or (c) the user pointed to an official source you can verify (e.g. the brand's own press kit). If none of those apply, ask the user — offer to use a plain text wordmark in the app's font, or omit the logo entirely. This applies to CARTO's own logo, customer logos, partner logos, and third-party brand marks (AWS, GCP, etc.) equally. A text wordmark styled with the theme is almost always an acceptable fallback and should be your default suggestion when asking.
