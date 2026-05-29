# Popup mapping — ArcGIS `popupInfo` → kepler `popupSettings`

ArcGIS Web Maps store popup configuration on `operationalLayers[].popupInfo`. CARTO Builder uses `keplerMapConfig.config.popupSettings.layers` — **a map keyed by layer id** (not dataset id), with one `{ enabled, hover, click }` entry per layer. Each event (`hover` / `click`) carries its own `{ style, fields, templateMode, template }` block, and each `fields[]` entry is `{ name, customName?, format, isExpression?, spatialIndexAggregation? }` where `format` is a **d3-format string** (`",.2f"`, `"$,.2f"`, `".3~s"`, `"%Y-%m-%d"`).

This file documents field-level translation, the click-only-by-default rule for migrated maps, media references, and Arcade-detection logic. The shape below mirrors what `carto maps schema popupsettings --json` returns; **always re-fetch with that command and let the live schema win** when this document and the schema disagree.

## ArcGIS `popupInfo` shape (relevant fields)

```json
{
  "title": "{name}",
  "description": null,
  "fieldInfos": [
    { "fieldName": "name",       "label": "Store",      "visible": true,  "format": null },
    { "fieldName": "population", "label": "Population", "visible": true,  "format": { "places": 0, "digitSeparator": true } },
    { "fieldName": "opened",     "label": "Opened",     "visible": true,  "format": { "dateFormat": "longMonthDayYear" } },
    { "fieldName": "url",        "label": "Website",    "visible": true,  "format": null, "stringFieldOption": "richtext" },
    { "fieldName": "objectid",   "label": "OID",        "visible": false }
  ],
  "expressionInfos": [
    { "name": "expr1", "title": "Density", "expression": "$feature.population / $feature.area" }
  ],
  "mediaInfos": [
    { "type": "image", "value": { "sourceURL": "$feature.photo_url" } }
  ]
}
```

## Translated kepler `popupSettings`

```json
{
  "popupSettings": {
    "coordinates": false,
    "layers": {
      "<layer-id>": {
        "enabled": true,
        "hover": { "style": "none", "fields": [], "templateMode": false },
        "click": {
          "style": "light",
          "fields": [
            { "name": "name",       "customName": "Store" },
            { "name": "population", "customName": "Population", "format": ",.0f" },
            { "name": "opened",     "customName": "Opened",     "format": "%B %-d, %Y" },
            { "name": "url",        "customName": "Website" },
            { "name": "_density",   "customName": "Density",    "format": ",.2f", "isExpression": true }
          ],
          "templateMode": false
        }
      }
    }
  }
}
```

The keyed entry is **the layer's own id** (the `id` on `keplerMapConfig.config.visState.layers[]`), NOT the dataset `$ref`. Mixing those up emits a popup that never fires.

## Translation rules

1. **`fieldInfos[].visible: false`** → omit from `click.fields`. Hidden fields don't appear in CARTO popups; there's no "include but hidden" mode in Builder.
2. **`fieldInfos[].format`** → d3-format string per the format-mapping table below; attach as `format` on the field entry.
3. **`fieldInfos[].label`** → `customName` on the field entry (when label differs from `fieldName`).
4. **Click-only by default — no hover popup.** ArcGIS Web Maps don't have a hover-popup concept; the popup appears when the user clicks a feature. **Faithfully reproduce this**: emit all visible fields as `click.fields` and emit `hover` with `style: "none"` and an empty `fields: []`. Do NOT apply Builder's "5-field hover cap" or otherwise split fields into hover vs. click — that's a fresh-authoring rule for `carto-create-builder-maps`, not a migration rule. Adding hover behavior the user didn't configure changes the map's interaction model from what they had in ArcGIS.
5. **`expressionInfos[]`** → translate via [`arcade-translation.md`](arcade-translation.md). Translatable expressions become a derived field in the layer's source SQL (synthetic name `_<slug-of-title>`); add the field to `click.fields` like any other column, with `isExpression: true` so Builder treats it as a SQL expression rather than a base column. Untranslatable expressions are recorded as `Notes: arcade-skipped: expressionInfos[<name>]: <expression-fragment>` on the manifest entry and dropped from popups.
6. **`mediaInfos[]`** — see "Media" below.
7. **`title` and `description`** — see "Title and description" below.

