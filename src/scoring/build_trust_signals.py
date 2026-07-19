from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path
from typing import Iterable

import pandas as pd

from src.data_quality import normalize_name
from src.ingestion.facility_intake import ROOT, is_missing
from src.processing.normalize_facilities import parse_string_list
from src.scoring.claim_corroboration import (
    assess_claim_corroboration,
    corroboration_ratio,
)


DEFAULT_SOURCE = ROOT / "data" / "processed" / "facilities_analysis_base.parquet"
RULES_PATH = ROOT / "config" / "trust_scoring_rules.json"
SIGNALS_PATH = ROOT / "data" / "processed" / "facility_trust_signals.parquet"
FLAGS_PATH = ROOT / "data" / "processed" / "facility_flags.parquet"
QUEUE_PARQUET_PATH = ROOT / "data" / "processed" / "facility_review_queue.parquet"
QUEUE_CSV_PATH = ROOT / "data" / "processed" / "facility_review_queue.csv"
PROFILE_PATH = ROOT / "outputs" / "profiling" / "facility_trust_profile.json"
VALIDATION_PATH = ROOT / "outputs" / "validation" / "facility_trust_validation.json"

RULES = json.loads(RULES_PATH.read_text(encoding="utf-8"))
CLAIM_FIELDS = ["capability", "procedure", "equipment"]
INVALID_CLAIM_STATUSES = {"invalid_scalar", "invalid_type", "invalid_members"}
PLACEHOLDER_PATTERN = re.compile(
    r"\b(no explicit|not provided|no specific|none listed|"
    r"no equipment|no procedure|not stated|not described|not mentioned)\b",
    flags=re.IGNORECASE,
)
CAPACITY_PATTERNS = [
    re.compile(r"\bbed capacity (?:of|is|:)?\s*(\d{1,5})\b", re.IGNORECASE),
    re.compile(r"\bcapacity (?:of|is|:)?\s*(\d{1,5})\s+beds?\b", re.IGNORECASE),
    re.compile(r"\b(\d{1,5})[- ]bedded (?:hospital|facility)\b", re.IGNORECASE),
]
YEAR_PATTERN = re.compile(
    r"\b(?:established|founded|opened|inaugurated)\s+(?:in|on)?\s*"
    r"(?:\d{1,2}\s+[A-Za-z]+\s+)?((?:18|19|20)\d{2})\b",
    re.IGNORECASE,
)

STATE_NAMES = [
    "Andhra Pradesh",
    "Arunachal Pradesh",
    "Assam",
    "Bihar",
    "Chhattisgarh",
    "Goa",
    "Gujarat",
    "Haryana",
    "Himachal Pradesh",
    "Jharkhand",
    "Karnataka",
    "Kerala",
    "Madhya Pradesh",
    "Maharashtra",
    "Manipur",
    "Meghalaya",
    "Mizoram",
    "Nagaland",
    "Odisha",
    "Punjab",
    "Rajasthan",
    "Sikkim",
    "Tamil Nadu",
    "Telangana",
    "Tripura",
    "Uttar Pradesh",
    "Uttarakhand",
    "West Bengal",
    "Andaman and Nicobar Islands",
    "Chandigarh",
    "Dadra and Nagar Haveli and Daman and Diu",
    "Delhi",
    "Jammu and Kashmir",
    "Ladakh",
    "Lakshadweep",
    "Puducherry",
]
STATE_ALIASES = {
    "ORISSA": "ODISHA",
    "TAMILNADU": "TAMIL NADU",
    "CHATTISGARH": "CHHATTISGARH",
    "PONDICHERRY": "PUDUCHERRY",
    "NCT OF DELHI": "DELHI",
    "NEW DELHI": "DELHI",
    "U P": "UTTAR PRADESH",
    "UP": "UTTAR PRADESH",
    "UTTARANCHAL": "UTTARAKHAND",
    "JAMMU & KASHMIR": "JAMMU AND KASHMIR",
}
CANONICAL_STATES = {normalize_name(value): normalize_name(value) for value in STATE_NAMES}
CANONICAL_STATES.update(STATE_ALIASES)


