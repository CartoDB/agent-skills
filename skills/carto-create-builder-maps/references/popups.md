# Map interactions — tooltip popup and info panel

`popupSettings` configures **two distinct interaction surfaces** that both live under the same `keplerMapConfig.config.popupSettings.layers[<layerId>]` block:

- **Tooltip popup** — a floating, transient bubble that renders on `hover` (follows the cursor) or `click` (anchors to the clicked feature). Styles: `light`, `lightWithHiFirst`, `dark`, `darkWithHiFirst`. Compact; small fields list. The everyday read-out.
- **Info panel** — a docked side panel that slides in on `click` only (style: `panel`). Persistent until the user dismisses it; significantly more screen real estate than the tooltip; suitable for long descriptions, multi-image cards, or rich HTML. **`panel` is rejected on `hover`** — the panel would jitter in and out as the cursor moves; Builder's UI only exposes the option under the click event for this reason.

Both surfaces share the same `fields[]` schema and the same `templateMode`-based custom HTML rendering — the choice between them is purely UX (transient bubble vs. docked panel) and which event triggers them (hover vs. click).

> **Author popups by default — they are the only per-feature read-out.** Widgets answer *aggregate* questions (viewport stats, global counts, distributions); popups answer *"what is this one feature?"*. Maps emitted by the CLI commonly ship without `popupSettings.layers[<id>]` populated, leaving viewers unable to retrieve attributes by hovering or clicking — a gap real Builder users almost never have because the UI nudges them into it. **Treat a missing popup as a bug**, not an omission, unless the dataset truly has nothing worth surfacing per row, or the layer is `heatmapTile` (see *"Layer-type support"* below — heatmapTile does not support interactions). Default authoring: at least `hover` with 2–3 identifying fields (name, key metric) per layer; promote to `click` with `style: "panel"` (info panel) when there are more than 5 fields, rich descriptions, or HTML cards.

> **Layer-type support — `heatmapTile` is the one exception.** Builder hard-disables the popup card on `heatmapTile` (tooltip in the layer panel: *"Interactions are not supported for Heatmap layer type."*). The layer is not pickable at runtime, so any `popupSettings.layers[<heatmapId>]` you ship is silently ignored — the popup never fires. **Tier-1 rejects this combination.** All other allowed layer types (`tileset`, `h3`, `quadbin`, `clusterTile`, `raster`) support popups; `clusterTile` works but picks resolve to the quadbin cell, not a row, so author popup fields with `spatialIndexAggregation` (see field options below).

> **Hard cap: hover = 5 fields per layer, click = unlimited.** Builder's UI enforces `MAX_HOVER_FIELDS = 5` — the "add field" button disappears at 5. Tier-1 in the CLI rejects configurations with 6+ hover fields pre-flight. Move overflow fields to `click` (no cap) when you need to show more context. Authored a hover popup with 6+ fields and wondering why `maps create` fails? This is why.

> ⚠️ **Anti-pattern: `items[]` with `{ field, label }`.** The canonical shape is `fields[]` with `{ name, customName }`. The popup schema accepts unknown keys (`additionalProperties: true`), so `items[]` / `field` / `label` passes structural validation but Builder's renderer **only reads `fields[]` / `name`**. Result on map open: empty popup; on some layer shapes the Builder app shell crashes with HTTP 500. The CLI's Tier-1 now rejects this shape, but the rejection happens *after* an authoring round trip — and the rename is mechanical: `items` → `fields`, `field` → `name`, `label` → `customName`. **Don't author the popup block from memory.** Run `carto maps schema popupSettings --json` and copy the shape from there.

Popups are keyed by **layer id**, not dataset id. Each layer can have independent `hover` and `click` settings.

```jsonc
"popupSettings": {
  "layers": {
    "my-layer-id": {
      "enabled": true,
      "hover": {
        "style": "light",                // floating tooltip on hover
        "fields": [
          { "name": "name" },
          { "name": "alcoholic_bev_euro", "format": "$,.2f", "customName": "Spend (€)" },
          { "name": "total_cap", "format": ".3~s", "customName": "Total capacity",
            "spatialIndexAggregation": "sum" }
        ],
        "templateMode": false
      },
      "click": {
        "style": "panel",                // docked info panel on click
        "fields": [ { "name": "name" }, { "name": "description" } ]
      }
    }
  }
}
```

**Style values** (from `carto maps schema enums`):