The single exception to rule 4: if the source `popupInfo` has an explicit hover configuration (rare — some custom ArcGIS apps configure hover popups via `applicationProperties` or layer-specific settings), preserve it. Detect by looking for `popupInfo.popupElements[].popupShowsAt: "hover"` or equivalent; absent that signal, default to click-only.

## Field format mapping

Kepler's `format` is a [d3-format](https://d3js.org/d3-format) (numbers / currency / SI) or [d3-time-format](https://d3js.org/d3-time-format) (dates) **string**, not an object. Translation:

| ArcGIS `format` | kepler `format` (string) |
|---|---|
| `{ "places": N, "digitSeparator": true }` | `",.Nf"` (comma thousands sep, N decimals — substitute the actual N) |
| `{ "places": N, "digitSeparator": false }` | `".Nf"` |
| `{ "places": 0, "digitSeparator": true }` | `",.0f"` (integer with thousands sep) |
| (currency-typed field, e.g. `revenue`, `price`) | `"$,.2f"` (heuristic — apply when the column name suggests money AND format has `digitSeparator: true`) |
| `{ "dateFormat": "shortDate" }` | `"%-m/%-d/%Y"` |
| `{ "dateFormat": "longDate" }` | `"%A, %B %-d, %Y"` |
| `{ "dateFormat": "longMonthDayYear" }` | `"%B %-d, %Y"` |
| `{ "dateFormat": "shortMonthDayYear" }` | `"%b %-d, %Y"` |
| `{ "dateFormat": "shortDateShortTime" }` | `"%-m/%-d/%Y %-I:%M %p"` |
| `{ "dateFormat": "shortDateLongTime" }` | `"%-m/%-d/%Y %-I:%M:%S %p"` |
| `null` (string field, no format) | omit `format` (kepler renders as plain string) |
| `null` with `stringFieldOption: "richtext"` | no field-list equivalent — promote the popup to `templateMode: true` with a `template` HTML string (see `carto-create-builder-maps/references/popups.md`), or drop the formatting and record `Notes: rich-text-collapsed: <field>` |
| (string field that is a URL) | omit `format` — kepler's field-list popup renders bare URLs as text. For clickable links, switch to `templateMode: true` with `<a href="{{field}}">{{field}}</a>` and record `Notes: link-via-template: <field>` |

**URL field detection** — usable signal when deciding whether to promote a popup to template mode: field name matches `_url` / `_link` / `URL` / `link` (case-insensitive), OR the first non-null value in the migrated table starts with `http://` or `https://`. Skip this on fast-path migrations; the user can convert to template mode later if they want clickable links.

## Title and description

The kepler field-list popup (`templateMode: false`) **does not have a separate title or description field** — there's `style`, `fields`, and the rendering surface is the field list itself. Use one of these strategies depending on the source:

- **Plain title (e.g. `"retail_stores"`)** — drop it. The field list speaks for itself once `customName`s are set; layering a non-templated headline on top adds nothing.
- **Templated title (`"{name}"` / `"{name} ({region})"`)** — promote the popup to `templateMode: true` with a `template` HTML string that renders the headline, e.g. `<h3>{{name}} ({{region}})</h3>` followed by an unordered list of remaining fields. Convert ArcGIS single-brace substitutions to double-brace Mustache:

  ```python
  import re
  template_body = re.sub(r"\{(\w+)\}", r"{{\1}}", arcgis_title_or_description)
  ```

  Then attach `template: "<h3>...</h3><ul>{{#fields}}<li><b>{{label}}:</b> {{value}}</li>{{/fields}}</ul>"` (or just hand-roll the field rows — see `carto-create-builder-maps/references/popups.md` for the full HTML template recipe).
