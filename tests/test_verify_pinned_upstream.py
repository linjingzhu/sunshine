"""Tests for the pinned-upstream check.

The bug this check replaced was a false positive: it asked `app.css` whether a
colour-pipeline token existed, and would have failed the build on a token that
does. So the point of these tests is not that the check passes -- it is that it
fails for the right reason and passes for the right reason, without touching the
network.
"""

import contextlib
from pathlib import Path
import re
import shutil
import subprocess
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
             mock.patch.object(checker, "check_asset_overlay", return_value=True), \
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

    def test_a_path_the_stack_creates_is_not_demanded_of_upstream(self) -> None:
        """The failure this exemption was written for.

        `chrome/common/sunshine/sunshine_webui_hosts.h` is created by the seam
        patch and cited by OMNIBOX_CONTRACT.md. It sits under `chrome/`, so
        nothing in its spelling separates it from an upstream path -- and
        upstream correctly does not have it, which this check reported as a
        missing citation until it learned the difference.
        """

        root = Path(self.enterExitStack.enter_context(tempfile.TemporaryDirectory()))
        (root / "docs").mkdir()
        (root / "docs" / "SOME_CONTRACT.md").write_text(
            "The hosts live in `chrome/common/sunshine/sunshine_webui_hosts.h`.\n",
            encoding="utf-8",
        )
        patches = root / "downstream" / "patches"
        patches.mkdir(parents=True)
        (patches / "series").write_text("0001-probe.patch\n", encoding="utf-8")
        (patches / "0001-probe.patch").write_text(
            "diff --git a/chrome/common/sunshine/sunshine_webui_hosts.h "
            "b/chrome/common/sunshine/sunshine_webui_hosts.h\n"
            "--- /dev/null\n"
            "+++ b/chrome/common/sunshine/sunshine_webui_hosts.h\n"
            "@@ -0,0 +1 @@\n"
            "+// created by the stack\n",
            encoding="utf-8",
        )

        report: list[str] = []
        with mock.patch.object(checker, "exists", lambda source, version, path: False):
            healthy = checker.check_citations("github", "152.0.7977.42", root, report)

        self.assertTrue(healthy, "\n".join(report))
        self.assertIn("created by the patch stack", "\n".join(report))

    def test_an_upstream_citation_still_fails_beside_a_created_one(self) -> None:
        """The exemption must not swallow the check it sits inside."""

        root = Path(self.enterExitStack.enter_context(tempfile.TemporaryDirectory()))
        (root / "docs").mkdir()
        (root / "docs" / "SOME_CONTRACT.md").write_text(
            "See `chrome/common/sunshine/sunshine_webui_hosts.h` and\n"
            "`components/omnibox/browser/omnibox_edit_model.h`.\n",
            encoding="utf-8",
        )
        patches = root / "downstream" / "patches"
        patches.mkdir(parents=True)
        (patches / "series").write_text("0001-probe.patch\n", encoding="utf-8")
        (patches / "0001-probe.patch").write_text(
            "diff --git a/chrome/common/sunshine/sunshine_webui_hosts.h "
            "b/chrome/common/sunshine/sunshine_webui_hosts.h\n"
            "--- /dev/null\n"
            "+++ b/chrome/common/sunshine/sunshine_webui_hosts.h\n"
            "@@ -0,0 +1 @@\n"
            "+// created by the stack\n",
            encoding="utf-8",
        )

        report: list[str] = []
        with mock.patch.object(checker, "exists", lambda source, version, path: False):
            healthy = checker.check_citations("github", "152.0.7977.42", root, report)

        self.assertFalse(healthy)
        self.assertIn("omnibox_edit_model.h", "\n".join(report))

    def test_the_repositorys_own_created_paths_are_the_expected_ones(self) -> None:
        """Reads the real stack, so a patch that stopped creating a cited file
        fails here rather than in CI's network step."""

        created = checker.stack_created_paths(REPOSITORY_ROOT)
        cited = set(checker.cited_paths(REPOSITORY_ROOT))
        self.assertEqual(
            {
                "chrome/common/sunshine/sunshine_webui_hosts.h",
                # Created by 0017 and cited by section 5 of
                # docs/ACCOUNT_LINK_PLAN.md, which names it as the first of the
                # three links carrying the client id from the release pipeline.
                "chrome/browser/ui/sunshine/BUILD.gn",
                "components/sunshine/document/project_store.cc",
                "chrome/browser/resources/sunshine/document/host.ts",
                "chrome/browser/resources/sunshine/shell/app.ts",
                "chrome/browser/resources/sunshine/shell/mount.ts",
                "chrome/browser/resources/sunshine/shell/mount_port.ts",
                "chrome/browser/ui/webui/sunshine/document/sunshine_document.mojom",
                "chrome/browser/ui/webui/sunshine/document/sunshine_document_content_ui.h",
                # Created by 0025 and cited by section 16 of
                # docs/COMMAND_PALETTE_CONTRACT.md, which names it as the file
                # the title guard reads. Upstream has no such path, so the
                # citation checker must know the stack makes it.
                "chrome/app/sunshine/sunshine_command_strings.grd",
            },
            created & cited,
        )

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
        # The larger budget, not the ordinary one: a 429 is a quota answer and
        # is retried on `THROTTLED_RETRIES`. The count is asserted rather than
        # ignored so that a change to either budget has to be deliberate.
        self.assertEqual(checker.THROTTLED_RETRIES, urlopen.call_count)

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


