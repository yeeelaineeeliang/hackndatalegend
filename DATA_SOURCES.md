# DATA_SOURCES.md

## Purpose

This file captures the current understanding of the challenge data pipeline and the supplemental public datasets that can enrich the `Data Readiness Desk` workflow.

## Foundational Data Refresh Pipeline

The upstream `Foundational Data Refresh (FDR)` pipeline:

- ingests public datasets and websites
- applies a medallion architecture
- performs GenAI-based information extraction
- resolves primary keys across sources
- consolidates disparate records into a single unified row per entity

Implication for this project:

- the final facility row is already a consolidated product, not a raw source record
- extracted fields should still be treated as noisy claims, not ground truth
- provenance and evidence remain critical because consolidation can hide upstream uncertainty

## Supplemental Data Sources

Two public datasets are relevant for enriching healthcare facility data in India:

- `india_post_pincode_directory.csv`
- `nfhs5_district_health_indicators.csv`

These are useful for:

- geographic enrichment
- district and state lookup
- demand-side public health context
- downstream planning and coverage analysis

Both are published under the `Government Open Data License - India` via `data.gov.in`.

## Challenge-Provided Reference Materials

The repository also contains:

- `Virtue Foundation Scheme Documentation.pdf`
- `prompts_and_pydantic_models/facility_and_ngo_fields.py`
- `prompts_and_pydantic_models/free_form.py`
- `prompts_and_pydantic_models/medical_specialties.py`
- `prompts_and_pydantic_models/organization_extraction.py`

These files define the intended facility schema and the upstream extraction behavior. They are reference inputs, not ground truth.

The reconciled project contract is documented in:

- `docs/EXTRACTION_CONTRACT.md`
- `config/facility_schema_contract.json`

Known caveats:

- prompt guidance conflicts on whether bed counts belong in `equipment`
- country inference is required in one section but general inference is prohibited elsewhere
- the specialty classifier imports a hierarchy module that was not included
- inferred fields must be distinguished from direct source evidence

## Main Facility Dataset

The 10,000-row challenge facility dataset is linked from the challenge brief through Databricks Marketplace.

Status:

- Marketplace listing identified
- local dataset export not yet present
- schema-driven staging and validation command implemented

See `docs/FACILITY_INTAKE.md`.

## General Data Quality Guidance

These are public-sector, real-world datasets. Expect:

- inconsistent place-name casing
- ambiguous postal mappings
- missing coordinates
- suppressed values
- cross-dataset spelling differences

Rules:

- document uncertain joins
- do not present inferred geography as exact unless verified
- preserve raw source fields during transformation
- preserve whether an extracted value was direct or inferred
- distinguish `null` (unknown or unprocessed) from an empty extracted list

## India Post PIN Code Directory

### File

- `india_post_pincode_directory.csv`

### Source

- Open Government Data Platform India
- Resource: `All India Pincode Directory till last month`

### Source URLs

- `https://www.data.gov.in/resource/all-india-pincode-directory-till-last-month`
- License: `https://www.data.gov.in/Godl`

### Coverage

- `165,627` rows
- `19,586` unique PIN codes
- `750` districts
- `37` states and union territories

A PIN is a 6-digit postal code similar to a ZIP code.

### Columns

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

### Important Grain Warning

This file is at the `post office` grain, not the `PIN code` grain.

Implications:

- a single PIN can appear on multiple rows
- a PIN may map to more than one district or state
- joining directly on `pincode` can fan out records

Required handling:

- check join cardinality before use
- deduplicate or aggregate to the intended join grain
- keep ambiguity flags where multiple candidate mappings exist

### Coverage Caveat

Approximately `12,600` rows have `NA` latitude or longitude values.

Do not assume full geocoding coverage.

### Use Cases

- enrich facility postcodes with district or state context
- build geography lookup tables keyed by PIN code, district, state, or post office
- inspect postal ambiguity before joining to facility records

## NFHS-5 District Health Indicators

### File

- `nfhs5_district_health_indicators.csv`

### Source

- National Family Health Survey 2019-21 district fact sheets via `data.gov.in`

### Source URLs

- `https://www.data.gov.in/catalog/national-family-health-survey-5-nfhs-5-india-districts-factsheet-data-provisional`
- Official fact sheets: `https://www.nfhsiips.in/nfhsuser/nfhs5.php`
- License: `https://www.data.gov.in/Godl`

### Coverage

- `706` district rows
- `109` columns
- field period: `2019-2021`

This is a district-level public health context dataset, not a facility dataset.

### Indicator Groups

- household conditions
- maternal and reproductive health
- child health and vaccination
- nutrition
- anaemia
- non-communicable diseases
- cancer screening
- tobacco
- alcohol

### Data Quality Notes

- rename long human-readable columns to `snake_case` before loading into database tables
- normalize district and state names before string-based joins
- treat `*` values as `NULL`, not zero
- treat parenthesized values such as `(29.5)` as lower-confidence estimates
- if NFHS-6 is introduced later, validate comparability before mixing vintages

### Use Cases

- add district-level health burden context
- compare facility availability against district health indicators
- support district rankings, demand-side views, or planning dashboards
- identify underserved districts where burden is high and trusted facility coverage is low

## Working With Location Data

The preferred administrative mapping strategy is spatial, not string-based.

Recommended approach:

- use facility latitude and longitude when available
- assign district or state via point-in-polygon joins
- then join district-level indicators from NFHS-5

Suggested sources for polygons:

- `geoBoundaries`
- `DataMeet India Maps`

Suggested tools:

- `GeoPandas`
- `Shapely`
- Databricks geospatial functions such as `ST_Point` and `ST_Contains`
- `QGIS` for inspection

## Join Strategy Guidance

### Preferred Join Order

1. Use facility coordinates to assign district when coordinates are available.
2. Use normalized postal enrichment when coordinates are missing.
3. Mark assignments as exact, inferred, or ambiguous.

### Why

String matching district names across Indian datasets is unreliable because spelling, casing, and transliteration vary. Spatial joins are more robust whenever coordinates exist.

## Relevance To Data Readiness Desk

These supplemental datasets matter because they improve our ability to distinguish:

- a true lack of care capacity
- a weak or ambiguous facility record
- a geography join that is uncertain

They also support our planned `high-leverage` logic, since a questionable record in a sparse district can materially affect downstream planning conclusions.
