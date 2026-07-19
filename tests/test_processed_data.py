from __future__ import annotations

import unittest
from pathlib import Path

import pandas as pd

from src.data_quality import INDIA_LATITUDE_BOUNDS, INDIA_LONGITUDE_BOUNDS


ROOT = Path(__file__).resolve().parents[1]


class ProcessedDataIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.preferred = pd.read_csv(
            ROOT / "data" / "processed" / "pincode_lookup_preferred.csv",
            dtype={"pincode": str},
        )
        cls.nfhs = pd.read_csv(
            ROOT / "data" / "processed" / "nfhs5_district_health_indicators_clean.csv"
        )

    def test_preferred_lookup_is_one_row_per_pincode(self) -> None:
        self.assertEqual(len(self.preferred), self.preferred["pincode"].nunique())

    def test_only_exact_rows_are_safe_for_direct_join(self) -> None:
        safe = self.preferred["is_safe_for_direct_join"].astype(str).str.lower() == "true"
        self.assertTrue((self.preferred.loc[safe, "resolution_status"] == "exact").all())

    def test_preferred_means_use_valid_coordinate_pairs(self) -> None:
        latitude = self.preferred["mean_valid_latitude"].dropna()
        longitude = self.preferred["mean_valid_longitude"].dropna()
        self.assertTrue(latitude.between(*INDIA_LATITUDE_BOUNDS).all())
        self.assertTrue(longitude.between(*INDIA_LONGITUDE_BOUNDS).all())

    def test_nfhs_has_unique_state_district_grain(self) -> None:
        self.assertFalse(
            self.nfhs.duplicated(["state_ut_normalized", "district_normalized"]).any()
        )


if __name__ == "__main__":
    unittest.main()