class CitationCoverageTests(unittest.TestCase):
    """No upstream citation may be added to the contracts without being checked.

    The rule this replaces named the Chromium top-level directories it would
    accept, and the list was already short: `media/` twice and `sandbox/` once
    had never been probed by anything, along with `google_apis/` and the
    `.asciipb` and `.md` suffixes. Nothing said so, because an unmatched
    citation is absent rather than rejected -- there is no probe, so there is no
    failure, so there is nothing to read.

    Widening the list would have fixed those five and left the sixth to the same
    silence. What is asserted instead is the property: every backticked token in
    docs/ that names a file inside a directory is either checked, or excluded
    for a reason written down here.
    """

    # A token that names a file inside a directory: it has a slash, and its
    # last segment carries a dot. Deliberately far looser than CITATION -- it
    # is the net, not the rule, and everything it catches has to be accounted
    # for one way or the other.
    CANDIDATE = re.compile(r"`([^`\n]*/[^`\n]*\.[^`\n]*)`")

    # Characters that mean the token is not one concrete path. `:` is a scheme
    # (`chrome://`, `https://`, `data:text/html`), `*{}<>…` stand for more than
    # one file (`session_restore.*`, `tab_strip_model.{h,cc}`,
    # `metadata/<area>/histograms.xml`, `tools/perf/…`), and `()"=,` appear only
    # where the backticks are quoting code or arithmetic rather than a path.
    NOT_A_SINGLE_PATH = set(':*{}<>…()"=,')

    def reason_it_is_not_an_upstream_citation(self, token: str) -> str | None:
        """Why a candidate is legitimately unchecked, or None if it should be.

        These are the boundary. Each corresponds to a family of tokens the
        contracts really contain -- a survey of docs/ produced every one of
        them -- and a candidate matching none of them is an upstream path that
        nothing is verifying.
        """

        if token.split("/", 1)[0] in checker.OWN_PREFIXES:
            return "ours, or the build tree"
        if any(character.isspace() for character in token):
            return "prose: contains whitespace"
        if set(token) & self.NOT_A_SINGLE_PATH:
            return "not one concrete path: scheme, glob or placeholder"
        if token.endswith("/"):
            return "a directory, not a file"
        if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.+-]*(?:/[A-Za-z0-9_][A-Za-z0-9_.+-]*)*", token):
            return "not a plain path"
        if not re.search(r"\.[A-Za-z][A-Za-z0-9]{0,7}$", token):
            return "no file suffix: a version, a ratio or a directory"
        return None

    def candidates(self) -> list[tuple[str, str]]:
        found = []
        for document in sorted((REPOSITORY_ROOT / "docs").rglob("*.md")):
            for token in self.CANDIDATE.findall(document.read_text(encoding="utf-8")):
                found.append((document.name, token.strip()))
        return found

    def test_every_upstream_looking_citation_in_the_contracts_is_checked(self) -> None:
        cited = set(checker.cited_paths(REPOSITORY_ROOT))
        unchecked = sorted({
            f"{document}: {token}"
            for document, token in self.candidates()
            if token not in cited and self.reason_it_is_not_an_upstream_citation(token) is None
        })
        self.assertEqual(
            [],
            unchecked,
            "a contract cites an upstream path that nothing probes; widen CITATION, "
            "or add the reason it is not a citation to this test",
        )

    def test_the_net_is_wide_enough_to_be_worth_casting(self) -> None:
        """A candidate pattern that caught only what CITATION already matches
        would make the property above circular."""

        tokens = {token for _, token in self.candidates()}
        self.assertGreater(len(tokens), len(checker.cited_paths(REPOSITORY_ROOT)))
        for prose in ("refs/tags/152.0.7977.42", "13.5/7.25", "max / min = 1.75",
                      "chrome/browser/ui/tabs/tab_strip_model.{h,cc}"):
            with self.subTest(token=prose):
                self.assertIn(prose, tokens)
                self.assertIsNotNone(self.reason_it_is_not_an_upstream_citation(prose))

    def test_the_property_catches_the_defect_it_was_written_for(self) -> None:
        """Run against the hand-kept alternation, this fails and names the
        citations that had never been probed."""

        previous = re.compile(
            r"`((?:base|build|chrome|components|content|net|services|third_party|tools|ui)"
            r"/[A-Za-z0-9_./]+\.(?:h|cc|mojom|css|ts|html|py|csv|json|gn|gni|xml))`"
        )
        cited = set()
        for document in sorted((REPOSITORY_ROOT / "docs").rglob("*.md")):
            cited |= set(previous.findall(document.read_text(encoding="utf-8")))
        unchecked = {
            token
            for _, token in self.candidates()
            if token not in cited and self.reason_it_is_not_an_upstream_citation(token) is None
        }
        self.assertIn("media/mojo/services/media_foundation_service.h", unchecked)
        self.assertIn("sandbox/policy/switches.cc", unchecked)
        self.assertIn("google_apis/google_api_keys.h", unchecked)

    def test_the_repository_directories_are_all_accounted_for(self) -> None:
        """`OWN_PREFIXES` is the one list still kept by hand, so it is checked.

        Read from what git tracks, not from what is on the disk. The first
        version listed the directory and failed on the build runner, where
        `artifacts/` exists because a build had run there and does not exist in
        a fresh clone. A rule that depends on whether the machine has built
        something is not checking the repository, and it fails for a reason
        unrelated to what it is for -- which is how a test gets deleted.

        A new *tracked* top-level directory is the real risk: its paths would
        be probed against Chromium, where they are not.
        """

        try:
            listed = subprocess.run(
                ("git", "ls-files", "-z"),
                cwd=REPOSITORY_ROOT, check=True, capture_output=True, text=True,
            ).stdout
        except (OSError, subprocess.CalledProcessError) as error:
            self.skipTest(f"git is needed to read the tracked tree: {error}")

        tracked = {
            entry.split("/", 1)[0] for entry in listed.split("\0")
            if entry and "/" in entry
        }
        self.assertGreaterEqual(len(tracked), 5, tracked)
        self.assertEqual(set(), tracked - set(checker.OWN_PREFIXES))

    def test_the_newly_covered_prefixes_and_suffixes_are_matched(self) -> None:
        """The five shapes the old alternation could not express."""

        for path in (
            "media/mojo/services/media_foundation_service.h",
            "sandbox/policy/switches.cc",
            "google_apis/google_api_keys.h",
            "components/safe_browsing/content/resources/download_file_types.asciipb",
            "tools/metrics/histograms/README.md",
        ):
            with self.subTest(path=path):
                self.assertEqual([path], checker.CITATION.findall(f"see `{path}` upstream"))

    def test_our_own_paths_are_still_not_upstream_citations(self) -> None:
        """The temp-tree contract: this must not depend on what is on disk, or
        pointing the checker at a fixture would change which paths are ours."""

        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root, True)
        (root / "docs").mkdir()
        (root / "docs" / "P.md").write_text(
            "`scripts/foo.py`, `docs/OPEN_DECISIONS.md`, `first_party/commands.json`,\n"
            "`config/chromium.version`, `downstream/patches/series`, `tests/test_x.py`,\n"
            "`out/Sunshine/chrome.exe`, `src/third_party/icu/BUILD.gn`, and `app.css`,\n"
            "but `sandbox/policy/switches.cc` is upstream.\n",
            encoding="utf-8",
        )
        self.assertEqual({"sandbox/policy/switches.cc"}, set(checker.cited_paths(root)))

    def test_prose_that_merely_contains_a_slash_is_not_a_path(self) -> None:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root, True)
        (root / "docs").mkdir()
        (root / "docs" / "P.md").write_text(
            "`text/plain`, `application/octet-stream`, `max / min = 1.75`, `13.5/7.25`,\n"
            "`refs/tags/152.0.7977.42`, `chrome://sunshine-security`, `https://github.com/`,\n"
            "`components/sessions/`, `tools/...`, `chrome/browser/sessions/session_restore.*`,\n"
            "`chrome/browser/ui/tabs/tab_strip_model.{h,cc}`, `chrome/browser/ui/startup/first_run`.\n",
            encoding="utf-8",
        )
        self.assertEqual({}, checker.cited_paths(root))


