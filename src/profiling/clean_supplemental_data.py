from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.data_quality import (
    NULL_LIKE_VALUES,
    choose_unique_mode,
    coordinate_status,
    normalize_name,
    snake_case,
)


ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw" / "supplemental"
PROCESSED_DIR = ROOT / "data" / "processed"
def clean_nfhs() -> None:
    input_path = RAW_DIR / "nfhs5_district_health_indicators.csv"
    output_path = PROCESSED_DIR / "nfhs5_district_health_indicators_clean.csv"
    raw = pd.read_csv(input_path, dtype=str, keep_default_na=False)
    raw = raw.apply(lambda col: col.map(lambda x: x.strip() if isinstance(x, str) else x))

    rename_map = {column: snake_case(column) for column in raw.columns}
    cleaned = raw.rename(columns=rename_map).copy()

    identifier_columns = {"district_names", "state_ut"}
    low_confidence_flags: dict[str, pd.Series] = {}
    for column in cleaned.columns:
        series = cleaned[column].astype(str).str.strip()
        parenthesized_mask = series.str.match(r"^\(.*\)$")
        if parenthesized_mask.any():
            low_confidence_flags[f"{column}_is_low_confidence_estimate"] = parenthesized_mask

        normalized = (
            series.replace({value: pd.NA for value in NULL_LIKE_VALUES})
            .str.replace(r"^\((.*)\)$", r"\1", regex=True)
        )
        if column not in identifier_columns:
            normalized = pd.to_numeric(normalized.str.replace(",", "", regex=False), errors="raise")
        cleaned[column] = normalized

    extra_columns = pd.DataFrame(low_confidence_flags)
    extra_columns["district_normalized"] = raw["District Names"].map(normalize_name)
    extra_columns["state_ut_normalized"] = raw["State/UT"].map(normalize_name)
    cleaned = pd.concat([cleaned, extra_columns], axis=1)
    cleaned.to_csv(output_path, index=False)


def build_pincode_reference() -> None:
    input_path = RAW_DIR / "india_post_pincode_directory.csv"
    output_path = PROCESSED_DIR / "pincode_lookup_preferred.csv"

    raw = pd.read_csv(input_path, dtype=str, keep_default_na=False)
    raw = raw.apply(lambda col: col.map(lambda x: x.strip() if isinstance(x, str) else x))
    raw["pincode"] = raw["pincode"].astype(str).str.strip()
    raw["district_normalized"] = raw["district"].map(normalize_name)
    raw["state_normalized"] = raw["statename"].map(normalize_name)
    raw["latitude_num"] = pd.to_numeric(raw["latitude"], errors="coerce")
    raw["longitude_num"] = pd.to_numeric(raw["longitude"], errors="coerce")
    raw["coordinate_status"] = [
        coordinate_status(latitude, longitude)
        for latitude, longitude in zip(raw["latitude"], raw["longitude"], strict=True)
    ]

    grouped = raw[raw["pincode"] != ""].groupby("pincode", dropna=False)
    records = []
    for pincode, group in grouped:
        district_candidates = sorted({value for value in group["district_normalized"].dropna()})
        state_candidates = sorted({value for value in group["state_normalized"].dropna()})
        preferred_district = choose_unique_mode(group["district_normalized"])
        preferred_state = choose_unique_mode(group["state_normalized"])
        valid_coordinates = group[group["coordinate_status"] == "valid"]

        ambiguous_district = len(district_candidates) > 1
        ambiguous_state = len(state_candidates) > 1
        missing_geo = len(district_candidates) == 0 or len(state_candidates) == 0

        if missing_geo:
            resolution_status = "missing_geo"
        elif ambiguous_state:
            resolution_status = "ambiguous_state"
        elif ambiguous_district and preferred_district is None:
            resolution_status = "ambiguous_district"
        elif ambiguous_district and preferred_district is not None:
            resolution_status = "district_mode_selected"
        else:
            resolution_status = "exact"

        records.append(
            {
                "pincode": pincode,
                "post_office_count": int(len(group)),
                "district_candidate_count": len(district_candidates),
                "state_candidate_count": len(state_candidates),
                "district_candidates": "|".join(district_candidates),
                "state_candidates": "|".join(state_candidates),
                "preferred_district": preferred_district,
                "preferred_state": preferred_state,
                "resolution_status": resolution_status,
                "is_safe_for_direct_join": resolution_status == "exact",
                "valid_coordinate_pair_count": int(len(valid_coordinates)),
                "invalid_coordinate_pair_count": int(
                    group["coordinate_status"].isin({"likely_swapped", "out_of_bounds"}).sum()
                ),
                "incomplete_coordinate_pair_count": int(
                    group["coordinate_status"].isin({"missing_pair", "incomplete_pair"}).sum()
                ),
                "likely_swapped_coordinate_count": int(
                    (group["coordinate_status"] == "likely_swapped").sum()
                ),
                "mean_valid_latitude": (
                    round(valid_coordinates["latitude_num"].mean(), 6)
                    if not valid_coordinates.empty
                    else pd.NA
                ),
                "mean_valid_longitude": (
                    round(valid_coordinates["longitude_num"].mean(), 6)
                    if not valid_coordinates.empty
                    else pd.NA
                ),
            }
        )

    preferred = pd.DataFrame(records).sort_values("pincode")
    preferred.to_csv(output_path, index=False)


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    clean_nfhs()
    build_pincode_reference()
    print("Wrote cleaned supplemental outputs")


if __name__ == "__main__":
    main()
