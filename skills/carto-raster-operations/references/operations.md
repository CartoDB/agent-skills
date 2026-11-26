# Procedure reference

Argument order is always inputs, operation arguments, `output_table`, `options`. Snowflake signatures are identical; types are `VARCHAR` / `ARRAY` / `FLOAT` instead of `STRING` / `ARRAY<...>` / `FLOAT64`. Table names are fully qualified (`project.dataset.table` on BigQuery, `database.schema.table` on Snowflake); the output dataset or schema must exist.

BigQuery calls use `` `carto-un`.carto.RASTER_X(...) `` (`carto-un` is the US project; use the one for the data's region). Snowflake calls use `carto.RASTER_X(...)` as in the docs: qualify it with the database and schema where the toolbox is installed if it isn't on the search path. On Snowflake arrays are `ARRAY_CONSTRUCT(...)`; on BigQuery `[...]`.

**Common options.** "common" below means `overviews`, `compression` and `compression_level`, accepted by every raster-writing procedure. The last two rows apply only where the procedure says so (`output_nodata` and `apply_scale_offset` are not accepted by `SET_NODATA`, `REPLACE_NODATA`, `SELECT_BANDS`, `STACK`):

| Option | Default | Meaning |
|---|---|---|
| `overviews` | `evaluate` | `evaluate` applies the operation on every zoom the inputs share; `none` computes the native zoom only (cheaper) |
| `compression` | `gzip` | `gzip` or `none` |
| `compression_level` | `1` | gzip 1 to 9 |
| `output_nodata` | the band's nodata; if none, `NaN` (float) or the type's min (signed) / max (unsigned) | Where a pixel can become nodata (clip, mask, filter, merge, reclassify). Must fit the band type |
| `apply_scale_offset` | `true` | Filter, mask, reclassify: conditions use physical values (`stored * scale + offset`); pixels are written back as stored |

Pixels are copied as stored; band type, scale, offset, description, unit and colour table are carried over (except `RASTER_RECLASSIFY`).

## RASTER_CLIP(raster_table, vector_query, output_table, options)

Keeps the pixels inside an area of interest; the rest become nodata; blocks the area does not reach are not written (the extent is cropped).

- `vector_query`: a table name or a query with polygons in a column named `geom` (geography; on Snowflake also geometry in SRID 4326). Several polygons are their union. Points and lines are ignored; an area with no polygon, or all-NULL rows, is rejected.
- Options: `intersect_center` (`false` default: pixels whose square overlaps the area; `true`: pixels whose centre is inside), `output_nodata`, common.
- BigQuery: a polygon larger than a hemisphere needs `ST_GEOGFROMTEXT(wkt, oriented => TRUE)`. Snowflake: polygons larger than a hemisphere select the complement; split them. Split antimeridian-crossing polygons on Snowflake.
- Long east-west edges deviate from the warehouse geodesic: densify the polygon (see [semantics.md](semantics.md)).

```sql bigquery
CALL `carto-un`.carto.RASTER_CLIP(
    '<my-project>.<my-dataset>.elevation',
    'SELECT geom FROM <my-project>.<my-dataset>.states WHERE name = \'Texas\'',
    '<my-project>.<my-dataset>.elevation_texas',
    '{"intersect_center": true, "output_nodata": -1}'
);
```

```sql snowflake
CALL carto.RASTER_CLIP(
    '<my-database>.<my-schema>.elevation',
    'SELECT geom FROM <my-database>.<my-schema>.states WHERE name = ''Texas''',
    '<my-database>.<my-schema>.elevation_texas',
    '{"intersect_center": true, "output_nodata": -1}'
);
```

## RASTER_MASK(raster_table, mask_raster, condition, output_table, options)

Keeps the pixels of `raster_table` where the mask raster satisfies the condition. The mask is on the same grid; its extent may differ (no block there means masked out). A pixel that is nodata in the raster stays nodata.

- `condition`: predicate over the **mask raster referenced as `$a`**: `'$a == 3'`, `'$a.band_2 > 0.5'`, `'$a[1] between 10 and 20'`, `'$a in (1, 2)'`. `NULL` keeps pixels valid in every band of the mask. A nodata mask pixel never satisfies a condition, also under `not(...)`.
- Options: `bands` (bands of `raster_table` to mask, default all), `output_nodata`, `apply_scale_offset`, common.

```sql bigquery
CALL `carto-un`.carto.RASTER_MASK(
    '<my-project>.<my-dataset>.elevation',
    '<my-project>.<my-dataset>.landcover',
    '$a == 3',
    '<my-project>.<my-dataset>.elevation_forest',
    NULL
);
```

```sql snowflake
CALL carto.RASTER_MASK(
    '<my-database>.<my-schema>.elevation',
    '<my-database>.<my-schema>.landcover',
    '$a == 3',
    '<my-database>.<my-schema>.elevation_forest',
    NULL
);
```

## RASTER_FILTER(raster_table, condition, output_table, options)

Keeps the pixels that satisfy a condition over the raster's own bands; the rest become nodata.

- `condition`: bands by name (`band_1 < 15`) or index (`$a[1]`; `$a` for a single-band raster; `$a.band_1` also works). The index form is the only way to reach band names with spaces, non-ASCII characters or operator words. Supports `< <= > >= == !=`, `x between a and b` (inclusive), `x in (a, b, ...)`, `and or not`, and the arithmetic and functions of `RASTER_ALGEBRA`. To remove matches, wrap it: `not(...)`. Nodata pixels never match, even under `not(...)`.
- Options: `bands` (bands that lose pixels, default all; the condition may read any band), `output_nodata`, `apply_scale_offset`, common.

```sql bigquery
CALL `carto-un`.carto.RASTER_FILTER(
    '<my-project>.<my-dataset>.terrain',
    'not(elevation between 0 and 100)',
    '<my-project>.<my-dataset>.terrain_filtered',
    '{"bands": ["elevation"], "output_nodata": 0}'
);
```

```sql snowflake
CALL carto.RASTER_FILTER(
    '<my-database>.<my-schema>.terrain',
    'not(elevation between 0 and 100)',
    '<my-database>.<my-schema>.terrain_filtered',
    '{"bands": ["elevation"], "output_nodata": 0}'
);
```

## RASTER_MERGE(input_rasters, overlap_rule, output_table, options)

Merges 2 to 26 rasters; the output covers the union of the extents. Same grid required, and the same band count, type, scale, offset and nodata per band.

- `overlap_rule` (required, no default): `first`, `last`, `min`, `max`, `mean`, `sum`, applied over the **valid** pixels (a nodata pixel falls through to the other input). Array order defines `first` / `last`. `sum` is rejected for bands with a non-zero `offset`.
- Options: `output_type` (default the input type; use `float32` for an exact `mean`), `output_nodata` (default the inputs' nodata), common.
- A `sum`/`mean` that does not fit the type (`uint8` 200 + 100) or is not finite becomes nodata (GDAL wraps around). Integer `mean` rounds half away from zero.
- More than 26 rasters: merge in several calls. Chaining is exact for `max` and `min`, not for `mean`.

```sql bigquery
CALL `carto-un`.carto.RASTER_MERGE(
    ['<my-project>.<my-dataset>.coverage_a', '<my-project>.<my-dataset>.coverage_b'],
    'mean',
    '<my-project>.<my-dataset>.coverage_mean',
    '{"output_type": "float32"}'
);
```

```sql snowflake
CALL carto.RASTER_MERGE(
    ARRAY_CONSTRUCT('<my-database>.<my-schema>.coverage_a', '<my-database>.<my-schema>.coverage_b'),
    'mean',
    '<my-database>.<my-schema>.coverage_mean',
    '{"output_type": "float32"}'
);
```

## RASTER_RECLASSIFY(raster_table, classes, output_table, options)

Maps values to classes. The output has **one band** (named like the input band), no scale/offset/unit.

- `classes`: JSON array, first match wins, up to 1,000. Each class has `value` (required) and either `from` / `to` (omit one for an open end; `to` below `from` is rejected) or `equals` (exact; cannot be combined with `from`/`to`). Optional `label` (value label) and `color` (`[r,g,b]` or `[r,g,b,a]`): with colours the output is drawn categorically in Builder.
- Options: `band` (required for multi-band input), `range_boundaries` (`min_inclusive` default `[from, to)`, `max_inclusive` `(from, to]`, `both`, `neither`; not applied to `equals`), `default_value` (pixels no class covers; default nodata), `output_type` (default the smallest integer type that fits the class values, else `float32`), `output_nodata` (default a value no class uses), `apply_scale_offset`, common.
- Nodata pixels are never classified, not even by an open-ended range or `default_value`.

```sql bigquery
CALL `carto-un`.carto.RASTER_RECLASSIFY(
    '<my-project>.<my-dataset>.elevation',
    '[{"to": 500, "value": 1, "color": [60, 160, 60], "label": "low"}, {"from": 500, "to": 1500, "value": 2, "color": [200, 200, 60], "label": "mid"}, {"from": 1500, "value": 3, "color": [200, 60, 60], "label": "high"}]',
    '<my-project>.<my-dataset>.elevation_classes',
    NULL
);
```

```sql snowflake
CALL carto.RASTER_RECLASSIFY(
    '<my-database>.<my-schema>.elevation',
    '[{"to": 500, "value": 1, "color": [60, 160, 60], "label": "low"}, {"from": 500, "to": 1500, "value": 2, "color": [200, 200, 60], "label": "mid"}, {"from": 1500, "value": 3, "color": [200, 60, 60], "label": "high"}]',
    '<my-database>.<my-schema>.elevation_classes',
    NULL
);
```

## RASTER_SET_NODATA(raster_table, nodata_values, output_table, options)

Declares nodata. The **first** value becomes the declared nodata; every pixel equal to any listed value, or to the previous declared nodata, is rewritten to it.

- `nodata_values`: non-empty array of numbers that fit the band type. `NaN`, `Infinity`, `-Infinity` for float bands only. On BigQuery write decimals (`[0.0]`, not `[0]`): integer literals are not coerced to `ARRAY<FLOAT64>`.
- Options: `bands` (default all; the rest are copied), common.

```sql bigquery
CALL `carto-un`.carto.RASTER_SET_NODATA(
    '<my-project>.<my-dataset>.imagery',
    [0.0, 255.0],
    '<my-project>.<my-dataset>.imagery_red_nodata',
    '{"bands": ["red"]}'
);
```

```sql snowflake
CALL carto.RASTER_SET_NODATA(
    '<my-database>.<my-schema>.imagery',
    ARRAY_CONSTRUCT(0, 255),
    '<my-database>.<my-schema>.imagery_red_nodata',
    '{"bands": ["red"]}'
);
```

## RASTER_REPLACE_NODATA(raster_table, replacement_value, output_table, options)

Writes a constant where pixels are nodata (including `NaN` and infinities on float bands); the selected bands stop declaring nodata.

- `replacement_value`: a finite **stored** value (scale/offset are not applied) that fits the type of every band to change.
- Options: `bands` (default all), common. Only blocks present in the input are processed; absent blocks are not created.
- To declare a new nodata afterwards, run `RASTER_SET_NODATA`.

```sql bigquery
CALL `carto-un`.carto.RASTER_REPLACE_NODATA(
    '<my-project>.<my-dataset>.elevation',
    0,
    '<my-project>.<my-dataset>.elevation_filled',
    NULL
);
```

```sql snowflake
CALL carto.RASTER_REPLACE_NODATA(
    '<my-database>.<my-schema>.elevation',
    0,
    '<my-database>.<my-schema>.elevation_filled',
    NULL
);
```

## RASTER_SELECT_BANDS(raster_table, bands, output_table, options)

Keeps the listed bands, in the order given, with their metadata and statistics; tiles are copied.

- `bands`: array of band names (exact match first, then ignoring case); an unknown or repeated band is rejected.
- Options: common only.

```sql bigquery
CALL `carto-un`.carto.RASTER_SELECT_BANDS(
    '<my-project>.<my-dataset>.sentinel2',
    ['red', 'green', 'blue'],
    '<my-project>.<my-dataset>.sentinel2_rgb',
    NULL
);
```

```sql snowflake
CALL carto.RASTER_SELECT_BANDS(
    '<my-database>.<my-schema>.sentinel2',
    ARRAY_CONSTRUCT('red', 'green', 'blue'),
    '<my-database>.<my-schema>.sentinel2_rgb',
    NULL
);
```

## RASTER_STACK(input_rasters, output_table, options)

Concatenates the bands of 2 to 26 rasters on the same grid, in array order; each band keeps its own type, nodata and metadata. Extents may differ; a band with no block somewhere is nodata there (or zeros counted as valid, when the band declares no nodata and is not float).

- Options: `band_names` (array, one name per output band, in order), common. Without it names are kept and a collision fails asking for `band_names`. Names cannot be `block` or `metadata`, cannot end in `_count`, `_min`, `_max`, `_sum`, `_mean`, `_stddev`, and are unique ignoring case.

```sql bigquery
CALL `carto-un`.carto.RASTER_STACK(
    ['<my-project>.<my-dataset>.elevation', '<my-project>.<my-dataset>.landcover'],
    '<my-project>.<my-dataset>.terrain_stack',
    '{"band_names": ["elevation", "landcover"]}'
);
```

```sql snowflake
CALL carto.RASTER_STACK(
    ARRAY_CONSTRUCT('<my-database>.<my-schema>.elevation', '<my-database>.<my-schema>.landcover'),
    '<my-database>.<my-schema>.terrain_stack',
    '{"band_names": ["elevation", "landcover"]}'
);
```

## RASTER_VECTORIZE(raster_table, output_table, options)

Turns one band into polygons: each region of contiguous pixels with the same value (4-neighbour: corner contact does not join) is one polygon, holes included. **The output is a table of polygons, not a raster**: columns `geom` (geography) and `value` (the stored value; scale/offset are not applied). Only the native zoom is read. Nodata and `NaN` are excluded.

- The band is an option: `band` (required for multi-band input). There is no band argument.
- `max_pixels` (default 100,000,000): a larger raster fails before anything is written. Larger rasters can fail when regions are joined: split with `RASTER_CLIP` and vectorize each part, or raise it at your own risk.
- A continuous band yields up to one polygon per pixel: `RASTER_RECLASSIFY` first.
- Regions meeting across +-180 are one polygon (not cut at the antimeridian).

```sql bigquery
CALL `carto-un`.carto.RASTER_VECTORIZE(
    '<my-project>.<my-dataset>.landcover',
    '<my-project>.<my-dataset>.landcover_polygons',
    '{"band": "class"}'
);
```

```sql snowflake
CALL carto.RASTER_VECTORIZE(
    '<my-database>.<my-schema>.landcover',
    '<my-database>.<my-schema>.landcover_polygons',
    '{"band": "class"}'
);
```
