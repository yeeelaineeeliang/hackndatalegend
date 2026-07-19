from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

import pandas as pd

from src.data_quality import coordinate_status, normalize_name
from src.ingestion.facility_intake import (
    CLAIM_FIELDS,
    CONTRACT,
    ROOT,
    build_row_status,
    is_missing,
    read_facility_data,
)


DEFAULT_SOURCE = ROOT / "data" / "raw" / "facilities" / "healthcare_facilities.csv"
PIN_LOOKUP_PATH = ROOT / "data" / "processed" / "pincode_lookup_preferred.csv"
OUTPUT_PATH = ROOT / "data" / "processed" / "facilities_analysis_base.parquet"
PROFILE_PATH = ROOT / "outputs" / "profiling" / "facility_normalization_profile.json"
VALIDATION_PATH = (
    ROOT / "outputs" / "validation" / "facility_normalization_validation.json"
)
ISSUES_PATH = ROOT / "data" / "processed" / "facility_normalization_issues.csv"

FACILITY_TYPE_MAP = {
    "hospital": ("hospital", "unchanged"),
    "pharmacy": ("pharmacy", "unchanged"),
    "doctor": ("doctor", "unchanged"),
    "clinic": ("clinic", "unchanged"),
    "dentist": ("dentist", "unchanged"),
    "farmacy": ("pharmacy", "corrected_typo"),
}
OPERATOR_TYPE_MAP = {
    "public": ("public", "unchanged"),
    "private": ("private", "unchanged"),
    "government": ("public", "mapped_synonym"),
}


def parse_string_list(value: object) -> tuple[list[str] | None, str]:
    if is_missing(value):
        return None, "missing"
    if isinstance(value, (list, tuple)):
        parsed = list(value)
    elif isinstance(value, str):
        text = value.strip()
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            try:
                parsed = ast.literal_eval(text)
            except (SyntaxError, ValueError):
                return None, "invalid_scalar"
    else:
        return None, "invalid_type"

    if not isinstance(parsed, list):
        return None, "invalid_scalar"
    if not all(isinstance(item, str) for item in parsed):
        return None, "invalid_members"
    return parsed, "empty_list" if not parsed else "parsed_list"


def normalize_enum(
    value: object,
    mapping: dict[str, tuple[str, str]],
) -> tuple[str | None, str]:
    if is_missing(value):
        return None, "missing"
    token = str(value).strip().lower()
    if token not in mapping:
        return None, "unmapped"
    return mapping[token]


def normalize_integer_series(series: pd.Series) -> tuple[pd.Series, pd.Series]:
    missing = series.map(is_missing)
    parsed = pd.to_numeric(series.where(~missing), errors="coerce")
    is_integer = parsed.notna() & parsed.mod(1).eq(0)
    normalized = pd.Series(pd.NA, index=series.index, dtype="Int64")
    normalized.loc[is_integer] = parsed.loc[is_integer].astype("int64")

    status = pd.Series("invalid_integer", index=series.index, dtype=object)
    status.loc[missing] = "missing"
    status.loc[is_integer] = "parsed"
    status.loc[is_integer & normalized.lt(0)] = "negative"
    return normalized, status


def normalize_pincode(value: object) -> tuple[str | None, str]:
    if is_missing(value):
        return None, "missing"
    text = str(value).strip()
    if len(text) == 6 and text.isdigit():
        return text, "valid"
    return None, "invalid"


def normalize_affiliations(value: object) -> tuple[list[str] | None, str]:
    parsed, status = parse_string_list(value)
    if parsed is None:
        return None, status
    allowed = set(CONTRACT["allowed_values"]["affiliationTypeIds"])
    normalized = list(dict.fromkeys(item.strip().lower() for item in parsed))
    if any(item not in allowed for item in normalized):
        return normalized, "contains_unmapped"
    if len(normalized) < len(parsed):
        return normalized, "deduplicated"
    return normalized, status


