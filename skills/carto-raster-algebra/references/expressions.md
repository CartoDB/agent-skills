# Raster algebra expressions

The same grammar runs in the Analytics Toolbox procedure and in the Workflows component. It is not SQL: column names, SQL functions and strings are rejected.

## Syntax

| Syntax | Meaning |
|---|---|
| `$a`, `$b`, ... | Inputs in the order passed (Workflows: `$a` to `$d`, in the order connected). A bare `$a` works only for a single-band input. |
| `$a.band_1`, `$a.nir` | Band by its name in the metadata (matched ignoring case). |
| `$a[4]` | Band by 1-based index. |
| `+ - * / %` | Arithmetic. |
| `^` or `**` | Power. Right-associative, and binds tighter than unary minus: `-$a ^ 2` is `-($a ^ 2)`. |
| `< <= > >= == !=` | Comparisons, returning 1 or 0. Chains like `0 < $a < 1` are rejected: write `$a > 0 and $a < 1`. |
| `and or not` (or `&& \|\| !`) | Logic, returning 1 or 0. |
| `if(cond, a, b)` | `a` where `cond` is not 0, `b` otherwise. |
| `abs sqrt exp log log10 log2 pow min max floor ceil round clamp(x, lo, hi) sin cos tan atan atan2` | Functions. `log` is the natural logarithm. `round` rounds halves up (`round(-2.5)` is `-2`), also when results are rounded to an integer output type. |
| `pi`, `e` | Constants. |
| `name = expr; name = expr` | Several output bands. `;` separates them; line breaks don't. |

## Output names

- Unnamed outputs are `band_1`, `band_2`, ... by position.
- A name is an identifier (letters, digits, `_`, not starting with a digit).
- Names are unique ignoring case.
- A name can't be `block` or `metadata`, and can't end in `_count`, `_min`, `_max`, `_sum`, `_mean` or `_stddev`: the output uses those for its statistics columns.
- Each output must reference at least one input; constant-only outputs are rejected.

## Nodata

An output pixel is nodata when any input pixel its expression references is nodata, or when the result is not finite (division by zero, `log` of a negative, `sqrt(-1)`).

- This includes both branches of `if()`: `if($a > 0, $a, $b)` is nodata wherever `$b` is nodata, even where `$a > 0`.
- So nodata can't be replaced inside the expression. If the user needs a value there (e.g. "no signal" counted as -140 dBm), the input itself must hold that value.
- Each output only depends on the inputs it uses: in `x = $a * 2; y = $b * 2`, nodata in `$b` doesn't affect `x`.
- With an integer output type, results that don't fit the type become nodata, and so do results equal to the type's nodata value (the max for unsigned, the min for signed types, e.g. 255 for `uint8`).
- Blocks where every output pixel is nodata are not written.

## Recipes

| Goal | Expression | Notes |
|---|---|---|
| Difference / change | `$b - $a` | |
| Relative change (%) | `100 * ($b - $a) / $a` | Nodata where `$a` is 0. |
| NDVI | `($a.nir - $a.red) / ($a.nir + $a.red)` | Use the band names from the metadata (often `band_N`). Sentinel-2: B8 is NIR, B4 is red. |
| NDWI | `($a.green - $a.nir) / ($a.green + $a.nir)` | |
| NBR | `($a.nir - $a.swir2) / ($a.nir + $a.swir2)` | |
| Burn severity (dNBR) | `$a - $b` | `$a` is pre-fire NBR, `$b` post-fire NBR. |
| Binary mask | `$a > 30` | `uint8` output: 1/0, nodata 255. |
| Classes | `if($a < 0.2, 1, if($a < 0.5, 2, 3))` | `uint8` output. |
| Keep values where a condition holds, 0 elsewhere | `if($a > 1000, $b, 0)` | Still nodata wherever `$b` is nodata. |
| Coverage gained by a new site (dBm) | `gained = $b >= -100 and $a < -100; improvement = $b - $a` | `$a` before, `$b` after. See the nodata note above. |
| Weighted overlay | `0.5 * $a + 0.3 * $b + 0.2 * $c` | Bring inputs to a common scale first, e.g. `clamp(($a - lo) / (hi - lo), 0, 1)`. |
| Clamp to a range | `clamp($a, 0, 1)` | |
| Several indices at once | `ndvi = (...); ndwi = (...)` | One pass over the data, one output table. |

## Common errors

The procedure reports the cause, and parse errors include the position in the expression. Typical messages:

| Message (abridged) | Fix |
|---|---|
| `Unknown identifier 'x' at position N` | Reference inputs as `$a` and bands as `$a.band_1`. |
| `$a has 4 bands; specify one, e.g. $a.band_1` | Bare `$a` only works on single-band inputs. |
| `Band 'nir' not found in $a. Available bands: ...` | Use a name from the list, or an index. |
| `Input(s) $c are not referenced by the expression` | Use every input, or pass fewer. |
| `Chained comparison at position N is not supported` | Combine comparisons with `and`. |
| `Output band name 'x_min' clashes with a reserved column name` | Rename the output. |
| `Inputs $a and $b are not on the same grid: ...` | Re-import at a common block size and resolution. |
| `Input $a is ...; RaQuet v0.5.0 is required` | Re-import as v0.5.0 ([running.md](running.md)). |
