# Reviewer Application

## Purpose

The Streamlit application turns the materialized trust outputs into the reviewer workflow required by the Data Readiness Desk track.

The application is packaged under `app/` as an independent Databricks Apps source directory.

## Workflow

### Readiness Overview

- flagged facility count
- contradiction count
- weak-evidence count
- high-leverage count
- issue-type distribution
- highest-priority records

### Review Queue

Filters:

- facility name, city, or PIN
- state or region
- issue type
- claim theme
- severity
- minimum review priority

The table preserves deterministic queue rank. The reviewer can open any matching facility.

### Facility Detail

The detail workflow shows:

- facility profile and geography confidence
- readiness, completeness, evidence, consistency, and leverage scores
- why the record is high priority
- long-form flag explanations
- exact field or extracted-claim receipts
- claim lists and parse states
- facility-level source links

Claim themes are keyword-derived navigation aids. They are not verified medical classifications.

## Deployment Package

Files:

- `app/app.py`
- `app/data_access.py`
- `app/app.yaml`
- `app/requirements.txt`
- `app/data/`

The detail dataset is split into eight deterministic Parquet shards. The largest packaged file is approximately `4.2 MB`, below the Databricks Apps `10 MB` per-file limit.

The package does not include the `36 MB` full analysis base.

## Refresh

After regenerating trust outputs, rebuild the app package:

```bash
python3 -m src.app_data.build_app_assets
```

This command also writes:

`outputs/validation/app_asset_validation.json`

Current result:

- `6` checks passed
- `0` warnings
- `0` failures

## Run Locally

```bash
cd app
python3 -m pip install -r requirements.txt
streamlit run app.py
```

## Deploy To Databricks Apps

Use `app/` as the deployment source directory. Its `app.yaml` starts Streamlit with:

```text
streamlit run app.py
```

Databricks Apps installs `app/requirements.txt` during deployment.

Official references:

- https://docs.databricks.com/aws/en/dev-tools/databricks-apps
- https://docs.databricks.com/aws/en/dev-tools/databricks-apps/deploy
- https://docs.databricks.com/gcp/en/dev-tools/databricks-apps/app-runtime

## Persistence

Reviewer decisions are durable. `app/review_store.py` is an append-only store:

- on Databricks Apps with a database resource attached, decisions are written
  to Lakebase Postgres (`review_decisions` table), outside the app filesystem,
  so they survive restarts and redeploys
- locally, a SQLite file is used for development
- the sidebar displays the active backend; if Lakebase is configured but
  unreachable, the decision form shows an explicit fallback warning instead of
  claiming durable persistence
- the latest decision per facility defines queue status; history is never
  overwritten and is visible in the Review log tab with CSV export

Verified in production on `July 19, 2026`: a decision recorded through the
deployed app was read back directly from the Lakebase instance.
