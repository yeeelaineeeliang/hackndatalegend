from __future__ import annotations

import json
import unittest
from pathlib import Path

import pandas as pd

from app.data_access import (
    filter_review_index,
    get_facility_bundle,
    load_flags,
    load_review_index,
)
from src.app_data.build_app_assets import (
    CLAIM_THEME_REGEX,
    derive_claim_themes,
    detail_shard,
)


ROOT = Path(__file__).resolve().parents[1]
APP_DATA_DIR = ROOT / "app" / "data"


class AppAssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.index = load_review_index(APP_DATA_DIR)
        cls.flags = load_flags(APP_DATA_DIR)
        cls.manifest = json.loads(
            (APP_DATA_DIR / "manifest.json").read_text(encoding="utf-8")
        )
        cls.validation = json.loads(
            (
                ROOT / "outputs" / "validation" / "app_asset_validation.json"
            ).read_text(encoding="utf-8")
        )

    def test_shard_assignment_is_stable(self) -> None:
        unique_id = "44444444-4444-4444-8444-444444444444"
        self.assertEqual(detail_shard(unique_id), detail_shard(unique_id))
        self.assertIn(detail_shard(unique_id), range(8))

    def test_claim_theme_detection_is_keyword_based(self) -> None:
        row = pd.Series(
            {
                "capability_parsed": ["24x7 emergency and trauma care"],
                "procedure_parsed": ["Hemodialysis"],
                "equipment_parsed": ["MRI scanner"],
            }
        )
        themes = derive_claim_themes(row)
        self.assertIn("Emergency & trauma", themes)
        self.assertIn("Renal & dialysis", themes)
        self.assertIn("Diagnostics", themes)
        self.assertEqual(len(CLAIM_THEME_REGEX), 10)

    def test_deployment_assets_are_complete_and_under_limit(self) -> None:
        self.assertEqual(self.manifest["queue_rows"], len(self.index))
        self.assertEqual(self.manifest["flag_rows"], len(self.flags))
        self.assertEqual(self.manifest["detail_rows"], len(self.index))
        self.assertLess(self.manifest["max_file_bytes"], 10 * 1024 * 1024)
        self.assertEqual(
            sum(item["rows"] for item in self.manifest["files"] if "shard" in item),
            len(self.index),
        )
        self.assertEqual(self.validation["overall_status"], "passed")
        self.assertEqual(self.validation["summary"]["failed"], 0)

    def test_filters_and_detail_lookup_use_same_facility_ids(self) -> None:
        filtered = filter_review_index(
            self.index,
            issue_types=["contradiction"],
            severities=["high"],
        )
        self.assertFalse(filtered.empty)
        selected_id = filtered.iloc[0]["unique_id"]
        summary, detail, facility_flags = get_facility_bundle(
            selected_id,
            self.index,
            self.flags,
            APP_DATA_DIR,
        )
        self.assertEqual(summary["unique_id"], detail["unique_id"])
        self.assertTrue((facility_flags["unique_id"] == selected_id).all())
        self.assertIn("contradiction", set(facility_flags["flag_type"]))


if __name__ == "__main__":
    unittest.main()
