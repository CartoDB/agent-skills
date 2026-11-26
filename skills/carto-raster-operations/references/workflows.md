# Workflows nodes, chaining and troubleshooting

## Nodes

Group **Raster Operations**, BigQuery and Snowflake, one node per procedure; each runs the matching procedure and is available when the connection's Analytics Toolbox ships it (BigQuery 1.28.0, Snowflake 1.29.0). Read a node's spec with `carto workflows components get <name> --connection <connection> --json` (or MCP `read_workflow_components`). If it isn't found, the organization doesn't have it enabled yet or the toolbox is older.

The frequent parameters are separate inputs. **Every other option goes in one optional JSON object, `customoptions` (title *Options*)**, like the Location Data Services nodes: `{"overviews": "none", "output_nodata": 0}`. Every option of the procedure is reachable there; a key that already has an input of its own is rejected.

| Component | Inputs | Procedure |
|---|---|---|
| `carto.rasterclip` Clip raster | `source`; `vector` (table) + `geo` (geography column); `intersect_center` (*Use pixel centre*) | `RASTER_CLIP` |
| `carto.rastermask` Mask raster | `source`; `mask` (table); `operator` (`greater`, `greater_equal`, `less`, `less_equal`, `equal`, `not_equal`, `between`, `in`, `valid`; default `valid`); `maskband` (a band name of the mask, not a variable); `value` / `minvalue` + `maxvalue` / `values` | `RASTER_MASK` (builds `condition`) |
| `carto.rasterfilter` Filter raster | `source`; `band`; `operator` (as mask, without `valid`); `value` / `minvalue` + `maxvalue` / `values`; `action` (`keep` default, `remove`) | `RASTER_FILTER` (builds `condition`; `remove` wraps it in `not(...)`) |
| `carto.rastermerge` Merge rasters | `sourcea`, `sourceb` required, `sourcec`, `sourced` optional; `overlap_rule` (default `first`) | `RASTER_MERGE` |
| `carto.rastersetnodata` Set raster nodata | `source`; `value` (a number, `NaN`, `Infinity`, `-Infinity`; non-finite for float bands only); advanced `more_values` (comma list) | `RASTER_SET_NODATA` |
| `carto.rasterreplacenodata` Replace raster nodata | `source`; `replacement` (number) | `RASTER_REPLACE_NODATA` |
| `carto.rasterreclassify` Reclassify raster | `source`; `band`; `classes` (table of `from` / `to` / `value`); `default_value` | `RASTER_RECLASSIFY` |
| `carto.rasterbands` Select raster bands | `source`; `bands` (several columns) | `RASTER_SELECT_BANDS` |
| `carto.rasterstack` Stack raster bands | `sourcea` to `sourced`; `band_names` (comma list) | `RASTER_STACK` |
| `carto.rastervectorize` Vectorize raster | `source`; `band` (required when the raster has several bands); `max_pixels` goes in `customoptions` | `RASTER_VECTORIZE` |

- Raster inputs are table sources (`ReadTable` with `data.type: "raster"` shows the raster in the Map tab; CLI 0.14.0 or later). Connect each node's `result` to the next node, or to `native.saveastable` to keep it.
- Differences from the SQL: the nodes build the `condition` for you (no free text), the numeric `value` fields accept numbers, variables and `+ - * /` only, and the `in` list takes at most 50 values.
- Vectorize outputs a plain table (`geom`, `value`), not a raster: do not connect it to a raster input.
- Node anatomy and CLI limits: see `carto-create-workflow` and [carto-raster-algebra running.md](../../carto-raster-algebra/references/running.md) for a raster node example.
- Like `RASTER_ALGEBRA`, a node replaces its own output on every run; the SQL procedures never overwrite.

## Chaining recipes

Every step writes a new table, so name each one. Use `{"overviews": "none"}` on intermediate steps that only feed another step.

