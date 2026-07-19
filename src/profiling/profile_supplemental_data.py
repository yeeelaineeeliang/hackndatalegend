from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.data_quality import coordinate_status, normalize_name, snake_case

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw" / "supplemental"
OUTPUT_DIR = ROOT / "outputs" / "profiling"
PROCESSED_DIR = ROOT / "data" / "processed"
def profile_pincode() -> dict:
    path = RAW_DIR / "india_post_pincode_directory.csv"
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    row_count = len(df)

    null_like = {"", "NA", "N/A", "NULL", "null"}
    column_profile = []
    for column in df.columns:
        series = df[column].astype(str).str.strip()
        missing_mask = series.isin(null_like)
        column_profile.append(
            {
                "column": column,
                "missing_count": int(missing_mask.sum()),
                "missing_pct": round(float(missing_mask.mean() * 100), 4),
                "unique_non_missing": int(series[~missing_mask].nunique()),
            }
        )

    pincode_counts = (
        df.assign(pincode=df["pincode"].astype(str).str.strip())
        .query("pincode != ''")
        .groupby("pincode")
        .size()
        .rename("row_count")
        .reset_index()
        .sort_values(["row_count", "pincode"], ascending=[False, True])
    )
    pincode_counts["district_count"] = (
        df.assign(
            pincode=df["pincode"].astype(str).str.strip(),
            district_norm=df["district"].map(normalize_name),
        )
        .query("pincode != ''")
        .groupby("pincode")["district_norm"]
        .nunique(dropna=True)
        .reindex(pincode_counts["pincode"])
        .to_list()
    )
    pincode_counts["state_count"] = (
        df.assign(
            pincode=df["pincode"].astype(str).str.strip(),
            state_norm=df["statename"].map(normalize_name),
        )
        .query("pincode != ''")
        .groupby("pincode")["state_norm"]
        .nunique(dropna=True)
        .reindex(pincode_counts["pincode"])
        .to_list()
    )
    pincode_counts["ambiguous_district"] = pincode_counts["district_count"] > 1
    pincode_counts["ambiguous_state"] = pincode_counts["state_count"] > 1

    pincode_enriched = df.assign(
        pincode=df["pincode"].astype(str).str.strip(),
        district_norm=df["district"].map(normalize_name),
        state_norm=df["statename"].map(normalize_name),
        latitude_num=pd.to_numeric(df["latitude"], errors="coerce"),
        longitude_num=pd.to_numeric(df["longitude"], errors="coerce"),
        coordinate_status=[
            coordinate_status(latitude, longitude)
            for latitude, longitude in zip(df["latitude"], df["longitude"], strict=True)
        ],
    )
    pincode_enriched["valid_latitude"] = pincode_enriched["latitude_num"].where(
        pincode_enriched["coordinate_status"] == "valid"
    )
    pincode_enriched["valid_longitude"] = pincode_enriched["longitude_num"].where(
        pincode_enriched["coordinate_status"] == "valid"
    )

    pincode_lookup = (
        pincode_enriched
        .query("pincode != ''")
        .groupby("pincode")
        .agg(
            post_office_count=("officename", "size"),
            unique_district_count=("district_norm", lambda s: s.nunique(dropna=True)),
            unique_state_count=("state_norm", lambda s: s.nunique(dropna=True)),
            district_candidates=("district_norm", lambda s: "|".join(sorted({x for x in s.dropna()}))),
            state_candidates=("state_norm", lambda s: "|".join(sorted({x for x in s.dropna()}))),
            office_type_candidates=("officetype", lambda s: "|".join(sorted({str(x).strip() for x in s if str(x).strip()}))),
            delivery_candidates=("delivery", lambda s: "|".join(sorted({str(x).strip() for x in s if str(x).strip()}))),
            valid_coordinate_pair_count=("coordinate_status", lambda s: int((s == "valid").sum())),
            invalid_coordinate_pair_count=(
                "coordinate_status",
                lambda s: int(s.isin({"likely_swapped", "out_of_bounds"}).sum()),
            ),
            incomplete_coordinate_pair_count=(
                "coordinate_status",
                lambda s: int(s.isin({"missing_pair", "incomplete_pair"}).sum()),
            ),
            mean_valid_latitude=("valid_latitude", "mean"),
            mean_valid_longitude=("valid_longitude", "mean"),
        )
        .reset_index()
    )
    pincode_lookup["mean_valid_latitude"] = pincode_lookup["mean_valid_latitude"].round(6)
    pincode_lookup["mean_valid_longitude"] = pincode_lookup["mean_valid_longitude"].round(6)
    pincode_lookup["ambiguous_district"] = pincode_lookup["unique_district_count"] > 1
    pincode_lookup["ambiguous_state"] = pincode_lookup["unique_state_count"] > 1

    ambiguity_report = pincode_lookup[
        (pincode_lookup["ambiguous_district"]) | (pincode_lookup["ambiguous_state"])
    ].sort_values(
        ["unique_state_count", "unique_district_count", "post_office_count", "pincode"],
        ascending=[False, False, False, True],
    )

    pincode_lookup.to_csv(PROCESSED_DIR / "pincode_lookup.csv", index=False)
    ambiguity_report.to_csv(PROCESSED_DIR / "pincode_ambiguity_report.csv", index=False)

    coordinate_statuses = pincode_enriched["coordinate_status"].value_counts()

    return {
        "dataset": "india_post_pincode_directory",
        "path": str(path.relative_to(ROOT)),
        "rows": row_count,
        "columns": len(df.columns),
        "unique_pincodes": int(df["pincode"].astype(str).str.strip().replace("", pd.NA).dropna().nunique()),
        "unique_districts": int(df["district"].map(normalize_name).dropna().nunique()),
        "unique_states": int(df["statename"].map(normalize_name).dropna().nunique()),
        "missing_coordinates_rows": int(
            (
                pd.to_numeric(df["latitude"], errors="coerce").isna()
                | pd.to_numeric(df["longitude"], errors="coerce").isna()
            ).sum()
        ),
        "coordinate_status_counts": {
            status: int(coordinate_statuses.get(status, 0))
            for status in [
                "valid",
                "missing_pair",
                "incomplete_pair",
                "likely_swapped",
                "out_of_bounds",
            ]
        },
        "duplicate_pincode_rows": int((pincode_counts["row_count"] > 1).sum()),
        "ambiguous_district_pincodes": int(pincode_lookup["ambiguous_district"].sum()),
        "ambiguous_state_pincodes": int(pincode_lookup["ambiguous_state"].sum()),
        "max_rows_per_pincode": int(pincode_counts["row_count"].max()),
        "top_pincode_row_counts": pincode_counts.head(10).to_dict(orient="records"),
        "column_profile": column_profile,
    }


