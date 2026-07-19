# PROJECT.md

## Project Name

`Data Readiness Desk`

## Challenge Context

This project is for the Databricks hackathon challenge focused on trusted healthcare intelligence for India. The challenge provides approximately 10,000 healthcare facility records with both structured fields and messy free-text claims. The goal is to build a deployable Databricks App that helps a non-technical user make better decisions from imperfect data.

We are intentionally focusing on one mission track:

- `Data Readiness Desk`

## Product Goal

Build a reviewer-facing application that determines what must be fixed before the dataset can be trusted for planning.

The app should surface:

- completeness gaps
- unsupported claims
- contradictory evidence
- high-leverage records where review most improves dataset usefulness

## Target User

Primary user:

- NGO or public-health operations reviewer validating healthcare facility data before planners use it

Secondary user:

- downstream planner who benefits from a cleaner, more trustworthy dataset after review decisions are recorded

## Product Principles

1. Evidence first.
   Every important output must point back to the exact field text or structured values that support it.

2. Honest uncertainty.
   Missing or weak evidence must be communicated clearly instead of masked behind confident scores.

3. Fix what matters most.
   The app should prioritize records whose correction most changes planning quality.

4. Human decisions persist.
   Review notes and overrides are durable product outputs, not temporary UI state.

5. Demo reliability over complexity.
   Precomputed signals are preferable to fragile live inference if that improves clarity and execution quality.

6. Validation before trust.
   Derived scores and joins must pass explicit validation checks before they are presented as decision-ready outputs.

## Scope

### In Scope

- dataset profiling
- data validation
- field coverage analysis
- rule-based or hybrid trust/readiness scoring
- decision validation
- ranked flagged review queue
- evidence inspection view
- reviewer notes and decisions
- persisted status changes
- one-minute live demo workflow

### Out of Scope for Initial Build

- full referral recommendation engine
- multi-track implementation
- heavy live agent orchestration in the demo path
- overbuilt design work before core workflow functions

## Functional Requirements

The first complete version should support this flow:

1. User opens the app and sees dataset readiness metrics.
2. User reviews a ranked queue of flagged facilities.
3. User filters by issue type, geography, or capability.
4. User opens a facility detail view.
5. User sees:
   - claims
   - evidence snippets
   - missingness
   - contradictions
   - readiness/trust signals
6. User records a decision and note.
7. Decision persists and updates the queue.

## Scoring Model

The initial implementation should combine these components:

- `completeness score`
- `evidence support score`
- `consistency score`
- `high-leverage score`

These scores should be paired with validation outputs such as:

- schema or parsing warnings
- join-confidence warnings
- contradiction checks
- confidence caps driven by sparse or weak evidence

The model does not need to be fully learned or probabilistic in the first version. It does need to be defensible, inspectable, and easy to explain in the demo.

## Suggested Technical Shape

### Data Layer

- raw facilities table
- enriched or normalized facilities table
- extracted claims table
- evidence spans table
- flags table
- validation results table
- review decisions table
- supplemental geography and district-health context tables

Expected supplemental inputs:

- India Post PIN code directory for postcode-to-geography enrichment
- NFHS-5 district indicators for district-level public health context

Challenge-provided schema references are reconciled in `docs/EXTRACTION_CONTRACT.md` and represented as `config/facility_schema_contract.json`.

Trust formulas are versioned in `config/trust_scoring_rules.json` and documented in `docs/TRUST_SCORING.md`. Claim evidence is capped below verified status until exact source spans are available.

Important modeling constraint:

- the PIN directory is not at one-row-per-PIN grain, so direct joins on `pincode` must be cardinality-checked and usually aggregated first
- district assignment should prefer spatial joins from facility coordinates over brittle string matching wherever possible

### Application Layer

- queue view
- facility detail view
- note and override workflow
- summary metrics view

### Persistence Layer

- reviewer status
- reviewer notes
- score overrides if allowed
- timestamps and reviewer identity

## Delivery Priorities

### Priority 1

- ingest dataset
- profile columns
- validate schema and joins
- produce first-pass flags
- create ranked review queue

### Priority 2

- build app surface
- implement persistence
- wire facility detail evidence view
- surface validation warnings alongside trust outputs

### Priority 3

- high-leverage explanation
- impact dashboard
- traceability improvements

## Success Criteria

We should consider the project successful if:

- the app works reliably in a live demo
- each flag is evidence-backed
- validation warnings prevent overconfident use of weak data
- the app clearly distinguishes weak data from true absence of care
- reviewer actions persist correctly
- the narrative is easy to understand in under one minute

## Working Agreements

- Keep the architecture simple until the end-to-end workflow exists.
- Prefer explicit heuristics over opaque logic early on.
- Every new feature should improve demo strength or judging criteria.
- Avoid building anything that does not clearly support the chosen track.
