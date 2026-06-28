# CARTO map configuration examples — full bundles ready for `carto maps create`

> Companion reference for the `carto-maps` skill. Each example is a complete map configuration validated end-to-end against a live CARTO organization and ready to pipe into `carto maps create`. Replace `<connection-id>` with a real one from `carto connections list`. For when to use what, see the parent `SKILL.md`; for cartographic decisions, see the sibling `cartography.md` in this `references/` directory.

## Index

- [§A — Minimal map (one table, one layer)](#a-minimal-working-map-one-table-one-layer)
- [§B — H3 aggregation map (from a query)](#b-h3-aggregation-map-from-a-query)
- [§C — Parameterized query (SQL parameters)](#c-parameterized-query-sql-parameters--let-users-filter-live)
- [§D — Widgets gallery — one of each kind](#d-widgets-gallery--one-of-each-kind)
- [§E — Split-map mode (side-by-side comparison)](#e-split-map-mode-side-by-side-comparison)
- [§F — Layer groups (collapsible folders)](#f-layer-groups-collapsible-folders)

---

## A. Minimal working map (one table, one layer)

The smallest configuration that renders cleanly. Point tileset, default DarkMint palette, no widgets / popups / agent.

```json
{
  "title": "NYC Collisions",
  "datasets": [{
    "$ref": "collisions",
    "type": "table",
    "source": "carto-demo-data.demo_tables.nyc_collisions",
    "connectionId": "<connection-id>",
    "geoColumn": "geom",
    "columns": ["geom"],
    "format": "tilejson",
    "label": "NYC Collisions"
  }],
  "keplerMapConfig": {
    "version": "v1",
    "config": {
      "mapState": {"latitude": 40.7128, "longitude": -74.006, "zoom": 11, "pitch": 0, "bearing": 0},
      "basemapConfig": {"styleId": "positron"},
      "mapStyle": {"styleType": "positron"},
      "visState": {
        "layers": [{
          "id": "collisions",
          "type": "tileset",
          "config": {
            "dataId": "$ref:collisions",
            "label": "Collisions",
            "color": [241, 92, 23],
            "isVisible": true,
            "hidden": false,
            "columns": {},
            "textLabel": [{"size":12,"color":[44,48,50],"field":null,"anchor":"start","offset":[0,0],"alignment":"center","outlineColor":[255,255,255]}],
            "visConfig": {
              "filled": true, "stroked": false, "opacity": 0.8,
              "radius": 4, "radiusRange": [0,50], "thickness": 1,
              "sizeRange": [0,10], "heightRange": [0,500], "elevationScale": 5,
              "colorRange": {"name":"DarkMint","type":"sequential","category":"CARTO","colors":["#d2fbd4","#a5dbc2","#7bbcb0","#559c9e","#3a7c89","#235d72","#123f5a"]}
            }
          },
          "visualChannels": {"colorField":null,"colorScale":"quantize","sizeField":null,"sizeScale":"linear","radiusField":null,"radiusScale":"linear","heightField":null,"heightScale":"linear","strokeColorField":null,"strokeColorScale":"quantize"}
        }],
        "filters": []
      }
    }
  }
}
```

## B. H3 aggregation map (from a query)

A `query`-typed dataset binned to H3 with `aggregationExp` summing two metrics per cell.

```json
{
  "title": "Power infrastructure density",
  "datasets": [{
    "$ref": "infra",
    "type": "query",
    "source": "SELECT h3_id as h3, SUM(generators) AS gens_sum, MAX(temp_c) AS temp_max FROM `proj.ds.infra_h3` GROUP BY h3_id",
    "connectionId": "<connection-id>",
    "geoColumn": "h3:h3",
    "format": "tilejson",
    "aggregationExp": "sum(gens_sum) as gens_sum,max(temp_max) as temp_max",
    "aggregationResLevel": 4,
    "label": "Infra (H3)"
  }],
  "keplerMapConfig": {
    "version": "v1",
    "config": {
      "mapState": {"latitude": 39.5, "longitude": -98.5, "zoom": 4, "pitch": 0, "bearing": 0},
      "basemapConfig": {"styleId": "positron"},
      "mapStyle": {"styleType": "positron"},
      "visState": {
        "layers": [{
          "id": "h3-infra",
          "type": "h3",
          "config": {
            "dataId": "$ref:infra",
            "label": "Generators per cell",
            "color": [90, 24, 70],
            "isVisible": true, "hidden": false, "columns": {},
            "textLabel": [{"size":12,"color":[44,48,50],"field":null,"anchor":"start","offset":[0,0],"alignment":"center","outlineColor":[255,255,255]}],
            "visConfig": {
              "filled": true, "stroked": true, "opacity": 0.8,
              "colorRange": {"name":"Global Warming","type":"sequential","category":"Uber","colors":["#5A1846","#900C3F","#C70039","#E3611C","#F1920E","#FFC300"]},
              "colorAggregation": "average", "strokeColor": [0,0,0], "strokeOpacity": 0.8
            }
          },
          "visualChannels": {"colorField":null,"colorScale":"quantize","sizeField":null,"heightField":null,"radiusField":null,"strokeColorField":null}
        }],
        "filters": []
      }
    }
  }
}
```

## C. Parameterized query (SQL parameters) — let users filter live

Two examples: a single DateRange parameter, then a multi-parameter map (Category + DateRange) with a timeseries widget. Author with the `{{paramName}}` shape — the CLI auto-derives `queryTemplate`, the provider-native `source`, and `queryParameters` from the connection's `provider_id`.

**C.1 — single DateRange parameter:**

```json
{
  "title": "NYC collisions — filter by date",
  "datasets": [{
    "$ref": "col",
    "type": "query",
    "source": "SELECT crash_datetime, number_of_persons_injured, geom FROM `carto-demo-data.demo_tables.nyc_collisions` WHERE crash_datetime >= {{date_from}} AND crash_datetime <= {{date_to}}",
    "connectionId": "<connection-id>",
    "geoColumn": "geom",
    "columns": ["crash_datetime", "number_of_persons_injured", "geom"],
    "format": "tilejson",
    "label": "Collisions"
  }],
  "keplerMapConfig": {
    "version": "v1",
    "config": {
      "mapState": {"latitude": 40.7128, "longitude": -74.006, "zoom": 11, "pitch": 0, "bearing": 0},
      "basemapConfig": {"styleId": "positron"},
      "mapStyle": {"styleType": "positron"},
      "mapSettings": {"sqlParameterControls": true},
      "visState": {
        "layers": [{
          "id": "col",
          "type": "tileset",
          "config": {
            "dataId": "$ref:col",
            "label": "Collisions",
            "color": [241, 92, 23],
            "isVisible": true, "hidden": false, "columns": {},
            "textLabel": [{"size":12,"color":[44,48,50],"field":null,"anchor":"start","offset":[0,0],"alignment":"center","outlineColor":[255,255,255]}],
            "visConfig": {"filled":true,"stroked":false,"opacity":0.8,"radius":4,"radiusRange":[0,50],"thickness":1,"sizeRange":[0,10],"heightRange":[0,500],"elevationScale":5,"colorRange":{"name":"Global Warming","type":"sequential","category":"Uber","colors":["#5A1846","#900C3F","#C70039","#E3611C","#F1920E","#FFC300"]}}
          },
          "visualChannels": {"colorField":null,"colorScale":"quantize","sizeField":null,"sizeScale":"linear","radiusField":null,"radiusScale":"linear","heightField":null,"heightScale":"linear","strokeColorField":null,"strokeColorScale":"quantize"}
        }],
        "filters": []
      },
      "sqlParameters": [{
        "id": "dr1",
        "name": "Date",
        "type": "DateRange",
        "start": {"value":"2020-01-01","sqlName":"date_from"},
        "end":   {"value":"2020-12-31","sqlName":"date_to"},
        "dataSources": [{"id":"$ref:col","name":"Collisions"}]
      }]
    }
  }
}
```

The `$ref:col` in `sqlParameters[].dataSources[].id` is resolved by the CLI to the real dataset UUID at create time, same as `dataId` in layers.

**C.2 — Category + DateRange + timeseries widget:**

```json
{
  "title": "311 Calls — filter by agency",
  "datasets": [{
    "$ref": "nyc311",
    "type": "query",
    "source": "SELECT created_date, agency, geom FROM `proj.ds.nyc_311` WHERE agency IN {{agency}} AND created_date >= {{date_from}} AND created_date <= {{date_to}}",
    "connectionId": "<connection-id>",
    "geoColumn": "geom",
    "columns": ["created_date","agency","geom"],
    "format": "tilejson",
    "label": "311 Calls"
  }],
  "keplerMapConfig": {
    "version": "v1",
    "config": {
      "mapState": {"latitude": 40.7128, "longitude": -74.006, "zoom": 11},
      "basemapConfig": {"styleId": "dark-matter"},
      "mapStyle": {"styleType": "dark-matter"},
      "mapSettings": {"sqlParameterControls": true},
      "visState": {"layers": [], "filters": []},
      "sqlParameters": [
        {"id": "p1", "name": "Agency", "type": "Category",
         "values": ["NYPD","HPD","DSNY","DOT","DEP"],
         "item": {"value": ["NYPD"], "sqlName": "agency"},
         "dataSources": [{"id": "$ref:nyc311", "name": "311 Calls"}]},
        {"id": "p2", "name": "Date", "type": "DateRange",
         "start": {"value":"2022-01-01","sqlName":"date_from"},
         "end":   {"value":"2022-03-31","sqlName":"date_to"},
         "dataSources": [{"id": "$ref:nyc311", "name": "311 Calls"}]}
      ],
      "widgets": [
        {"id":"w1","type":"timeseries","title":"Calls over time","column":"created_date",
         "operation":"count","stepSize":"day","chartType":"line","dataSource":"$ref:nyc311","isValid":true}
      ]
    }
  }
}
```

## D. Widgets gallery — one of each kind

All seven widget kinds in one map (formula × 2, histogram, category, pie, timeseries, range). Validated live: renders with real numbers populated.

```json
{
  "title": "NYC collisions — widgets gallery",
  "datasets": [{
    "$ref": "col",
    "type": "query",
    "source": "SELECT crash_datetime, number_of_persons_injured, contributing_factor_vehicle_1, vehicle_type_code_1, geom FROM `carto-demo-data.demo_tables.nyc_collisions` WHERE crash_datetime >= DATETIME '2018-01-01' AND crash_datetime <= DATETIME '2018-12-31'",
    "connectionId": "<connection-id>",
    "geoColumn": "geom",
    "columns": ["crash_datetime","number_of_persons_injured","contributing_factor_vehicle_1","vehicle_type_code_1","geom"],
    "format": "tilejson",
    "label": "Collisions 2018"
  }],
  "keplerMapConfig": {
    "version": "v1",
    "config": {
      "mapState": {"latitude":40.7128,"longitude":-74.006,"zoom":11,"pitch":0,"bearing":0},
      "basemapConfig": {"styleId":"positron"},
      "mapStyle": {"styleType":"positron"},
      "visState": {
        "layers": [{ "id":"col","type":"tileset",
          "config": {
            "dataId":"$ref:col","label":"Collisions","color":[241,92,23],
            "isVisible":true,"hidden":false,"columns":{},
            "textLabel":[{"size":12,"color":[44,48,50],"field":null,"anchor":"start","offset":[0,0],"alignment":"center","outlineColor":[255,255,255]}],
            "visConfig":{"filled":true,"stroked":false,"opacity":0.8,"radius":3,"radiusRange":[0,50],"thickness":1,"sizeRange":[0,10],"heightRange":[0,500],"elevationScale":5,"colorRange":{"name":"Global Warming","type":"sequential","category":"Uber","colors":["#5A1846","#900C3F","#C70039","#E3611C","#F1920E","#FFC300"]}}
          },
          "visualChannels":{"colorField":null,"colorScale":"quantize","sizeField":null,"sizeScale":"linear","radiusField":null,"radiusScale":"linear","heightField":null,"heightScale":"linear","strokeColorField":null,"strokeColorScale":"quantize"}
        }],
        "filters": []
      },
      "widgets": [
        // Right-side panel widgets (rendered in the right rail, top-to-bottom in array order):
        // headline metrics
        { "id":"w1","type":"formula","title":"Total incidents","column":"","operation":"count","formatter":"DECIMAL_SHORT_COMMA","dataSource":"$ref:col","global":false,"isValid":true },
        { "id":"w2","type":"formula","title":"Total injured","column":"number_of_persons_injured","operation":"sum","formatter":"DECIMAL_SHORT_COMMA","dataSource":"$ref:col","global":false,"isValid":true },
        // categorical breakdowns
        { "id":"w4","type":"category","title":"Vehicle type","column":"vehicle_type_code_1","operation":"count","dataSource":"$ref:col","operationColumn":"vehicle_type_code_1","global":false,"isValid":true },
        { "id":"w5","type":"pie","title":"Contributing factor","column":"contributing_factor_vehicle_1","operation":"count","dataSource":"$ref:col","operationColumn":"contributing_factor_vehicle_1","global":false,"isValid":true },
        // distribution / filter
        { "id":"w3","type":"histogram","title":"Injuries distribution","column":"number_of_persons_injured","operation":"count","buckets":20,"formatter":"DECIMAL_SHORT_COMMA","xAxisFormatter":"DECIMAL_SHORT_COMMA","dataSource":"$ref:col","global":false,"isValid":true },
        { "id":"w7","type":"range","title":"Injuries range","column":"number_of_persons_injured","operation":"count","dataSource":"$ref:col","global":true,"isValid":true },
        // Bottom-of-map surface (rendered below the map view, NOT in the right panel — array position
        // doesn't affect on-screen position for these kinds, but keep them last by convention):
        { "id":"w6","type":"timeseries","title":"Over time","column":"crash_datetime","operation":"count","stepSize":"month","chartType":"line","dataSource":"$ref:col","operationColumn":"crash_datetime","global":false,"isValid":true,"collapsible":true,"autoCollapse":true,"showControls":false }
      ]
    }
  }
}
```

## E. Split-map mode (side-by-side comparison)

A two-layer map in **split view** — left side shows 2020 collisions, right side shows 2024. Same dataset, two `query`-typed sub-selections wired to two layers, with `splitMaps` toggling visibility per side. See `references/configuration-shape.md` *§ Split-map mode* for the validation rules.

```json
{
  "title": "NYC Collisions: 2020 vs 2024",
  "datasets": [
    {
      "$ref": "col-2020",
      "type": "query",
      "source": "SELECT geom FROM `carto-demo-data.demo_tables.nyc_collisions` WHERE EXTRACT(YEAR FROM crash_datetime) = 2020",
      "connectionId": "<connection-id>",
      "geoColumn": "geom",
      "columns": ["geom"],
      "format": "tilejson",
      "label": "Collisions 2020"
    },
    {
      "$ref": "col-2024",
      "type": "query",
      "source": "SELECT geom FROM `carto-demo-data.demo_tables.nyc_collisions` WHERE EXTRACT(YEAR FROM crash_datetime) = 2024",
      "connectionId": "<connection-id>",
      "geoColumn": "geom",
      "columns": ["geom"],
      "format": "tilejson",
      "label": "Collisions 2024"
    }
  ],
  "keplerMapConfig": {
    "version": "v1",
    "config": {
      "mapState": {
        "latitude": 40.7128, "longitude": -74.006, "zoom": 11, "pitch": 0, "bearing": 0,
        "isSplit": true
      },
      "basemapConfig": {"styleId": "positron"},
      "mapStyle": {"styleType": "positron"},
      "visState": {
        "layers": [
          {
            "id": "L_2020", "type": "tileset",
            "config": {
              "dataId": "$ref:col-2020", "label": "2020",
              "color": [25, 118, 210], "isVisible": true, "hidden": false, "columns": {},
              "textLabel": [{"size":12,"color":[44,48,50],"field":null,"anchor":"start","offset":[0,0],"alignment":"center","outlineColor":[255,255,255]}],
              "visConfig": {"filled": true, "stroked": false, "opacity": 0.8, "radius": 4, "radiusRange": [0,50], "thickness": 1}
            },
            "visualChannels": {"colorField":null,"colorScale":"quantize","sizeField":null,"sizeScale":"linear","radiusField":null,"radiusScale":"linear"}
          },
          {
            "id": "L_2024", "type": "tileset",
            "config": {
              "dataId": "$ref:col-2024", "label": "2024",
              "color": [216, 27, 96], "isVisible": true, "hidden": false, "columns": {},
              "textLabel": [{"size":12,"color":[44,48,50],"field":null,"anchor":"start","offset":[0,0],"alignment":"center","outlineColor":[255,255,255]}],
              "visConfig": {"filled": true, "stroked": false, "opacity": 0.8, "radius": 4, "radiusRange": [0,50], "thickness": 1}
            },
            "visualChannels": {"colorField":null,"colorScale":"quantize","sizeField":null,"sizeScale":"linear","radiusField":null,"radiusScale":"linear"}
          }
        ],
        "filters": [],
        "splitMaps": [
          { "layers": { "L_2020": true,  "L_2024": false } },
          { "layers": { "L_2020": false, "L_2024": true  } }
        ]
      }
    }
  }
}
```

**What this demonstrates:**
- `splitMaps.length === 2` and `mapState.isSplit: true` agree (single source of truth = `splitMaps.length`; the boolean is its required mirror).
- Every layer id (`L_2020`, `L_2024`) appears as a key in **both** side entries — Builder hides the layer entirely on a side if its id is absent.
- The two layers use distinct hues (blue vs magenta) — split view is for comparison, so the two sides need readable separation, not a shared ramp.
- Both datasets share the same source table; the per-side filter happens in SQL upstream, not via spatial filters or post-fetch row filters.

---

## F. Layer groups (collapsible folders)

Three layers, two folded into a **"Reference"** group and one left ungrouped at the top level. Shows the `layerGrouping` array sitting at the config root (sibling of `visState`). Authoritative shape: `carto maps schema layergrouping`; full rules in `references/layers.md` → *"Layer groups"*.

```json
{
  "title": "Stores with reference context",
  "datasets": [
    { "name": "stores",   "source": "carto-dw.demo.stores",        "type": "table" },
    { "name": "districts","source": "carto-dw.demo.districts",     "type": "table" },
    { "name": "roads",    "source": "carto-dw.demo.major_roads",   "type": "table" }
  ],
  "keplerMapConfig": {
    "version": "v1",
    "config": {
      "mapState": { "latitude": 40.42, "longitude": -3.70, "zoom": 11 },
      "visState": {
        "layers": [
          {
            "id": "L_stores", "type": "tileset",
            "config": {
              "dataId": "$ref:stores", "label": "Stores",
              "color": [120, 80, 200], "isVisible": true, "hidden": false, "columns": {},
              "textLabel": [{"size":12,"color":[44,48,50],"field":null,"anchor":"start","offset":[0,0],"alignment":"center","outlineColor":[255,255,255]}],
              "visConfig": {"filled": true, "stroked": false, "opacity": 0.9, "radius": 5}
            },
            "visualChannels": {"colorField":null,"colorScale":"quantize","sizeField":null,"sizeScale":"linear","radiusField":null,"radiusScale":"linear"}
          },
          {
            "id": "L_districts", "type": "tileset",
            "config": {
              "dataId": "$ref:districts", "label": "Districts",
              "color": [180, 180, 180], "isVisible": true, "hidden": false, "columns": {},
              "textLabel": [{"size":12,"color":[44,48,50],"field":null,"anchor":"start","offset":[0,0],"alignment":"center","outlineColor":[255,255,255]}],
              "visConfig": {"filled": false, "stroked": true, "opacity": 0.7, "thickness": 1}
            },
            "visualChannels": {"colorField":null,"colorScale":"quantize","sizeField":null,"sizeScale":"linear","radiusField":null,"radiusScale":"linear"}
          },
          {
            "id": "L_roads", "type": "tileset",
            "config": {
              "dataId": "$ref:roads", "label": "Major roads",
              "color": [90, 90, 90], "isVisible": true, "hidden": false, "columns": {},
              "textLabel": [{"size":12,"color":[44,48,50],"field":null,"anchor":"start","offset":[0,0],"alignment":"center","outlineColor":[255,255,255]}],
              "visConfig": {"filled": false, "stroked": true, "opacity": 0.6, "thickness": 2}
            },
            "visualChannels": {"colorField":null,"colorScale":"quantize","sizeField":null,"sizeScale":"linear","radiusField":null,"radiusScale":"linear"}
          }
        ],
        "filters": []
      },
      "layerGrouping": [
        { "type": "layer", "layerId": "L_stores" },
        {
          "type": "group", "id": "g-reference", "name": "Reference",
          "isCollapsed": true, "isVisible": true,
          "children": [
            { "type": "layer", "layerId": "L_districts" },
            { "type": "layer", "layerId": "L_roads" }
          ]
        }
      ]
    }
  }
}
```

**What this demonstrates:**
- `layerGrouping` is a **flat, ordered array** at the config root — *not* nested in `visState`, and *not* a field on any layer. Panel order is top-to-bottom: the ungrouped "Stores" layer first, then the folded "Reference" group.
- Layers join the group by appearing in its **`children`** — there's no `groupId` on `L_districts` / `L_roads`.
- Each `layerId` matches a `visState.layers[].id` (the layer `id`, not the `$ref` dataId). A dangling id would be flagged by the validator and pruned by Builder.
- `isCollapsed: true` ships the group folded in the panel; `isVisible: true` keeps both reference layers rendering (group visibility ANDs with each layer's own `isVisible`).
- The "Stores" layer is omitted from any group on purpose — listing it as a top-level `{type:"layer"}` entry just fixes its panel order. Dropping it from the array entirely would still work: Builder appends ungrouped layers on load.
