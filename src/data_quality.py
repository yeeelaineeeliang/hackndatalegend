from __future__ import annotations

import re

import pandas as pd


INDIA_LATITUDE_BOUNDS = (6.0, 38.0)
INDIA_LONGITUDE_BOUNDS = (68.0, 98.0)
NULL_LIKE_VALUES = {"", "NA", "N/A", "NULL", "null", "*"}


def snake_case(value: str) -> str:
    value = value.strip().lower()
    value = value.replace("%", " pct ")
    value = value.replace("&", " and ")
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = re.sub(r"_+", "_", value)
    return value.strip("_")


def normalize_name(value: object) -> str | None:
    if pd.isna(value):
        return None
    text = str(value).strip()
    if text in NULL_LIKE_VALUES:
        return None
    return re.sub(r"\s+", " ", text).upper()


def coordinate_status(latitude: object, longitude: object) -> str:
    latitude_num = pd.to_numeric(pd.Series([latitude]), errors="coerce").iloc[0]
    longitude_num = pd.to_numeric(pd.Series([longitude]), errors="coerce").iloc[0]

    latitude_missing = pd.isna(latitude_num)
    longitude_missing = pd.isna(longitude_num)
    if latitude_missing and longitude_missing:
        return "missing_pair"
    if latitude_missing or longitude_missing:
        return "incomplete_pair"

    lat_min, lat_max = INDIA_LATITUDE_BOUNDS
    lon_min, lon_max = INDIA_LONGITUDE_BOUNDS
    if lat_min <= latitude_num <= lat_max and lon_min <= longitude_num <= lon_max:
        return "valid"
    if lat_min <= longitude_num <= lat_max and lon_min <= latitude_num <= lon_max:
        return "likely_swapped"
    return "out_of_bounds"


def choose_unique_mode(series: pd.Series) -> str | None:
    values = [value for value in series if value]
    if not values:
        return None
    counts = pd.Series(values).value_counts()
    top_count = counts.iloc[0]
    top_values = sorted(counts[counts == top_count].index.tolist())
    return top_values[0] if len(top_values) == 1 else None

