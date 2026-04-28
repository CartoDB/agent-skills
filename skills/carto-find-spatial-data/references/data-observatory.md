# Discovering datasets in the Data Observatory

## Search

```bash
carto do search [options] --json
```

| Flag | Effect |
|---|---|
| `--keyword <term>` | Free-text search across name, description, tags. |
| `--country <code>` | ISO country code filter (`usa`, `gbr`, `esp`, …). |
| `--category <name>` | Filter by category (demographics, points-of-interest, mobility, environment, financial, …). |
| `--license free\|paid` | Free public-domain datasets vs licensed/paid. |
| `--page-size <n>` / `--page <n>` | Pagination. |

```bash
# US census tract demographics, free only
carto do search --keyword "census" --country usa --license free --json

# Mobility data globally, paid acceptable
carto do search --category mobility --license paid --json
```

The result is a list of dataset summaries: `{ id, name, provider, category, license, country, geography_level, time_coverage }`.

## Inspecting a dataset

```bash
carto do get <dataset-id> --json
```

Returns the full dataset record:

- **Schema** — column names and types (essential before subscribing — confirms the table will have the columns you need).
- **Coverage** — geographic extent (countries, regions) and temporal range.
- **Geography level** — block group, tract, ZIP code, country, H3 hex resolution, etc.
- **Update cadence** — how often the source data refreshes (monthly, quarterly, never, real-time).
- **License & pricing tier** — free, freemium, premium-tier-1, etc.
- **Provider** — original data publisher (US Census Bureau, Mastercard, etc.).

## Categories worth knowing

| Category | Typical datasets |
|---|---|
| `demographics` | Census, ACS, age/income/race aggregates, population estimates. |
| `points-of-interest` | Foursquare, OSM, Spatial.ai, brand POIs. |
| `boundaries` | Admin boundaries (countries, states, ZIP, postal codes), block groups, tracts. |
| `mobility` | Anonymous foot traffic, origin-destination flows, commute patterns. |
| `environmental` | Weather, climate, air quality, elevation. |
| `financial` | Mastercard transactional, Equifax, Yodlee. |
| `risk` | FEMA flood zones, wildfire risk, insurance loss. |
| `real-estate` | Property data, valuations, transactions. |

## Evaluating fit

Before recommending a dataset, check:

1. **Country coverage** matches the user's question.
2. **Geography level** is at or finer than what the analysis needs (you can aggregate up; you can't downscale without statistical inference).
3. **Time coverage** spans the user's date range.
4. **License** matches their plan and budget.

If any of these don't fit, surface that explicitly — pushing a dataset that "almost works" wastes a subscription slot.

## Listing your subscriptions

```bash
carto do subscriptions list --json
```

Shows datasets you've already subscribed to, with status (`active`, `expired`, `pending`), destination table, and last refresh timestamp.
