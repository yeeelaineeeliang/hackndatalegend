from __future__ import annotations

import json
from difflib import get_close_matches
from pathlib import Path

import pandas as pd

from src.data_quality import (
    INDIA_LATITUDE_BOUNDS,
    INDIA_LONGITUDE_BOUNDS,
    coordinate_status,
    normalize_name,
    snake_case,
)


ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw" / "supplemental"
PROCESSED_DIR = ROOT / "data" / "processed"
OUTPUT_DIR = ROOT / "outputs" / "validation"

PIN_COLUMNS = {
    "circlename",
    "regionname",
    "divisionname",
    "officename",
    "pincode",
    "officetype",
    "delivery",
    "district",
    "statename",
    "latitude",
    "longitude",
}
NFHS_IDENTIFIER_COLUMNS = {"District Names", "State/UT"}


def check(check_id: str, status: str, message: str, observed: object = None) -> dict:
    result = {"check_id": check_id, "status": status, "message": message}
    if observed is not None:
        result["observed"] = observed
    return result


def build_geography_crosswalk_candidates(pin: pd.DataFrame, nfhs: pd.DataFrame) -> pd.DataFrame:
    pin_pairs = (
        pd.DataFrame(
            {
                "state_normalized": pin["statename"].map(normalize_name),
                "district_normalized": pin["district"].map(normalize_name),
            }
        )
        .dropna()
        .drop_duplicates()
    )
    nfhs_pairs = (
        pd.DataFrame(
            {
                "state_raw": nfhs["State/UT"].str.strip(),
                "district_raw": nfhs["District Names"].str.strip(),
                "state_normalized": nfhs["State/UT"].map(normalize_name),
                "district_normalized": nfhs["District Names"].map(normalize_name),
            }
        )
        .drop_duplicates()
        .sort_values(["state_normalized", "district_normalized"])
    )
    exact_pairs = set(zip(pin_pairs["state_normalized"], pin_pairs["district_normalized"]))
    districts_by_state = {
        state: sorted(group["district_normalized"].dropna().unique())
        for state, group in pin_pairs.groupby("state_normalized")
    }

    records = []
    for row in nfhs_pairs.itertuples(index=False):
        exact_match = (row.state_normalized, row.district_normalized) in exact_pairs
        candidates = []
        if not exact_match:
            candidates = get_close_matches(
                row.district_normalized,
                districts_by_state.get(row.state_normalized, []),
                n=3,
                cutoff=0.45,
            )
        records.append(
            {
                "nfhs_state_raw": row.state_raw,
                "nfhs_district_raw": row.district_raw,
                "state_normalized": row.state_normalized,
                "district_normalized": row.district_normalized,
                "exact_match": exact_match,
                "candidate_1": candidates[0] if len(candidates) > 0 else None,
                "candidate_2": candidates[1] if len(candidates) > 1 else None,
                "candidate_3": candidates[2] if len(candidates) > 2 else None,
                "review_status": "accepted_exact" if exact_match else "requires_review",
            }
        )
    return pd.DataFrame(records)


