from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pandas as pd

from src.ingestion.facility_intake import ROOT
from src.scoring.build_trust_signals import list_or_none, trace_list


ANALYSIS_BASE_PATH = ROOT / "data" / "processed" / "facilities_analysis_base.parquet"
SIGNALS_PATH = ROOT / "data" / "processed" / "facility_trust_signals.parquet"
FLAGS_PATH = ROOT / "data" / "processed" / "facility_flags.parquet"
QUEUE_PATH = ROOT / "data" / "processed" / "facility_review_queue.parquet"
APP_DATA_DIR = ROOT / "app" / "data"
APP_VALIDATION_PATH = ROOT / "outputs" / "validation" / "app_asset_validation.json"
DETAIL_SHARDS = 8
MAX_DATABRICKS_APP_FILE_BYTES = 10 * 1024 * 1024

CLAIM_THEME_PATTERNS = {
    "Emergency & trauma": r"\b(emergency|trauma|casualty)\b",
    "Critical care": r"\b(icu|intensive care|ventilator|critical care)\b",
    "Maternity": r"\b(maternity|obstetric|delivery|gynae|gynec)\w*",
    "Neonatal & pediatric": r"\b(nicu|neonat|pediatric|paediatric)\w*",
    "Oncology": r"\b(oncology|cancer|chemotherapy|radiotherapy)\b",
    "Cardiac care": r"\b(cardiac|cardiology|cath lab|cardiovascular)\b",
    "Renal & dialysis": r"\b(?:hemo|haemo|peri)?dialysis\b|\b(?:renal|nephro)\w*",
    "Surgery": r"\b(surgery|surgical|operation theatre|operating theatre)\b",
    "Diagnostics": r"\b(mri|ct scan|ultrasound|radiology|diagnostic)\w*",
    "Blood services": r"\b(blood bank|transfusion)\b",
}
CLAIM_THEME_REGEX = {
    label: re.compile(pattern, re.IGNORECASE)
    for label, pattern in CLAIM_THEME_PATTERNS.items()
}


