# Raster algebra expressions

## Syntax

| Syntax | Meaning |
|---|---|
| `$a`, `$b`, … | Inputs in the order passed (`$a` alone only for single-band inputs). |
| `$a.band_1`, `$a.nir` | Band by metadata name. |
| `$a[4]` | Band by 1-based index. |
| `+ - * / %` | Arithmetic. |
| `^` or `**` | Power, right-associative; binds tighter than unary minus (`-$a^2` = `-($a^2)`). |
| `< <= > >= == !=` | Comparisons → 1 or 0. |
| `and or not` (`&& \|\| !`) | Logic → 1 or 0. |
| `if(cond, a, b)` | Conditional. |
| `abs sqrt exp log log10 log2 pow min max floor ceil round clamp(x,lo,hi) sin cos tan atan atan2` | Functions. |
| `pi`, `e` | Constants. |
| `name = expr; name = expr` | Several output bands. |

Anything else (unknown identifiers, SQL, strings) is rejected with the position of the error.

## Recipes

| Goal | Expression |
|---|---|
| Difference / change | `$b - $a` |
| Relative change (%) | `100 * ($b - $a) / $a` |
| NDVI (Sentinel-2: B8 nir, B4 red) | `($a.nir - $a.red) / ($a.nir + $a.red)` |
| NDWI (green, nir) | `($a.green - $a.nir) / ($a.green + $a.nir)` |
| NBR (nir, swir2) | `($a.nir - $a.swir2) / ($a.nir + $a.swir2)` |
| Burn severity (dNBR) from pre/post NBR rasters | `$a - $b` |
| Binary mask | `$a > 30` (use `output_type: uint8`) |
| Classes | `if($a < 0.2, 1, if($a < 0.5, 2, 3))` with `output_type: uint8` |
| Keep values where a condition holds, 0 elsewhere | `if($a > 1000, $b, 0)` |
| Coverage gained by a new site (dBm) | `gained = $b >= -100 and $a < -100; improvement = $b - $a` |
| Weighted overlay | `0.5 * $a + 0.3 * $b + 0.2 * $c` |
| Clamp to a range | `clamp($a, 0, 1)` |

## Options

| Option | Guidance |
|---|---|
| `output_type` | `float32` (default) for ratios/indices; integer types for classes/masks (results are rounded; out-of-range → nodata). |
| `output_nodata` | Default `NaN` for floats. Set a number (e.g. `-9999`) if a downstream tool can't handle NaN. |
| `overviews` | `evaluate` (default): renderable at every zoom immediately. `none`: native resolution only — cheaper, and exact for non-linear expressions. |

## Choosing the output type

- Indices and ratios: `float32`.
- Masks and classes: `uint8` (default nodata 255). For 0/255 masks set `output_nodata` (e.g. `254`), since 255 would be read as nodata.
- Integer outputs are rounded; values outside the type range become nodata.