| Goal | Chain |
|---|---|
| Elevation above 1,000 m inside a region | `RASTER_CLIP` (AOI) then `RASTER_FILTER` (`'band_1 > 1000'`) |
| Land cover classes as polygons for one region | `RASTER_CLIP`, then `RASTER_RECLASSIFY` (group classes), then `RASTER_VECTORIZE` |
| Mosaic tiles, classify, polygons | `RASTER_MERGE` (`overlap_rule`), then `RASTER_RECLASSIFY`, then `RASTER_VECTORIZE` |
| Mosaic tiles that use different nodata | `RASTER_SET_NODATA` on each input (same value), then `RASTER_MERGE` |
| Multi-band indices on a subset of bands | `RASTER_SELECT_BANDS`, then `carto-raster-algebra` |
| Combine two single-band rasters, then compute | `RASTER_STACK` (or pass both to `RASTER_ALGEBRA` directly), then `carto-raster-algebra` |
| Remove cloud pixels | `RASTER_MASK` with a cloud-free mask raster (`NULL` condition keeps valid mask pixels) |
| Treat 0 as no data and fill it | `RASTER_SET_NODATA` (`[0.0]`), then `RASTER_REPLACE_NODATA` |
| Large raster to polygons | `RASTER_CLIP` into areas, `RASTER_VECTORIZE` each (or raise `max_pixels`) |

## Troubleshooting

Show the user the error as is: it names the band, value or grid property at fault. Messages are paraphrased below.

| Symptom | What to do |
|---|---|
| "RaQuet v0.5.0 is required" | The input is a legacy or earlier raster: re-import it, then confirm `version` is `0.5.0` in its metadata row |
| Interleaved / lossy / WebP / RGB image not supported | Re-import without the color tags (see `carto-raster-algebra`) |
| Block size error ("square block size, a power of two and divisible by 16") | Re-import the raster with 256x256 or 512x512 blocks |
| Grid mismatch (block size or native zoom differ) | Re-import all rasters with the same block size and `max_zoom`; there is no resampling |
| Output table already exists or is an input | Choose a new `output_table`; ask before dropping anything |
| Unknown option key | Fix the key named in the error; options are one JSON string or `NULL` |
| Result has no valid pixel, no table created | The condition, mask or area removed everything: check the values, the AOI and the band; check `apply_scale_offset` |
| `output_nodata -1 is not representable as uint8 ...` | Pick a value inside the range the error gives, or a wider `output_type` |
| Merge: inputs declare different nodata | Run `RASTER_SET_NODATA` on the inputs with the same value first |
| Merge: band count, type, scale or offset differ | Make the inputs agree: `RASTER_SELECT_BANDS`, or re-import |
| `overlap_rule` missing or invalid | Pass `first`, `last`, `min`, `max`, `mean` or `sum` |
| Reclassify / vectorize on a multi-band raster fails | Pass `{"band": "<name>"}`, or `RASTER_SELECT_BANDS` first |
| Stack: duplicate band names | Pass `{"band_names": [...]}`, one per output band |
| Clip: "area of interest has no polygon" or "returned no geometries" | `vector_query` needs a column `geom` with at least one non-NULL polygon |
| Clip keeps one extra row/column, or edge pixels differ from QGIS | Use `intersect_center: true`; densify long east-west edges |
| Clip with a large polygon returns the complement or nothing | BigQuery: `ST_GEOGFROMTEXT(wkt, oriented => TRUE)`; Snowflake: split the polygon into pieces smaller than a hemisphere |
| Vectorize: raster has more pixels than `max_pixels` | Clip into areas, or reclassify then vectorize in parts; raising `max_pixels` is at the user's risk |
| BigQuery `RASTER_SET_NODATA` type error on `[0]` | Use decimals: `[0.0]` |
| BigQuery `Invalid ... table name` | Table names allow letters, digits, underscores and dashes only |
| Filter `== 0.1` on float32 matches nothing | Use `between 0.0999 and 0.1001`, or reclassify |
| Workflows node missing | The organization or the connection's toolbox does not have it yet: use the SQL procedure |
