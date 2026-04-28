# Spatial SQL — Postgres / PostGIS dialect

PostGIS exposes the canonical `ST_*` function family. Default geometry type is `GEOMETRY` (planar with a stored SRID, usually 4326). `GEOGRAPHY` is also supported for spheroid-true distance calculations.

This dialect also applies to **Redshift**, which mirrors most PostGIS spatial functions (with caveats — see end of doc).

## Canonical patterns

### Distance filter (radius in meters)

```sql postgres
SELECT id, name
FROM stores
WHERE ST_DWithin(
  geom::geography,
  ST_SetSRID(ST_MakePoint(-73.98, 40.75), 4326)::geography,
  1000           -- meters; cast to GEOGRAPHY for spheroid distance
)
```

If `geom` is already `GEOGRAPHY`, the cast is unnecessary.

### Spatial join

```sql postgres
SELECT
  p.id      AS event_id,
  poly.name AS neighborhood
FROM events p
JOIN neighborhoods poly
  ON ST_Contains(poly.geom, p.geom)
```

For best performance, **both tables need GiST indexes on `geom`**:

```sql postgres
CREATE INDEX events_geom_gix       ON events       USING GIST (geom);
CREATE INDEX neighborhoods_geom_gix ON neighborhoods USING GIST (geom);
```

### H3 aggregation

PostGIS doesn't ship H3 natively; CARTO's spatial extension installs `h3_lat_lng_to_cell` in the org's database. If the extension is present:

```sql postgres
SELECT
  carto.h3_lat_lng_to_cell(ST_Y(geom), ST_X(geom), 9) AS h3,
  COUNT(*) AS events
FROM events
GROUP BY h3
```

If the extension is not installed, fall back to a lat/lng grid bucket.

### Buffer + area

```sql postgres
SELECT
  id,
  ST_Area(ST_Buffer(geom::geography, 500)) AS buffer_area_m2
FROM stores
```

## Performance defaults

- **Always have a GiST index on geometry columns.** Without one, even `ST_DWithin` does a full table scan.
- **Cast to `GEOGRAPHY` for distance in meters**; native `GEOMETRY` distance is in the SRID's units (degrees for SRID 4326 = useless).
- **`ST_SetSRID` + `ST_MakePoint`** is the safe way to construct a point — `ST_GeomFromText('POINT(...)', 4326)` also works but is slower.

## Redshift differences

- Redshift supports most PostGIS functions but not all (no `ST_GeogFromText`; no `H3_*`).
- Redshift Serverless billing per query — favor `sql job` over many small `sql query` calls.
- Spatial indexes are implicit / managed by Redshift — no explicit `CREATE INDEX` needed.

## Gotchas

- `ST_MakePoint(lng, lat)` — longitude first.
- Default SRID on a fresh `GEOMETRY` column is `0` (unknown). `ST_SetSRID` it to `4326` immediately, or distance functions will return nonsense.
- `ST_DWithin` requires both arguments in the **same SRID**. Use `ST_Transform` if mixing.
