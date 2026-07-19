# Trust Scoring

## Purpose

The trust layer ranks facility records for human review. It does not declare that a facility or medical claim is true.

The scoring configuration is versioned in:

`config/trust_scoring_rules.json`

The implementation is:

`src/scoring/build_trust_signals.py`

## Outputs

- `data/processed/facility_trust_signals.parquet`
- `data/processed/facility_flags.parquet`
- `data/processed/facility_review_queue.parquet`
- `data/processed/facility_review_queue.csv`
- `outputs/profiling/facility_trust_profile.json`
- `outputs/validation/facility_trust_validation.json`

## Scores

All scores range from `0` to `100`.

### Completeness

Completeness is a weighted sum of identity, classification, geography, description, claims, and quantitative fields.

Claim fields preserve processing semantics:

- non-empty parsed list: full completeness credit
- empty list: half credit because processing completed but produced no supported facts
- null or invalid list: no credit because unknown and unprocessed states cannot be separated

The weights sum to `1.0` and are stored in the scoring configuration.

### Evidence Support

Evidence support measures available traceability, not truth. It uses:

- source URL availability
- source identifier availability
- source content identifier availability
- description availability
- claim-list quality

Facility-level URLs are not aligned to exact claim spans in the provided export. Evidence support is therefore capped at `75`, and every facility retains:

`claim_level_source_alignment_unverified`

The score cannot be interpreted as claim verification until source text and exact evidence spans are available.

### Consistency

Consistency starts at `100` and applies explicit penalties for:

- recognized source state disagreement with an exact PIN reference state
- invalid coordinate pairs
- unsupported facility type
- invalid claim-list structure
- placeholder or negative text stored as a positive claim
- strict total-bed claim disagreement
- explicit founded or opened year disagreement

State/PIN checks run only when the source value is a recognized Indian state or union territory. City names stored in the state field do not trigger a contradiction automatically.

Capacity and year checks use narrow regular-expression patterns. They are review candidates, not automatic corrections, because a source can mention a department, expansion, or related organization.

### Readiness

Readiness combines:

- completeness: `40%`
- evidence support: `30%`
- consistency: `30%`

### High Leverage

High leverage combines percentile ranks for:

- capacity: `35%`
- number of doctors: `25%`
- claim count: `25%`
- source URL count: `15%`

Missing values receive zero for that leverage component. This score estimates the potential planning impact of reviewing a record; it is not a quality score.

### Review Priority

Review priority combines:

- readiness risk, calculated as `100 - readiness`: `75%`
- high leverage: `25%`

The queue is sorted by this result, then high-severity flag count, then facility ID for deterministic ordering.

## Flag Traceability

Each long-form flag includes:

- facility ID and name
- issue and field
- severity and reason code
- plain-language explanation
- evidence snippet
- evidence type
- up to five source URLs
- inference state
- confidence
- validation status

Placeholder claims and missing fields are never silently rewritten. Contradictions remain review candidates.

## Current Result

- facility signal rows: `9,989`
- flags: `30,646`
- flagged facilities: `9,774`
- queue rows: `9,774`
- validation: `6` passed, `1` warning, `0` failed

The warning applies to all facilities because claim-level source alignment is unavailable.

## Reproduce

```bash
python3 -m src.scoring.build_trust_signals
```