def build_analysis_base(
    raw: pd.DataFrame,
    pin_lookup: pd.DataFrame,
) -> pd.DataFrame:
    frame = raw.copy()
    frame.columns = [str(column) for column in frame.columns]
    row_status = build_row_status(frame)

    frame["source_row_number"] = row_status["source_row_number"]
    frame["structurally_valid"] = row_status["structurally_valid"]
    frame["exact_duplicate"] = row_status["exact_duplicate"]
    frame["scoring_eligible"] = row_status["scoring_eligible"]
    frame["intake_issue_codes"] = row_status["issue_codes"]
    frame["name_normalized"] = frame["name"].map(
        lambda value: None if is_missing(value) else str(value).strip()
    )

    facility_types = frame["facilityTypeId"].map(
        lambda value: normalize_enum(value, FACILITY_TYPE_MAP)
    )
    frame["facility_type_normalized"] = facility_types.str[0]
    frame["facility_type_normalization_action"] = facility_types.str[1]

    operator_types = frame["operatorTypeId"].map(
        lambda value: normalize_enum(value, OPERATOR_TYPE_MAP)
    )
    frame["operator_type_normalized"] = operator_types.str[0]
    frame["operator_type_normalization_action"] = operator_types.str[1]

    affiliations = frame["affiliationTypeIds"].map(normalize_affiliations)
    frame["affiliation_type_ids_normalized"] = affiliations.str[0]
    frame["affiliation_type_ids_status"] = affiliations.str[1]

    for field in CLAIM_FIELDS:
        parsed = frame[field].map(parse_string_list)
        frame[f"{field}_parsed"] = parsed.str[0]
        frame[f"{field}_parse_status"] = parsed.str[1]

    for field in ["numberDoctors", "capacity", "yearEstablished"]:
        normalized, status = normalize_integer_series(frame[field])
        frame[f"{field}_normalized"] = normalized
        frame[f"{field}_normalization_status"] = status

    pincodes = frame["address_zipOrPostcode"].map(normalize_pincode)
    frame["pincode_normalized"] = pincodes.str[0]
    frame["pincode_normalization_status"] = pincodes.str[1]
    frame["state_name_normalized"] = frame["address_stateOrRegion"].map(normalize_name)

    frame["latitude_normalized"] = pd.to_numeric(frame["latitude"], errors="coerce")
    frame["longitude_normalized"] = pd.to_numeric(frame["longitude"], errors="coerce")
    frame["coordinate_pair_status"] = [
        coordinate_status(latitude, longitude)
        for latitude, longitude in zip(
            frame["latitude"], frame["longitude"], strict=True
        )
    ]

    lookup = pin_lookup.copy()
    lookup["pincode"] = lookup["pincode"].astype(str).str.zfill(6)
    lookup = lookup.drop_duplicates("pincode").set_index("pincode")
    frame["pincode_reference_status"] = frame["pincode_normalized"].map(
        lookup["resolution_status"]
    )
    frame["pincode_reference_district"] = frame["pincode_normalized"].map(
        lookup["preferred_district"]
    )
    frame["pincode_reference_state"] = frame["pincode_normalized"].map(
        lookup["preferred_state"]
    )
    exact_reference = frame["pincode_reference_status"].eq("exact")
    frame["district_assigned_from_pincode"] = frame[
        "pincode_reference_district"
    ].where(exact_reference)
    frame["state_assigned_from_pincode"] = frame["pincode_reference_state"].where(
        exact_reference
    )
    frame["pincode_join_confidence"] = "unresolved"
    frame.loc[exact_reference, "pincode_join_confidence"] = "exact_reference_mapping"
    frame.loc[
        frame["pincode_reference_status"].notna() & ~exact_reference,
        "pincode_join_confidence",
    ] = "ambiguous_reference_mapping"
    frame.loc[
        frame["pincode_normalization_status"].eq("missing"),
        "pincode_join_confidence",
    ] = "missing_pincode"
    frame.loc[
        frame["pincode_normalization_status"].eq("invalid"),
        "pincode_join_confidence",
    ] = "invalid_pincode"
    return frame