def fake_response(payload: bytes, status: int = 200):
    response = mock.MagicMock()
    response.status = status
    response.read.return_value = payload
    response.__enter__.return_value = response
    return response


class DirectoryListingTests(unittest.TestCase):
    """Existence answered per directory instead of per path.

    The guard failed CI at 900d747 with a 429 from googlesource -- the
    authoritative host, not the mirror that was throttled before. The quota is
    on how many requests one anonymous client makes, so the retry that handles a
    burst cannot help; the only fix is to ask fewer questions. ~215 cited paths
    sit in ~99 directories.
    """

    LISTING = (
        b")]}'\n{\"id\": \"abc\", \"entries\": ["
        b"{\"mode\": 33188, \"type\": \"blob\", \"name\": \"switches.cc\"},"
        b"{\"mode\": 33188, \"type\": \"blob\", \"name\": \"switches.h\"}]}"
    )

    def test_a_gitiles_listing_is_parsed_past_its_xssi_guard(self) -> None:
        """Gitiles prefixes JSON with `)]}'`, which is not valid JSON and is
        there precisely so that a naive parser does not eat it."""

        with mock.patch.object(checker, "_open", return_value=fake_response(self.LISTING)):
            names = checker.directory_entries("googlesource", "152.0.7977.42", "sandbox/policy")
        self.assertEqual({"switches.cc", "switches.h"}, names)

    def test_the_mirror_cannot_list_and_says_so_without_asking(self) -> None:
        """raw.githubusercontent.com has no listing route. Returning None is
        what keeps the per-path probe as the mirror's fallback."""

        with mock.patch.object(checker, "_open", side_effect=AssertionError("no request")):
            self.assertIsNone(checker.directory_entries("github", "152.0.7977.42", "base"))

    def test_an_unparseable_listing_falls_back_rather_than_reporting_absence(self) -> None:
        """If the route changes and returns HTML, every path under it must be
        probed individually -- not reported missing. Reading an unreadable
        listing as an empty directory would accuse every contract citing it."""

        for payload in (b"<!doctype html><title>gitiles</title>", b")]}'\n{\"id\": \"abc\"}",
                        b")]}'\n{\"entries\": []}", b"not json at all"):
            with self.subTest(payload=payload[:20]):
                with mock.patch.object(checker, "_open", return_value=fake_response(payload)):
                    self.assertIsNone(
                        checker.directory_entries("googlesource", "152.0.7977.42", "base")
                    )

    def test_a_missing_directory_falls_back_instead_of_condemning_its_paths(self) -> None:
        error = urllib.error.HTTPError("https://example.invalid", 404, "", None, None)
        with mock.patch.object(checker, "_open", side_effect=error):
            self.assertIsNone(checker.directory_entries("googlesource", "152.0.7977.42", "gone"))

    def test_a_throttled_listing_stops_the_run(self) -> None:
        """The rule that must not be weakened, restated for the new request.

        A 429 must never become absence, and it must not become a fallback
        either: probing each path in a directory the host just refused turns one
        refusal into as many requests as the directory holds.
        """

        with mock.patch.object(checker.time, "sleep"), mock.patch.object(
            checker.urllib.request, "urlopen",
            side_effect=urllib.error.HTTPError("https://example.invalid", 429, "", None, None),
        ):
            with self.assertRaises(checker.UpstreamCheckError):
                checker.directory_entries("googlesource", "152.0.7977.42", "base")


