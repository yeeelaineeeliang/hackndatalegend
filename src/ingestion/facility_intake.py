from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import shutil
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
RAW_FACILITY_DIR = ROOT / "data" / "raw" / "facilities"
PROCESSED_DIR = ROOT / "data" / "processed"
PROFILE_DIR = ROOT / "outputs" / "profiling"
VALIDATION_DIR = ROOT / "outputs" / "validation"
CONTRACT_PATH = ROOT / "config" / "facility_schema_contract.json"

SUPPORTED_SUFFIXES = {".csv", ".json", ".jsonl", ".parquet"}
UUID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-"
    r"[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
)
CONTRACT = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
CONTRACT_FIELDS = (
    set(CONTRACT["identity_fields"])
    | set(CONTRACT["core_readiness_fields"])
    | set(CONTRACT["geography_fields"])
)
CORE_FIELDS = ["name", *CONTRACT["core_readiness_fields"]]
CLAIM_FIELDS = [
    field
    for field, field_type in CONTRACT["core_readiness_fields"].items()
    if field_type == "list[string]"
]
NUMERIC_FIELDS = [
    field
    for field, field_type in CONTRACT["core_readiness_fields"].items()
    if field_type == "integer"
]
COLUMN_ALIASES = {
    "name": ["facility_name", "facilityName", "organization_name", "organizationName"],
    "description": ["facility_description", "facilityDescription"],
    "capability": ["capabilities"],
    "procedure": ["procedures"],
    "equipment": ["equipments"],
    "numberDoctors": ["number_doctors", "doctor_count", "doctors"],
    "capacity": ["bed_capacity", "number_beds", "beds"],
    "yearEstablished": ["year_established", "established_year"],
    "address_zipOrPostcode": ["pincode", "pin_code", "postal_code", "postcode", "zip"],
    "address_stateOrRegion": ["state", "state_name", "region"],
    "address_city": ["city", "town"],
    "latitude": ["lat"],
    "longitude": ["lon", "lng", "long"],
}


def normalized_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_facility_data(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path, dtype=object)
    if suffix == ".parquet":
        return pd.read_parquet(path)
    if suffix == ".jsonl":
        return pd.read_json(path, lines=True)
    if suffix == ".json":
        return pd.read_json(path)
    raise ValueError(f"Unsupported facility data format: {suffix}")


def resolve_columns(columns: list[str]) -> dict[str, str | None]:
    token_to_columns: dict[str, list[str]] = {}
    for column in columns:
        token_to_columns.setdefault(normalized_token(column), []).append(column)

    resolved = {}
    for canonical in CONTRACT_FIELDS | set(COLUMN_ALIASES):
        candidates = [canonical, *COLUMN_ALIASES.get(canonical, [])]
        matches = []
        for candidate in candidates:
            matches.extend(token_to_columns.get(normalized_token(candidate), []))
        unique_matches = list(dict.fromkeys(matches))
        resolved[canonical] = unique_matches[0] if len(unique_matches) == 1 else None
    return resolved


