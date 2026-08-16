"""Static gates for Stage 1 Chromium-owned browser contracts."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class Stage1BrowserContractTests(unittest.TestCase):
    def assert_contract(self, filename: str, required: tuple[str, ...]) -> None:
        path = ROOT / "docs" / filename
        self.assertTrue(path.is_file(), f"missing contract: {filename}")
        text = path.read_text(encoding="utf-8")
        for marker in required:
            with self.subTest(file=filename, marker=marker):
                self.assertIn(marker, text)

    def test_bookmarks_history_ownership(self) -> None:
        self.assert_contract(
            "BOOKMARKS_HISTORY_CONTRACT.md",
            ("NavigationController", "HistoryService", "BookmarkModel", "TabRestoreService", "Incognito"),
        )

    def test_session_profile_ownership(self) -> None:
        self.assert_contract(
            "SESSION_PROFILE_CONTRACT.md",
            ("session_service.*", "session_restore.*", "TabRestoreService", "Incognito", "Guest"),
        )

    def test_extension_evidence_gate(self) -> None:
        self.assert_contract(
            "EXTENSION_COMPATIBILITY_GATE.md",
            ("Manifest V3", "unpacked", "Chrome Web Store", "GO", "NO-GO"),
        )

    def test_runtime_patch_series_remains_unchanged(self) -> None:
        series = (ROOT / "downstream/patches/series").read_text(encoding="utf-8")
        for deferred in ("bookmarks", "history", "session", "profile", "extension"):
            self.assertNotIn(deferred, series.lower())


if __name__ == "__main__":
    unittest.main()
