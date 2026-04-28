# Spatial SQL — Snowflake dialect

Snowflake supports two types: `GEOGRAPHY` (WGS84, spheroid) and `GEOMETRY` (planar). Functions are uppercase and prefixed `ST_`.

## Canonical patterns

### Distance filter

```sql snowflake
SELECT id, name
FROM ANALYTICS.PUBLIC.STORES
WHERE ST_DWITHIN(
  geom,
  ST_MAKEPOINT(-73.98, 40.75),
  1000              -- meters when geom is GEOGRAPHY
)
```

### Spatial join

```sql snowflake
SELECT
  p.id        AS event_id,
  poly.name   AS neighborhood
FROM ANALYTICS.PUBLIC.EVENTS p
JOIN ANALYTICS.PUBLIC.NEIGHBORHOODS poly
  ON ST_CONTAINS(poly.geom, p.geom)
```

### H3 aggregation (Snowflake-native H3, no extension required)

```sql snowflake
SELECT
  H3_LATLNG_TO_CELL(ST_Y(geom), ST_X(geom), 9) AS h3,
  COUNT(*) AS events
FROM ANALYTICS.PUBLIC.EVENTS
GROUP BY h3
```

### Buffer + area

```sql snowflake
SELECT
  id,
  ST_AREA(ST_BUFFER(geom, 500)) AS buffer_area_m2
FROM ANALYTICS.PUBLIC.STORES
```

## Performance defaults

- Snowflake doesn't have a spatial index per se, but **clustering keys** on geometry-derived columns (e.g. an H3 index) accelerate filters.
- Pre-compute and store H3 cells as a column for high-cardinality spatial filtering — avoids repeated `H3_LATLNG_TO_CELL` calls.
- Larger warehouse sizes parallelize spatial joins more aggressively; if a join is too slow, scale up before optimizing the SQL.

## Gotchas

- **Function casing matters in some contexts** — `ST_DWITHIN` (uppercase) is the canonical form; lowercase `st_dwithin` works in queries but is inconsistent in shared scripts.
- `ST_MAKEPOINT(longitude, latitude)` — longitude first.
- `GEOGRAPHY` vs `GEOMETRY`: `ST_AREA` returns m² for `GEOGRAPHY` and the unit of the SRID for `GEOMETRY`. Don't mix them in one query.
