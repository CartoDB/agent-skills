# Map JSON Structure Reference

This document describes the JSON structure used for creating and updating maps via the CARTO CLI. CARTO maps use [Kepler.gl](https://kepler.gl) for geospatial visualization.

## Overview

Map JSON combines:
- **Map metadata**: title, description, privacy settings
- **Datasets**: data sources and connections
- **keplerMapConfig**: Kepler.gl visualization configuration (including **layers**)
- **Agent configuration**: AI assistant settings (optional)

## CRITICAL: Datasets vs Layers

**A map needs BOTH datasets AND layers to display data.**

- **Datasets** = data sources (what data to load)
- **Layers** = visualizations (how to display the data)

```
datasets[] ──────► defines data sources with connectionId, source table, columns
                          │
                          │ layer.config.dataId references dataset.id
                          ▼
keplerMapConfig.visState.layers[] ──────► defines how to visualize each dataset
```

**If you create a map with only datasets but no layers, the map will be empty!**

---

## Map Creation Checklist

Before creating a map, verify:

- [ ] **Dataset**: Has valid `connectionId` (UUID from `carto connections list`)
- [ ] **Dataset**: Has correct `source` (fully qualified table name or SQL query)
- [ ] **Dataset**: Has correct `geoColumn` (geometry column name, e.g., `"geom"` or `"h3:h3"`)
- [ ] **Dataset**: Has `columns` array including at least the geometry column
- [ ] **Layer**: Has `dataId` that will reference the dataset's ID
- [ ] **Layer**: Has `type` matching your geometry (e.g., `"tileset"` for polygons/points)
- [ ] **Layer**: Has `isVisible: true`
- [ ] **mapState**: Has appropriate `latitude`, `longitude`, `zoom` for your data location

---

## Common Mistakes

### 1. Dataset without Layer (Most Common!)
**Problem**: Map shows no data despite having datasets configured.
**Cause**: Datasets define data sources, but layers define visualization. Without layers, nothing displays.
**Fix**: Add a layer in `keplerMapConfig.config.visState.layers[]` with `dataId` referencing your dataset.

### 2. Wrong dataId in Layer
**Problem**: Layer doesn't show data.
**Cause**: Layer's `dataId` doesn't match any dataset ID.
**Fix**: After creating a map, get the map JSON to find the auto-generated dataset IDs, then update layers.

### 3. Wrong geoColumn
**Problem**: "No geometry found" or similar errors.
**Cause**: `geoColumn` doesn't match the actual column name in your table.
**Fix**: Check your table schema for the correct geometry column name.

### 4. Missing connectionId
**Problem**: Dataset fails to load.
**Cause**: `connectionId` is missing or invalid.
**Fix**: Use `carto connections list` to get valid connection UUIDs.

### 5. Wrong Map URL format
**Problem**: Map URL returns 404 or wrong page.
**Cause**: Using wrong URL pattern.
**Fix**:
- Private maps: `https://{tenant_domain}/builder/{map_id}`
- Public maps: `https://{tenant_domain}/map/{map_id}`
- Get tenant_domain from `carto auth status`

---

## Minimal Working Example

This is the **minimum JSON needed to create a map that actually displays data**:

```json
{
  "title": "My Map",
  "datasets": [
    {
      "type": "table",
      "source": "project.dataset.my_table",
      "label": "My Data",
      "connectionId": "YOUR-CONNECTION-UUID",
      "geoColumn": "geom",
      "columns": ["geom"],
      "format": "tilejson"
    }
  ],
  "keplerMapConfig": {
    "version": "v1",
    "config": {
      "mapState": {
        "latitude": 40.0,
        "longitude": -3.0,
        "zoom": 6
      },
      "mapStyle": {
        "styleType": "positron"
      },
      "visState": {
        "layers": [
          {
            "id": "layer-1",
            "type": "tileset",
            "config": {
              "dataId": "DATASET_ID_PLACEHOLDER",
              "label": "My Layer",
              "color": [100, 100, 200],
              "isVisible": true,
              "visConfig": {
                "filled": true,
                "opacity": 0.7,
                "stroked": true,
                "strokeColor": [255, 255, 255]
              }
            }
          }
        ]
      }
    }
  }
}
```

**Note on dataId**: When you first create a map, you won't know the dataset ID yet (it's auto-generated). Two approaches:

