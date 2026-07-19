# Extraction Contract

## Purpose

This document reconciles the challenge-provided schema documentation and extraction models into rules the Data Readiness Desk can validate.

## Reference Sources

- `Virtue Foundation Scheme Documentation.pdf`
- `prompts_and_pydantic_models/facility_and_ngo_fields.py`
- `prompts_and_pydantic_models/free_form.py`
- `prompts_and_pydantic_models/medical_specialties.py`
- `prompts_and_pydantic_models/organization_extraction.py`
- machine-readable contract: `config/facility_schema_contract.json`

## Stable Field Groups

Identity and classification:

- `name`
- `facilityTypeId`
- `operatorTypeId`
- `affiliationTypeIds`

Core readiness fields:

- `description`
- `capability`
- `procedure`
- `equipment`
- `numberDoctors`
- `capacity`
- `yearEstablished`

Geography:

- parsed address fields
- city and state or region
- postal code
- country and country code

## Evidence Policy

Every extracted claim used by a flag or score must preserve:

- source field
- exact supporting text
- whether support is direct, corroborating, inferred, or missing
- whether the value was inferred
- confidence
- validation status

An inferred value must never be presented as direct evidence.

## Null And Empty Semantics

- `null`: the field was not processed or remains unknown
- empty list: extraction ran and found no supported facts

This distinction prevents an unprocessed field from looking like verified absence.

## Resolved Contract Conflicts

### Bed Counts

The free-form prompt describes beds as equipment, while its Pydantic field description says not to list bed counts as equipment.

Canonical policy:

- numeric total inpatient beds belong in `capacity`
- a phrase such as `45-bed ICU` may support an ICU capability claim
- bed counts do not become equipment unless the source names a specific bed device or model

### Country Inference

The organization prompt prohibits inference generally but requires country inference from contextual clues.

Canonical policy:

- explicit country text is direct evidence
- country derived from a domain, phone code, or other context is allowed only as an inferred value
- inferred geography must retain its evidence basis and cannot receive direct-evidence confidence

### Specialty Hierarchy Dependency

`medical_specialties.py` depends on `fdr.config.medical_specialties`, which is not included in the provided directory.

Canonical policy:

- treat the visible specialty mappings as reference guidance
- do not execute or validate the full classifier until the exact hierarchy is available
- preserve the raw specialty claim even when taxonomy validation is unavailable

## Intake Implication

When the main facility dataset arrives, ingestion validation should compare its columns and values with `config/facility_schema_contract.json`, while preserving any additional source columns unchanged.