| Style | Surface | Available on |
|---|---|---|
| `light` | Tooltip popup (light theme) | hover, click |
| `lightWithHiFirst` | Tooltip popup (light, headline first) | hover, click |
| `dark` | Tooltip popup (dark theme) | hover, click |
| `darkWithHiFirst` | Tooltip popup (dark, headline first) | hover, click |
| `panel` | **Info panel** (docked side panel) | **click only** |
| `none` | Disabled | hover, click |

**Field options:** `name` (dataset column, required), `customName` (display override), `isExpression: true` if `name` is SQL not a column, `format` (d3-format spec — `"$,.2f"` currency, `",.0f"` integer, `".3~s"` SI-short, `"%"` percent, `"%Y-%m-%d"` dates), `spatialIndexAggregation` (**required** on h3 / quadbin / clusterTile layers — see [`layers.md`](layers.md) *"h3 / quadbin aggregation restrictions"* for the long-form alias rule and column-type gating; same enum as layer aggregations).

> **Keyed by layer id, not dataset id.** `popupSettings.layers["foo"]` applies to the *layer* whose top-level `id` is `"foo"` — two layers over the same dataset can have independent tooltips and info panels.

## HTML popup template — `templateMode: true`

`templateMode: true` + a `template` string switches the popup (tooltip OR info panel — the rendering surface is independent) from a **structured field list** to a **full HTML render surface**. This is much more capable than just "customise the field shape" — the template is the entire DOM tree the popup paints, and arbitrary nested markup + inline CSS works.

`templateEdited: true` marks human-modified templates — preserve on edits so Builder doesn't offer to re-generate.

### What works

- **Arbitrary nested HTML** — `<div>`, `<span>`, `<a>`, `<img>`, lists, headings.
- **Inline CSS via `style="…"`** — solid `background`, `box-shadow`, `border-radius`, `flex`, custom fonts. Anything you can put in an inline style attribute. **Avoid `linear-gradient` / `radial-gradient` backgrounds** — they read as decoration over the data and clash with Builder's flat surfaces; pick a single solid colour (often a per-row column like `{{header_color}}`, see recipe below) instead.
- **`{{column}}` substitution works ANYWHERE in the template, including inside attribute values** — this is dumb text replacement, not a typed expression engine. Useful patterns:
  - `style="width: {{rating}}%;"` — drives a CSS bar from a column value.
  - `src="https://chart.example/svg?data=[{{mon}},{{tue}},{{wed}}]"` — chart-image URL composed from columns.
  - `href="mailto:{{email}}"` — mailto link from an email column.