def check(check_id: str, status: str, message: str, observed: object) -> dict:
    return {
        "check_id": check_id,
        "status": status,
        "message": message,
        "observed": observed,
    }


def validate_analysis_base(
    raw: pd.DataFrame,
    normalized: pd.DataFrame,
) -> tuple[dict, dict]:
    source_columns = [str(column) for column in raw.columns]
    checks = []
    checks.append(
        check(
            "normalization.row_preservation",
            "pass" if len(raw) == len(normalized) else "fail",
            "Normalization preserves every raw source row.",
            {"raw_rows": len(raw), "normalized_rows": len(normalized)},
        )
    )
    source_preserved = raw.set_axis(source_columns, axis=1).equals(
        normalized[source_columns]
    )
    checks.append(
        check(
            "normalization.source_field_preservation",
            "pass" if source_preserved else "fail",
            "All 51 source columns remain unchanged in the analysis base.",
            {"source_columns": len(source_columns), "preserved": source_preserved},
        )
    )

    eligible = normalized[normalized["scoring_eligible"]]
    unique_eligible_ids = eligible["unique_id"].nunique()
    checks.append(
        check(
            "normalization.scoring_grain",
            (
                "pass"
                if len(eligible) == unique_eligible_ids
                and not eligible["exact_duplicate"].any()
                else "fail"
            ),
            "Scoring-eligible rows are one row per facility ID.",
            {
                "eligible_rows": len(eligible),
                "unique_facility_ids": unique_eligible_ids,
            },
        )
    )

    for column, allowed in [
        ("facility_type_normalized", CONTRACT["allowed_values"]["facilityTypeId"]),
        ("operator_type_normalized", CONTRACT["allowed_values"]["operatorTypeId"]),
    ]:
        values = set(eligible[column].dropna())
        invalid = sorted(values - set(allowed))
        checks.append(
            check(
                f"normalization.{column}",
                "pass" if not invalid else "fail",
                f"{column} contains only contract values or null.",
                invalid,
            )
        )

    unmapped_facility_types = int(
        eligible["facility_type_normalization_action"].eq("unmapped").sum()
    )
    checks.append(
        check(
            "normalization.unmapped_facility_types",
            "warn" if unmapped_facility_types else "pass",
            "Unsupported facility categories remain null and visible for review.",
            unmapped_facility_types,
        )
    )

    unsafe_assignments = int(
        (
            normalized["district_assigned_from_pincode"].notna()
            & ~normalized["pincode_reference_status"].eq("exact")
        ).sum()
    )
    checks.append(
        check(
            "normalization.pincode_assignment_safety",
            "pass" if not unsafe_assignments else "fail",
            "PIN-derived districts are assigned only from exact reference mappings.",
            unsafe_assignments,
        )
    )

    unresolved_pincodes = int(
        eligible["pincode_join_confidence"].ne("exact_reference_mapping").sum()
    )
    checks.append(
        check(
            "normalization.pincode_coverage",
            "warn" if unresolved_pincodes else "pass",
            "Unresolved or ambiguous PIN joins remain explicitly flagged.",
            {
                "exact_reference_mappings": int(
                    eligible["pincode_join_confidence"]
                    .eq("exact_reference_mapping")
                    .sum()
                ),
                "not_exact": unresolved_pincodes,
            },
        )
    )

    invalid_claim_rows = 0
    for field in CLAIM_FIELDS:
        invalid_claim_rows += int(
            eligible[f"{field}_parse_status"]
            .isin({"invalid_scalar", "invalid_type", "invalid_members"})
            .sum()
        )
    checks.append(
        check(
            "normalization.claim_parsing",
            "warn" if invalid_claim_rows else "pass",
            "Claim parsing failures are counted and never converted into empty lists.",
            invalid_claim_rows,
        )
    )

    failures = sum(item["status"] == "fail" for item in checks)
    warnings = sum(item["status"] == "warn" for item in checks)
    validation = {
        "generated_at": pd.Timestamp.utcnow().isoformat(),
        "overall_status": (
            "failed" if failures else "passed_with_warnings" if warnings else "passed"
        ),
        "summary": {
            "checks": len(checks),
            "passed": sum(item["status"] == "pass" for item in checks),
            "warnings": warnings,
            "failed": failures,
        },
        "checks": checks,
    }

    profile = {
        "generated_at": pd.Timestamp.utcnow().isoformat(),
        "raw_rows": len(raw),
        "analysis_base_rows": len(normalized),
        "source_columns_preserved": len(source_columns),
        "derived_columns": len(normalized.columns) - len(source_columns),
        "structurally_valid_rows": int(normalized["structurally_valid"].sum()),
        "scoring_eligible_rows": int(normalized["scoring_eligible"].sum()),
        "facility_type_actions": {
            str(key): int(value)
            for key, value in eligible[
                "facility_type_normalization_action"
            ].value_counts(dropna=False).items()
        },
        "operator_type_actions": {
            str(key): int(value)
            for key, value in eligible[
                "operator_type_normalization_action"
            ].value_counts(dropna=False).items()
        },
        "pincode_join_confidence": {
            str(key): int(value)
            for key, value in eligible["pincode_join_confidence"]
            .value_counts(dropna=False)
            .items()
        },
        "coordinate_pair_status": {
            str(key): int(value)
            for key, value in eligible["coordinate_pair_status"]
            .value_counts(dropna=False)
            .items()
        },
        "claim_parse_status": {
            field: {
                str(key): int(value)
                for key, value in eligible[f"{field}_parse_status"]
                .value_counts(dropna=False)
                .items()
            }
            for field in CLAIM_FIELDS
        },
    }
    return profile, validation