1. **Create then update**: Create the map, then `carto maps get <id> --json` to find the dataset ID, then update with the correct `dataId` in the layer.

2. **Use placeholder**: Use any string as placeholder, create the map, then immediately update with the real ID.

---

## Top-Level Structure

```json
{
  "title": "Map Title",
  "description": "Optional description",
  "privacy": "private|shared|public",
  "collaborative": true,
  "keplerMapConfig": { /* Kepler.gl config */ },
  "datasets": [ /* Array of dataset configs */ ],
  "agent": { /* Optional AI agent config */ }
}
```

**Fields:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `title` | string | Yes | Map title |
| `description` | string | No | Map description |
| `privacy` | string | No | `"private"`, `"shared"`, or `"public"`. Default: `"private"` |
| `collaborative` | boolean | No | Enable collaborative editing. Default: `false` |
| `keplerMapConfig` | object | Yes | Kepler.gl visualization configuration |
| `datasets` | array | Yes | Array of dataset configurations |
| `agent` | object | No | AI agent configuration |

---

## Datasets Structure

Datasets define the data sources used in the map.

```json
{
  "datasets": [
    {
      "type": "table",
      "source": "project.dataset.table_name",
      "label": "Display Name",
      "connectionId": "connection-uuid",
      "geoColumn": "geom",
      "columns": ["geom", "column1", "column2"],
      "format": "tilejson"
    }
  ]
}
```

**Dataset Fields:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Auto | Unique identifier (UUID). Generated by API |
| `type` | string | Yes | `"table"` or `"query"` |
| `source` | string | Yes | Fully qualified table name or SQL query |
| `label` | string | Yes | Display name shown in UI |
| `name` | string | No | Additional name field |
| `color` | string | No | Color for dataset in UI (hex: `"#FF5733"`) |
| `connectionId` | string | Yes | UUID of the connection to use |
| `connectionName` | string | Read-only | Connection name (returned by API) |
| `geoColumn` | string | Yes | Geometry column name. Use `"h3:h3"` for H3 indexes |
| `spatialIndex` | string | No | Spatial index type |
| `columns` | array | Yes | Array of column names to include |
| `format` | string | Yes | Data format. Usually `"tilejson"` |
| `aggregationExp` | string | No | SQL aggregation expression for tilesets |
| `aggregationResLevel` | number | No | Aggregation resolution level (for H3) |

### Table Dataset Example

```json
{
  "type": "table",
  "source": "carto-demo-data.demo_tables.nyc_collisions",
  "label": "NYC Collisions",
  "connectionId": "62c90ed4-eeec-46d0-bda9-c7ea173e26f0",
  "geoColumn": "geom",
  "columns": ["geom", "_carto_point_density"],
  "format": "tilejson"
}
```

### Query Dataset Example

```json
{
  "type": "query",
  "source": "SELECT h3, COUNT(*) as total FROM `project.dataset.table` GROUP BY h3",
  "label": "Aggregated Data",
  "connectionId": "62c90ed4-eeec-46d0-bda9-c7ea173e26f0",
  "geoColumn": "h3:h3",
  "columns": ["h3"],
  "format": "tilejson",
  "aggregationExp": "count(total) as total_count",
  "aggregationResLevel": 4
}
```

---

## keplerMapConfig Structure

The `keplerMapConfig` contains the Kepler.gl visualization configuration.

```json
{
  "keplerMapConfig": {
    "version": "v1",
    "config": {
      "mapState": { /* Map viewport */ },
      "mapStyle": { /* Base map styling */ },
      "visState": {
        "layers": [ /* Visual layers */ ],
        "filters": [ /* Data filters */ ]
      },
      "uiState": { /* UI panel states */ },
      "widgets": [ /* Dashboard widgets */ ],
      "mapSettings": { /* Map capabilities */ }
    }
  }
}
```

### mapState - Viewport Configuration

Controls the map's camera position.

```json
{
  "mapState": {
    "latitude": 40.7128,
    "longitude": -73.9060,
    "zoom": 13.5,
    "pitch": 0,
    "bearing": 0,
    "dragRotate": false,
    "isSplit": false
  }
}
```