def detail_shard(unique_id: str, shard_count: int = DETAIL_SHARDS) -> int:
    digest = hashlib.sha256(unique_id.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % shard_count


def derive_claim_themes(row: pd.Series) -> list[str]:
    claims: list[str] = []
    for field in ["capability_parsed", "procedure_parsed", "equipment_parsed"]:
        claims.extend(list_or_none(row[field]) or [])
    text = " ".join(claims)
    return [
        label for label, pattern in CLAIM_THEME_REGEX.items() if pattern.search(text)
    ]


def aggregate_flag_index(flags: pd.DataFrame) -> pd.DataFrame:
    records = []
    for unique_id, group in flags.groupby("unique_id", sort=False):
        flag_types = sorted(set(group["flag_type"].astype(str)))
        records.append(
            {
                "unique_id": unique_id,
                "flag_types": flag_types,
                "reason_codes": sorted(set(group["reason_code"].astype(str))),
                "severities": sorted(set(group["severity"].astype(str))),
                "has_contradiction": "contradiction" in flag_types,
                "has_weak_evidence": bool(
                    set(flag_types) & {"weak_evidence", "traceability_gap"}
                ),
                "has_geography_uncertainty": "geography_uncertainty" in flag_types,
                "has_information_gap": bool(
                    set(flag_types) & {"completeness_gap", "information_gap"}
                ),
            }
        )
    return pd.DataFrame(records)


def build_app_assets(
    analysis_base: pd.DataFrame,
    signals: pd.DataFrame,
    flags: pd.DataFrame,
    queue: pd.DataFrame,
    output_dir: Path = APP_DATA_DIR,
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    queue_ids = set(queue["unique_id"])
    details = analysis_base[
        analysis_base["scoring_eligible"] & analysis_base["unique_id"].isin(queue_ids)
    ].copy()
    details["claim_themes"] = details.apply(derive_claim_themes, axis=1)
    details["source_urls_parsed"] = details["source_urls"].map(trace_list)
    details["detail_shard"] = details["unique_id"].map(detail_shard)

    signal_columns = [
        "unique_id",
        "claim_count",
        "weak_claim_count",
        "claimed_theme_count",
        "corroborated_theme_count",
        "unsupported_theme_count",
        "unsupported_themes",
        "claim_corroboration_ratio",
        "source_url_count",
        "source_id_count",
        "capacity_normalized",
        "number_doctors_normalized",
        "year_established_normalized",
        "capacity_leverage",
        "doctor_leverage",
        "claim_leverage",
        "source_leverage",
    ]
    index = queue.merge(signals[signal_columns], on="unique_id", how="left")
    index = index.merge(
        details[["unique_id", "claim_themes"]], on="unique_id", how="left"
    )
    index = index.merge(aggregate_flag_index(flags), on="unique_id", how="left")

    flags.to_parquet(output_dir / "flags.parquet", index=False)
    index.to_parquet(output_dir / "review_index.parquet", index=False)

    detail_columns = [
        "unique_id",
        "name",
        "description",
        "facilityTypeId",
        "facility_type_normalized",
        "facility_type_normalization_action",
        "operatorTypeId",
        "operator_type_normalized",
        "address_line1",
        "address_line2",
        "address_line3",
        "address_city",
        "address_stateOrRegion",
        "address_zipOrPostcode",
        "pincode_normalized",
        "pincode_reference_status",
        "pincode_reference_district",
        "pincode_reference_state",
        "pincode_join_confidence",
        "latitude",
        "longitude",
        "coordinate_pair_status",
        "numberDoctors",
        "numberDoctors_normalized",
        "capacity",
        "capacity_normalized",
        "yearEstablished",
        "yearEstablished_normalized",
        "capability_parse_status",
        "capability_parsed",
        "procedure_parse_status",
        "procedure_parsed",
        "equipment_parse_status",
        "equipment_parsed",
        "claim_themes",
        "source_urls_parsed",
        "detail_shard",
    ]
    shard_manifest = []
    for shard in range(DETAIL_SHARDS):
        shard_path = output_dir / f"facility_details_{shard:02d}.parquet"
        shard_frame = details.loc[
            details["detail_shard"].eq(shard), detail_columns
        ]
        shard_frame.to_parquet(shard_path, index=False)
        shard_manifest.append(
            {
                "shard": shard,
                "path": shard_path.name,
                "rows": len(shard_frame),
                "bytes": shard_path.stat().st_size,
            }
        )

    manifest = {
        "generated_at": pd.Timestamp.utcnow().isoformat(),
        "queue_rows": len(index),
        "flag_rows": len(flags),
        "detail_rows": len(details),
        "detail_shards": DETAIL_SHARDS,
        "max_file_bytes": max(
            [
                (output_dir / "flags.parquet").stat().st_size,
                (output_dir / "review_index.parquet").stat().st_size,
                *[item["bytes"] for item in shard_manifest],
            ]
        ),
        "files": [
            {
                "path": "flags.parquet",
                "rows": len(flags),
                "bytes": (output_dir / "flags.parquet").stat().st_size,
            },
            {
                "path": "review_index.parquet",
                "rows": len(index),
                "bytes": (output_dir / "review_index.parquet").stat().st_size,
            },
            *shard_manifest,
        ],
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    validation = validate_app_assets(details, index, flags, manifest)
    APP_VALIDATION_PATH.parent.mkdir(parents=True, exist_ok=True)
    APP_VALIDATION_PATH.write_text(
        json.dumps(validation, indent=2), encoding="utf-8"
    )
    if validation["overall_status"] == "failed":
        raise ValueError("App asset validation failed.")
    return manifest


def validate_app_assets(
    details: pd.DataFrame,
    index: pd.DataFrame,
    flags: pd.DataFrame,
    manifest: dict,
) -> dict:
    checks = []

    def add(check_id: str, passed: bool, message: str, observed: object) -> None:
        checks.append(
            {
                "check_id": check_id,
                "status": "pass" if passed else "fail",
                "message": message,
                "observed": observed,
            }
        )

    add(
        "app.queue_grain",
        index["unique_id"].is_unique,
        "Review index contains one row per queued facility.",
        {"rows": len(index), "unique_ids": int(index["unique_id"].nunique())},
    )
    add(
        "app.detail_coverage",
        set(index["unique_id"]) == set(details["unique_id"]),
        "Every queued facility has exactly one packaged detail record.",
        {"queue_ids": len(set(index["unique_id"])), "detail_ids": len(set(details["unique_id"]))},
    )
    unknown_flag_ids = set(flags["unique_id"]) - set(index["unique_id"])
    add(
        "app.flag_referential_integrity",
        not unknown_flag_ids,
        "Every packaged flag references a queued facility.",
        len(unknown_flag_ids),
    )
    missing_flag_ids = set(index["unique_id"]) - set(flags["unique_id"])
    add(
        "app.flag_coverage",
        not missing_flag_ids,
        "Every queued facility has at least one packaged flag.",
        len(missing_flag_ids),
    )
    add(
        "app.deployment_file_size",
        manifest["max_file_bytes"] < MAX_DATABRICKS_APP_FILE_BYTES,
        "Every generated app data file is below the Databricks Apps file limit.",
        {
            "max_file_bytes": manifest["max_file_bytes"],
            "limit_bytes": MAX_DATABRICKS_APP_FILE_BYTES,
        },
    )
    shard_rows = sum(
        item["rows"] for item in manifest["files"] if "shard" in item
    )
    add(
        "app.shard_row_count",
        shard_rows == len(details),
        "Detail shards preserve the complete queued facility set.",
        {"shard_rows": shard_rows, "detail_rows": len(details)},
    )

    failures = sum(item["status"] == "fail" for item in checks)
    return {
        "generated_at": pd.Timestamp.utcnow().isoformat(),
        "overall_status": "failed" if failures else "passed",
        "summary": {
            "checks": len(checks),
            "passed": len(checks) - failures,
            "warnings": 0,
            "failed": failures,
        },
        "checks": checks,
    }


def main() -> None:
    manifest = build_app_assets(
        pd.read_parquet(ANALYSIS_BASE_PATH),
        pd.read_parquet(SIGNALS_PATH),
        pd.read_parquet(FLAGS_PATH),
        pd.read_parquet(QUEUE_PATH),
    )
    print(
        f"Wrote {manifest['queue_rows']} queue rows and "
        f"{manifest['detail_shards']} detail shards; app validation passed"
    )


if __name__ == "__main__":
    main()
