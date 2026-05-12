# Extraction tools — picking and using them

The `discover` skill enumerates items via the ArcGIS REST API. Two practical paths; the agent picks silently based on what's installed:

1. **`arcgis` Python package** (`pip install arcgis`) — high-level wrapper, nicer for paging and item-detail follow-ups.
2. **`curl` + `jq`** — zero-Python fallback; works anywhere.

Pick `arcgis` Python if `python3 -c "import arcgis"` succeeds without error. Otherwise use `curl` + `jq`.

## Auth patterns

### Anonymous (public AGOL only)

Some ArcGIS Online groups and items are publicly readable without auth. The `/sharing/rest/portals/self` endpoint will still respond, but the `user` field will be empty. Search results are limited to `access: public`.

```bash
curl -s "https://www.arcgis.com/sharing/rest/portals/self?f=json" | jq '.name'
```

### Token (recommended for Portals + AGOL accounts)

Tokens come from one of:

- A long-lived API token the user generates in the Portal/AGOL UI.
- A short-lived token from `/sharing/rest/generateToken` using `username` + `password`.
- An OAuth2 access token from a registered application's flow.

Read the token from the `ARCGIS_TOKEN` env var before prompting the user. Never log a token; never write it to the manifest.

`curl` with token:

```bash
curl -s "https://<portal>/sharing/rest/portals/self?f=json&token=$ARCGIS_TOKEN" | jq '.user.username'
```

`arcgis` Python with token:

```python
from arcgis.gis import GIS
gis = GIS("https://<portal>", token=os.environ["ARCGIS_TOKEN"])
print(gis.users.me.username)
```

### Username / password → exchange for a token

When the user can't supply a token directly:

```bash
curl -s -X POST "https://<portal>/sharing/rest/generateToken" \
  -d "username=$USERNAME" \
  -d "password=$PASSWORD" \
  -d "client=referer" \
  -d "referer=https://<portal>" \
  -d "expiration=120" \
  -d "f=json" \
  | jq -r '.token'
```

Use the returned token for the rest of the session. Don't store the password.

## Enumeration

### `arcgis` Python — page through items the user owns

```python
from arcgis.gis import GIS

gis = GIS(portal_url, token=token)
me = gis.users.me

batch_size = 100
items: list[dict] = []
start = 1
while True:
    page = gis.content.search(
        query=f"owner:{me.username}",
        max_items=batch_size,
        sort_field="modified",
        sort_order="desc",
    )
    items.extend(p.id for p in page)
    if len(page) < batch_size:
        break
    # arcgis-python doesn't expose `nextStart` directly; fall back to time-window slicing
    # for >10K orgs (rare). For most orgs, max_items=10000 with a single search call works.
```

For most Portals (< 10 K items) a single `gis.content.search(..., max_items=10000)` returns everything; use the loop above only when paging is needed.

### `curl` + `jq` — page through `/sharing/rest/search`

```bash
PORTAL="https://<portal>"
TOKEN="$ARCGIS_TOKEN"
QUERY='owner:bmunoz'   # URL-encode in your invocation
START=1
NUM=100

while :; do
  PAGE=$(curl -s "$PORTAL/sharing/rest/search" \
    --data-urlencode "q=$QUERY" \
    --data-urlencode "start=$START" \
    --data-urlencode "num=$NUM" \
    --data-urlencode "sortField=modified" \
    --data-urlencode "sortOrder=desc" \
    --data-urlencode "f=json" \
    --data-urlencode "token=$TOKEN")

  # collect items into a JSON array file
  echo "$PAGE" | jq '.results[]' >> MIGRATION_INVENTORY.ndjson

  NEXT=$(echo "$PAGE" | jq -r '.nextStart')
  [ "$NEXT" = "-1" ] && break
  START=$NEXT
done
```

Keep going until `nextStart == -1`. Don't rely on counting results — paging size can be smaller than `num` for various reasons.

### Scoping the search query

| Goal | `q` value |
|---|---|
| All items owned by current user | `owner:<username>` |
| All items in an org | `orgid:<orgid>` (from `/portals/self`) |
| Items in a specific group | `group:<groupid>` |
| Items in a specific folder | `ownerfolder:<folderid>` |
| Public AGOL only, by tag | `tags:"<tag>" access:public` |
| Filter by type | append ` type:"Feature Service"` (quote the type) |

The agent sets `q` based on the user's Phase-1 scope confirmation. Default is `owner:<username>`.

## Per-item detail follow-ups

Some classifications need more than the search result:

- **Web Map dependencies**: fetch `<portal>/sharing/rest/content/items/<id>/data?f=json` to read `operationalLayers[].url`.
- **Dashboard widget hints**: same endpoint; the `data` payload has `widgets[]` and `dataSources[]`.
- **Feature Service layer count**: fetch `<service-url>?f=json` to read `layers[]` and `tables[]`.
- **GP Service tasks**: fetch `<service-url>?f=json` to read `tasks[]`.

Cache every detail call into `MIGRATION_INVENTORY.json` so downstream skills don't re-hit the REST API.

## Rate limits and pagination

ArcGIS doesn't publish a hard rate limit, but the convention is < 600 requests/minute per user. The `discover` skill is well within this; downstream skills doing per-feature queries are not.

For paging:

- Always use a deterministic `sortField` (e.g. `modified` or `created`). Without it, page boundaries can shift between calls and skip / duplicate items.
- For very large orgs (> 10 K items), narrow the search with a time window (`modified:[2026-01-01T00:00:00Z TO 2026-12-31T23:59:59Z]`) and walk windows.

## When the agent should stop and ask

- 401 / 403 from the portal → ask for fresh credentials. Don't retry.
- > 10 K items in the user's scope → confirm whether to enumerate fully or filter.
- Any item type returns no usable URL or `id` → record the raw response in the inventory and surface as a manifest gap.
