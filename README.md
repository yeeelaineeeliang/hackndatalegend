# dataLegend

Hackathon workspace for the Databricks challenge: building the trust layer for Indian healthcare.

Current focus:

- Track: `Data Readiness Desk`
- Product: reviewer-facing app that identifies which healthcare facility records must be fixed before planners can trust the dataset
- Outcome: ranked review queue, evidence-backed flags, persisted reviewer decisions

## Repository Purpose

This repo is the execution workspace for:

- dataset profiling
- scoring and flag generation
- app development
- demo preparation
- submission packaging

## Core Problem

The challenge dataset contains messy structured and unstructured facility records. Claims such as ICU, trauma, or maternity capability may be incomplete, unsupported, or contradictory. Planners should not act directly on those claims.

This project builds a `Data Readiness Desk` that helps reviewers:

- find incomplete records
- detect suspicious or contradictory claims
- prioritize high-leverage fixes
- persist review decisions for downstream planning use

## Planned Workflow

1. Ingest and profile the dataset.
2. Compute completeness, evidence support, contradiction, and leverage signals.
3. Produce a ranked review queue.
4. Build an app for inspection, review, and note-taking.
5. Persist reviewer decisions.
6. Package a clean live demo and submission.

## Expected Repository Structure

This structure can evolve, but this is the intended shape:

```text
.
├── README.md
├── PROJECT.md
├── AGENTS.md
├── HACKATHON_PLAN.md
├── data/
├── notebooks/
├── src/
├── app/
├── outputs/
└── docs/
```

## Documentation Guide

- `README.md`: fast orientation and repo usage
- `PROJECT.md`: product scope, architecture, and delivery plan
- `ROADMAP.md`: phased execution plan, status tracker, and pivot reference
- `AGENTS.md`: working rules for human and AI collaborators
- `HACKATHON_PLAN.md`: competition strategy and track-specific product framing
- `DATA_SOURCES.md`: source overview, enrichment datasets, and join-risk guidance
- `docs/REFERENCE_LAYER.md`: canonical cleaned-reference policy for PIN and NFHS joins
- `docs/EXTRACTION_CONTRACT.md`: reconciled facility schema, evidence rules, and prompt caveats
- `docs/FACILITY_INTAKE.md`: challenge dataset access, staging, profiling, and validation
- `docs/NORMALIZED_FACILITY_LAYER.md`: canonical analysis-base transformations and provenance policy
- `docs/TRUST_SCORING.md`: score formulas, flag traceability, review ranking, and limitations
- `docs/APP.md`: reviewer workflow, deployment package, local run, and Databricks deployment

## Local Environment

Create an isolated environment and install the pinned dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

Run the current pipeline:

```bash
python3 -m src.profiling.profile_supplemental_data
python3 -m src.profiling.clean_supplemental_data
python3 -m src.validation.validate_supplemental_data
python3 -m src.ingestion.facility_intake data/raw/facilities/healthcare_facilities.csv
python3 -m src.processing.normalize_facilities
python3 -m src.scoring.build_trust_signals
python3 -m src.app_data.build_app_assets
python3 -m unittest discover -v
```

The validation command exits non-zero for structural failures. Source uncertainty that has been quarantined remains visible as a warning.

## Current Data Readiness

The challenge export is staged and normalized. The canonical analysis base contains `9,989` unique scoring-eligible facilities while retaining every malformed and duplicate source row for audit.

The trust layer materializes traceable, receipt-backed flags and a ranked queue of `9,958` facilities. Claim-vs-evidence corroboration (rules `v1.1.0`) checks every high-acuity capability claim — ICU, emergency and trauma, NICU, maternity, oncology, cardiac, dialysis, surgery — for operational evidence across description, procedure, and equipment: of `6,616` facilities claiming high-acuity care, only `681` are fully corroborated, and `3,799` carry at least one claim with no supporting evidence anywhere in the record.

Evidence support remains explicitly capped at `75` because the export does not align each extracted claim to an exact source span. The app says so out loud instead of hiding it.

## The Reviewer App

The application under `app/` provides:

- readiness overview with issue distribution and impact metrics
- filterable ranked review queue that reflects live review status
- facility detail with scores, claims, corroboration state, and flag receipts
- reviewer decision form: confirm, needs review, incorrect claim, missing evidence, or resolved, plus a durable note
- append-only review log with CSV export

Decisions persist in Lakebase Postgres when deployed on Databricks Apps with a database resource attached, and in local SQLite during development. The latest decision per facility defines its queue status; history is never overwritten.

Run locally:

```bash
cd app
streamlit run app.py
```

## One-Minute Demo Path

1. Planners cannot trust raw facility claims, so we built the Data Readiness Desk.
2. Overview: the queue ranks 9,958 facilities by where review matters most.
3. Open a top-priority facility: it claims ICU care, but no ventilator, intensivist, or critical-care evidence exists anywhere in the record — the flag shows exactly what was searched.
4. Record the decision "incorrect claim" with a note; it persists and the queue updates.
5. The review log shows the durable audit trail downstream planners inherit.

## Deployment

The app ships to Databricks Apps from the `app/` directory (`app.yaml` is the entry point). After `databricks auth login`, sync `app/` to the workspace, create the app, and attach a Lakebase database resource so the decision store selects Postgres automatically.
