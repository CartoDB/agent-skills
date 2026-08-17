# Discovering datasets in the Data Observatory

Discovery works on any MCP session (OAuth or token) via `search_data_observatory`, or on the CLI via `carto do`. Same filters and result shape on both.

## Search

- **MCP:** `search_data_observatory` `method: "list_datasets"` with `keyword`, `country`, `category`, `license`, and pagination fields. Use `method: "list_filters"` to enumerate the valid filter values, and `method: "search_variables"` to search individual columns/variables across datasets.
- **CLI:** `carto do search [options] --json`.

| Filter | Effect |
|---|---|
| `keyword` / `--keyword <term>` | Free-text across name, description, tags. |
| `country` / `--country <code>` | ISO country code (`usa`, `gbr`, `esp`, …). |
| `category` / `--category <name>` | demographics, points-of-interest, mobility, environment, financial, … |
| `license` / `--license free\|paid` | Free public-domain vs licensed/paid. |
| page size / page | Pagination. |

```bash
# US census tract demographics, free only
carto do search --keyword "census" --country usa --license free --json

# Mobility data globally, paid acceptable
carto do search --category mobility --license paid --json
```

Results are dataset summaries: `{ id, name, provider, category, license, country, geography_level, time_coverage }`.

## Inspecting a dataset

`search_data_observatory` `method: "get_dataset"` (or `method: "sample"` to preview rows), or `carto do get <dataset-id> --json`. Returns the full record:

- **Schema** — column names and types (confirm the table will have the columns you need before subscribing).
- **Coverage** — geographic extent (countries, regions) and temporal range.
- **Geography level** — block group, tract, ZIP code, country, H3 hex resolution, etc.
- **Update cadence** — monthly, quarterly, never, real-time.
- **License & pricing tier** — free, freemium, premium-tier-1, etc.
- **Provider** — original publisher (US Census Bureau, Mastercard, etc.).

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
2. **Geography level** is at or finer than the analysis needs (you can aggregate up; you can't downscale without statistical inference).
3. **Time coverage** spans the user's date range.
4. **License** matches their plan and budget.

If any don't fit, surface that explicitly — pushing a dataset that "almost works" wastes a subscription slot.

## Listing your subscriptions

`manage_data_observatory_subscriptions` `method: "list"` (OAuth session), or `carto do subscriptions list --json`. Shows datasets already subscribed, with status (`active`, `expired`, `pending`), destination table, and last refresh timestamp.