class CitationRequestCountTests(unittest.TestCase):
    """The deliverable is the request count, so it is asserted."""

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, True)
        (self.root / "docs").mkdir()
        (self.root / "docs" / "C.md").write_text(
            "`chrome/browser/ui/tabs/tab_strip_model.h`, `chrome/browser/ui/tabs/tab_group_model.h`,\n"
            "`chrome/browser/ui/tabs/split_tab_util.h`, `base/check.h`, `base/logging.h`.\n",
            encoding="utf-8",
        )
        self.listed: list[str] = []
        self.probed: list[str] = []

    def listing(self, names: dict[str, set[str]]):
        def entries(source: str, version: str, directory: str):
            self.listed.append(directory)
            return names.get(directory)
        return entries

    def probe(self, present: bool = True):
        def exists(source: str, version: str, path: str) -> bool:
            self.probed.append(path)
            return present
        return exists

    def test_five_paths_in_two_directories_cost_two_requests(self) -> None:
        names = {
            "chrome/browser/ui/tabs": {"tab_strip_model.h", "tab_group_model.h", "split_tab_util.h"},
            "base": {"check.h", "logging.h"},
        }
        report: list[str] = []
        with mock.patch.object(checker, "directory_entries", self.listing(names)), \
             mock.patch.object(checker, "exists", self.probe()):
            healthy = checker.check_citations("googlesource", "152.0.7977.42", self.root, report)

        self.assertTrue(healthy, "\n".join(report))
        self.assertEqual(2, len(self.listed))
        self.assertEqual([], self.probed, "a listed directory must not also be probed")
        self.assertIn("2 directory listing(s), 0 individual probe(s)", "\n".join(report))

    def test_a_path_absent_from_its_directory_listing_is_reported(self) -> None:
        """The listing has to be able to fail the check, or it is decoration."""

        names = {
            "chrome/browser/ui/tabs": {"tab_strip_model.h", "tab_group_model.h"},
            "base": {"check.h", "logging.h"},
        }
        report: list[str] = []
        with mock.patch.object(checker, "directory_entries", self.listing(names)), \
             mock.patch.object(checker, "exists", self.probe()):
            healthy = checker.check_citations("googlesource", "152.0.7977.42", self.root, report)

        self.assertFalse(healthy)
        joined = "\n".join(report)
        self.assertIn("chrome/browser/ui/tabs/split_tab_util.h", joined)
        self.assertIn("C.md", joined)

    def test_a_directory_that_cannot_be_listed_is_probed_path_by_path(self) -> None:
        names = {"base": {"check.h", "logging.h"}}  # the tabs directory lists as None
        report: list[str] = []
        with mock.patch.object(checker, "directory_entries", self.listing(names)), \
             mock.patch.object(checker, "exists", self.probe()):
            healthy = checker.check_citations("googlesource", "152.0.7977.42", self.root, report)

        self.assertTrue(healthy, "\n".join(report))
        self.assertEqual(3, len(self.probed))
        self.assertIn("1 directory listing(s), 3 individual probe(s)", "\n".join(report))

    def test_the_mirror_still_works_entirely_by_probe(self) -> None:
        """`--source github` cannot list, and must keep checking the same
        paths rather than checking none of them."""

        report: list[str] = []
        with mock.patch.object(checker, "exists", self.probe()):
            healthy = checker.check_citations("github", "152.0.7977.42", self.root, report)
        self.assertTrue(healthy, "\n".join(report))
        self.assertEqual(5, len(self.probed))

    def test_the_real_contracts_group_into_far_fewer_directories(self) -> None:
        """The saving is a property of the corpus, so it is measured on it."""

        citations = checker.cited_paths(REPOSITORY_ROOT)
        directories = {path.rsplit("/", 1)[0] for path in citations}
        self.assertGreater(len(citations), 200)
        self.assertLess(len(directories), len(citations) / 2)


