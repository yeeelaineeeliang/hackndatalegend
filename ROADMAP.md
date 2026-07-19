# ROADMAP.md

## Purpose

This document is the working execution map for the hackathon project. It is meant to:

- keep the build sequence explicit
- define what "done" means for each phase
- show current status at a glance
- make pivots easier if the project needs to change direction

## Project Summary

- challenge: Databricks hackathon, trust layer for Indian healthcare
- selected track: `Data Readiness Desk`
- product thesis: build the review gate that decides what must be fixed before planners can trust facility data
- primary workflow: flag -> validate -> inspect -> decide -> persist

## Status Legend

- `not started`
- `in progress`
- `blocked`
- `done`

## Phase Overview

### Phase 0: Foundations

Goal:

- establish a clean repo, clear docs, stable raw inputs, and source constraints

Deliverables:

- repo docs
- source inventory
- raw source copies in canonical locations
- initial profiling outputs

Done means:

- all current source files live inside the repo
- source grain and join risks are documented
- initial profiling outputs are reproducible

Status:

- `done`

Notes:

- completed by `July 18, 2026`

### Phase 1: Reference Data Layer

Goal:

- create clean, reusable support tables from supplemental data

Deliverables:

- cleaned `pincode_lookup`
- `pincode_ambiguity_report`
- NFHS column mapping
- district and state normalization map
- documented join strategy for geography

Done means:

- we have a canonical policy for how to use ambiguous PIN mappings
- NFHS columns are normalized and ready for loading
- downstream code can join against prepared reference tables without touching raw files

Status:

- `done`

Risks:

- ambiguous PIN-to-district mappings
- district naming inconsistencies across datasets

Notes:

- completed by `July 18, 2026`
- conservative PIN join policy documented in `docs/REFERENCE_LAYER.md`
- cleaned NFHS output generated and ready for downstream use
- invalid coordinate pairs are quarantined from preferred coordinate means
- unresolved NFHS/PIN geography names are blocked from automatic joining

### Phase 1.5: Validation And Reproducibility

Goal:

- turn documented trust rules into executable quality gates

Deliverables:

- pinned local Python environment
- supplemental validation report
- coordinate quarantine output
- cross-source geography review candidates
- unit and integration tests
- facility schema contract derived from challenge reference materials

Done means:

- structural failures return a non-zero command status
- source warnings remain visible and cannot silently enter trusted joins
- the full supplemental pipeline can be rerun from documented commands

Status:

- `done`

Current validation result:

- `9` checks passed
- `2` source-quality warnings
- `0` failures

### Phase 2: Main Facility Data Intake

Goal:

- bring in the challenge healthcare facility dataset and convert it into an analysis-ready base table without losing provenance

Deliverables:

- raw facility dataset staged in repo or accessible in Databricks
- schema profile
- null coverage report
- normalized core fields
- preserved raw claims and source text fields
- ingestion validation checks for schema, parsing, and joins

Done means:

- we understand the grain, key identifiers, and field reliability of the facility data
- the base table is stable enough to build scoring on top of it
- validation catches structurally unsafe rows before scoring begins

Status:

- `done`

Current result:

- `10,088` raw rows preserved
- `10,000` structurally valid facility rows
- `9,989` unique scoring-eligible facility rows
- all `51` raw columns preserved unchanged in the normalized analysis base
- `36` provenance and normalization columns added
- `6` normalization checks passed, `3` warnings remain visible, `0` failed

Notes:

- completed by `July 18, 2026`
- canonical source: `data/raw/facilities/healthcare_facilities.csv`
- analysis base: `data/processed/facilities_analysis_base.parquet`
- malformed rows and exact duplicate copies remain preserved but are excluded from scoring
- normalization policy is documented in `docs/NORMALIZED_FACILITY_LAYER.md`

### Phase 3: Trust Logic

Goal:

- define how the app decides what is incomplete, suspicious, contradictory, or high leverage

Deliverables:

- completeness scoring
- evidence support checks
- consistency checks
- high-leverage scoring
- decision validation rules
- facility-level flags table

Done means:

- every major flag can be explained clearly
- scores are reproducible
- output can be ranked into a review queue
- weak or contradictory evidence is explicitly surfaced as validation state, not hidden inside the score

Status:

- `done`

Key principle:

- trust logic must be evidence-backed, not just heuristic labels with no receipts

Current result:

- `9,989` facility-level trust signal rows
- long-form evidence-backed flags, including claim-vs-evidence corroboration flags
- `9,958` ranked review-queue rows
- claim corroboration (rules `v1.1.0`): high-acuity capability claims are checked
  for operational evidence across description, procedure, and equipment;
  `6,616` facilities claim high-acuity themes, only `681` are fully corroborated
- evidence support capped at `75` while claim-to-source alignment is unavailable
- `6` trust-output validation checks passed, `1` warning remains visible, `0` failed

Notes:

- completed by `July 18, 2026`
- formulas and limitations documented in `docs/TRUST_SCORING.md`
- scoring rules versioned in `config/trust_scoring_rules.json`

