from __future__ import annotations

import unittest
from pathlib import Path

import pandas as pd

from src.ingestion.facility_intake import (
    analyze_facility_data,
    build_row_status,
    list_value_status,
    read_facility_data,
    resolve_columns,
)


ROOT = Path(__file__).resolve().parents[1]


class FacilityIntakeTests(unittest.TestCase):
    def test_resolve_columns_supports_explicit_aliases(self) -> None:
        resolved = resolve_columns(
            ["facility_name", "description", "capabilities", "number_doctors", "postal_code"]
        )
        self.assertEqual(resolved["name"], "facility_name")
        self.assertEqual(resolved["capability"], "capabilities")
        self.assertEqual(resolved["numberDoctors"], "number_doctors")
        self.assertEqual(resolved["address_zipOrPostcode"], "postal_code")

    def test_list_value_status_preserves_null_and_empty_distinction(self) -> None:
        self.assertEqual(list_value_status(None), "missing")
        self.assertEqual(list_value_status("[]"), "empty_list")
        self.assertEqual(list_value_status('["ICU"]'), "parsed_list")
        self.assertEqual(list_value_status("ICU"), "scalar_text")

    def test_sample_fixture_passes_core_contract(self) -> None:
        path = ROOT / "tests" / "fixtures" / "facilities_sample.csv"
        frame = read_facility_data(path)
        profile, validation, column_profile = analyze_facility_data(frame, path.name)
        self.assertEqual(profile["rows"], 3)
        self.assertEqual(profile["columns"], 12)
        self.assertEqual(profile["structurally_valid_rows"], 3)
        self.assertEqual(profile["scoring_eligible_rows"], 3)
        self.assertEqual(validation["summary"]["failed"], 0)
        self.assertIn(validation["overall_status"], {"passed", "passed_with_warnings"})
        self.assertEqual(len(column_profile), 12)

    def test_missing_core_fields_fail_validation(self) -> None:
        frame = pd.DataFrame({"name": ["Only a name"]})
        _, validation, _ = analyze_facility_data(frame, "incomplete.csv")
        self.assertGreater(validation["summary"]["failed"], 0)

    def test_exact_duplicate_is_ineligible_for_scoring(self) -> None:
        row = {
            "unique_id": "44444444-4444-4444-8444-444444444444",
            "organization_type": "facility",
            "name": "Duplicate Facility",
        }
        status = build_row_status(pd.DataFrame([row, row]))
        self.assertEqual(int(status["structurally_valid"].sum()), 2)
        self.assertEqual(int(status["exact_duplicate"].sum()), 1)
        self.assertEqual(int(status["scoring_eligible"].sum()), 1)


if __name__ == "__main__":
    unittest.main()
