from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]


class AppUiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._temp_dir = tempfile.TemporaryDirectory()
        cls._previous_review_path = os.environ.get("REVIEW_DB_PATH")
        os.environ["REVIEW_DB_PATH"] = str(
            Path(cls._temp_dir.name) / "ui-contract.sqlite"
        )
        cls.app = AppTest.from_file(
            ROOT / "app" / "app.py",
            default_timeout=30,
        ).run(timeout=30)

    @classmethod
    def tearDownClass(cls) -> None:
        if cls._previous_review_path is None:
            os.environ.pop("REVIEW_DB_PATH", None)
        else:
            os.environ["REVIEW_DB_PATH"] = cls._previous_review_path
        cls._temp_dir.cleanup()

    def test_app_renders_without_exceptions(self) -> None:
        self.assertEqual(list(self.app.exception), [])

    def test_every_required_input_has_a_visible_label(self) -> None:
        self.assertEqual(
            {item.label for item in self.app.text_input},
            {"Search queue", "Reviewer"},
        )
        self.assertEqual(
            {item.label for item in self.app.multiselect},
            {
                "State or region",
                "Issue type",
                "Claim theme",
                "Severity",
                "Review status",
            },
        )
        self.assertEqual(
            {item.label for item in self.app.selectbox},
            {"Selected review record", "Decision"},
        )
        self.assertEqual(
            {item.label for item in self.app.text_area},
            {"Decision note"},
        )
        self.assertEqual(
            {item.label for item in self.app.slider},
            {"Minimum priority"},
        )

    def test_demo_actions_and_navigation_are_present(self) -> None:
        button_labels = {item.label for item in self.app.button}
        self.assertIn("Clear all filters", button_labels)
        self.assertIn("Record decision", button_labels)

        tab_labels = {item.label for item in self.app.tabs}
        self.assertTrue(
            {"Overview", "Review queue", "Audit log", "Method"}.issubset(
                tab_labels
            )
        )


if __name__ == "__main__":
    unittest.main()