### Phase 4: Review Queue Product Layer

Goal:

- convert trust outputs into a workflow a reviewer can actually use

Deliverables:

- dataset readiness overview
- ranked flagged queue
- filter controls
- issue type grouping
- facility detail view showing evidence and gaps
- validation warnings and confidence state in the detail workflow

Done means:

- a reviewer can open the app and understand what to inspect first
- each flagged record explains why it is in the queue

Status:

- `done`

Current result:

- responsive Streamlit reviewer application implemented
- readiness overview and issue distribution implemented
- queue filters cover geography, issue type, claim theme, severity, and priority
- facility detail exposes scores, profile fields, claim lists, source links, and flag receipts
- deployment assets split into eight deterministic shards
- largest packaged file is approximately `2.54 MB`
- `6` app-asset validation checks passed, `0` warnings, `0` failed

Notes:

- completed by `July 18, 2026`
- application workflow documented in `docs/APP.md`
- browser-verified on desktop and mobile
- persistence remains intentionally out of scope until Phase 5

### Phase 5: Persistence

Goal:

- make reviewer actions durable

Deliverables:

- review decisions store
- reviewer notes
- override handling if needed
- timestamps and status history

Done means:

- decisions survive across sessions
- the queue reflects prior human review

Status:

- `done`

Why it matters:

- this is a core challenge requirement, not an optional extra

Current result:

- append-only decision store in `app/review_store.py` with a full audit trail
- backend auto-detection: Lakebase Postgres on Databricks Apps, SQLite locally
- facility decision form, live queue status, review-status filter, impact
  metrics, and a review-log tab with CSV export
- round-trip tested: latest decision wins, queue and filters reflect it

### Phase 6: Competition Differentiation

Goal:

- add one feature that clearly improves the judging story beyond the minimum workflow

Preferred differentiator:

- `high-leverage ranking`

Possible stretch deliverables:

- before/after readiness improvement view
- traceability view from claim to score to flag
- explicit `data desert` vs `medical desert` indicators

Done means:

- we can point to one meaningful capability beyond a basic review dashboard

Status:

- `done`

Current result:

- claim-vs-evidence corroboration answers the challenge's marquee Trust Scorer
  question: an ICU claim with no ventilator, intensivist, or critical-care
  evidence is flagged with a receipt showing exactly what was searched
- high-leverage ranking and explicit data-desert messaging are also live

### Phase 7: Demo And Submission

Goal:

- make the project legible, reliable, and persuasive under hackathon constraints

Deliverables:

- one-minute demo path
- concise repo readme for judges
- architecture summary
- submission checklist
- stable app deployment

Done means:

- the demo works end-to-end without improvisation
- the narrative clearly covers user, workflow, technical approach, and tradeoffs

Status:

- `in progress`

Remaining:

- Databricks CLI OAuth login (interactive, user-run)
- deploy to Databricks Apps and attach a Lakebase database resource
- live end-to-end verification of the demo path

## Execution Order

1. finish the supplemental reference layer
2. ingest and profile the main facility dataset
3. build trust logic and flags
4. materialize the review queue
5. build the app shell
6. add persistence
7. add one differentiator
8. tighten demo and submission

## Critical Decision Rules

When choosing what to do next, prefer work that:

1. reduces demo risk
2. improves evidence and trust
3. adds validation where confidence could otherwise be overstated
4. clarifies the reviewer workflow
5. strengthens persistence or traceability

Avoid work that:

- adds scope without improving judging criteria
- looks impressive but is hard to demo reliably
- depends on unverified geography assumptions
- hides uncertainty instead of exposing it

## Progress Snapshot

### Completed

- project docs created
- hackathon strategy documented
- supplemental datasets staged in repo
- canonical raw data paths established
- supplemental profiling pass completed
- first derived reference artifacts generated
- supplemental validation gate implemented
- challenge schema and extraction prompts reconciled
- reproducible environment and tests added
- main facility dataset staged with a checksum manifest
- facility intake and normalization gates executed on the full dataset
- provenance-preserving facility analysis base generated
- explainable trust scores and long-form flags generated
- deterministic ranked review queue materialized
- responsive reviewer application and deployment-safe assets completed

### In Progress

- implement durable reviewer decisions and notes

### Next

- persist reviewer decisions and notes
- update queue status from prior review decisions
- add a visible audit history to facility detail

## Pivot Guidance

If the current plan stops making sense, evaluate pivots in this order:

1. keep the same track, simplify implementation
2. keep the trust logic, narrow the feature surface
3. keep the data layer, reduce UI ambition
4. only consider changing tracks if the main dataset makes Data Readiness Desk unworkable

A pivot is justified only if it improves:

- reliability
- evidence quality
- demo clarity
- score potential against the judging rubric

## Definition Of Success

The project is successful if the final submission makes this argument convincingly:

"Planners should not trust raw facility claims. Our app validates the data, identifies what must be reviewed first, shows the evidence behind each concern, and preserves human decisions so downstream planning starts from a safer dataset."