def is_missing(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and pd.isna(value):
        return True
    if isinstance(value, str) and value.strip().lower() in {"", "null", "none", "na", "n/a"}:
        return True
    return False


def list_value_status(value: object) -> str:
    if is_missing(value):
        return "missing"
    if isinstance(value, list):
        return "native_list"
    if isinstance(value, tuple):
        return "native_list"
    if not isinstance(value, str):
        return "invalid_type"

    text = value.strip()
    if text == "[]":
        return "empty_list"
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        try:
            parsed = ast.literal_eval(text)
        except (SyntaxError, ValueError):
            return "scalar_text"
    return "parsed_list" if isinstance(parsed, list) else "scalar_text"


def build_column_profile(frame: pd.DataFrame) -> pd.DataFrame:
    rows = len(frame)
    records = []
    for column in frame.columns:
        series = frame[column]
        missing = series.map(is_missing)
        records.append(
            {
                "column": column,
                "dtype": str(series.dtype),
                "missing_count": int(missing.sum()),
                "missing_pct": round(float(missing.mean() * 100), 4) if rows else 0.0,
                "unique_non_missing": int(series[~missing].astype(str).nunique()),
            }
        )
    return pd.DataFrame(records)


def build_row_status(frame: pd.DataFrame) -> pd.DataFrame:
    unique_id = frame.get("unique_id", pd.Series(index=frame.index, dtype=object))
    organization_type = frame.get(
        "organization_type", pd.Series(index=frame.index, dtype=object)
    )
    valid_uuid = unique_id.astype(str).str.fullmatch(UUID_PATTERN.pattern, na=False)
    valid_organization_type = organization_type.eq("facility")
    structurally_valid = valid_uuid & valid_organization_type
    exact_duplicate = frame.astype(str).duplicated(keep="first") & structurally_valid
    duplicate_unique_id = unique_id.duplicated(keep=False) & structurally_valid

    issue_codes = []
    for index in frame.index:
        issues = []
        if not valid_uuid.loc[index]:
            issues.append("invalid_unique_id")
        if not valid_organization_type.loc[index]:
            issues.append("invalid_organization_type")
        if duplicate_unique_id.loc[index]:
            issues.append("duplicate_unique_id")
        issue_codes.append("|".join(issues))

    return pd.DataFrame(
        {
            "source_row_number": frame.index + 2,
            "unique_id": unique_id,
            "name": frame.get("name", pd.Series(index=frame.index, dtype=object)),
            "organization_type": organization_type,
            "structurally_valid": structurally_valid,
            "exact_duplicate": exact_duplicate,
            "scoring_eligible": structurally_valid & ~exact_duplicate,
            "issue_codes": issue_codes,
        },
        index=frame.index,
    )


def check(check_id: str, status: str, message: str, observed: object = None) -> dict:
    result = {"check_id": check_id, "status": status, "message": message}
    if observed is not None:
        result["observed"] = observed
    return result


def analyze_facility_data(frame: pd.DataFrame, source_name: str) -> tuple[dict, dict, pd.DataFrame]:
    columns = [str(column) for column in frame.columns]
    frame = frame.copy()
    frame.columns = columns
    resolved = resolve_columns(columns)
    column_profile = build_column_profile(frame)
    row_status = build_row_status(frame)
    valid_frame = frame[row_status["structurally_valid"]]

    coverage = {}
    for canonical in CORE_FIELDS:
        source_column = resolved.get(canonical)
        if source_column is None:
            coverage[canonical] = None
            continue
        missing = valid_frame[source_column].map(is_missing)
        coverage[canonical] = (
            round(float((~missing).mean()), 4) if len(valid_frame) else 0.0
        )

    claim_parsing = {}
    for canonical in CLAIM_FIELDS:
        source_column = resolved.get(canonical)
        if source_column is None:
            claim_parsing[canonical] = None
            continue
        statuses = valid_frame[source_column].map(list_value_status).value_counts().to_dict()
        claim_parsing[canonical] = {key: int(value) for key, value in statuses.items()}

    numeric_parsing = {}
    for canonical in NUMERIC_FIELDS:
        source_column = resolved.get(canonical)
        if source_column is None:
            numeric_parsing[canonical] = None
            continue
        source = valid_frame[source_column]
        missing = source.map(is_missing)
        non_missing = source[~missing]
        parsed = pd.to_numeric(non_missing, errors="coerce")
        numeric_parsing[canonical] = {
            "non_missing": int(len(non_missing)),
            "parse_failures": int(parsed.isna().sum()),
            "negative_values": int((parsed < 0).sum()),
        }

    profile = {
        "generated_at": pd.Timestamp.utcnow().isoformat(),
        "source_name": source_name,
        "contract_version": CONTRACT["contract_version"],
        "rows": len(frame),
        "structurally_valid_rows": int(row_status["structurally_valid"].sum()),
        "quarantined_malformed_rows": int((~row_status["structurally_valid"]).sum()),
        "exact_duplicate_rows": int(row_status["exact_duplicate"].sum()),
        "scoring_eligible_rows": int(row_status["scoring_eligible"].sum()),
        "columns": len(frame.columns),
        "duplicate_rows": int(frame.astype(str).duplicated().sum()),
        "resolved_columns": resolved,
        "core_field_coverage": coverage,
        "claim_field_parsing": claim_parsing,
        "numeric_field_parsing": numeric_parsing,
    }

    checks = []
    checks.append(
        check(
            "facility.non_empty",
            "pass" if len(frame) else "fail",
            "Facility source contains records.",
            len(frame),
        )
    )
    malformed_rows = int((~row_status["structurally_valid"]).sum())
    checks.append(
        check(
            "facility.structural_rows",
            "warn" if malformed_rows else "pass",
            "Rows without a valid facility UUID and organization type are quarantined.",
            {
                "structurally_valid": int(row_status["structurally_valid"].sum()),
                "quarantined": malformed_rows,
            },
        )
    )
    duplicate_ids = (
        valid_frame["unique_id"].nunique()
        if "unique_id" in valid_frame
        else 0
    )
    duplicated_id_rows = (
        int(valid_frame["unique_id"].duplicated(keep=False).sum())
        if "unique_id" in valid_frame
        else 0
    )
    checks.append(
        check(
            "facility.unique_id",
            "warn" if duplicated_id_rows else "pass",
            "Duplicate facility IDs are retained for review and exact duplicate copies are ineligible for scoring.",
            {
                "duplicate_ids": int(len(valid_frame) - duplicate_ids),
                "rows_with_duplicate_ids": duplicated_id_rows,
                "exact_duplicate_copies": int(row_status["exact_duplicate"].sum()),
            },
        )
    )
    checks.append(
        check(
            "facility.expected_scale",
            "pass" if 9000 <= len(valid_frame) <= 11000 else "warn",
            "Challenge brief describes approximately 10,000 facility rows.",
            len(valid_frame),
        )
    )
    missing_core = [field for field in CORE_FIELDS if resolved.get(field) is None]
    checks.append(
        check(
            "facility.core_columns",
            "fail" if missing_core else "pass",
            "Core readiness fields can be resolved without ambiguous aliases.",
            missing_core,
        )
    )

    for field, stats in numeric_parsing.items():
        if stats is None:
            continue
        failures = stats["parse_failures"]
        negatives = stats["negative_values"]
        checks.append(
            check(
                f"facility.{field}_parsing",
                "warn" if failures or negatives else "pass",
                f"{field} values are non-negative and numerically parseable when present.",
                stats,
            )
        )

    for field in ["facilityTypeId", "operatorTypeId"]:
        source_column = resolved.get(field)
        if source_column is None:
            continue
        allowed = set(CONTRACT["allowed_values"][field])
        values = (
            valid_frame[source_column][~valid_frame[source_column].map(is_missing)]
            .astype(str)
            .str.strip()
        )
        invalid_values = sorted(set(values) - allowed)
        checks.append(
            check(
                f"facility.{field}_enum",
                "warn" if invalid_values else "pass",
                f"{field} values conform to the challenge schema enumeration.",
                invalid_values,
            )
        )

    for field, statuses in claim_parsing.items():
        if statuses is None:
            continue
        inspected = sum(
            count for status, count in statuses.items() if status not in {"missing"}
        )
        list_values = sum(
            count
            for status, count in statuses.items()
            if status in {"native_list", "parsed_list", "empty_list"}
        )
        ratio = list_values / inspected if inspected else 0.0
        checks.append(
            check(
                f"facility.{field}_list_shape",
                "pass" if ratio >= 0.95 else "warn",
                f"{field} preserves list structure; scalar text requires explicit parsing policy.",
                {"list_shape_rate": round(ratio, 4), "statuses": statuses},
            )
        )

    geography_fields = [
        "address_zipOrPostcode",
        "address_stateOrRegion",
        "address_city",
        "latitude",
        "longitude",
    ]
    resolved_geography = {
        field: resolved.get(field) for field in geography_fields if resolved.get(field)
    }
    checks.append(
        check(
            "facility.geography_keys",
            "pass" if resolved_geography else "warn",
            "At least one geography key is available for reference enrichment.",
            resolved_geography,
        )
    )

    failures = sum(item["status"] == "fail" for item in checks)
    warnings = sum(item["status"] == "warn" for item in checks)
    validation = {
        "generated_at": pd.Timestamp.utcnow().isoformat(),
        "source_name": source_name,
        "overall_status": "failed" if failures else "passed_with_warnings" if warnings else "passed",
        "summary": {
            "checks": len(checks),
            "passed": sum(item["status"] == "pass" for item in checks),
            "warnings": warnings,
            "failed": failures,
        },
        "checks": checks,
    }
    return profile, validation, column_profile


def stage_source(source_path: Path) -> Path:
    if source_path.suffix.lower() not in SUPPORTED_SUFFIXES:
        raise ValueError(f"Unsupported facility data format: {source_path.suffix}")
    RAW_FACILITY_DIR.mkdir(parents=True, exist_ok=True)
    destination = RAW_FACILITY_DIR / f"healthcare_facilities{source_path.suffix.lower()}"
    source_hash = file_sha256(source_path)
    if destination.exists() and file_sha256(destination) != source_hash:
        raise FileExistsError(
            f"{destination.relative_to(ROOT)} already exists with different contents; "
            "refusing to overwrite the canonical raw source."
        )
    if not destination.exists():
        shutil.copy2(source_path, destination)

    manifest = {
        "source_filename": source_path.name,
        "canonical_path": str(destination.relative_to(ROOT)),
        "sha256": source_hash,
        "bytes": source_path.stat().st_size,
        "staged_at": pd.Timestamp.utcnow().isoformat(),
    }
    manifest_path = RAW_FACILITY_DIR / "source_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return destination


def write_outputs(
    profile: dict,
    validation: dict,
    column_profile: pd.DataFrame,
    row_status: pd.DataFrame,
    frame: pd.DataFrame,
) -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    column_profile.to_csv(PROCESSED_DIR / "facility_column_profile.csv", index=False)
    row_status.to_csv(PROCESSED_DIR / "facility_row_status.csv", index=False)
    issue_mask = row_status["issue_codes"].ne("")
    issue_columns = [
        column
        for column in [
            "unique_id",
            "name",
            "organization_type",
            "facilityTypeId",
            "operatorTypeId",
            "numberDoctors",
            "capacity",
            "yearEstablished",
        ]
        if column in frame
    ]
    issue_output = pd.concat(
        [
            row_status.loc[issue_mask, ["source_row_number", "issue_codes", "scoring_eligible"]],
            frame.loc[issue_mask, issue_columns],
        ],
        axis=1,
    )
    issue_output.to_csv(PROCESSED_DIR / "facility_ingestion_issues.csv", index=False)
    (PROFILE_DIR / "facility_data_profile.json").write_text(
        json.dumps(profile, indent=2),
        encoding="utf-8",
    )
    (VALIDATION_DIR / "facility_ingestion_validation.json").write_text(
        json.dumps(validation, indent=2),
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stage, profile, and validate the challenge facility dataset."
    )
    parser.add_argument("source", type=Path, help="Path to CSV, JSON, JSONL, or Parquet data.")
    parser.add_argument(
        "--stage",
        action="store_true",
        help="Copy the source into data/raw/facilities with a checksum manifest.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source_path = args.source.expanduser().resolve()
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    intake_path = stage_source(source_path) if args.stage else source_path
    frame = read_facility_data(intake_path)
    profile, validation, column_profile = analyze_facility_data(frame, intake_path.name)
    row_status = build_row_status(frame)
    write_outputs(profile, validation, column_profile, row_status, frame)
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
