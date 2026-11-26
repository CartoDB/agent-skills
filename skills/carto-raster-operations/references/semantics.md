# Semantics, limits and differences from other tools

## Nodata

- A pixel is **nodata** when it equals the band's declared nodata (compared before scale/offset; nodata is not itself scaled), or, on a float band, when it is `NaN`, `+Infinity` or `-Infinity`, declared or not. Statistics ignore nodata pixels.
- Nodata is **never reclassified or kept by a predicate**: filter keeps nodata pixels nodata (also under `not(...)`), reclassify never assigns a class to it, mask keeps source nodata even where the mask is valid.
- An operation that can create nodata on a band with none declares one (`output_nodata`, else `NaN` for floats, the type min for signed or max for unsigned integers). A valid pixel equal to that value becomes nodata: set `output_nodata` when the default can be a real value (for example `254` for a 0/255 raster).
- A declared nodata the band type cannot hold (`-127` on `uint8`) is ignored with a warning and not written. A value **you** give that the type cannot hold (`output_nodata`, `nodata_values`, `replacement_value`, a class value) is rejected naming band, value and range.
- `"NaN"`, `"Infinity"`, `"-Infinity"` are valid on float bands only.
- Typical sequence for "treat 0 as no data, then fill it": `RASTER_SET_NODATA` with `[0.0]`, then `RASTER_REPLACE_NODATA` with the new value. Replace removes the declared nodata.

## Predicates (filter, mask conditions)

Evaluated in Float64, on valid pixels, on **physical values** (`stored * scale + offset`) unless `apply_scale_offset` is `false`. Equality is exact: a float32 pixel never equals `0.1` as Float64, so use `between`. `between a and b` includes both ends. A non-finite pixel never matches. `=` is not an operator: use `==`.

## Overviews

Each zoom is computed from the input's own tile at that zoom; the pyramid is never rebuilt from the native result. So low-zoom tiles of filter, reclassify, conditional mask and merge `sum`/`mean` are not coarser versions of the native result, and a categorical raster built with averaged overviews can hold class values at low zoom that do not exist at native zoom. `{"overviews": "none"}` computes the native zoom only. `RASTER_VECTORIZE` reads the native zoom only.

## Limits and failure modes

- **Inputs**: RaQuet v0.5.0 only. Legacy v0 rasters and RGB images imported as WebP are not supported: re-import. Block size square, power of two, divisible by 16; sequential band layout; no time dimension; no lossy tiles.
- **Grid**: same block size and `max_zoom` to merge, mask or stack. No automatic resampling (it would change pixel values): re-import at a common resolution.
- **Output**: always a new table; fails if it exists or is an input; the dataset or schema must exist. Failure drops only the table the call created.
- **Empty result is an error**, and no table is created. Blocks with no valid pixel are not written, so filtering or clipping crops the extent.
- **Types**: `int64`, `uint64`, `float16` are rejected by operations that evaluate values; `SELECT_BANDS` and `STACK` copy them, but Builder cannot render them.
- **Size**: call time grows with the number of bands (about 20 to 45 s for a 100-band, one-block raster). Snowflake `BINARY` cells hold 8 MB.
- **Table names**: BigQuery accepts letters, digits, underscores and dashes only.
- **Pixel zoom 30 or finer** on Snowflake: `RASTER_CLIP` and `RASTER_VECTORIZE` can lose pixels or polygons.
- **Clip edges**: edges are geodesics in the warehouse and straight lines in the raster projection; a long east-west edge deviates up to `pi * sin(lat) * n^2 / (4 * W)` pixels (`n` = edge length in pixels, `W = 2^pixel_zoom`). Densify the polygon so no east-west edge is longer than `sqrt(2 * W / (pi * sin(lat)))` pixels. Edges are not densified for you.
- **Pixel-aligned AOI**: a clip can keep one extra row or column towards the pole; use `intersect_center: true` or shrink the area by a fraction of a pixel.
- **Clip then aggregate**: `RASTER_AGG_VALUES` counts pixels that only touch a pixel-aligned polygon; the clip does not, so the two can differ.
- **Cloud differences**: BigQuery and Snowflake produce the same integer results; float values and statistics agree within 1e-6 relative; sampled `quantiles` / `top_values` are approximate (1,000-pixel sample, `approximated_stats: true`).

## Where results differ from GDAL, rasterio and QGIS

Agents coming from those tools assume their defaults. These do not hold here.

| Operation | GDAL / rasterio / QGIS | Here |
|---|---|---|
| Clip | Keep pixels whose **centre** is inside the polygon | Default keeps pixels whose square **overlaps** the polygon (a superset, never fewer). `intersect_center: true` gives the centre rule. DuckDB `ST_Clip` (duckdb-raquet) uses the centre, so it differs at the boundary by default |
| Clip AOI | Polygons | Union of the polygonal parts; points and lines ignored; no polygon is an error |
| Merge | `first` default in rasterio; last wins in `gdal_merge.py` | No default: `overlap_rule` is required. No `count` rule |
| Merge resolution / nodata | Resamples or masks each source by its own nodata | Different resolution rejected (no resampling); different nodata rejected (run `RASTER_SET_NODATA` first) |
| Merge overflow | Integer overflow wraps around | Result that does not fit the type becomes nodata |
| Set nodata | `gdal_edit -a_nodata` changes only the declared value | Also **rewrites** pixels equal to a listed value or the old nodata |
| Replace nodata | scale/offset are the caller's job | `replacement_value` is a **stored** value |
| Filter / compare | Raw stored values; NumPy compares in the band type | **Physical values** by default, Float64 exact comparison |
| Reclassify | QGIS: `min < v <= max`; unmatched keep their value; GDAL: unmatched is an error | `[from, to)` default (`range_boundaries` selects the others); unmatched become `default_value` or nodata |
| Nodata | GDAL treats NaN as a value when no nodata is declared | NaN and infinities on float bands are always nodata |
| Overviews | Not applicable | Computed from the input's own overviews, not from the result (see above) |
| Vectorize | `gdal_polygonize`: planar, 4-connected by default, nodata excluded | 4-connected, nodata excluded; regions meeting across +-180 are **one** polygon (geography) |
| Band metadata | Follows the band | Same for select and stack; names collide only through `band_names` |
