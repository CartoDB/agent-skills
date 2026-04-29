---
name: carto-pattern-geocoding
description: Builds geocoding workflows in CARTO that convert street addresses or place names into geographic coordinates. Triggers when the user mentions geocoding, address to coordinates, address resolution, geolocate addresses, "add geometry from addresses", lat/lon from address, place name to point, address matching, forward geocoding, converting addresses to points, or has tabular data with address columns but no spatial geometry column and needs to create one.
license: MIT
---

# Geocoding Addresses in CARTO Workflows

Converts street addresses or place names into geographic coordinates (point geometries). This is an essential first step when working with tabular data that has an address column but no spatial column.

**Prerequisites**: Load `carto-create-workflow` for the development process, JSON structure, and validation commands.

---

## Instructions

A geocoding workflow follows this pipeline:

```
Source Table (with address column) -> Geocode -> (Filter successful) -> Save
```

### Step 1: Load Source Data

Use `native.gettablebyname`. The input table must contain a column with address strings (e.g. `address`, `full_address`, `location`).

**Success**: Node outputs a table with at least one text column containing address data.

### Step 2: Geocode

Use `native.geocode` with:

| Input | Description | Required |
|-------|-------------|----------|
| `source` | Table with address data | Yes |
| `address` | Column containing the address string | Yes |
| `country` | Country filter to improve accuracy (e.g. `"United States"`, `"United Kingdom"`) | No, but strongly recommended |

The address column can contain full addresses (`"123 Main St, Springfield, IL 60001"`) or composite values built from multiple columns (concatenate street + city + postal code in a prior `native.selectexpression` step).

**Two output handles**: The geocode component produces two separate outputs:
- **`match`**: Rows where geocoding succeeded -- a `geom` column with point geometry is added, plus a `CARTO_GEOCODE_METADATA` JSON column with quality info (confidence score, match type).
- **`unmatch`**: Rows where geocoding failed -- `geom` is NULL.

Connect downstream nodes to the correct handle based on your needs.

**Success**: The geocode node is configured with the address column and (ideally) a country filter. Edges connect to the `match` and/or `unmatch` output handles.

### Step 3: Filter or Review Results (optional)

For the **match** output:
- Optionally filter by confidence using the metadata column (e.g. extract confidence from `CARTO_GEOCODE_METADATA` via `native.selectexpression`).

For the **unmatch** output:
- Save to a separate table for review and manual correction.
- Common failure causes: typos, incomplete addresses, PO boxes, ambiguous place names.

**Success**: High-confidence geocoded rows are isolated; failed rows are captured for review.

### Step 4: Save Results

Use `native.saveastable` to persist the geocoded output. The `geom` column contains WGS84 (EPSG:4326) point geometries, ready for visualization in CARTO Builder or further spatial analysis.

**Success**: Validated workflow that can be uploaded via `carto workflows create`.

---

## Geocoding Under the Hood

The workflow component wraps the CARTO Analytics Toolbox function `GEOCODE_TABLE`, which:
- Adds a `geom` column with point geometry to each row
- Adds a `CARTO_GEOCODE_METADATA` JSON column with quality information (confidence, match type)
- Uses CARTO Location Data Services (LDS) -- each geocoded row consumes LDS quota

Check available quota:
```sql
SELECT * FROM CARTO_DATASERVICES.CARTO.LDS_QUOTA_INFO()
```

---

## Gotchas

- **Geocoding consumes LDS quota.** Each row geocoded counts against the account's Location Data Services quota. Check quota availability before bulk operations, especially on large tables.
- **Two output handles: `match` and `unmatch`.** Don't connect to the wrong one -- `match` has geometries, `unmatch` has NULLs. If you connect the `unmatch` handle to a spatial operation, it will fail.
- **Country filter is strongly recommended.** Without it, ambiguous addresses may resolve to the wrong country (e.g. "Springfield" exists in 30+ US states and in other countries). The country parameter improves both accuracy and speed.
- **Address formatting matters.** Well-formatted addresses produce better results: `"123 Main St, Springfield, IL 60001"` works better than `"123 main street springfield"`. Include city, state/region, and postal code when available.
- **On Snowflake, the metadata column name is uppercased.** Use `CARTO_GEOCODE_METADATA` in expressions. Column casing follows the provider's conventions.
- **For large tables, consider batching.** Geocoding hundreds of thousands of rows in a single run can exhaust quota or time out. Split into batches if needed.
- **Output geometry is always WGS84 points.** The `geom` column contains EPSG:4326 point geometries regardless of the input address format or country.
- **Failed geocodes deserve review.** The `unmatch` output is not just noise -- it often reveals data quality issues (missing postal codes, abbreviated city names, non-standard formatting) that can be fixed and re-geocoded.

---

## Reference Templates

Academy tutorials and workflow templates covering geocoding:

| Resource | Description | URL |
|----------|-------------|-----|
| Geocoding (BigQuery AT) | Step-by-step geocoding with Analytics Toolbox for BigQuery | [Academy link](https://academy.carto.com/advanced-spatial-analytics/spatial-analytics-for-bigquery/step-by-step-tutorials/geocoding-your-address-data) |
| Geocoding (Snowflake AT) | Step-by-step geocoding with Analytics Toolbox for Snowflake | [Academy link](https://academy.carto.com/advanced-spatial-analytics/spatial-analytics-for-snowflake/step-by-step-tutorials/geocoding-your-address-data) |
| Workflow template: Geocode street addresses | Generating new spatial data from addresses | [Academy link](https://academy.carto.com/creating-workflows/workflow-templates/generating-new-spatial-data) |

---

## Common Variations

| Variation | How |
|-----------|-----|
| Composite address from multiple columns | Add a `native.selectexpression` step before geocoding to concatenate street, city, state, zip into one column |
| Geocode + spatial join | Chain: Geocode -> match -> Spatial Join (e.g. point-in-polygon to assign regions) |
| Geocode + enrichment | Chain: Geocode -> match -> Buffer/Isochrone -> Enrich (add demographics around each geocoded point) |
| Capture failures for re-processing | Connect both `match` and `unmatch` handles to separate `native.saveastable` nodes |
| Filter by confidence | After geocode, use `native.selectexpression` to extract confidence from the metadata JSON, then filter |
