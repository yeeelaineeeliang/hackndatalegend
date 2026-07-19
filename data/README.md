# Data Directory

## Layout

```text
data/
├── README.md
├── raw/
│   ├── facilities/
│   └── supplemental/
└── processed/
```

## Conventions

- `raw/` contains immutable source copies.
- `processed/` contains cleaned, normalized, or aggregated outputs derived from raw data.
- Never overwrite raw source files after ingesting them into the repo.
- Keep source filenames stable and human-readable.

## Current Raw Sources

### `raw/supplemental/india_post_pincode_directory.csv`

- original source file: `5c2f62fe-5afa-4119-a499-fec9d604d5bd.csv`
- source type: public API export from `data.gov.in`
- grain: one row per post office
- row count: `165,627` data rows plus header
- columns: `11`

Key cautions:

- `pincode` is not unique
- one PIN can map to multiple post offices and potentially multiple districts
- latitude and longitude can be `NA`

### `raw/supplemental/nfhs5_district_health_indicators.csv`

- original source file: `datafile.csv`
- source type: public CSV export from `data.gov.in`
- grain: one row per district
- row count: `706` data rows plus header
- columns: `109`

Key cautions:

- headers should be normalized before database loading
- `*` should be treated as `NULL`
- parenthesized values indicate lower-confidence estimates
- district and state names require normalization before joining

### `raw/facilities/healthcare_facilities.csv`

- original source file: `New_Query_2026_07_18_22_02_29.csv`
- source type: Databricks Marketplace table export
- raw rows: `10,088`
- columns: `51`
- SHA-256: `47bb1aad11f84a68aed3025d2887665bb164bc38c535c39e59eddb436c556691`

The directory also contains `source_manifest.json`.

## Planned Derived Datasets

These are the first expected outputs under `processed/`:

- `pincode_lookup.csv`
- `pincode_ambiguity_report.csv`
- `nfhs5_district_health_indicators_clean.csv`
- `district_name_normalization_map.csv`

Current generated outputs:

- `pincode_lookup.csv`
- `pincode_ambiguity_report.csv`
- `nfhs5_column_mapping.csv`
- `district_name_normalization_map.csv`
- `pincode_lookup_preferred.csv`
- `nfhs5_district_health_indicators_clean.csv`
- `pincode_coordinate_issues.csv`
- `nfhs_pincode_geography_crosswalk_candidates.csv`
- `facility_column_profile.csv`
- `facility_row_status.csv`
- `facility_ingestion_issues.csv`
- `facilities_analysis_base.parquet`
- `facility_normalization_issues.csv`
- `facility_trust_signals.parquet`
- `facility_flags.parquet`
- `facility_review_queue.parquet`
- `facility_review_queue.csv`

## Intake Rule

Before any modeling or joins:

1. inspect the raw file shape
2. document grain and join risks
3. preserve a stable raw copy
4. only then create cleaned derivatives
