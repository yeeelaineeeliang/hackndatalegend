# INGESTION.md

## Current Inputs

The following raw source copies are staged in the repository:

- [healthcare_facilities.csv](/Users/yeelingliang/Documents/dataLegend/data/raw/facilities/healthcare_facilities.csv:1)
- [india_post_pincode_directory.csv](/Users/yeelingliang/Documents/dataLegend/data/raw/supplemental/india_post_pincode_directory.csv:1)
- [nfhs5_district_health_indicators.csv](/Users/yeelingliang/Documents/dataLegend/data/raw/supplemental/nfhs5_district_health_indicators.csv:1)

## Source Inventory

### Challenge Healthcare Facilities

- repo path: `data/raw/facilities/healthcare_facilities.csv`
- source grain: intended as one row per facility
- rows detected: `10,088` raw rows
- structurally valid facility rows: `10,000`
- unique scoring-eligible facilities: `9,989`
- columns detected: `51`
- source checksum: `47bb1aad11f84a68aed3025d2887665bb164bc38c535c39e59eddb436c556691`

Observed intake issues:

- `88` malformed rows are quarantined
- `11` exact duplicate copies are excluded from scoring
- raw rows and fields remain unchanged in all cases
- normalized analysis base is `data/processed/facilities_analysis_base.parquet`

### India Post PIN Directory

- repo path: `data/raw/supplemental/india_post_pincode_directory.csv`
- source grain: post office
- rows detected: `165,627` data rows
- columns detected: `11`
- profiled on repo-local copy: yes

Observed profiling highlights:

- `19,586` unique PIN codes
- `750` unique districts
- `37` unique states and union territories
- `12,015` rows missing at least one coordinate
- `2,602` rows have out-of-bounds or likely swapped coordinate pairs
- `9` rows have only one coordinate present
- `17,443` PIN codes appear on multiple rows
- `1,478` PIN codes map to multiple districts
- `290` PIN codes map to multiple states
- max observed rows for a single PIN: `153`

Header:

- `circlename`
- `regionname`
- `divisionname`
- `officename`
- `pincode`
- `officetype`
- `delivery`
- `district`
- `statename`
- `latitude`
- `longitude`

### NFHS-5 District Health Indicators

- repo path: `data/raw/supplemental/nfhs5_district_health_indicators.csv`
- source grain: district
- rows detected: `706` data rows
- columns detected: `109`
- profiled on repo-local copy: yes

Observed profiling highlights:

- `698` unique normalized district names
- `36` unique normalized states and union territories
- `29` columns contain missing values
- `48` columns contain parenthesized low-confidence estimates
- `543` of `706` state-district pairs exactly match the PIN directory after conservative normalization

Important first columns:

- `District Names`
- `State/UT`
- `Number of Households surveyed`
- `Number of Women age 15-49 years interviewed`
- `Number of Men age 15-54 years interviewed`

## First Processing Rules

### PIN Directory

- preserve raw rows as-is
- parse `NA` coordinates as null
- never assume one row per `pincode`
- create a derived lookup table only after profiling one-to-many mappings

### NFHS-5

- trim whitespace from values
- normalize column names to `snake_case`
- convert `*` to null
- mark parenthesized values as lower-confidence estimates
- convert indicator values to numeric types
- normalize district and state names before any joins

## Next Build Step

The next technical task should be a lightweight profiling pass that produces:

- null coverage by column
- unique counts for core geography fields
- `pincode` duplication statistics
- NFHS district/state normalization candidates

Status:

- completed on `July 18, 2026`
- machine-readable profile: `outputs/profiling/supplemental_data_profile.json`
- derived tables:
  - `data/processed/pincode_lookup.csv`
  - `data/processed/pincode_ambiguity_report.csv`
  - `data/processed/nfhs5_column_mapping.csv`
  - `data/processed/district_name_normalization_map.csv`
  - `data/processed/pincode_coordinate_issues.csv`
  - `data/processed/nfhs_pincode_geography_crosswalk_candidates.csv`
  - `data/processed/pincode_lookup_preferred.csv`
  - `data/processed/nfhs5_district_health_indicators_clean.csv`
- validation report: `outputs/validation/supplemental_validation_report.json`
- facility intake validation: `outputs/validation/facility_ingestion_validation.json`
- facility normalization validation: `outputs/validation/facility_normalization_validation.json`
