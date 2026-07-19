# Data Legend Hackathon Plan

## Chosen Track

`Data Readiness Desk`

Why this is the right track:

- It fits the challenge thesis directly: turning messy healthcare data into something a planner can trust.
- It has the clearest minimum workflow with the highest chance of a reliable live demo.
- It lets us score well on the largest judging buckets without needing a full referral or geospatial product.
- It creates a strong story: "before you plan, you must know what is safe to trust."

## Product Thesis

Build a reviewer-facing Databricks App that identifies the records most worth fixing before planners use the dataset.

The app should answer:

- Which records are incomplete?
- Which records are contradictory?
- Which records make strong claims with weak evidence?
- Which records are high leverage, meaning fixing them most improves dataset usefulness?
- Which records fail validation checks and should not be trusted without review?

## Winning Product Framing

Do not pitch this as a generic data quality dashboard.

Pitch it as:

`The trust gate before planning decisions.`

Narrative:

- NGOs and planners cannot act on raw facility claims.
- They need a review queue that prioritizes what to inspect first.
- Our app turns 10k records into an auditable queue with evidence, confidence, and persisted human decisions.

## Minimum Lovable Workflow

This must work end-to-end in the live demo:

1. Reviewer opens the app.
2. Reviewer sees summary metrics:
   - incomplete records
   - contradictory records
   - suspicious claims
   - high-leverage records
3. Reviewer filters the queue by issue type, region, and capability.
4. Reviewer opens one facility.
5. App shows:
   - original structured fields
   - extracted claims
   - exact supporting or missing evidence snippets
   - why the record was flagged
   - validation warnings
   - a trust/readiness score
6. Reviewer records a decision:
   - confirm
   - needs review
   - incorrect claim
   - missing evidence
   - resolved
7. Reviewer adds a note or override.
8. Decision persists and updates queue status.

If we nail this cleanly, we satisfy the track.

## Feature Priorities

### Tier 1: Must Have

- Ranked flagged review queue
- Exact evidence snippets for each flag
- Readiness/trust score per facility
- Validation warnings per facility
- Filters by geography and capability
- Persistent reviewer actions and notes
- Simple audit trail for each decision

### Tier 2: Strong Stretch

- "Why this record matters" high-leverage explanation
- Dataset-level before/after quality improvement view
- Distinguish "true medical desert risk" from "data desert risk"
- Trace view showing extraction -> rule checks -> final flag

### Tier 3: Only If Time Allows

- India map view
- Agentic validator loop
- Natural-language query over flagged records

## Core Scoring Logic

We do not need perfect ML. We need defensible heuristics with clear evidence.

## Validation Layer

Validation should run both before and after scoring.

### Data Validation

- required fields present
- PIN, year, coordinate, and count parsing checks
- join cardinality checks
- geography conflict checks when PIN and coordinates disagree

### Decision Validation

- claimed capability unsupported by text or structured corroboration
- contradictory evidence across fields
- confidence caps for sparse evidence
- warnings when a conclusion depends on inferred geography

### 1. Completeness Score

Score missingness on important fields:

- description
- capability
- procedure
- equipment
- numberDoctors
- capacity
- yearEstablished
- source URL if present in dataset

Weighted idea:

- critical fields missing: larger penalty
- optional fields missing: smaller penalty

### 2. Evidence Support Score

For each claimed capability, check whether the description/procedure/equipment text supports it.

Examples:

- ICU claim but no ventilator, critical care, or ICU-related text -> weak support
- maternity claim with delivery or obstetric signals -> stronger support
- emergency surgery claim with no surgeon/anesthesia/OT signals -> suspicious

### 3. Consistency Score

Detect contradictions like:

- specialty claim without matching procedures
- high-acuity claim with no doctors/capacity/equipment evidence
- structured field says one thing, free text implies another
- duplicate or near-duplicate facilities with conflicting attributes

### 4. High-Leverage Score

This is where we can differentiate.

A record is high leverage if:

- it sits in a sparse region
- it is one of few facilities for a capability
- it has high planner relevance but low confidence
- resolving it would materially change regional coverage conclusions

Simple first-pass formula:

`high_leverage = planner_importance x uncertainty x regional_sparsity`

Where:

- `planner_importance` depends on capability severity such as ICU, NICU, trauma, maternity
- `uncertainty` comes from low evidence + contradictions + missing fields
- `regional_sparsity` increases when the region has few candidate facilities

## Recommended Data Model

### Input Tables

- `facilities_raw`
- `facilities_enriched`
- `facility_claims`
- `facility_evidence_spans`
- `facility_flags`

### App Persistence Tables

