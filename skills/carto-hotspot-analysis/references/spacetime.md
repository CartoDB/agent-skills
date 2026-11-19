# Spacetime Variants

These components run on BigQuery and Snowflake only. Columns are documented in lowercase; on Snowflake they surface UPPERCASE.

## Getis-Ord Spacetime (`native.getisordspacetime`)

- Extends basic Gi* to detect clusters in both space AND time.
- Inputs: `indexcol`, `datecol` (the time-bin column), `valuecol`, `kernel` (spatial) and `kerneltime` (temporal), each one of `uniform`, `triangular`, `quadratic`, `quartic`, `gaussian`, `size` (k-ring, default 3), `bandwidth` (time steps, default 3, 1-10) and `timeinterval` (`year`, `quarter`, `month`, `week`, `day`, `hour`, `minute` or `second`: the unit of your time bins). `kernel`, `kerneltime` and `timeinterval` have no default: always set them.
- Output: `index` (Snowflake: the input index column name), `date`, `gi`, `p_value`.
- Data must be pre-aggregated into time bins (e.g. weekly counts per H3 cell).
- Pipeline: points -> H3 -> create time column (BigQuery: `DATETIME_TRUNC(CAST(datetime AS TIMESTAMP), WEEK)`; Snowflake: `DATE_TRUNC('WEEK', datetime)`) -> GROUP BY (h3, time_bin) -> Getis-Ord Spacetime -> filter `p_value < 0.05 AND gi > 0`.
- The date column can be DATE, DATETIME or TIMESTAMP; on BigQuery the component casts it to DATETIME itself, so no CAST step is needed.
- Temporal bandwidth choice dramatically affects results. `bandwidth=1` detects rapid changes; `bandwidth=3+` smooths over longer trends.

## Spacetime Hotspot Classification (`native.spacetimehotspotsclassification`)

- Chains AFTER Getis-Ord Spacetime output. Set `indexcol` to `index` (Snowflake: the original index column name), `datecol` to `date` (Getis-Ord Spacetime renames the time column), and leave `valuecol` = `gi` and `pvaluecol` = `p_value` (their defaults).
- Classifies each cell's temporal trend: new hotspot, consecutive, intensifying, diminishing, sporadic, oscillating, historical. Output: `classification` (text), `tau`, `tau_p` and the index column. Check the exact `classification` values in the output table before filtering on them.
- Trend test: `algorithm` is `Mann-Kendall` (default) or `Modified Mann-Kendall`; `threshold` is one of `0.01`, `0.05` (default), `0.1`, `1`.
- Do NOT filter by `p_value` before classification: the trend test needs every time step.
- Pipeline: ... -> Getis-Ord Spacetime -> Spacetime Hotspots Classification.

## Time Series Clustering (`native.timeseriesclustering`)

- Groups locations by similarity of their temporal Gi* pattern.
- Chain: Getis-Ord Spacetime -> filter significant cells -> Cluster Time Series.
- Inputs: `partitioning_col` = the index column, `ts_col` = `date`, `value_col` = `gi`, `method`, and `n_clusters` (no default: ask the user how many groups they want). Output: the index column plus `cluster`.
- Method: `Profile` (shape-based) or `Value` (magnitude-based), capitalized exactly like this.
- Keep only cells significant in at least 60% of time steps before clustering, to avoid clustering noise: add `sig` = `CASE WHEN p_value < 0.05 THEN 1 ELSE 0 END` with `native.selectexpression`, `native.groupby` by the index column with `sig,avg` (gives `sig_avg`), `native.where` `sig_avg >= 0.6`, then `native.join` (Inner) with the Getis-Ord Spacetime output as `maintable` and the `match` output as `secondarytable` on the index column.
