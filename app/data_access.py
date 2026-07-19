from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pandas as pd


DATA_DIR = Path(__file__).resolve().parent / "data"


def values_as_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    try:
        return [str(item) for item in list(value)]
    except TypeError:
        return []


@lru_cache(maxsize=1)
def load_review_index(data_dir: Path = DATA_DIR) -> pd.DataFrame:
    return pd.read_parquet(data_dir / "review_index.parquet")


@lru_cache(maxsize=1)
def load_flags(data_dir: Path = DATA_DIR) -> pd.DataFrame:
    return pd.read_parquet(data_dir / "flags.parquet")


@lru_cache(maxsize=16)
def load_detail_shard(shard: int, data_dir: Path = DATA_DIR) -> pd.DataFrame:
    return pd.read_parquet(data_dir / f"facility_details_{shard:02d}.parquet")


def apply_review_status(index: pd.DataFrame, latest: pd.DataFrame) -> pd.DataFrame:
    updated = index.copy()
    updated["review_status"] = "unreviewed"
    updated["reviewed_by"] = None
    if latest.empty:
        return updated
    status_map = latest.set_index("facility_id")["review_status"]
    reviewer_map = latest.set_index("facility_id")["reviewer"]
    matched = updated["unique_id"].map(status_map)
    updated.loc[matched.notna(), "review_status"] = matched[matched.notna()]
    updated["reviewed_by"] = updated["unique_id"].map(reviewer_map)
    return updated


def filter_review_index(
    index: pd.DataFrame,
    *,
    search: str = "",
    states: list[str] | None = None,
    issue_types: list[str] | None = None,
    claim_themes: list[str] | None = None,
    severities: list[str] | None = None,
    review_statuses: list[str] | None = None,
    min_priority: float = 0,
) -> pd.DataFrame:
    mask = index["review_priority_score"].ge(min_priority)
    if search.strip():
        token = search.strip().lower()
        mask &= (
            index["name"].fillna("").str.lower().str.contains(token, regex=False)
            | index["address_city"]
            .fillna("")
            .str.lower()
            .str.contains(token, regex=False)
            | index["pincode"].fillna("").astype(str).str.contains(token, regex=False)
        )
    if states:
        mask &= index["address_state"].isin(states)
    if issue_types:
        selected = set(issue_types)
        mask &= index["flag_types"].map(
            lambda value: bool(selected & set(values_as_list(value)))
        )
    if claim_themes:
        selected = set(claim_themes)
        mask &= index["claim_themes"].map(
            lambda value: bool(selected & set(values_as_list(value)))
        )
    if severities:
        selected = set(severities)
        mask &= index["severities"].map(
            lambda value: bool(selected & set(values_as_list(value)))
        )
    if review_statuses:
        mask &= index["review_status"].isin(review_statuses)
    return index.loc[mask].copy()


def get_facility_bundle(
    unique_id: str,
    index: pd.DataFrame,
    flags: pd.DataFrame,
    data_dir: Path = DATA_DIR,
) -> tuple[pd.Series, pd.Series, pd.DataFrame]:
    index_match = index[index["unique_id"].eq(unique_id)]
    if index_match.empty:
        raise KeyError(f"Facility not found in review index: {unique_id}")
    summary = index_match.iloc[0]
    shard = int(summary.get("detail_shard", -1))
    if shard < 0:
        from hashlib import sha256

        shard = int(sha256(unique_id.encode("utf-8")).hexdigest()[:8], 16) % 8
    details = load_detail_shard(shard, data_dir)
    detail_match = details[details["unique_id"].eq(unique_id)]
    if detail_match.empty:
        raise KeyError(f"Facility detail not found: {unique_id}")
    facility_flags = flags[flags["unique_id"].eq(unique_id)].copy()
    severity_order = {"high": 3, "medium": 2, "low": 1}
    facility_flags["_severity_order"] = (
        facility_flags["severity"].map(severity_order).fillna(0)
    )
    facility_flags = facility_flags.sort_values(
        ["_severity_order", "confidence"], ascending=[False, False]
    ).drop(columns="_severity_order")
    return summary, detail_match.iloc[0], facility_flags