### mapStyle - Base Map Styling

```json
{
  "mapStyle": {
    "styleType": "positron",
    "visibleLayerGroups": {
      "land": true,
      "water": true,
      "building": true,
      "road": true,
      "border": false,
      "label": true
    }
  }
}
```

**Base map styleTypes:** `"positron"`, `"dark"`, `"voyager"`, `"satellite"`

### visState.layers - Visual Layers

Defines how data is visualized. Each layer references a dataset by `dataId`.

**Layer Types:**
- `"tileset"`: Point/polygon tilesets
- `"h3"`: H3 hexagon aggregations
- `"geojson"`: GeoJSON features
- `"point"`: Point features
- `"arc"`: Connection lines
- `"hexagon"`: Hexbin aggregations

**Tileset Layer Example:**
```json
{
  "id": "layer-1",
  "type": "tileset",
  "config": {
    "dataId": "dataset-uuid-here",
    "label": "Layer Name",
    "color": [255, 69, 0],
    "isVisible": true,
    "columns": {},
    "visConfig": {
      "filled": true,
      "opacity": 0.8,
      "radius": 5,
      "colorRange": {
        "name": "Global Warming",
        "type": "sequential",
        "colors": ["#5A1846", "#900C3F", "#C70039", "#E3611C", "#F1920E", "#FFC300"]
      }
    },
    "visualChannels": {
      "colorField": {"name": "column_name", "type": "integer"},
      "colorScale": "quantile",
      "sizeField": {"name": "density", "type": "integer"},
      "sizeScale": "sqrt"
    }
  }
}
```

**H3 Layer Example:**
```json
{
  "id": "h3-layer",
  "type": "h3",
  "config": {
    "dataId": "h3-dataset-uuid",
    "label": "H3 Aggregation",
    "color": [18, 147, 154],
    "isVisible": true,
    "visConfig": {
      "filled": true,
      "opacity": 0.8,
      "colorRange": {
        "name": "Teal @CARTOColors",
        "type": "sequential",
        "colors": ["#d1eeea", "#a8dbd9", "#85c4c9", "#68abb8", "#4f90a6", "#3b738f"]
      },
      "colorAggregation": "count"
    },
    "visualChannels": {
      "colorField": {"name": "count_field", "type": "integer"},
      "colorScale": "custom"
    }
  }
}
```

### widgets - Dashboard Widgets

```json
{
  "widgets": [
    {
      "id": "widget-uuid",
      "type": "formula",
      "title": "Total Count",
      "column": "",
      "global": true,
      "isValid": true,
      "operation": "count",
      "dataSource": "dataset-uuid"
    }
  ]
}
```

**Widget Operations:** `"count"`, `"sum"`, `"avg"`, `"min"`, `"max"`

### mapSettings - Map Capabilities

```json
{
  "mapSettings": {
    "scrollWheelZoom": true,
    "addressSearchBar": false,
    "basemapsSelector": false,
    "measurementUnit": "kilometers",
    "featureSelectionTool": true,
    "sqlParameterControls": true,
    "showMeasureDistanceTool": false,
    "exportViewportData": false,
    "reorderLayers": true,
    "comments": false
  }
}
```

---

## Agent Configuration

Optional AI assistant configuration.

```json
{
  "agent": {
    "enabledForViewer": true,
    "config": {
      "model": "account-id::gemini-2.5-flash",
      "tools": ["tool-uuid-1", "tool-uuid-2"],
      "useCase": "Description of what this agent does",
      "capabilities": {
        "showDetails": false,
        "querySources": false
      },
      "instructions": "# Instructions for the agent\n\nDetailed markdown...",
      "introduction": {
        "welcome": "Welcome message for users",
        "starters": [
          "Suggested question 1",
          "Suggested question 2"
        ]
      }
    }
  }
}
```

**Agent Fields:**
| Field | Description |
|-------|-------------|
| `enabledForViewer` | Whether viewers can interact with agent |
| `config.model` | AI model: `"{account-id}::{model-name}"` |
| `config.tools` | Array of tool UUIDs |
| `config.useCase` | Brief purpose description |
| `config.capabilities.showDetails` | Show detailed information |
| `config.capabilities.querySources` | Allow querying data sources |
| `config.instructions` | Markdown instructions for agent |
| `config.introduction.welcome` | Welcome message |
| `config.introduction.starters` | Suggested conversation starters |