- **Arcade-driven title** — route through `arcade-translation.md`. Plain `$feature.X` translates to `{{X}}` in the template. Per-row math + simple aggregations become a derived SQL field referenced by name. Anything more complex → record `Notes: arcade-skipped: title: <fragment>` and either drop the title or fall back to a plain field reference.

The source `description` follows the same logic — drop if plain, promote to `templateMode: true` if it contains substitutions or Arcade, record `Notes: arcade-skipped:` for any fragment that doesn't translate.

## Media (`mediaInfos`)

ArcGIS popups can embed images and charts. Builder's field-list popup doesn't render images natively — they require `templateMode: true` with `<img>` tags in the `template` HTML.

| ArcGIS `type` | Translation |
|---|---|
| `image` with static `sourceURL` | Promote popup to `templateMode: true`; embed `<img src="<url>" />` in the `template` HTML. Record `Notes: image-via-template: static URL`. |
| `image` with `$feature.X` URL | Promote popup to `templateMode: true`; embed `<img src="{{X}}" />` in the `template` HTML. Mustache substitutes `{{X}}` per feature. Record `Notes: image-via-template: <field>`. |
| `barchart` / `linechart` / `piechart` / `columnchart` | Builder doesn't render inline popup charts → skip with `Notes: media-chart-skipped: <chart-type>`. Suggest in the chat summary that the user add a Builder `histogram` or `pie` widget at the map level if the chart was important. |

Multiple `image` mediaInfos: emit one `<img>` tag per image in the `template` HTML, in source order. The popup template is a single string — concatenate all images plus a field list (or a Mustache iteration over fields) into one HTML body.

## Arcade detection

A field's content or a `popupInfo` field is "Arcade" if it contains:

- `$feature.` (attribute reference)
- `$layer`, `$map`, `$feature` (without subscript)
- A function-call form: `Sum(`, `Max(`, `Min(`, `Average(`, `Mean(`, `Count(`, `IIf(`, `When(`, `Iif(`, `If(`, `FeatureSetByName(`, `Filter(`, etc.
- The `expressionInfos[]` array existing on the layer (every entry there is Arcade by definition)

Plain `{name}`-style brace substitutions are NOT Arcade — they're ArcGIS's simpler attribute-substitution and translate to `{{name}}` directly without going through the Arcade translator.

## Empty popups — omit `popupSettings` entirely

If **no** source layer has a populated `popupInfo`, **do not emit `keplerMapConfig.config.visState.popupSettings` at all** — the key is absent from `visState` entirely. Not `{}`, not `{layers: {}}`, not `{layers: []}`, not `{coordinates: false, layers: {}}`. All those empty-shape forms have been observed crashing Builder's loader on initial load. Verified against a manually-created Builder map with no popups — Builder UI doesn't write the key either.

This **deliberately overrides** `carto-create-builder-maps`'s "Popups — emit by default" guidance, which is a fresh-authoring rule (the agent is helping the user start a new map and end users can't otherwise inspect features). For migration, the user's prior decision is the source of truth.

When **some** source layers have popups and others don't, emit `popupSettings.layers` with entries ONLY for the layers that have source `popupInfo`. Don't pre-fill entries with empty `click.fields` for popup-less layers — leave them absent from the keyed map. The absence is the "no popup on this layer" signal.

If the user later wants per-feature popups on a migrated layer, they can add them in Builder via the layer's popup panel — Builder's default-popup behavior kicks in when they click "add popup" on a layer that doesn't have one configured.

## When in doubt

- Builder rejects the popup config? `carto maps schema popupsettings --json` and align fragment shape; the schema wins over this document.
- A `mediaInfos[]` references a chart with an unfamiliar shape? Skip with `Notes:` and surface in Phase 7's summary.
- Field with `null` format and ambiguous type (string `"42"` vs. number)? Trust the warehouse type from `carto connections describe <conn> <fqn>` over the popup config.
- Source title contains nested braces (`"{store.name}"`)? Trim to top-level field reference (`{{store_name}}` if the migrated field is flattened, or `Notes: nested-field-reference-collapsed: <title>`).