def validate() -> dict:
    pin_path = RAW_DIR / "india_post_pincode_directory.csv"
    nfhs_path = RAW_DIR / "nfhs5_district_health_indicators.csv"
    preferred_path = PROCESSED_DIR / "pincode_lookup_preferred.csv"
    clean_nfhs_path = PROCESSED_DIR / "nfhs5_district_health_indicators_clean.csv"

    pin = pd.read_csv(pin_path, dtype=str, keep_default_na=False)
    nfhs = pd.read_csv(nfhs_path, dtype=str, keep_default_na=False)
    preferred = pd.read_csv(preferred_path, dtype={"pincode": str})
    clean_nfhs = pd.read_csv(clean_nfhs_path)
    checks = []

    missing_pin_columns = sorted(PIN_COLUMNS - set(pin.columns))
    checks.append(
        check(
            "pin.required_columns",
            "fail" if missing_pin_columns else "pass",
            "PIN source contains all required columns.",
            missing_pin_columns,
        )
    )
    invalid_pincodes = int((~pin["pincode"].str.strip().str.fullmatch(r"\d{6}")).sum())
    checks.append(
        check(
            "pin.format",
            "fail" if invalid_pincodes else "pass",
            "PIN values are six digits.",
            invalid_pincodes,
        )
    )

    pin["coordinate_status"] = [
        coordinate_status(latitude, longitude)
        for latitude, longitude in zip(pin["latitude"], pin["longitude"], strict=True)
    ]
    coordinate_counts = {
        key: int(value) for key, value in pin["coordinate_status"].value_counts().to_dict().items()
    }
    coordinate_issues = pin[pin["coordinate_status"] != "valid"].copy()
    coordinate_issues.to_csv(PROCESSED_DIR / "pincode_coordinate_issues.csv", index=False)
    invalid_coordinate_count = coordinate_counts.get("likely_swapped", 0) + coordinate_counts.get(
        "out_of_bounds", 0
    )
    checks.append(
        check(
            "pin.coordinate_quality",
            "warn" if invalid_coordinate_count else "pass",
            "Invalid coordinates are quarantined and excluded from preferred PIN means.",
            coordinate_counts,
        )
    )

    unique_pincodes = int(pin["pincode"].str.strip().replace("", pd.NA).dropna().nunique())
    preferred_unique = int(preferred["pincode"].nunique())
    cardinality_valid = len(preferred) == unique_pincodes == preferred_unique
    checks.append(
        check(
            "pin.preferred_cardinality",
            "pass" if cardinality_valid else "fail",
            "Preferred PIN lookup has exactly one row per source PIN.",
            {
                "source_unique_pincodes": unique_pincodes,
                "preferred_rows": len(preferred),
                "preferred_unique_pincodes": preferred_unique,
            },
        )
    )
    safe_mask = preferred["is_safe_for_direct_join"].astype(str).str.lower() == "true"
    unsafe_safe_rows = int((safe_mask & (preferred["resolution_status"] != "exact")).sum())
    checks.append(
        check(
            "pin.safe_join_policy",
            "fail" if unsafe_safe_rows else "pass",
            "Only exact PIN mappings are marked safe for direct joins.",
            unsafe_safe_rows,
        )
    )
    invalid_preferred_means = int(
        (
            preferred["mean_valid_latitude"].notna()
            & ~preferred["mean_valid_latitude"].between(*INDIA_LATITUDE_BOUNDS)
        ).sum()
        + (
            preferred["mean_valid_longitude"].notna()
            & ~preferred["mean_valid_longitude"].between(*INDIA_LONGITUDE_BOUNDS)
        ).sum()
    )
    checks.append(
        check(
            "pin.preferred_coordinate_bounds",
            "fail" if invalid_preferred_means else "pass",
            "Preferred coordinate means contain only validated India coordinate pairs.",
            invalid_preferred_means,
        )
    )

    missing_nfhs_identifiers = sorted(NFHS_IDENTIFIER_COLUMNS - set(nfhs.columns))
    checks.append(
        check(
            "nfhs.identifier_columns",
            "fail" if missing_nfhs_identifiers else "pass",
            "NFHS source contains its district and state identifiers.",
            missing_nfhs_identifiers,
        )
    )
    snake_names = [snake_case(column) for column in nfhs.columns]
    snake_collisions = sorted({name for name in snake_names if snake_names.count(name) > 1})
    checks.append(
        check(
            "nfhs.snake_case_collisions",
            "fail" if snake_collisions else "pass",
            "NFHS headers remain unique after snake_case normalization.",
            snake_collisions,
        )
    )
    duplicate_district_rows = int(
        clean_nfhs.duplicated(["state_ut_normalized", "district_normalized"], keep=False).sum()
    )
    checks.append(
        check(
            "nfhs.district_grain",
            "fail" if duplicate_district_rows else "pass",
            "Clean NFHS output has one row per normalized state and district pair.",
            duplicate_district_rows,
        )
    )
    indicator_columns = [
        column
        for column in snake_names
        if column not in {"district_names", "state_ut"}
    ]
    nonnumeric_cells = 0
    for column in indicator_columns:
        series = clean_nfhs[column].dropna()
        nonnumeric_cells += int(pd.to_numeric(series, errors="coerce").isna().sum())
    checks.append(
        check(
            "nfhs.numeric_indicators",
            "fail" if nonnumeric_cells else "pass",
            "All cleaned NFHS indicator values are numeric or null.",
            nonnumeric_cells,
        )
    )

    crosswalk = build_geography_crosswalk_candidates(pin, nfhs)
    crosswalk.to_csv(PROCESSED_DIR / "nfhs_pincode_geography_crosswalk_candidates.csv", index=False)
    exact_matches = int(crosswalk["exact_match"].sum())
    exact_match_rate = exact_matches / len(crosswalk)
    checks.append(
        check(
            "geography.cross_source_match",
            "pass" if exact_match_rate >= 0.95 else "warn",
            "Unmatched NFHS geography pairs require review or spatial assignment before enrichment.",
            {
                "exact_matches": exact_matches,
                "total_nfhs_pairs": len(crosswalk),
                "exact_match_rate": round(exact_match_rate, 4),
                "requires_review": int((~crosswalk["exact_match"]).sum()),
            },
        )
    )

    failed = sum(item["status"] == "fail" for item in checks)
    warned = sum(item["status"] == "warn" for item in checks)
    overall_status = "failed" if failed else "passed_with_warnings" if warned else "passed"
    return {
        "generated_at": pd.Timestamp.utcnow().isoformat(),
        "overall_status": overall_status,
        "summary": {
            "checks": len(checks),
            "passed": sum(item["status"] == "pass" for item in checks),
            "warnings": warned,
            "failed": failed,
        },
        "checks": checks,
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    report = validate()
    output_path = OUTPUT_DIR / "supplemental_validation_report.json"
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        f"{report['overall_status']}: "
        f"{report['summary']['passed']} passed, "
        f"{report['summary']['warnings']} warnings, "
        f"{report['summary']['failed']} failed"
    )
    print(f"Wrote {output_path.relative_to(ROOT)}")
    if report["overall_status"] == "failed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()