def profile_nfhs() -> dict:
    path = RAW_DIR / "nfhs5_district_health_indicators.csv"
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    df = df.apply(lambda col: col.map(lambda x: x.strip() if isinstance(x, str) else x))
    row_count = len(df)

    column_mapping = [{"original": column, "snake_case": snake_case(column)} for column in df.columns]
    pd.DataFrame(column_mapping).to_csv(PROCESSED_DIR / "nfhs5_column_mapping.csv", index=False)

    null_like = {"", "NA", "N/A", "NULL", "null", "*"}
    column_profile = []
    parenthesized_value_counts = {}
    for column in df.columns:
        series = df[column].astype(str).str.strip()
        missing_mask = series.isin(null_like)
        parenthesized_mask = series.str.match(r"^\(.*\)$")
        parenthesized_value_counts[column] = int(parenthesized_mask.sum())
        column_profile.append(
            {
                "column": column,
                "snake_case": snake_case(column),
                "missing_count": int(missing_mask.sum()),
                "missing_pct": round(float(missing_mask.mean() * 100), 4),
                "parenthesized_estimate_count": int(parenthesized_mask.sum()),
                "unique_non_missing": int(series[~missing_mask].nunique()),
            }
        )

    district_norm = df["District Names"].map(normalize_name)
    state_norm = df["State/UT"].map(normalize_name)
    normalization_map = (
        pd.DataFrame(
            {
                "district_raw": df["District Names"],
                "district_normalized": district_norm,
                "state_raw": df["State/UT"],
                "state_normalized": state_norm,
            }
        )
        .drop_duplicates()
        .sort_values(["state_normalized", "district_normalized"], na_position="last")
    )
    normalization_map.to_csv(PROCESSED_DIR / "district_name_normalization_map.csv", index=False)

    return {
        "dataset": "nfhs5_district_health_indicators",
        "path": str(path.relative_to(ROOT)),
        "rows": row_count,
        "columns": len(df.columns),
        "unique_districts": int(district_norm.dropna().nunique()),
        "unique_states": int(state_norm.dropna().nunique()),
        "columns_with_missing_values": int(sum(item["missing_count"] > 0 for item in column_profile)),
        "columns_with_parenthesized_estimates": int(sum(v > 0 for v in parenthesized_value_counts.values())),
        "top_columns_by_missing_pct": sorted(column_profile, key=lambda item: item["missing_pct"], reverse=True)[:10],
        "column_profile": column_profile,
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    results = {
        "generated_at": pd.Timestamp.utcnow().isoformat(),
        "profiles": [profile_pincode(), profile_nfhs()],
    }

    output_path = OUTPUT_DIR / "supplemental_data_profile.json"
    output_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Wrote {output_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
