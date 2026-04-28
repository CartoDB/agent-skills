# Spatial SQL — BigQuery dialect

BigQuery's spatial functions live under the `ST_*` family. Geometries are `GEOGRAPHY` type — spheroid-aware (WGS84) by default.

## Canonical patterns

### Distance filter (point-in-radius)

```sql bigquery
SELECT id, name
FROM `my_project.demo.stores`
WHERE ST_DWithin(
  geom,
  ST_GeogPoint(-73.98, 40.75),
  1000              -- meters
)
```

### Spatial join (which polygon contains each point)

```sql bigquery
SELECT
  p.id        AS event_id,
  poly.name   AS neighborhood
FROM `my_project.demo.events` p
JOIN `my_project.demo.neighborhoods` poly
  ON ST_Contains(poly.geom, p.geom)
```

### H3 aggregation (CARTO's `carto-spatial-extension` H3 module on BQ)

```sql bigquery
SELECT
  `carto-un`.carto.H3_FROMGEOGPOINT(geom, 9) AS h3,
  COUNT(*) AS events
FROM `my_project.demo.events`
GROUP BY h3
```

### Buffer + area

```sql bigquery
SELECT
  id,
  ST_Area(ST_Buffer(geom, 500)) AS buffer_area_m2
FROM `my_project.demo.stores`
```

## Performance defaults

- **Cluster on geometry**: BigQuery supports clustering by `GEOGRAPHY` (`CLUSTER BY geom`). Tables CARTO imports are already clustered when possible.
- **Partition by date** when both date and geometry filters apply — the date partition prunes far more than spatial filters.
- **Avoid `SELECT *`** on tables with `GEOGRAPHY` columns: the geometry can be huge per row.
- **`bigquery-public-data.geo_*`** datasets are public and read-only — useful for joins to admin boundaries without a CARTO subscription.

## Gotchas

- `ST_GeogPoint(lng, lat)` — **longitude first**, latitude second. Reversing them silently produces points in the wrong hemisphere.
- BigQuery `GEOGRAPHY` is on the spheroid; `ST_Distance(a, b)` returns meters, not degrees.
- Mixing `GEOGRAPHY` (BQ) with `GEOMETRY` (Snowflake/Postgres) styles: not interchangeable. BigQuery has no `GEOMETRY` type.