- **Inline images** — `<img src="data:image/svg+xml;base64,…">` (data URI) is the default for icons / small graphics: no fetch, no CSP allowlist needed, contained in the bundle. External `<img src="https://…">` works but fetches per hover (slow on rate-limited hosts, requires the host in the public viewer's CSP allowlist for public maps, and exposes the substituted URL — including any `{{column}}` PII — to the image server). Reserve external URLs for one-off rich content where the host is reliable and allowlisted.
- **Aggregated columns on h3 / quadbin / clusterTile layers** — reference `{{column_aggregation}}`, not the bare column. A `colorField: "net_worth"` with `spatialIndexAggregation: "average"` becomes `{{net_worth_average}}` in the template. Bare `{{net_worth}}` renders empty on aggregated layers. (`heatmapTile` does not support popups at all — see *"Layer-type support"* at the top of this file.)

### What is sanitised out

The renderer strips anything that could execute or escape the popup sandbox:

- `<script>` tags — removed entirely.
- Event-handler attributes — `onclick`, `onerror`, `onload`, etc. — stripped.
- `<iframe>`, `<object>`, `<embed>`, `<style>` blocks — removed.
- `javascript:` URLs in `href` / `src` — neutralised.

### What the templating language doesn't have

- **No conditionals.** `{{#if …}}` / ternaries are not supported. Per-row variation has to be **baked into the source SQL** as a derived column, then read into the template like any other field:

  ```sql
  SELECT
    *,
    CASE WHEN category = 'hospital' THEN '#3969AC'
         WHEN category = 'school'   THEN '#F2B701'
         ELSE                            '#7F3C8D' END AS header_color
  FROM facilities
  ```

  Then in the template: `style="background: {{header_color}};"`.

- **No loops.** Can't iterate over a JSON column.
- **No number formatting / locale / currency helpers.** Pre-format upstream in the SQL (`FORMAT('%.2f', revenue) AS revenue_fmt`) or at minimum cast.
- **No null fallbacks.** A NULL column substitutes as the literal string `null` — coalesce in the source SQL.
- **No arithmetic.** `{{a}} + {{b}}` literally renders as `<value-a> + <value-b>`. Compute upstream.
- **No CSS pseudo-classes / pseudo-elements.** `:hover`, `::before`, `::after`, `@media` queries don't work — the popup has no document stylesheet for them to attach to. Inline CSS only.
- **No CSS classes referenced from external stylesheets.** `class="my-card"` is preserved on the element but the rule doesn't exist in the popup's scope. Use inline `style="…"` instead.

### CSS pseudo-classes / hover / media queries don't work

If the design needs `:hover` colour change, animated bars, or responsive layout, those features aren't reachable from inside the popup template. The popup is rendered in an isolated container with inline-style-only painting; nothing in the host document stylesheet leaks in. Design accordingly — favour static layouts driven entirely by inline `style="…"` attributes.

### Leave headroom for Builder's close ✕

Builder paints its own close ✕ on top of the popup template — a fixed, absolutely-positioned icon in the top-right corner of the rendering surface. The template has no way to move, hide, or restyle it (the popup container, its padding, and the ✕ are outside the sanitised template DOM you control). On a custom HTML template that fills its outer container edge-to-edge, the ✕ overlaps whatever you place in the top-right: title text, a value, a tag, a status badge.

**Authoring rule:** on `panel` and `click` tooltip templates, reserve roughly **28–32 px of right padding** on the outermost container, or keep the top-right ~32 × 32 px region empty of content (no critical text or interactive elements there). Hover tooltips render with no close ✕ — the rule applies to click-anchored surfaces only. Headroom on the outer `<div>` is the simplest fix and is reflected in the recipe below.

### Concrete recipe — facility card with solid header + rating bar + mailto

Source SQL pre-bakes the per-row colour:

```sql
SELECT
  *,
  CASE WHEN category = 'hospital' THEN '#3969AC'
       WHEN category = 'school'   THEN '#F2B701'
       ELSE                            '#7F3C8D' END AS header_color
FROM facilities
```

Layer `popupSettings.layers["facilities"].click`:

```jsonc
{
  "style": "panel",
  "templateMode": true,
  "templateEdited": true,
  "template": "<div style=\"font-family: -apple-system, system-ui, sans-serif; max-width: 320px; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.12);\">  <div style=\"background: {{header_color}}; color: #fff; padding: 12px 32px 12px 16px;\">    <div style=\"font-size: 11px; text-transform: uppercase; letter-spacing: 0.6px; opacity: 0.85;\">{{category}}</div>    <div style=\"font-size: 16px; font-weight: 600; margin-top: 2px;\">{{name}}</div>  </div>  <div style=\"padding: 12px 16px; color: #1d2733; font-size: 13px; line-height: 1.4;\">    <div style=\"margin-bottom: 8px;\"><strong>{{address}}</strong></div>    <div style=\"display: flex; align-items: center; gap: 8px; margin-bottom: 8px;\">      <span style=\"font-size: 11px; color: #6b7785; min-width: 48px;\">Rating</span>      <div style=\"flex: 1; background: #eef0f2; border-radius: 4px; height: 6px; overflow: hidden;\">        <div style=\"width: {{rating}}%; height: 100%; background: {{header_color}};\"></div>      </div>      <span style=\"font-size: 11px; color: #1d2733; min-width: 28px; text-align: right;\">{{rating}}%</span>    </div>    <a href=\"mailto:{{email}}\" style=\"color: {{header_color}}; text-decoration: none; font-weight: 500;\">Contact →</a>  </div></div>",
  "fields": [
    { "name": "name" },
    { "name": "category" },
    { "name": "address" },
    { "name": "rating" },
    { "name": "email" },
    { "name": "header_color" }
  ]
}
```

Note the header band uses `padding: 12px 32px 12px 16px` — the extra 32 px of right padding keeps `{{name}}` from sliding under Builder's close ✕. The header itself is a solid `{{header_color}}` fill (no gradient), so the card reads as a single deliberate accent colour against the flat panel chrome.

Even with `templateMode: true`, every column referenced as `{{name}}` must still appear in `fields[]` — that's how the renderer knows to fetch them per feature.
