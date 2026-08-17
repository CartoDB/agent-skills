# BigQuery connection

## Auth modes

- **OAuth (interactive)** — user logs in via Google; best for one-off / interactive usage.
- **Service account JSON** — best for shared/team connections and CI; the JSON key is uploaded once and CARTO uses it on every operation.

CARTO's hosted "carto_dw" connection (auto-provisioned for paid orgs) is BigQuery-backed. If `connections list` shows a connection called `carto_dw`, that's it — use it before creating a new BQ connection.

## Required fields when creating

- **Project ID** — e.g. `my-gcp-project-12345`. Must be the project that hosts the datasets CARTO will read/write. Billing project may differ; defaults to the same.
- **Service account JSON** (when not using OAuth) — the file uploaded contains `client_email`, `private_key`, etc.
- **Default dataset** (optional but recommended) — where CARTO writes tilesets and named-source materializations.

## Minimum IAM (service account)

- `roles/bigquery.dataEditor` on the dataset(s) CARTO will write to.
- `roles/bigquery.dataViewer` on datasets it will only read.
- `roles/bigquery.jobUser` on the project (to run queries / load jobs).
- `roles/bigquery.readSessionUser` if using the BigQuery Storage API (faster reads).

For the carto-demo-data project (read-only public data CARTO ships):

- `roles/bigquery.dataViewer` on `carto-demo-data` (or rely on default public access).

## Creating it

The fields above feed either `manage_connections` (`create`, MCP) or the interactive `carto connections create` (choose provider `bigquery`, auth `service-account`, upload the JSON key, set `project_id` and `default_dataset`). Verify with a `describe` on a known table, e.g. `carto-demo-data.demo_tables.nyc_collisions`.

## Troubleshooting

- **"BigQuery API has not been used in project X"** — enable `bigquery.googleapis.com` and `bigquerystorage.googleapis.com` in the GCP console.
- **Auth works but queries 404** — wrong default project. The CLI/UI shows the project in the connection — confirm it matches where the dataset actually lives.
- **`AccessDenied` on writes** — the service account lacks `dataEditor` on the target dataset.
