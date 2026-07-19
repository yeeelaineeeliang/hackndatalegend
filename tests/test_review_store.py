import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

import review_store  # noqa: E402
from data_access import apply_review_status, filter_review_index  # noqa: E402


class ReviewStoreSqliteTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        patcher = mock.patch.object(
            review_store, "SQLITE_PATH", Path(self._tmp.name) / "decisions.sqlite"
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._tmp.cleanup)
        with mock.patch.dict("os.environ", {}, clear=False):
            self.store = review_store.ReviewStore()

    def test_backend_is_sqlite_without_pghost(self) -> None:
        self.assertEqual(self.store.backend, "sqlite")

    def test_append_and_load_round_trip(self) -> None:
        self.store.append_decision(
            facility_id="f-1",
            facility_name="Test Hospital",
            review_status="needs_review",
            reviewer="tester",
            note="first pass",
        )
        decisions = self.store.load_decisions()
        self.assertEqual(len(decisions), 1)
        row = decisions.iloc[0]
        self.assertEqual(row["facility_id"], "f-1")
        self.assertEqual(row["review_status"], "needs_review")
        self.assertEqual(row["reviewer"], "tester")

    def test_latest_decision_wins_and_history_is_kept(self) -> None:
        self.store.append_decision(
            facility_id="f-1",
            facility_name="Test Hospital",
            review_status="incorrect_claim",
            reviewer="tester",
            note="",
        )
        self.store.append_decision(
            facility_id="f-1",
            facility_name="Test Hospital",
            review_status="resolved",
            reviewer="tester",
            note="fixed",
        )
        self.assertEqual(len(self.store.load_decisions()), 2)
        latest = self.store.latest_decisions()
        self.assertEqual(len(latest), 1)
        self.assertEqual(latest.iloc[0]["review_status"], "resolved")

    def test_unknown_status_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.store.append_decision(
                facility_id="f-1",
                facility_name="Test Hospital",
                review_status="not_a_status",
                reviewer="tester",
                note="",
            )

    def test_blank_reviewer_defaults(self) -> None:
        self.store.append_decision(
            facility_id="f-2",
            facility_name="Other Hospital",
            review_status="resolved",
            reviewer="   ",
            note="",
        )
        self.assertEqual(
            self.store.load_decisions().iloc[0]["reviewer"], "anonymous reviewer"
        )


class ApplyReviewStatusTest(unittest.TestCase):
    def _index(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "unique_id": ["f-1", "f-2"],
                "review_status": ["unreviewed", "unreviewed"],
                "review_priority_score": [50.0, 40.0],
            }
        )

    def test_merges_latest_decisions_into_index(self) -> None:
        latest = pd.DataFrame(
            {
                "facility_id": ["f-2"],
                "review_status": ["missing_evidence"],
                "reviewer": ["tester"],
            }
        )
        merged = apply_review_status(self._index(), latest)
        self.assertEqual(merged.loc[1, "review_status"], "missing_evidence")
        self.assertEqual(merged.loc[1, "reviewed_by"], "tester")
        self.assertEqual(merged.loc[0, "review_status"], "unreviewed")

    def test_empty_decisions_leave_index_unreviewed(self) -> None:
        merged = apply_review_status(self._index(), pd.DataFrame())
        self.assertTrue((merged["review_status"] == "unreviewed").all())

    def test_filter_by_review_status(self) -> None:
        latest = pd.DataFrame(
            {
                "facility_id": ["f-1"],
                "review_status": ["resolved"],
                "reviewer": ["tester"],
            }
        )
        merged = apply_review_status(self._index(), latest)
        filtered = filter_review_index(merged, review_statuses=["resolved"])
        self.assertEqual(list(filtered["unique_id"]), ["f-1"])


if __name__ == "__main__":
    unittest.main()
