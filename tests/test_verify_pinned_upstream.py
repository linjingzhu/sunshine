"""Tests for the pinned-upstream check.

The bug this check replaced was a false positive: it asked `app.css` whether a
colour-pipeline token existed, and would have failed the build on a token that
does. So the point of these tests is not that the check passes -- it is that it
fails for the right reason and passes for the right reason, without touching the
network.
"""

import contextlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import urllib.error

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))

import verify_pinned_upstream as checker  # noqa: E402


SEAM_TEXT = {
    "chrome/browser/ui/tabs/tab_strip_model.h": "class TabStripModel {};",
    "chrome/browser/ui/tabs/tab_group_model.h": "class TabGroupModel {};",
    "chrome/browser/ui/tabs/tab_strip_model_observer.h": "void OnTabStripModelChanged();",
    "components/sessions/core/session_service_commands.cc": (
        "CreateAddTabExtraDataCommand CreateAddWindowExtraDataCommand"
    ),
    "components/sessions/core/session_types.h": (
        "struct SESSIONS_EXPORT SessionTab {\n  int extra_data;\n};\n"
        "struct SESSIONS_EXPORT SessionWindow {\n  int extra_data;\n};\n"
    ),
    "chrome/browser/resources/new_tab_page/app.css": ":host {\n  --ntp-theme-text-shadow: none;\n}",
    "chrome/browser/ui/color/chrome_color_id.h": "kColorNewTabPagePrimaryForeground,",
}


def fake_fetch(overrides: dict[str, str] | None = None):
    text = dict(SEAM_TEXT)
    text.update(overrides or {})

    def fetch(source: str, version: str, path: str) -> str:
        return text[path]

    return fetch


