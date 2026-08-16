"""Prevent development status from overstating unverified native work."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class DevelopmentStatusContractTests(unittest.TestCase):
    def test_runtime_reports_disclose_missing_native_verification(self) -> None:
        reports = (
            ROOT / ".ai/reports/2026-08-16-sunshine-new-tab.md",
            ROOT / ".ai/reports/2026-08-16-windows-native-build-pipeline.md",
        )
        for report in reports:
            with self.subTest(report=report.name):
                text = report.read_text(encoding="utf-8").lower()
                self.assertTrue(
                    "not claimed" in text or "pending" in text,
                    f"{report.name} must disclose pending native verification",
                )

    def test_feature_contracts_do_not_ship_runtime_patches_early(self) -> None:
        series = (ROOT / "downstream/patches/series").read_text(encoding="utf-8")
        self.assertNotIn("download-safety", series)
        self.assertNotIn("permission-policy", series)


if __name__ == "__main__":
    unittest.main()

