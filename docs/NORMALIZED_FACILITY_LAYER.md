# Normalized Facility Layer

## Purpose

`data/processed/facilities_analysis_base.parquet` is the canonical input to trust scoring. It makes noisy fields usable without replacing or hiding the source values.

## Grain And Preservation

- all `10,088` raw rows are retained
- all `51` raw columns are retained unchanged
- `88` malformed rows remain visible with `structurally_valid = false`
- second copies of `11` exact duplicate rows remain visible with `exact_duplicate = true`
- `9,989` rows have `scoring_eligible = true`
- scoring-eligible rows are unique by `unique_id`

The source CSV remains immutable. Derived fields are appended in the Parquet analysis base.

## Derived Field Groups

Row provenance:

- `source_row_number`
- `structurally_valid`
- `exact_duplicate`
- `scoring_eligible`
- `intake_issue_codes`

Normalized classifications:

- `facility_type_normalized`
- `facility_type_normalization_action`
- `operator_type_normalized`
- `operator_type_normalization_action`
- `affiliation_type_ids_normalized`
- `affiliation_type_ids_status`

Claims and numeric fields:

- parsed arrays and parse statuses for `capability`, `procedure`, and `equipment`
- normalized integers and statuses for `numberDoctors`, `capacity`, and `yearEstablished`

Geography:

- normalized PIN and state name
- parsed coordinates and coordinate-pair status
- PIN reference resolution status
- exact PIN-derived district and state assignments
- explicit PIN join confidence

## Correction Policy

Only two source enum corrections are automatic:

- `farmacy` becomes `pharmacy` with action `corrected_typo`
- `government` becomes `public` with action `mapped_synonym`

The unsupported category `nursing_home` remains null in the contract-normalized field with action `unmapped`. It is not forced into `hospital` or `clinic`.

Raw enum fields remain unchanged.

## Claim Semantics

- null source value becomes parsed null with status `missing`
- `[]` becomes an empty parsed array with status `empty_list`
- a valid non-empty string array becomes `parsed_list`
- scalar, mixed-member, or invalid values remain parsed null with an explicit failure status

An invalid list is never converted into an empty list because that would incorrectly imply verified absence.

## Geography Policy

PIN enrichment uses only `pincode_lookup_preferred.csv`.

- district and state are assigned only when `resolution_status = exact`
- ambiguous mappings remain unassigned
- coordinate pairs are classified but no point-in-polygon district is inferred yet
- PIN-derived geography is reference enrichment, not proof of a facility's exact location

## Current Validation

Run:

```bash
python3 -m src.processing.normalize_facilities
```

Current result:

- `6` checks passed
- `3` warnings
- `0` failures

Warnings:

- `1` scoring-eligible record has unmapped facility type `nursing_home`
- `830` scoring-eligible records do not have an exact PIN reference mapping
- `10` claim fields contain invalid non-string list members

Review artifact:

`data/processed/facility_normalization_issues.csv`