class PinnedUpstreamTests(unittest.TestCase):
    def setUp(self) -> None:
        self.enterExitStack = contextlib.ExitStack()
        self.addCleanup(self.enterExitStack.close)

    def run_verify(self, overrides=None):
        # Patch application and citation probing each need the network; they
        # have their own offline tests below. Stubbing them here keeps these
        # cases about seams and tokens, and keeps the suite runnable offline.
        with mock.patch.object(checker, "fetch", fake_fetch(overrides)), \
             mock.patch.object(checker, "check_patch_stack", return_value=True), \
             mock.patch.object(checker, "check_citations", return_value=True):
            return checker.verify()

    def test_it_passes_when_upstream_still_provides_everything(self) -> None:
        healthy, report = self.run_verify()
        self.assertTrue(healthy, "\n".join(report))
        self.assertFalse([line for line in report if "FAIL" in line])

    def test_a_missing_seam_fails(self) -> None:
        healthy, report = self.run_verify(
            {"chrome/browser/ui/tabs/tab_strip_model.h": "class SomethingElse {};"}
        )
        self.assertFalse(healthy)
        self.assertTrue(any("TabStripModel" in line and "FAIL" in line for line in report))

    def test_a_missing_colour_id_fails_and_names_what_it_looked_for(self) -> None:
        """The failure has to name its own fix, or the next reader repeats the
        mistake of checking the wrong file."""

        healthy, report = self.run_verify(
            {"chrome/browser/ui/color/chrome_color_id.h": "kColorNewTabPageSecondaryForeground,"}
        )
        self.assertFalse(healthy)
        joined = "\n".join(report)
        self.assertIn("--color-new-tab-page-primary-foreground", joined)
        self.assertIn("kColorNewTabPagePrimaryForeground", joined)
        self.assertIn("chrome_color_id.h", joined)

    def test_the_colour_token_is_not_looked_for_in_the_stylesheet(self) -> None:
        """The regression that motivated this file.

        Verified at 152.0.7977.42: app.css contains no
        `--color-new-tab-page-primary-foreground`, because Chromium emits
        `--color-new-tab-page-*` from colour IDs and serves them through
        chrome://theme. A check that greps the stylesheet fails on a valid
        token, so the stylesheet must not be where this token is looked up.
        """

        for path, token, _needle, _explanation in checker.TOKENS:
            if token == "--color-new-tab-page-primary-foreground":
                self.assertEqual("chrome/browser/ui/color/chrome_color_id.h", path)
                break
        else:
            self.fail("the wordmark's colour token is no longer checked at all")

    def test_extra_data_must_sit_in_the_right_struct(self) -> None:
        """`extra_data` elsewhere in the file is not evidence for these structs."""

        healthy, _ = self.run_verify(
            {
                "components/sessions/core/session_types.h": (
                    "int extra_data;\n"
                    "struct SESSIONS_EXPORT SessionTab {\n  int other;\n};\n"
                    "struct SESSIONS_EXPORT SessionWindow {\n  int extra_data;\n};\n"
                )
            }
        )
        self.assertFalse(healthy)

    def test_a_cited_path_that_moved_upstream_fails_and_names_the_document(self) -> None:
        """A contract is only as good as the sources it names.

        This surface moves: the omnibox edit model and view left
        components/omnibox/browser/ for chrome/browser/ui/omnibox/. A path cited
        from memory reads as evidence while pointing at nothing, so the failure
        must say which document to fix.
        """

        root = Path(self.enterExitStack.enter_context(tempfile.TemporaryDirectory()))
        (root / "docs").mkdir()
        (root / "docs" / "SOME_CONTRACT.md").write_text(
            "Navigation is owned by `components/omnibox/browser/omnibox_edit_model.h`.\n",
            encoding="utf-8",
        )

        report: list[str] = []
        with mock.patch.object(checker, "exists", lambda source, version, path: False):
            healthy = checker.check_citations("github", "152.0.7977.42", root, report)

        self.assertFalse(healthy)
        joined = "\n".join(report)
        self.assertIn("components/omnibox/browser/omnibox_edit_model.h", joined)
        self.assertIn("SOME_CONTRACT.md", joined)

    def test_ordinary_prose_is_not_mistaken_for_an_upstream_citation(self) -> None:
        """`app.css` and repository paths appear constantly in these documents."""

        root = Path(self.enterExitStack.enter_context(tempfile.TemporaryDirectory()))
        (root / "docs").mkdir()
        (root / "docs" / "PROSE.md").write_text(
            "The wordmark lives in `app.css`, validated by `scripts/foo.py`,\n"
            "and the seam is `chrome/browser/ui/tabs/tab_strip_model.h`.\n",
            encoding="utf-8",
        )

        self.assertEqual(
            {"chrome/browser/ui/tabs/tab_strip_model.h"},
            set(checker.cited_paths(root)),
        )

    def test_the_repository_cites_only_paths_that_exist(self) -> None:
        """Guards the real documents, not a fixture -- but offline-safe.

        The network form of this runs in CI; here we only assert the citations
        are extractable and non-empty, so a regex that silently stops matching
        cannot turn this check into a no-op that always passes.
        """

        citations = checker.cited_paths(REPOSITORY_ROOT)
        self.assertGreater(len(citations), 20)
        for path in citations:
            with self.subTest(path=path):
                self.assertRegex(path, r"^[a-z_]+/")
                self.assertNotIn("`", path)

    def test_section_stops_at_the_closing_brace(self) -> None:
        text = "struct A {\n  wanted;\n};\nstruct B {\n  unwanted;\n};"
        body = checker.section(text, "struct A {")
        self.assertIn("wanted", body)
        self.assertNotIn("unwanted", body)

    def test_the_authoritative_source_is_the_default(self) -> None:
        """The mirror exists for blocked environments, not as a second truth."""

        self.assertIn("googlesource", checker.SOURCES)
        self.assertIn("github", checker.SOURCES)
        workflow = (
            REPOSITORY_ROOT / ".github/workflows/architecture-guard-self-hosted.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("python scripts/verify_pinned_upstream.py", workflow)
        self.assertNotIn("--source github", workflow)

    def test_the_pinned_version_is_read_without_the_ref_prefix(self) -> None:
        self.assertEqual("152.0.7977.42", checker.pinned_version(REPOSITORY_ROOT))


class ThrottlingIsNotAbsenceTests(unittest.TestCase):
    """A throttled probe must never be reported as a missing upstream path.

    It was. GitHub rate-limits this account, and a run that probes two hundred
    paths starts collecting 429s partway through; `exists` caught every
    HTTPError and returned False, so the checker accused eleven contracts of
    citing paths that had been there minutes earlier. A guard that fails for a
    reason unrelated to what it checks is worse than no guard, because the next
    real failure reads as more of the same.
    """

    def _error(self, code: int) -> urllib.error.HTTPError:
        return urllib.error.HTTPError("https://example.invalid", code, "", None, None)

    def test_a_rate_limited_probe_raises_instead_of_reporting_absence(self) -> None:
        with mock.patch.object(checker.time, "sleep"), mock.patch.object(
            checker.urllib.request, "urlopen", side_effect=self._error(429)
        ) as urlopen:
            with self.assertRaises(checker.UpstreamCheckError):
                checker.exists("github", "152.0.7977.42", "base/check.h")
        self.assertEqual(checker.RETRIES, urlopen.call_count)

    def test_a_server_error_raises_instead_of_reporting_absence(self) -> None:
        with mock.patch.object(checker.time, "sleep"), mock.patch.object(
            checker.urllib.request, "urlopen", side_effect=self._error(503)
        ):
            with self.assertRaises(checker.UpstreamCheckError):
                checker.exists("github", "152.0.7977.42", "base/check.h")

    def test_a_missing_path_is_still_reported_as_missing(self) -> None:
        """The retry must not turn a real 404 into a stalled run."""

        with mock.patch.object(checker.time, "sleep"), mock.patch.object(
            checker.urllib.request, "urlopen", side_effect=self._error(404)
        ) as urlopen:
            self.assertFalse(checker.exists("github", "152.0.7977.42", "base/gone.h"))
        self.assertEqual(1, urlopen.call_count, "a 404 must not be retried")

    def test_a_probe_that_recovers_on_retry_succeeds(self) -> None:
        response = mock.MagicMock()
        response.status = 200
        response.__enter__.return_value = response
        with mock.patch.object(checker.time, "sleep"), mock.patch.object(
            checker.urllib.request, "urlopen", side_effect=[self._error(429), response]
        ):
            self.assertTrue(checker.exists("github", "152.0.7977.42", "base/check.h"))


if __name__ == "__main__":
    unittest.main()
