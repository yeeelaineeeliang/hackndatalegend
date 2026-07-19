# Data Readiness Desk — a lie detector for hospital capability claims

**Live app:** https://data-readiness-desk-7474649574693760.aws.databricksapps.com · Databricks Apps, Free Edition · Track: `Data Readiness Desk`

In India, a family can drive six hours to a hospital whose ICU was a claim, not a capability. We ran every capability claim in the 10,000-facility challenge dataset against the operational evidence in its own record — equipment, staff, procedures — and the results are the argument for this product:

- **1,061 facilities claim an ICU with zero supporting evidence anywhere in their record.**
- Of `6,616` facilities claiming high-acuity care (ICU, trauma, NICU, maternity, oncology, cardiac, dialysis, surgery), only **`681` — about 10% — are fully evidence-backed**.
- **38% of the entire dataset** contains at least one capability claim with no textual support at all.
- The consolidated record ranked #1 for review contains a maternity claim that literally cites *a different hospital*.

Planners cannot act on claims like these. The Data Readiness Desk is the trust gate in front of them: every suspicious claim is flagged with the **exact text that was searched and what was — or wasn't — found**, ranked by where review most changes planning outcomes, and every human decision persists as a durable, auditable record.

## What It Does

1. **Scores** all 10k records for completeness, evidence support, consistency, and leverage — precomputed, reproducible, versioned rules.
2. **Corroborates** every high-acuity capability claim against operational evidence across fields; uncorroborated claims are flagged with receipts.
3. **Ranks** a review queue by where human attention most improves the dataset.
4. **Persists** reviewer decisions (confirm / needs review / incorrect claim / missing evidence / resolved, plus notes) in Lakebase Postgres — an append-only audit trail that survives sessions and redeploys.
5. **Admits what it doesn't know**: evidence scores are capped until claims align to exact source spans, and missing data is never presented as missing care.

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

1. "1,061 hospitals in this dataset claim an ICU with zero supporting evidence. A wrong referral is a family driving six hours for nothing. We built the trust gate that catches it."
2. Overview: the queue ranks 9,958 facilities by where human review most changes planning outcomes.
3. Open the #1 record: its maternity claim literally cites a different hospital — the flag shows the exact text we searched and what we found.
4. Record a decision with a note; it persists to Lakebase and the queue updates instantly.
5. The review log is the durable audit trail downstream planners inherit: human judgment becomes institutional knowledge.

## Deployment

The app ships to Databricks Apps from the `app/` directory (`app.yaml` is the entry point). After `databricks auth login`, sync `app/` to the workspace, create the app, and attach a Lakebase database resource so the decision store selects Postgres automatically.
