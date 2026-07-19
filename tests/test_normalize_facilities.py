from __future__ import annotations

import unittest

import pandas as pd

from src.processing.normalize_facilities import (
    build_analysis_base,
    normalize_affiliations,
    normalize_enum,
    normalize_integer_series,
    parse_string_list,
    validate_analysis_base,
    FACILITY_TYPE_MAP,
    OPERATOR_TYPE_MAP,
)


def facility_row(**overrides: object) -> dict[str, object]:
    row = {
        "unique_id": "44444444-4444-4444-8444-444444444444",
        "organization_type": "facility",
        "name": " Test Hospital ",
        "facilityTypeId": "farmacy",
        "operatorTypeId": "government",
        "affiliationTypeIds": '["government","government"]',
        "capability": '["ICU"]',
        "procedure": "[]",
        "equipment": None,
        "numberDoctors": "12",
        "capacity": None,
        "yearEstablished": "2001",
        "address_zipOrPostcode": "110001",
        "address_stateOrRegion": " Delhi ",
        "latitude": "28.63",
        "longitude": "77.21",
    }
    row.update(overrides)
    return row


def pin_lookup() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "pincode": "110001",
                "preferred_district": "NEW DELHI",
                "preferred_state": "DELHI",
                "resolution_status": "exact",
            },
            {
                "pincode": "999999",
                "preferred_district": "A",
                "preferred_state": "B",
                "resolution_status": "ambiguous_district",
            },
        ]
    )


class NormalizeFacilitiesTests(unittest.TestCase):
    def test_parse_string_list_preserves_null_and_empty(self) -> None:
        self.assertEqual(parse_string_list(None), (None, "missing"))
        self.assertEqual(parse_string_list("[]"), ([], "empty_list"))
        self.assertEqual(parse_string_list('["ICU"]'), (["ICU"], "parsed_list"))
        self.assertEqual(parse_string_list("ICU"), (None, "invalid_scalar"))

    def test_enum_normalization_is_explicit(self) -> None:
        self.assertEqual(
            normalize_enum("farmacy", FACILITY_TYPE_MAP),
            ("pharmacy", "corrected_typo"),
        )
        self.assertEqual(
            normalize_enum("government", OPERATOR_TYPE_MAP),
            ("public", "mapped_synonym"),
        )
        self.assertEqual(
            normalize_enum("nursing_home", FACILITY_TYPE_MAP),
            (None, "unmapped"),
        )

    def test_affiliations_are_deduplicated_without_hiding_action(self) -> None:
        normalized, status = normalize_affiliations(
            '["government","government","academic"]'
        )
        self.assertEqual(normalized, ["government", "academic"])
        self.assertEqual(status, "deduplicated")

    def test_integer_normalization_rejects_fractional_values(self) -> None:
        normalized, status = normalize_integer_series(
            pd.Series(["12", "1.5", None, "-2"])
        )
        self.assertEqual(normalized.iloc[0], 12)
        self.assertTrue(pd.isna(normalized.iloc[1]))
        self.assertEqual(status.tolist(), ["parsed", "invalid_integer", "missing", "negative"])

    def test_analysis_base_preserves_raw_and_assigns_only_exact_pin(self) -> None:
        raw = pd.DataFrame(
            [
                facility_row(),
                facility_row(
                    unique_id="55555555-5555-4555-8555-555555555555",
                    address_zipOrPostcode="999999",
                ),
            ]
        )
        normalized = build_analysis_base(raw, pin_lookup())

        self.assertTrue(raw.equals(normalized[raw.columns]))
        self.assertEqual(normalized.loc[0, "facility_type_normalized"], "pharmacy")
        self.assertEqual(normalized.loc[0, "operator_type_normalized"], "public")
        self.assertEqual(
            normalized.loc[0, "district_assigned_from_pincode"], "NEW DELHI"
        )
        self.assertTrue(pd.isna(normalized.loc[1, "district_assigned_from_pincode"]))
        self.assertEqual(
            normalized.loc[1, "pincode_join_confidence"],
            "ambiguous_reference_mapping",
        )

        _, validation = validate_analysis_base(raw, normalized)
        self.assertEqual(validation["summary"]["failed"], 0)


if __name__ == "__main__":
    unittest.main()
