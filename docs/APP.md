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

The detail dataset is split into eight deterministic Parquet shards. The largest packaged file is approximately `2.54 MB`, below the Databricks Apps `10 MB` per-file limit.

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

## Current Boundary

Phase 4 is read-only. Reviewer decisions and notes are not yet durable and must not be represented as persisted.

Persistence is the next phase.
