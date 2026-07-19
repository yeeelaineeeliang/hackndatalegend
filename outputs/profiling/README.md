# Profiling Outputs

## Purpose

This directory stores machine-readable profiling outputs for raw datasets before transformation or modeling.

## Current Files

### `supplemental_data_profile.json`

Combined profiling results for:

- `data/raw/supplemental/india_post_pincode_directory.csv`
- `data/raw/supplemental/nfhs5_district_health_indicators.csv`

Includes:

- row and column counts
- missingness by column
- uniqueness statistics
- PIN ambiguity metrics
- NFHS missingness and parenthesized-estimate counts

## Interpretation Notes

- The PIN dataset is highly non-unique at the `pincode` level and must not be joined naively.
- The NFHS dataset has many sparse columns and several low-confidence estimate fields that should be carried with caution flags.