def build_issue_output(normalized: pd.DataFrame) -> pd.DataFrame:
    issue_mask = (
        normalized["intake_issue_codes"].ne("")
        | normalized["facility_type_normalization_action"].isin(
            {"corrected_typo", "unmapped"}
        )
        | normalized["operator_type_normalization_action"].isin(
            {"mapped_synonym", "unmapped"}
        )
        | normalized["pincode_join_confidence"].ne("exact_reference_mapping")
    )
    columns = [
        "source_row_number",
        "unique_id",
        "name",
        "scoring_eligible",
        "intake_issue_codes",
        "facilityTypeId",
        "facility_type_normalized",
        "facility_type_normalization_action",
        "operatorTypeId",
        "operator_type_normalized",
        "operator_type_normalization_action",
        "address_zipOrPostcode",
        "pincode_normalized",
        "pincode_reference_status",
        "pincode_join_confidence",
    ]
    return normalized.loc[issue_mask, columns]


def write_outputs(
    normalized: pd.DataFrame,
    profile: dict,
    validation: dict,
) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    VALIDATION_PATH.parent.mkdir(parents=True, exist_ok=True)
    normalized.to_parquet(OUTPUT_PATH, index=False)
    build_issue_output(normalized).to_csv(ISSUES_PATH, index=False)
    PROFILE_PATH.write_text(json.dumps(profile, indent=2), encoding="utf-8")
    VALIDATION_PATH.write_text(json.dumps(validation, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the provenance-preserving facility analysis base."
    )
    parser.add_argument(
        "source",
        type=Path,
        nargs="?",
        default=DEFAULT_SOURCE,
        help="Validated facility source file.",
    )
    parser.add_argument(
        "--pin-lookup",
        type=Path,
        default=PIN_LOOKUP_PATH,
        help="One-row-per-PIN conservative reference lookup.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    raw = read_facility_data(args.source.expanduser().resolve())
    pin_lookup = pd.read_csv(
        args.pin_lookup.expanduser().resolve(),
        dtype={"pincode": str},
    )
    normalized = build_analysis_base(raw, pin_lookup)
    profile, validation = validate_analysis_base(raw, normalized)
    write_outputs(normalized, profile, validation)
    print(
        f"{validation['overall_status']}: "
        f"{validation['summary']['passed']} passed, "
        f"{validation['summary']['warnings']} warnings, "
        f"{validation['summary']['failed']} failed"
    )
    if validation["overall_status"] == "failed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
