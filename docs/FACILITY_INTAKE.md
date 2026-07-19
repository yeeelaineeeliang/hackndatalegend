# Facility Data Intake

## Dataset Access

The challenge brief links to the Databricks Marketplace listing:

`https://login.databricks.com/signin?intent=SIGN_IN&auto_login=true&destination_url=%2Fmarketplace%2Fconsumer%2Flistings%2F19326b3d-db63-4627-abc0-cf4e8131a305&utm_source=open-in-databricks&utm_medium=marketplace&utm_campaign=dais-devrel-hackathon`

The Marketplace export has been staged at:

`data/raw/facilities/healthcare_facilities.csv`

The checksum manifest records the original export filename and SHA-256 digest.

## Canonical Raw Location

To stage a replacement export deliberately, use:

```bash
python3 -m src.ingestion.facility_intake /path/to/facilities.csv --stage
```

Supported formats:

- CSV
- JSON
- JSON Lines
- Parquet

The command:

- copies the source to `data/raw/facilities/healthcare_facilities.<format>`
- writes `data/raw/facilities/source_manifest.json` with its checksum
- preserves source columns unchanged
- profiles schema and coverage
- validates core fields, parsing, claim-list shape, and geography readiness

## Generated Outputs

- `data/processed/facility_column_profile.csv`
- `data/processed/facility_row_status.csv`
- `data/processed/facility_ingestion_issues.csv`
- `outputs/profiling/facility_data_profile.json`
- `outputs/validation/facility_ingestion_validation.json`

## Intake Gate

Structural failures return a non-zero exit status. Expected source sparsity and parse uncertainty remain visible as warnings.

No trust scoring should run until:

- core readiness fields resolve unambiguously
- numeric parsing risks are quantified
- claim fields preserve `null` versus empty-list semantics
- geographic joins have an explicit confidence state

Malformed rows and exact duplicate copies are preserved in the raw source and review artifacts but are not eligible for trust scoring.

## Verified Full-Dataset Result

- raw rows: `10,088`
- columns: `51`
- structurally valid facility rows: `10,000`
- malformed rows quarantined: `88`
- exact duplicate copies excluded: `11`
- unique scoring-eligible facilities: `9,989`
- intake result: `10` passed, `4` warnings, `0` failed

Warnings cover quarantined structural rows, exact duplicate IDs, and source enum values outside the provided contract.

## Normalization

After intake passes, run:

```bash
python3 -m src.processing.normalize_facilities
```

This produces the provenance-preserving analysis base and a separate normalization validation gate. See `docs/NORMALIZED_FACILITY_LAYER.md`.