if __name__ == "__main__":
    unittest.main()


class LineEndingTests(unittest.TestCase):
    """The harness must not rewrite the bytes it is about to check.

    All three patches failed to apply on the Windows build runner and applied
    cleanly on Linux. The patch stack was correct: the checker wrote each
    fetched upstream file with `write_text`, whose text mode translates "\\n"
    to the platform line ending, so the temp tree held CRLF while the patches
    carry LF context. A harness that corrupts its own inputs reports a defect
    in whatever it is checking.

    Asserted structurally because the defect is invisible on the platform this
    suite usually runs on -- a behavioural test would pass on Linux whichever
    call were used, which is exactly how this survived until CI existed.
    """

    SOURCE = (REPOSITORY_ROOT / "scripts/verify_pinned_upstream.py").read_text(encoding="utf-8")

    def test_upstream_files_are_written_as_bytes(self) -> None:
        self.assertIn("write_bytes(", self.SOURCE)
        self.assertNotIn("write_text(", self.SOURCE)

    def test_the_temp_repository_disables_line_ending_conversion(self) -> None:
        self.assertIn("core.autocrlf=false", self.SOURCE)
        self.assertIn("core.eol=lf", self.SOURCE)


class ThrottleBudgetTests(unittest.TestCase):
    """A quota answer needs more patience than a burst answer.

    Both hosts meter anonymous clients over a window, and the ordinary backoff
    spends less time than the window lasts, so a run that meets the limit gives
    up while waiting would have answered. This buys patience, never permission:
    a 429 that outlasts the larger budget is still a failure, and is still
    never reported as a missing path.
    """

    def _error(self, code: int) -> urllib.error.HTTPError:
        return urllib.error.HTTPError("https://example.invalid", code, "", None, None)

    def test_a_throttled_answer_is_retried_more_than_an_ordinary_error(self) -> None:
        for code, expected in ((429, checker.THROTTLED_RETRIES), (503, checker.THROTTLED_RETRIES)):
            with self.subTest(code=code), mock.patch.object(checker.time, "sleep"), \
                    mock.patch.object(checker.urllib.request, "urlopen",
                                      side_effect=self._error(code)) as urlopen:
                with self.assertRaises(checker.UpstreamCheckError):
                    checker.exists("github", "152.0.7977.42", "base/check.h")
            self.assertEqual(expected, urlopen.call_count)

    def test_an_ordinary_error_keeps_the_smaller_budget(self) -> None:
        with mock.patch.object(checker.time, "sleep"), mock.patch.object(
            checker.urllib.request, "urlopen", side_effect=self._error(500)
        ) as urlopen:
            with self.assertRaises(checker.UpstreamCheckError):
                checker.exists("github", "152.0.7977.42", "base/check.h")
        self.assertEqual(checker.RETRIES, urlopen.call_count)

    def test_a_missing_path_is_still_never_retried(self) -> None:
        """The whole point survives the larger budget."""

        with mock.patch.object(checker.time, "sleep"), mock.patch.object(
            checker.urllib.request, "urlopen", side_effect=self._error(404)
        ) as urlopen:
            self.assertFalse(checker.exists("github", "152.0.7977.42", "base/gone.h"))
        self.assertEqual(1, urlopen.call_count)

    def test_a_throttled_run_that_never_recovers_still_fails(self) -> None:
        with mock.patch.object(checker.time, "sleep"), mock.patch.object(
            checker.urllib.request, "urlopen", side_effect=self._error(429)
        ):
            with self.assertRaises(checker.UpstreamCheckError):
                checker.exists("github", "152.0.7977.42", "base/check.h")