def list_or_none(value: object) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, str):
        parsed, _ = parse_string_list(value)
        return parsed
    if isinstance(value, Iterable):
        values = list(value)
        return values if all(isinstance(item, str) for item in values) else None
    return None


def trace_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            try:
                parsed = ast.literal_eval(value)
            except (SyntaxError, ValueError):
                return []
    elif isinstance(value, Iterable):
        parsed = list(value)
    else:
        return []
    if not isinstance(parsed, list):
        return []
    return [item for item in parsed if isinstance(item, str) and item.strip()]


def canonical_state(value: object) -> str | None:
    normalized = normalize_name(value)
    return CANONICAL_STATES.get(normalized)


def strict_capacity_claims(texts: Iterable[str]) -> set[int]:
    values: set[int] = set()
    for text in texts:
        for pattern in CAPACITY_PATTERNS:
            values.update(int(match) for match in pattern.findall(text))
    return values


def strict_year_claims(texts: Iterable[str]) -> set[int]:
    return {
        int(match)
        for text in texts
        for match in YEAR_PATTERN.findall(text)
    }


def percentile_signal(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    result = pd.Series(0.0, index=series.index)
    available = numeric.notna()
    if available.any():
        result.loc[available] = numeric.loc[available].rank(pct=True, method="average")
    return result


def claim_completeness(status: str) -> float:
    semantics = RULES["claim_semantics"]
    if status == "parsed_list":
        return float(semantics["parsed_list_completeness"])
    if status == "empty_list":
        return float(semantics["empty_list_completeness"])
    return float(semantics["missing_or_invalid_completeness"])


def add_flag(
    records: list[dict],
    row: pd.Series,
    *,
    flag_type: str,
    field_name: str,
    severity: str,
    reason_code: str,
    explanation: str,
    evidence_text: str,
    evidence_type: str,
    confidence: float,
    validation_status: str,
) -> None:
    urls = trace_list(row["source_urls"])
    records.append(
        {
            "unique_id": row["unique_id"],
            "name": row["name"],
            "flag_type": flag_type,
            "field_name": field_name,
            "severity": severity,
            "reason_code": reason_code,
            "explanation": explanation,
            "evidence_text": evidence_text[:1000],
            "evidence_type": evidence_type,
            "evidence_source_urls": urls[:5],
            "is_inferred": evidence_type != "structured_value",
            "confidence": round(float(confidence), 2),
            "validation_status": validation_status,
        }
    )


def build_trust_outputs(
    analysis_base: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    eligible = analysis_base[analysis_base["scoring_eligible"]].copy().reset_index(drop=True)
    completeness_weights = RULES["completeness_weights"]
    penalties = RULES["consistency_penalties"]
    flag_records: list[dict] = []
    component_records: list[dict] = []

    for _, row in eligible.iterrows():
        claim_lists = {
            field: list_or_none(row[f"{field}_parsed"]) for field in CLAIM_FIELDS
        }
        claim_statuses = {
            field: str(row[f"{field}_parse_status"]) for field in CLAIM_FIELDS
        }
        urls = trace_list(row["source_urls"])
        source_ids = trace_list(row["source_ids"])

        component_values = {
            "name": 0.0 if is_missing(row["name_normalized"]) else 1.0,
            "facility_type": (
                0.0 if is_missing(row["facility_type_normalized"]) else 1.0
            ),
            "operator_type": (
                0.0 if is_missing(row["operator_type_normalized"]) else 1.0
            ),
            "address_city": 0.0 if is_missing(row["address_city"]) else 1.0,
            "address_state": (
                0.0 if is_missing(row["address_stateOrRegion"]) else 1.0
            ),
            "pincode": 1.0 if row["pincode_normalization_status"] == "valid" else 0.0,
            "coordinates": 1.0 if row["coordinate_pair_status"] == "valid" else 0.0,
            "description": 0.0 if is_missing(row["description"]) else 1.0,
            "capability": claim_completeness(claim_statuses["capability"]),
            "procedure": claim_completeness(claim_statuses["procedure"]),
            "equipment": claim_completeness(claim_statuses["equipment"]),
            "number_doctors": (
                1.0 if row["numberDoctors_normalization_status"] == "parsed" else 0.0
            ),
            "capacity": (
                1.0 if row["capacity_normalization_status"] == "parsed" else 0.0
            ),
            "year_established": (
                1.0 if row["yearEstablished_normalization_status"] == "parsed" else 0.0
            ),
        }
        completeness_score = 100 * sum(
            completeness_weights[field] * component_values[field]
            for field in completeness_weights
        )

        missing_field_specs = [
            ("facility_type", "facilityTypeId", "medium"),
            ("operator_type", "operatorTypeId", "medium"),
            ("address_city", "address_city", "medium"),
            ("address_state", "address_stateOrRegion", "high"),
            ("pincode", "address_zipOrPostcode", "high"),
            ("coordinates", "coordinates", "high"),
            ("number_doctors", "numberDoctors", "medium"),
            ("capacity", "capacity", "high"),
            ("year_established", "yearEstablished", "low"),
        ]
        for component, field, severity in missing_field_specs:
            if component_values[component] == 0:
                raw_value = row.get(field)
                add_flag(
                    flag_records,
                    row,
                    flag_type="completeness_gap",
                    field_name=field,
                    severity=severity,
                    reason_code=f"missing_or_invalid_{component}",
                    explanation=f"{field} is missing or not usable for planning.",
                    evidence_text=f"Raw {field}: {raw_value!r}",
                    evidence_type="structured_value",
                    confidence=1.0,
                    validation_status="confirmed_gap",
                )

        weak_claim_count = 0
        claim_count = 0
        for field in CLAIM_FIELDS:
            claims = claim_lists[field] or []
            claim_count += len(claims)
            placeholder_claims = [
                claim
                for claim in claims
                if claim.strip() and PLACEHOLDER_PATTERN.search(claim)
            ]
            blank_claims = [claim for claim in claims if not claim.strip()]
            weak_claims = [*placeholder_claims, *blank_claims]
            weak_claim_count += len(weak_claims)
            if claim_statuses[field] == "missing":
                add_flag(
                    flag_records,
                    row,
                    flag_type="completeness_gap",
                    field_name=field,
                    severity="high",
                    reason_code="claim_field_unprocessed_or_unknown",
                    explanation=(
                        f"{field} is null, so absence of claims cannot be distinguished "
                        "from an unprocessed field."
                    ),
                    evidence_text=f"Raw {field}: null",
                    evidence_type="structured_value",
                    confidence=1.0,
                    validation_status="confirmed_gap",
                )
            elif claim_statuses[field] == "empty_list":
                add_flag(
                    flag_records,
                    row,
                    flag_type="information_gap",
                    field_name=field,
                    severity="medium",
                    reason_code="processed_no_supported_facts",
                    explanation=(
                        f"{field} was processed but contains no supported facts."
                    ),
                    evidence_text=f"Raw {field}: []",
                    evidence_type="structured_value",
                    confidence=1.0,
                    validation_status="confirmed_empty_result",
                )
            elif claim_statuses[field] in INVALID_CLAIM_STATUSES:
                add_flag(
                    flag_records,
                    row,
                    flag_type="parsing_issue",
                    field_name=field,
                    severity="high",
                    reason_code="invalid_claim_structure",
                    explanation=(
                        f"{field} could not be parsed as a list containing only strings."
                    ),
                    evidence_text=f"Raw {field}: {str(row[field])[:800]}",
                    evidence_type="structured_value",
                    confidence=1.0,
                    validation_status="confirmed_parse_failure",
                )
            if placeholder_claims:
                add_flag(
                    flag_records,
                    row,
                    flag_type="weak_evidence",
                    field_name=field,
                    severity="high",
                    reason_code="placeholder_or_negative_claim",
                    explanation=(
                        f"{len(placeholder_claims)} {field} entries describe missing evidence "
                        "or use placeholder language but are stored as positive claims."
                    ),
                    evidence_text=placeholder_claims[0].strip(),
                    evidence_type="extracted_claim_text",
                    confidence=0.95,
                    validation_status="needs_source_verification",
                )
            if blank_claims:
                add_flag(
                    flag_records,
                    row,
                    flag_type="extraction_noise",
                    field_name=field,
                    severity="medium",
                    reason_code="empty_claim_entry",
                    explanation=(
                        f"{len(blank_claims)} blank entries are stored inside the "
                        f"{field} claim list."
                    ),
                    evidence_text="[empty string claim]",
                    evidence_type="extracted_claim_text",
                    confidence=1.0,
                    validation_status="confirmed_extraction_noise",
                )

        claim_quality = (
            max(0.0, 1.0 - weak_claim_count / claim_count) if claim_count else 0.0
        )

        description_text = "" if is_missing(row["description"]) else str(row["description"])
        assessments = assess_claim_corroboration(
            claim_lists["capability"] or [],
            description_text,
            claim_lists["procedure"] or [],
            claim_lists["equipment"] or [],
        )
        support_ratio = corroboration_ratio(assessments)
        for assessment in assessments:
            if assessment["support_level"] == "unsupported":
                add_flag(
                    flag_records,
                    row,
                    flag_type="unsupported_claim",
                    field_name="capability",
                    severity=assessment["acuity"],
                    reason_code=f"uncorroborated_{assessment['theme_id']}_claim",
                    explanation=(
                        f"{assessment['theme_label']} is claimed, but no operational "
                        "evidence (equipment, staff, or procedures) and no repeat "
                        "mention exists in description, procedure, or equipment."
                    ),
                    evidence_text=(
                        f"Claimed: {assessment['claimed_entry']!r}; searched "
                        "description, procedure, and equipment; no supporting terms found."
                    ),
                    evidence_type="claim_evidence_comparison",
                    confidence=0.85,
                    validation_status="needs_source_verification",
                )
            elif assessment["support_level"] == "mentioned_only":
                add_flag(
                    flag_records,
                    row,
                    flag_type="weak_evidence",
                    field_name="capability",
                    severity="medium",
                    reason_code=f"{assessment['theme_id']}_claim_repeated_not_evidenced",
                    explanation=(
                        f"{assessment['theme_label']} recurs in "
                        f"{assessment['evidence_field']} but no operational evidence "
                        "(equipment, staff, or procedures) corroborates it."
                    ),
                    evidence_text=(
                        f"Claimed: {assessment['claimed_entry']!r}; "
                        f"{assessment['evidence_field']} says: "
                        f"{assessment['evidence_snippet']!r}"
                    ),
                    evidence_type="claim_evidence_comparison",
                    confidence=0.75,
                    validation_status="needs_source_verification",
                )

        evidence_weights = RULES["evidence_support"]
        corroboration_component = (
            support_ratio
            if support_ratio is not None
            else float(evidence_weights["claim_corroboration_neutral"])
        )
        raw_evidence_score = 100 * (
            evidence_weights["source_urls"] * bool(urls)
            + evidence_weights["source_ids"] * bool(source_ids)
            + evidence_weights["source_content_id"]
            * (not is_missing(row["source_content_id"]))
            + evidence_weights["description"] * (not is_missing(row["description"]))
            + evidence_weights["claim_quality"] * claim_quality
            + evidence_weights["claim_corroboration"] * corroboration_component
        )
        evidence_score = (
            raw_evidence_score
            * float(evidence_weights["claim_level_verification_cap"])
            / 100
        )
        if not urls:
            add_flag(
                flag_records,
                row,
                flag_type="traceability_gap",
                field_name="source_urls",
                severity="high",
                reason_code="missing_source_urls",
                explanation="No source URL is available to inspect the facility claims.",
                evidence_text=f"Raw source_urls: {row['source_urls']!r}",
                evidence_type="structured_value",
                confidence=1.0,
                validation_status="confirmed_gap",
            )

        if row["pincode_join_confidence"] != "exact_reference_mapping":
            add_flag(
                flag_records,
                row,
                flag_type="geography_uncertainty",
                field_name="address_zipOrPostcode",
                severity="medium",
                reason_code="district_from_pincode_not_exact",
                explanation=(
                    "The PIN reference cannot safely assign one district and state."
                ),
                evidence_text=(
                    f"PIN: {row['address_zipOrPostcode']!r}; "
                    f"normalized PIN: {row['pincode_normalized']!r}; "
                    f"reference status: {row['pincode_reference_status']!r}; "
                    f"join confidence: {row['pincode_join_confidence']}"
                ),
                evidence_type="cross_source_comparison",
                confidence=1.0,
                validation_status="unresolved_geography",
            )

        consistency_penalty = 0
        source_state = canonical_state(row["address_stateOrRegion"])
        reference_state = canonical_state(row["pincode_reference_state"])
        if (
            row["pincode_reference_status"] == "exact"
            and source_state
            and reference_state
            and source_state != reference_state
        ):
            consistency_penalty += penalties["state_pincode_disagreement"]
            add_flag(
                flag_records,
                row,
                flag_type="contradiction",
                field_name="address_stateOrRegion",
                severity="high",
                reason_code="state_pincode_disagreement",
                explanation=(
                    "The recognized source state disagrees with the exact PIN reference state."
                ),
                evidence_text=(
                    f"Source state: {row['address_stateOrRegion']}; "
                    f"PIN {row['pincode_normalized']} reference state: "
                    f"{row['pincode_reference_state']}"
                ),
                evidence_type="cross_source_comparison",
                confidence=0.9,
                validation_status="needs_human_review",
            )

        if row["coordinate_pair_status"] in {
            "out_of_bounds",
            "likely_swapped",
            "incomplete_pair",
        }:
            consistency_penalty += penalties["invalid_coordinates"]
            add_flag(
                flag_records,
                row,
                flag_type="contradiction",
                field_name="coordinates",
                severity="high",
                reason_code="invalid_coordinate_pair",
                explanation="The coordinate pair is incomplete or outside broad India bounds.",
                evidence_text=(
                    f"latitude={row['latitude']!r}, longitude={row['longitude']!r}, "
                    f"status={row['coordinate_pair_status']}"
                ),
                evidence_type="structured_value",
                confidence=1.0,
                validation_status="confirmed_invalid",
            )

        if row["facility_type_normalization_action"] == "unmapped":
            consistency_penalty += penalties["unmapped_facility_type"]

        invalid_claim_fields = sum(
            status in INVALID_CLAIM_STATUSES for status in claim_statuses.values()
        )
        placeholder_claim_fields = sum(
            any(
                not claim.strip() or PLACEHOLDER_PATTERN.search(claim)
                for claim in (claim_lists[field] or [])
            )
            for field in CLAIM_FIELDS
        )
        consistency_penalty += (
            penalties["invalid_claim_field"] * invalid_claim_fields
        )
        consistency_penalty += (
            penalties["placeholder_claim_field"] * placeholder_claim_fields
        )

        evidence_texts = []
        if not is_missing(row["description"]):
            evidence_texts.append(str(row["description"]))
        for claims in claim_lists.values():
            evidence_texts.extend(claims or [])

        capacity_claims = strict_capacity_claims(evidence_texts)
        structured_capacity = row["capacity_normalized"]
        capacity_disagreement = len(capacity_claims) > 1 or (
            pd.notna(structured_capacity)
            and bool(capacity_claims)
            and int(structured_capacity) not in capacity_claims
        )
        if capacity_disagreement:
            consistency_penalty += penalties["capacity_claim_disagreement"]
            add_flag(
                flag_records,
                row,
                flag_type="contradiction",
                field_name="capacity",
                severity="high",
                reason_code="capacity_claim_disagreement",
                explanation=(
                    "Structured capacity and strict total-bed claims do not resolve "
                    "to one consistent value."
                ),
                evidence_text=(
                    f"Structured capacity: {structured_capacity}; "
                    f"strict total-bed claims: {sorted(capacity_claims)}"
                ),
                evidence_type="cross_field_comparison",
                confidence=0.85,
                validation_status="needs_human_review",
            )

        year_claims = strict_year_claims(evidence_texts)
        structured_year = row["yearEstablished_normalized"]
        year_disagreement = len(year_claims) > 1 or (
            pd.notna(structured_year)
            and bool(year_claims)
            and int(structured_year) not in year_claims
        )
        if year_disagreement:
            consistency_penalty += penalties["year_claim_disagreement"]
            add_flag(
                flag_records,
                row,
                flag_type="contradiction",
                field_name="yearEstablished",
                severity="medium",
                reason_code="year_claim_disagreement",
                explanation=(
                    "Structured establishment year and explicit founded/opened claims "
                    "do not resolve to one consistent value."
                ),
                evidence_text=(
                    f"Structured year: {structured_year}; "
                    f"explicit year claims: {sorted(year_claims)}"
                ),
                evidence_type="cross_field_comparison",
                confidence=0.8,
                validation_status="needs_human_review",
            )

        component_records.append(
            {
                "unique_id": row["unique_id"],
                "name": row["name"],
                "facility_type": row["facility_type_normalized"],
                "operator_type": row["operator_type_normalized"],
                "address_city": row["address_city"],
                "address_state": row["address_stateOrRegion"],
                "pincode": row["pincode_normalized"],
                "district_reference": row["district_assigned_from_pincode"],
                "state_reference": row["state_assigned_from_pincode"],
                "pincode_join_confidence": row["pincode_join_confidence"],
                "completeness_score": round(completeness_score, 2),
                "evidence_support_score": round(evidence_score, 2),
                "evidence_confidence_cap": float(
                    evidence_weights["claim_level_verification_cap"]
                ),
                "evidence_validation_status": (
                    "claim_level_source_alignment_unverified"
                ),
                "consistency_score": round(
                    max(0.0, 100.0 - consistency_penalty), 2
                ),
                "claim_count": claim_count,
                "weak_claim_count": weak_claim_count,
                "claimed_theme_count": len(assessments),
                "corroborated_theme_count": sum(
                    item["support_level"] == "corroborated" for item in assessments
                ),
                "unsupported_theme_count": sum(
                    item["support_level"] == "unsupported" for item in assessments
                ),
                "unsupported_themes": [
                    item["theme_label"]
                    for item in assessments
                    if item["support_level"] != "corroborated"
                ],
                "claim_corroboration_ratio": (
                    round(support_ratio, 3) if support_ratio is not None else None
                ),
                "source_url_count": len(urls),
                "source_id_count": len(source_ids),
                "capacity_normalized": row["capacity_normalized"],
                "number_doctors_normalized": row["numberDoctors_normalized"],
                "year_established_normalized": row["yearEstablished_normalized"],
            }
        )

    signals = pd.DataFrame(component_records)
    leverage_weights = RULES["score_weights"]["high_leverage"]
    signals["capacity_leverage"] = percentile_signal(signals["capacity_normalized"])
    signals["doctor_leverage"] = percentile_signal(
        signals["number_doctors_normalized"]
    )
    signals["claim_leverage"] = percentile_signal(signals["claim_count"])
    signals["source_leverage"] = percentile_signal(signals["source_url_count"])
    signals["high_leverage_score"] = (
        100
        * (
            leverage_weights["capacity"] * signals["capacity_leverage"]
            + leverage_weights["number_doctors"] * signals["doctor_leverage"]
            + leverage_weights["claim_count"] * signals["claim_leverage"]
            + leverage_weights["source_count"] * signals["source_leverage"]
        )
    ).round(2)

    readiness_weights = RULES["score_weights"]["readiness"]
    signals["readiness_score"] = (
        readiness_weights["completeness"] * signals["completeness_score"]
        + readiness_weights["evidence_support"] * signals["evidence_support_score"]
        + readiness_weights["consistency"] * signals["consistency_score"]
    ).round(2)
    priority_weights = RULES["score_weights"]["review_priority"]
    signals["review_priority_score"] = (
        priority_weights["readiness_risk"] * (100 - signals["readiness_score"])
        + priority_weights["high_leverage"] * signals["high_leverage_score"]
    ).round(2)

    flags = pd.DataFrame(flag_records)
    if flags.empty:
        flags = pd.DataFrame(
            columns=[
                "unique_id",
                "name",
                "flag_type",
                "field_name",
                "severity",
                "reason_code",
                "explanation",
                "evidence_text",
                "evidence_type",
                "evidence_source_urls",
                "is_inferred",
                "confidence",
                "validation_status",
            ]
        )
    severity_order = {"high": 3, "medium": 2, "low": 1}
    flags["severity_rank"] = flags["severity"].map(severity_order).fillna(0)
    flag_summary = (
        flags.groupby("unique_id")
        .agg(
            flag_count=("reason_code", "size"),
            high_severity_flag_count=(
                "severity",
                lambda values: int((values == "high").sum()),
            ),
            primary_issue=(
                "reason_code",
                lambda values: values.iloc[0],
            ),
        )
        .reset_index()
    )
    primary = (
        flags.sort_values(
            ["unique_id", "severity_rank", "confidence"],
            ascending=[True, False, False],
        )
        .drop_duplicates("unique_id")
        [["unique_id", "reason_code"]]
        .rename(columns={"reason_code": "primary_issue"})
    )
    flag_summary = flag_summary.drop(columns=["primary_issue"]).merge(
        primary, on="unique_id", how="left"
    )
    signals = signals.merge(flag_summary, on="unique_id", how="left")
    signals["flag_count"] = signals["flag_count"].fillna(0).astype(int)
    signals["high_severity_flag_count"] = (
        signals["high_severity_flag_count"].fillna(0).astype(int)
    )
    signals["review_status"] = "unreviewed"

    queue_columns = [
        "unique_id",
        "name",
        "facility_type",
        "operator_type",
        "address_city",
        "address_state",
        "pincode",
        "district_reference",
        "pincode_join_confidence",
        "readiness_score",
        "completeness_score",
        "evidence_support_score",
        "consistency_score",
        "high_leverage_score",
        "review_priority_score",
        "flag_count",
        "high_severity_flag_count",
        "primary_issue",
        "review_status",
        "evidence_validation_status",
    ]
    queue = (
        signals[signals["flag_count"] > 0][queue_columns]
        .sort_values(
            ["review_priority_score", "high_severity_flag_count", "unique_id"],
            ascending=[False, False, True],
        )
        .reset_index(drop=True)
    )
    queue.insert(0, "queue_rank", queue.index + 1)
    flags = flags.drop(columns=["severity_rank"]).sort_values(
        ["unique_id", "severity", "reason_code"]
    )
    return signals, flags, queue


def check(check_id: str, status: str, message: str, observed: object) -> dict:
    return {
        "check_id": check_id,
        "status": status,
        "message": message,
        "observed": observed,
    }


def validate_trust_outputs(
    analysis_base: pd.DataFrame,
    signals: pd.DataFrame,
    flags: pd.DataFrame,
    queue: pd.DataFrame,
) -> tuple[dict, dict]:
    eligible = analysis_base[analysis_base["scoring_eligible"]]
    checks = []
    checks.append(
        check(
            "trust.signal_grain",
            (
                "pass"
                if len(signals) == len(eligible)
                and signals["unique_id"].is_unique
                else "fail"
            ),
            "Trust signals contain one row per scoring-eligible facility.",
            {"eligible": len(eligible), "signals": len(signals)},
        )
    )
    score_columns = [
        "completeness_score",
        "evidence_support_score",
        "consistency_score",
        "high_leverage_score",
        "readiness_score",
        "review_priority_score",
    ]
    invalid_scores = int(
        sum(
            signals[column].isna().sum()
            + (~signals[column].between(0, 100)).sum()
            for column in score_columns
        )
    )
    checks.append(
        check(
            "trust.score_bounds",
            "pass" if not invalid_scores else "fail",
            "All scores are non-null and bounded from 0 to 100.",
            invalid_scores,
        )
    )
    evidence_cap = RULES["evidence_support"]["claim_level_verification_cap"]
    above_cap = int((signals["evidence_support_score"] > evidence_cap).sum())
    checks.append(
        check(
            "trust.evidence_cap",
            "pass" if not above_cap else "fail",
            "Evidence support cannot imply claim-level verification without aligned spans.",
            {"cap": evidence_cap, "rows_above_cap": above_cap},
        )
    )
    unknown_flag_ids = int((~flags["unique_id"].isin(signals["unique_id"])).sum())
    checks.append(
        check(
            "trust.flag_referential_integrity",
            "pass" if not unknown_flag_ids else "fail",
            "Every flag references a scoring-eligible facility.",
            unknown_flag_ids,
        )
    )
    incomplete_flags = int(
        flags[
            ["reason_code", "explanation", "evidence_text", "validation_status"]
        ]
        .isna()
        .any(axis=1)
        .sum()
        + flags["evidence_text"].astype(str).str.strip().eq("").sum()
    )
    checks.append(
        check(
            "trust.flag_traceability",
            "pass" if not incomplete_flags else "fail",
            "Every flag includes a reason, explanation, evidence, and validation state.",
            incomplete_flags,
        )
    )
    queue_valid = (
        queue["unique_id"].is_unique
        and queue["queue_rank"].tolist() == list(range(1, len(queue) + 1))
        and queue["review_priority_score"].is_monotonic_decreasing
    )
    checks.append(
        check(
            "trust.queue_order",
            "pass" if queue_valid else "fail",
            "The review queue is unique, sequential, and priority ordered.",
            {"queue_rows": len(queue), "valid": queue_valid},
        )
    )
    systemic_unverified = int(
        signals["evidence_validation_status"]
        .eq("claim_level_source_alignment_unverified")
        .sum()
    )
    checks.append(
        check(
            "trust.claim_level_verification",
            "warn" if systemic_unverified else "pass",
            "Facility-level URLs do not prove alignment between each claim and source text.",
            systemic_unverified,
        )
    )

    failures = sum(item["status"] == "fail" for item in checks)
    warnings = sum(item["status"] == "warn" for item in checks)
    validation = {
        "generated_at": pd.Timestamp.utcnow().isoformat(),
        "rules_version": RULES["rules_version"],
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
        "rules_version": RULES["rules_version"],
        "facility_signals": len(signals),
        "flags": len(flags),
        "flagged_facilities": int(flags["unique_id"].nunique()),
        "queue_rows": len(queue),
        "score_summary": {
            column: {
                str(key): round(float(value), 2)
                for key, value in signals[column]
                .describe(percentiles=[0.25, 0.5, 0.75, 0.9])
                .items()
            }
            for column in score_columns
        },
        "flags_by_reason": {
            str(key): int(value)
            for key, value in flags["reason_code"].value_counts().items()
        },
        "flags_by_severity": {
            str(key): int(value)
            for key, value in flags["severity"].value_counts().items()
        },
    }
    return profile, validation


def write_outputs(
    signals: pd.DataFrame,
    flags: pd.DataFrame,
    queue: pd.DataFrame,
    profile: dict,
    validation: dict,
) -> None:
    SIGNALS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    VALIDATION_PATH.parent.mkdir(parents=True, exist_ok=True)
    signals.to_parquet(SIGNALS_PATH, index=False)
    flags.to_parquet(FLAGS_PATH, index=False)
    queue.to_parquet(QUEUE_PARQUET_PATH, index=False)
    queue.to_csv(QUEUE_CSV_PATH, index=False)
    PROFILE_PATH.write_text(json.dumps(profile, indent=2), encoding="utf-8")
    VALIDATION_PATH.write_text(json.dumps(validation, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build explainable facility trust signals and review queue."
    )
    parser.add_argument(
        "source",
        type=Path,
        nargs="?",
        default=DEFAULT_SOURCE,
        help="Normalized facility analysis-base Parquet file.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    analysis_base = pd.read_parquet(args.source.expanduser().resolve())
    signals, flags, queue = build_trust_outputs(analysis_base)
    profile, validation = validate_trust_outputs(
        analysis_base, signals, flags, queue
    )
    write_outputs(signals, flags, queue, profile, validation)
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
