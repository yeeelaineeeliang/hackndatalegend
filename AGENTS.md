# AGENTS.md

## Purpose

This file defines how human and AI collaborators should work in this repository.

## Mission

Ship a strong hackathon submission for the `Data Readiness Desk` track. The product must help reviewers determine which healthcare facility records are safe to trust, which require review, and why.

## Collaboration Rules

1. Optimize for working software and a clear demo.
2. Stay inside the chosen track unless a cross-track idea clearly improves the current submission.
3. Prefer simple, auditable logic over speculative complexity.
4. Do not add product scope that weakens the core review workflow.
5. Every flag or score should be explainable.

## Documentation Rules

- Keep `README.md` current for a new collaborator.
- Update `PROJECT.md` when scope, architecture, or delivery priorities change.
- Record major technical or product decisions in a dedicated note under `docs/` once that folder exists.

## Coding Rules

- Favor readable code over premature abstraction.
- Separate data preparation, scoring, and UI concerns.
- Keep rule logic inspectable and well named.
- Add concise comments only where the code would otherwise be ambiguous.
- Avoid hidden side effects in scoring functions.

## Data Handling Rules

- Treat challenge fields as noisy claims, not ground truth.
- Preserve raw source values during transformation.
- Keep traceability from derived flags back to input fields or text spans.
- Do not silently discard contradictory or incomplete records.

## Product Rules

- The reviewer queue is the primary workflow.
- Facility detail must expose evidence, not just scores.
- Persistence is a core requirement, not a stretch feature.
- The app must distinguish `medical desert` risk from `data desert` uncertainty wherever relevant.

## Demo Rules

- The demo path should be short and deterministic.
- Avoid steps that depend on slow or brittle live inference.
- Every demo action should reinforce one judging dimension:
  - evidence and trust
  - product judgment
  - technical execution
  - ambition

## AI Agent Expectations

When an AI agent works in this repo, it should:

- inspect local context before making structural decisions
- keep the chosen track central
- propose or implement the smallest complete change that moves the submission forward
- call out risks, assumptions, and missing inputs directly
- preserve user-made changes unless explicitly asked to replace them

## Recommended Build Sequence

1. dataset intake
2. schema and coverage profiling
3. first-pass scoring rules
4. flagged queue generation
5. app shell
6. persistence
7. demo tightening

## Definition Of Done For New Work

A task is complete when:

- the change works locally for its intended purpose
- the impact on the demo or scoring is clear
- relevant docs stay consistent
- no unnecessary scope was introduced
- applicable validation and tests pass

## Current Verification Commands

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