class AssetOverlayDestinationTests(unittest.TestCase):
    """The overlay's upstream half.

    `PinnedUpstreamTests` stubs this check out so those cases stay offline and
    stay about seams. That leaves the check itself untested, which matters more
    here than for a patch: `git apply` refuses a hunk whose context moved, so a
    patch reports an upstream restructure on its own. A file copy does not.
    These are the cases that make the restructure loud.
    """

    def overlay(self, *destinations: str) -> Path:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        for destination in destinations:
            path = root / "downstream/assets" / destination
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"\x00\x01")
        return root

    def test_a_destination_upstream_still_has_passes(self) -> None:
        root = self.overlay("chrome/app/theme/chromium/win/chromium.ico")
        report: list[str] = []
        with mock.patch.object(checker, "exists", lambda source, version, path: True):
            healthy = checker.check_asset_overlay("github", "152.0.7977.42", root, report)

        self.assertTrue(healthy, "\n".join(report))
        self.assertTrue(any("chromium.ico" in line and "OK" in line for line in report))

    def test_a_destination_upstream_renamed_fails_and_names_it(self) -> None:
        # The failure this exists for. Upstream moves the icon, the copy lands
        # beside the real one, the `.rc` still names Chromium's, and the build
        # ships Chromium's icon. Every command in the pipeline succeeds.
        root = self.overlay("chrome/app/theme/chromium/win/chromium.ico")
        report: list[str] = []
        with mock.patch.object(checker, "exists", lambda source, version, path: False):
            healthy = checker.check_asset_overlay("github", "152.0.7977.42", root, report)

        self.assertFalse(healthy)
        joined = "\n".join(report)
        self.assertIn("chrome/app/theme/chromium/win/chromium.ico", joined)
        self.assertIn("FAIL", joined)

    def test_no_overlay_asks_upstream_nothing(self) -> None:
        root = self.overlay()
        report: list[str] = []
        probe = mock.Mock(return_value=True)
        with mock.patch.object(checker, "exists", probe):
            self.assertTrue(checker.check_asset_overlay("github", "152.0.7977.42", root, report))
        probe.assert_not_called()