- `review_decisions`
  - `decision_id`
  - `facility_id`
  - `review_status`
  - `reviewer_note`
  - `override_score`
  - `created_at`
  - `updated_at`
  - `reviewer_id`

- `saved_views` or `saved_filters`
- `scenario_snapshots` if we add trend views

## UX Structure

Keep the product brutally simple.

### Screen 1: Overview

- four KPI cards
- issue-type breakdown
- top high-leverage records
- queue table

### Screen 2: Review Queue

- filters on left or top
- sortable table
- columns:
  - facility
  - state/city/PIN
  - claimed capability
  - issue type
  - readiness score
  - leverage score
  - status

### Screen 3: Facility Review Drawer/Page

- facility profile
- claims and evidence
- flags with explanations
- exact text citations
- reviewer action form

### Screen 4: Impact View

- records reviewed
- percent resolved
- estimated reduction in uncertainty
- optional before/after distribution

## What Will Impress Judges

Focus on these four messages:

1. `Every flag has receipts.`
   - exact sentence or field snippet

2. `We validate before we trust.`
   - scores are checked against explicit warnings and contradictions

3. `We do not confuse missing data with missing care.`
   - explicitly separate data desert from medical desert

4. `We prioritize fixes that change planning outcomes the most.`
   - explain high-leverage ranking

5. `Human review becomes durable institutional knowledge.`
   - decisions persist and influence downstream use

## Suggested Technical Architecture

### Databricks Components

- Databricks App for UI
- Lakehouse tables for transformed data
- Vector Search or indexed retrieval for evidence lookup if needed
- Lakebase for reviewer notes and persistent actions
- MLflow tracing if we implement reasoning traces

### Practical Build Approach

- Batch-enrich records first
- Precompute flags and scores
- Serve app from precomputed tables
- Avoid heavy live inference during demo unless necessary

This reduces demo risk substantially.

## Implementation Strategy

### Phase 1: Fast Baseline

- load dataset
- validate schema and geography fields
- define rules for completeness, evidence support, and contradictions
- produce `facility_flags`
- produce a ranked queue

### Phase 2: Product Surface

- build app screens
- implement record detail panel
- wire persistent decisions

### Phase 3: Differentiation

- high-leverage score
- impact summary
- traceability view

## Concrete Rule Ideas

### Suspicious Claim Rules

- ICU claimed but no ICU-related evidence in text
- trauma claimed but no surgery/emergency indicators
- NICU claimed but no neonatal-related evidence
- high capacity implied but capacity missing
- advanced procedures listed but zero doctor count

### Contradiction Rules

- equipment says dialysis but capability omits nephrology-related care
- capability says oncology but no cancer-related procedure/equipment text
- description says clinic/basic care while structured field claims tertiary capabilities

### Data Desert Warnings

- region has low field coverage overall
- confidence interval for regional readiness is low
- too few complete records for strong planning conclusion

## Demo Script

The demo must stay under one minute and feel decisive.

Suggested script:

1. "Planners cannot trust raw facility claims, so we built the Data Readiness Desk."
2. "Here is a review queue ranked by where data fixes matter most."
3. "This facility is flagged because it claims ICU, but the supporting text does not corroborate it."
4. "We show the exact evidence, the missing fields, and the contradiction logic."
5. "A reviewer marks it as unsupported, adds a note, and that decision persists."
6. "Now the queue and dataset readiness metrics update, so downstream planners work from a safer dataset."

## Submission Strategy

Our story in the repo and demo should be:

- user: NGO/public health reviewer
- pain: cannot trust raw claims
- workflow: prioritize -> inspect -> decide -> persist
- technical edge: evidence-grounded scoring and leverage-aware ranking
- tradeoff: precomputed scoring for reliability over flashy but fragile live agents

## What Not To Do

- Do not build a generic chatbot.
- Do not spread effort across multiple tracks too early.
- Do not rely on opaque LLM judgments without explicit evidence.
- Do not make the demo depend on slow live multi-step reasoning.
- Do not overinvest in visual polish before the queue + detail + persistence loop works.

## Best Next Build Order

1. Get the dataset into the workspace.
2. Profile the columns and null coverage.
3. Define the first scoring heuristics.
4. Generate a review queue CSV/table.
5. Build a simple app around that queue.
6. Add persistent review actions.
7. Add high-leverage ranking explanation.
8. Tighten the demo and narrative.

## Immediate Next Task

The highest-value next move is to inspect the actual dataset schema and produce:

- a field dictionary
- first-pass quality metrics
- an initial flagging heuristic

Once that exists, we can start implementing the app instead of guessing.
