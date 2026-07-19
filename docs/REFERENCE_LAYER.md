# REFERENCE_LAYER.md

## Purpose

This document defines the cleaned supplemental reference layer that downstream facility ingestion and scoring should use.

## Current Reference Tables

- [pincode_lookup_preferred.csv](/Users/yeelingliang/Documents/dataLegend/data/processed/pincode_lookup_preferred.csv:1)
- [pincode_ambiguity_report.csv](/Users/yeelingliang/Documents/dataLegend/data/processed/pincode_ambiguity_report.csv:1)
- [nfhs5_district_health_indicators_clean.csv](/Users/yeelingliang/Documents/dataLegend/data/processed/nfhs5_district_health_indicators_clean.csv:1)
- [district_name_normalization_map.csv](/Users/yeelingliang/Documents/dataLegend/data/processed/district_name_normalization_map.csv:1)
- [nfhs5_column_mapping.csv](/Users/yeelingliang/Documents/dataLegend/data/processed/nfhs5_column_mapping.csv:1)
- [pincode_coordinate_issues.csv](/Users/yeelingliang/Documents/dataLegend/data/processed/pincode_coordinate_issues.csv:1)
- [nfhs_pincode_geography_crosswalk_candidates.csv](/Users/yeelingliang/Documents/dataLegend/data/processed/nfhs_pincode_geography_crosswalk_candidates.csv:1)

## PIN Join Policy

The raw PIN source is one row per post office, not one row per PIN. Direct joins from facilities to the raw source are not allowed.

Use `pincode_lookup_preferred.csv` instead.

### Resolution Status

- `exact`
  - one district candidate and one state candidate
  - safe for direct lookup use

- `district_mode_selected`
  - multiple district candidates but one district is the clear mode
  - usable only as a fallback when no coordinate-based geography is available
  - should remain flagged as inferred

- `ambiguous_district`
  - multiple district candidates with no single clear district winner
  - do not auto-assign district from PIN alone

- `ambiguous_state`
  - multiple state candidates
  - do not auto-assign state or district from PIN alone

- `missing_geo`
  - no usable district or state candidate
  - do not use for administrative assignment

### Practical Rule Order

1. Prefer coordinate-based district assignment whenever facility latitude and longitude exist.
2. If coordinates are missing, allow PIN lookup only when `resolution_status = exact`.
3. If coordinates are missing and `resolution_status = district_mode_selected`, allow only as an explicitly inferred fallback.
4. If `resolution_status` is `ambiguous_district`, `ambiguous_state`, or `missing_geo`, require manual review or a stronger geography source.

PIN join safety applies only to district and state assignment. It does not make a PIN-level mean coordinate an exact facility coordinate.

### Coordinate Policy

- coordinate pairs inside broad India bounds are marked `valid`
- likely latitude/longitude swaps are quarantined, not silently corrected
- out-of-bounds and incomplete pairs are excluded from aggregate coordinates
- `mean_valid_latitude` and `mean_valid_longitude` summarize only valid post-office coordinate pairs
- PIN-level means must not replace facility coordinates or point-in-polygon assignment

### Current Counts

- `18,228` exact PIN mappings
- `1,135` district-mode-selected PIN mappings
- `100` missing-geo PIN mappings
- `71` ambiguous-district PIN mappings
- `52` ambiguous-state PIN mappings

## NFHS Cleaning Policy

Use `nfhs5_district_health_indicators_clean.csv` for analytics and joins.

### Cleaning Rules Applied

- original headers converted to `snake_case`
- surrounding whitespace trimmed from values
- `*`, `NA`, `N/A`, and empty strings treated as null
- parenthesized values converted to raw numeric text and paired with boolean low-confidence flags
- indicator values converted to numeric types
- normalized join helpers added:
  - `district_normalized`
  - `state_ut_normalized`

### Join Guidance

Use district joins conservatively:

1. Prefer a district assigned from facility coordinates.
2. Otherwise use a reviewed or exact PIN-derived district.
3. Normalize names before string comparison.
4. Preserve whether the district assignment was exact, inferred, or unresolved.

Only `543` of `706` NFHS state-district pairs currently match the PIN source after conservative normalization. The remaining `163` rows in `nfhs_pincode_geography_crosswalk_candidates.csv` require review or spatial assignment; fuzzy candidates are suggestions, never accepted joins.

## Validation Gate

Run:

```bash
python3 -m src.validation.validate_supplemental_data
```

The current report is `outputs/validation/supplemental_validation_report.json`.

Current result:

- `9` checks passed
- `2` source-quality warnings
- `0` failures

Warnings cover quarantined coordinate defects and unresolved cross-source geography names.
