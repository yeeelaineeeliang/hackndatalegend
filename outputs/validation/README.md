# Validation Outputs

Current reports:

- `supplemental_validation_report.json`
- `facility_ingestion_validation.json`
- `facility_normalization_validation.json`
- `facility_trust_validation.json`
- `app_asset_validation.json`

## Current Report

`supplemental_validation_report.json` is the executable quality gate for the supplemental reference layer.

The report distinguishes:

- `pass`: the invariant is satisfied
- `warn`: source uncertainty is present but quarantined or explicitly restricted
- `fail`: the processed layer is structurally unsafe and the command exits non-zero

Warnings do not authorize unsafe joins. They identify records that require review, a stronger source, or spatial assignment.
