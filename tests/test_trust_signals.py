from __future__ import annotations

import unittest

import pandas as pd

from src.processing.normalize_facilities import build_analysis_base
from src.scoring.build_trust_signals import (
    build_trust_outputs,
    canonical_state,
    strict_capacity_claims,
    strict_year_claims,
    trace_list,
    validate_trust_outputs,
)


def raw_facility(**overrides: object) -> dict[str, object]:
    row = {
        "unique_id": "44444444-4444-4444-8444-444444444444",
        "organization_type": "facility",
        "name": "Test Hospital",
        "facilityTypeId": "hospital",
        "operatorTypeId": "private",
        "affiliationTypeIds": "[]",
        "capability": '["24x7 emergency care"]',
        "procedure": '["No explicit procedures listed in provided content"]',
        "equipment": '["MRI scanner"]',
        "numberDoctors": "12",
        "capacity": "100",
        "yearEstablished": "2001",
        "address_line1": "1 Test Road",
        "address_line2": None,
        "address_line3": None,
        "address_city": "Delhi",
        "address_stateOrRegion": "Delhi",
        "address_zipOrPostcode": "110001",
        "address_country": "India",
        "address_countryCode": "IN",
        "description": "Established in 2001 with a bed capacity of 100.",
        "latitude": "28.63",
        "longitude": "77.21",
        "source_types": '["dynamic"]',
        "source_ids": '["source-1"]',
        "source_content_id": "content-1",
        "content_table_id": "content-1",
        "source_urls": '["https://example.org",null]',
    }
    row.update(overrides)
    return row


def lookup() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "pincode": "110001",
                "preferred_district": "NEW DELHI",
                "preferred_state": "DELHI",
                "resolution_status": "exact",
            }
        ]
    )


class TrustSignalTests(unittest.TestCase):
    def test_trace_list_ignores_null_members(self) -> None:
        self.assertEqual(
            trace_list('["https://example.org",null]'),
            ["https://example.org"],
        )

    def test_state_aliases_are_conservative(self) -> None:
        self.assertEqual(canonical_state("NCT of Delhi"), "DELHI")
        self.assertEqual(canonical_state("Orissa"), "ODISHA")
        self.assertIsNone(canonical_state("Mumbai"))

    def test_strict_claim_extractors(self) -> None:
        self.assertEqual(
            strict_capacity_claims(["A hospital with a bed capacity of 120."]),
            {120},
        )
        self.assertEqual(
            strict_year_claims(["The hospital was established in 2004."]),
            {2004},
        )

    def test_outputs_are_explainable_and_bounded(self) -> None:
        raw = pd.DataFrame([raw_facility()])
        analysis_base = build_analysis_base(raw, lookup())
        signals, flags, queue = build_trust_outputs(analysis_base)
        _, validation = validate_trust_outputs(
            analysis_base, signals, flags, queue
        )

        self.assertEqual(validation["summary"]["failed"], 0)
        self.assertEqual(len(signals), 1)
        self.assertLessEqual(signals.loc[0, "evidence_support_score"], 75)
        self.assertIn("placeholder_or_negative_claim", set(flags["reason_code"]))
        self.assertFalse(flags["evidence_text"].astype(str).str.strip().eq("").any())
        self.assertEqual(queue.loc[0, "queue_rank"], 1)


if __name__ == "__main__":
    unittest.main()