**Available models:** `"gemini-2.5-flash"`, `"gemini-2.0-flash"`, `"gpt-4o"`

---

## Complete Example

```json
{
  "title": "NYC Traffic Analysis",
  "description": "Traffic and collision data analysis",
  "privacy": "shared",
  "collaborative": true,
  "datasets": [
    {
      "type": "table",
      "source": "carto-demo-data.demo_tables.nyc_traffic_counts",
      "label": "Traffic Counts",
      "connectionId": "62c90ed4-eeec-46d0-bda9-c7ea173e26f0",
      "geoColumn": "geom",
      "columns": ["geom", "datetime", "volume"],
      "format": "tilejson"
    },
    {
      "type": "query",
      "source": "SELECT h3, COUNT(*) as total_collisions FROM `carto-demo-data.demo_tables.nyc_collisions` GROUP BY h3",
      "label": "Collision Aggregation",
      "connectionId": "62c90ed4-eeec-46d0-bda9-c7ea173e26f0",
      "geoColumn": "h3:h3",
      "columns": ["h3"],
      "format": "tilejson",
      "aggregationExp": "count(total_collisions) as collision_count",
      "aggregationResLevel": 4
    }
  ],
  "keplerMapConfig": {
    "version": "v1",
    "config": {
      "mapState": {
        "latitude": 40.7128,
        "longitude": -73.9060,
        "zoom": 11,
        "pitch": 0,
        "bearing": 0,
        "dragRotate": false,
        "isSplit": false
      },
      "mapStyle": {
        "styleType": "positron",
        "visibleLayerGroups": {
          "land": true,
          "water": true,
          "building": true,
          "road": true,
          "border": false,
          "label": true
        }
      },
      "visState": {
        "layers": [
          {
            "id": "traffic-layer",
            "type": "tileset",
            "config": {
              "dataId": "REPLACE_WITH_DATASET_ID_1",
              "label": "Traffic Volume",
              "color": [246, 186, 0],
              "isVisible": true,
              "visConfig": {
                "filled": true,
                "opacity": 0.8,
                "radius": 3,
                "colorRange": {
                  "name": "Global Warming",
                  "type": "sequential",
                  "colors": ["#5A1846", "#900C3F", "#C70039", "#E3611C", "#F1920E", "#FFC300"]
                }
              }
            }
          }
        ],
        "filters": []
      },
      "widgets": [
        {
          "id": "widget-1",
          "type": "formula",
          "title": "Total Traffic Events",
          "operation": "count",
          "dataSource": "REPLACE_WITH_DATASET_ID_1",
          "global": true
        }
      ],
      "mapSettings": {
        "scrollWheelZoom": true,
        "featureSelectionTool": true,
        "measurementUnit": "kilometers"
      }
    }
  }
}
```

---

## Important Notes

### Dataset IDs and References
- When **creating** a map, datasets are created first and return IDs
- The `keplerMapConfig` must reference these IDs in layer `dataId` fields
- Use placeholders like `"REPLACE_WITH_DATASET_ID_1"` and replace after dataset creation
- When **updating**, dataset IDs remain the same unless datasets are recreated

### Connection Requirements
- `connectionId` must be a valid UUID from your organization's connections
- Use `carto connections list` to find connection IDs
- Connection must have access to the tables/datasets referenced

### Privacy Settings
- `"private"`: Only you can access
- `"shared"`: Organization members can access
- `"public"`: Anyone with link can access

### Best Practices
1. **Start simple**: Begin with basic datasets and layers, add complexity incrementally
2. **Test datasets**: Verify dataset queries work before adding to map
3. **Use labels**: Clear labels help identify layers and datasets in the UI
4. **Match types**: Ensure `geoColumn` matches your data's geometry type
5. **Layer order**: Layers are rendered in array order (first = bottom)
6. **Color consistency**: Use color palettes from CARTO Colors

### Resources
- [Kepler.gl Documentation](https://docs.kepler.gl/)
- [CARTO Colors](https://carto.com/carto-colors/)
