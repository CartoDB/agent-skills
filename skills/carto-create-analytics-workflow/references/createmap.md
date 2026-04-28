# `native.createmap` — Map visualization from a workflow

The `native.createmap` component creates a CARTO Builder map from workflow output. It is the recommended way to visualize workflow results.

> **Note:** when a dedicated `carto-create-builder-maps` skill lands, the non-workflow side of map authoring will move there. Workflow-context map creation stays here because it's a node in the workflow DAG.

---

## When to use

- The user wants to "see the results on a map".
- The user asks to "visualize" or "display" the output.
- The user wants a dashboard or to share results visually.
- The final step of a workflow that produces spatial data.

---

## Component inputs

Fetch the full schema with:

```bash
carto workflows components get native.createmap --connection <connection> --json
```

Key inputs:

| Input | Type | Description |
|-------|------|-------------|
| `source` | Table | Input table to visualize |
| `name` | String | Name for the created map |
| `geo` | Column | Geometry/spatial column to use for rendering |

---

## Basic usage

```json
{
  "id": "create-map-1",
  "type": "generic",
  "data": {
    "name": "native.createmap",
    "label": "Create Map",
    "inputs": [
      { "name": "source", "type": "Table", "value": "" },
      { "name": "name", "type": "String", "value": "My Analysis Results" },
      { "name": "geo", "type": "Column", "value": "geom" }
    ],
    "outputs": []
  },
  "position": { "x": 800, "y": 100 }
}
```

---

## Spatial index columns: H3 and Quadbin

**Do NOT convert H3 or Quadbin indices to geometry for map visualization.**

CARTO Builder natively understands H3 and Quadbin spatial indices. When your workflow output contains these columns, leave them as-is:

- **H3** — keep the H3 cell index column (e.g. `h3`, `h3_index`).
- **Quadbin** — keep the Quadbin index column (e.g. `quadbin`, `qb_index`).

Builder will recognize the spatial index column, render the cells with proper boundaries, and apply appropriate styling and aggregations.

### When to extract geometry

Only use `native.h3boundary` or `native.quadbinboundary` when:

1. You need to perform spatial operations on the cell geometries (e.g. spatial join, buffer).
2. You're exporting to a non-CARTO system that doesn't understand spatial indices.
3. The user explicitly requests polygon geometries.

### Correct vs unnecessary

**Correct** — let Builder handle H3 visualization:

```
source -> h3frompoint -> groupby (count per cell) -> createmap (geo: "h3")
```

**Unnecessary** — adding `h3boundary` just for visualization:

```
source -> h3frompoint -> groupby -> h3boundary -> createmap (geo: "h3_geo")
```

The second works but adds unnecessary computation. Builder can render H3 cells directly.

---

## Geometry column selection

When using `native.createmap`, the `geo` input must reference a valid spatial column:

| Data type | Column to use |
|-----------|---------------|
| H3 | The H3 column directly (e.g. `h3`, `index`) — Builder renders cells natively |
| Quadbin | The Quadbin column directly (e.g. `quadbin`) — Builder renders cells natively |
| Point / Line / Polygon / MultiPolygon | The geometry column name (e.g. `geom`, `geometry`, `geom_buffer`) |

---

## Best practices

- **Check the output schema before `createmap`.** Validate the workflow and inspect available columns to ensure the geometry column exists.
- **Name maps descriptively.** The `name` input becomes the map title in Builder.
- **One map per workflow output.** Each `createmap` component creates a separate map. For multiple layers, create multiple maps or use Builder to combine them.
- **Spatial indices render faster than polygon geometries** for aggregated data — prefer them when possible.
