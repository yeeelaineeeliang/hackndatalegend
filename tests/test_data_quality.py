from __future__ import annotations

import unittest

import pandas as pd

from src.data_quality import (
    choose_unique_mode,
    coordinate_status,
    normalize_name,
    snake_case,
)


class DataQualityUnitTests(unittest.TestCase):
    def test_snake_case(self) -> None:
        self.assertEqual(snake_case("Women with high blood sugar (%)"), "women_with_high_blood_sugar_pct")

    def test_normalize_name(self) -> None:
        self.assertEqual(normalize_name("  North   Goa "), "NORTH GOA")
        self.assertIsNone(normalize_name("*"))

    def test_coordinate_status(self) -> None:
        self.assertEqual(coordinate_status("28.6139", "77.2090"), "valid")
        self.assertEqual(coordinate_status("77.2090", "28.6139"), "likely_swapped")
        self.assertEqual(coordinate_status("NA", "NA"), "missing_pair")
        self.assertEqual(coordinate_status("28.6139", "NA"), "incomplete_pair")
        self.assertEqual(coordinate_status("0", "0"), "out_of_bounds")

    def test_choose_unique_mode(self) -> None:
        self.assertEqual(choose_unique_mode(pd.Series(["A", "A", "B"])), "A")
        self.assertIsNone(choose_unique_mode(pd.Series(["A", "B"])))
        self.assertIsNone(choose_unique_mode(pd.Series([], dtype=object)))


if __name__ == "__main__":
    unittest.main()

