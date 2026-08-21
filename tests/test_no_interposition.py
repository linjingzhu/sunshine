"""Tests for the non-interposition check.

Four contract criteria say the defect is the existence of a Sunshine-owned copy
of something Chromium already owns. A check for that passes on an empty
repository, so every rule below is proved by injecting the violation it is
supposed to catch.

Three tests assert the opposite. `test_a_parser_in_a_patch_context_line_is_not_a_violation`
and `test_a_timer_in_a_patch_context_line_is_not_a_violation` pin the rule that
makes the whole check usable: a patch is mostly upstream, and the shipped
`0002-sunshine-new-tab.patch` already carries an idle timeout constant in its
context. `test_reading_pinned_state_in_a_function_is_not_a_violation` pins the
other one: AT-1 requires pinned state to be read from `TabStripModel`, so a
rule that fired on the word would fire on the compliant implementation.
"""

from pathlib import Path
import json
import shutil
import sys
import tempfile
import unittest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))

import verify_no_interposition as checker  # noqa: E402


class NoInterpositionTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, directory, True)
        self.root = Path(directory) / "repo"
        shutil.copytree(
            REPOSITORY_ROOT,
            self.root,
            ignore=shutil.ignore_patterns(".git", "__pycache__", "chromium"),
        )

    # --- helpers -------------------------------------------------------------

    def assertRejected(self, needle: str) -> None:
        failures = checker.validate(self.root)
        self.assertTrue(failures, "the violation was accepted")
        self.assertTrue(any(needle in f for f in failures), f"{needle!r} not in {failures}")

    def assertAccepted(self) -> None:
        self.assertEqual([], checker.validate(self.root))

    def write_patch(self, added: tuple[str, ...] = (), context: tuple[str, ...] = ()) -> None:
        """A patch whose added and context lines are controlled separately."""

        lines = [
            "diff --git a/chrome/browser/ui/sunshine/probe.cc b/chrome/browser/ui/sunshine/probe.cc",
            "--- a/chrome/browser/ui/sunshine/probe.cc",
            "+++ b/chrome/browser/ui/sunshine/probe.cc",
            "@@ -1,2 +1,4 @@",
        ]
        lines.extend(f" {line}" for line in context)
        lines.extend(f"+{line}" for line in added)
        (self.root / "downstream/patches/0003-probe.patch").write_text(
            "\n".join(lines) + "\n", encoding="utf-8"
        )

    def write_module(self, **overrides: object) -> None:
        path = self.root / "first_party/modules/sunshine-workspace/module.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest.update(overrides)
        path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # --- the repository today ------------------------------------------------

    def test_the_repository_interposes_on_nothing_today(self) -> None:
        """Enforces: OS-9, AT-1, AT-9, AT-12, PB-5.

        Criterion: docs/OMNIBOX_CONTRACT.md OMA-20;
        docs/TAB_LIFECYCLE_CONTRACT.md 13.2 (invariant 1);
        docs/ADVANCED_TABS_CONTRACT.md 11.10;
        docs/PERFORMANCE_BUDGET.md PB-5, cheap form.
        """

        self.assertEqual([], checker.validate(REPOSITORY_ROOT))

    def test_the_extractors_are_reading_something(self) -> None:
        """A check that reads nothing passes for the wrong reason."""

        self.assertGreater(len(checker.sunshine_sources(self.root)), 10)
        self.assertGreater(len(checker.declared_names(self.root)), 100)

    # --- OMNIBOX_CONTRACT OMA-20: no second parser ---------------------------

    def test_a_classifier_constructed_in_first_party_code_is_rejected(self) -> None:
        self.write_patch(added=("  AutocompleteInput input(text, metrics::OmniboxEventProto::OTHER);",))
        self.assertRejected("an omnibox classifier")

    def test_a_registry_lookup_is_rejected(self) -> None:
        """A TLD list Sunshine does not have to write out is still a TLD list."""

        self.write_patch(added=("  auto domain = net::registry_controlled_domains::GetDomainAndRegistry(host);",))
        self.assertRejected("a registry/TLD lookup")

    def test_a_language_url_parser_in_a_model_module_is_rejected(self) -> None:
        (self.root / "scripts/route_model.py").write_text(
            "from urllib.parse import urlparse\n\n\ndef host_of(text):\n"
            "    return urlparse(text).hostname\n",
            encoding="utf-8",
        )
        self.assertRejected("a URL parser")

    def test_a_scheme_table_written_as_literals_is_rejected(self) -> None:
        self.write_patch(added=('  const kHandled = ["https://", "javascript:", "view-source:"];',))
        self.assertRejected("scheme table")

    def test_a_tld_list_written_as_literals_is_rejected(self) -> None:
        self.write_patch(added=('  const kKnown = [".com", ".org", ".net", ".io"];',))
        self.assertRejected("TLD list")

    def test_a_development_host_allowlist_field_is_rejected(self) -> None:
        """OMNIBOX_CONTRACT section 5: no trusted-local-hosts preference."""

        self.write_patch(added=('  "host_allowlist": ["build-box"],',))
        self.assertRejected("a host validator or development-host allowlist")

    def test_a_suggestion_cache_field_is_rejected(self) -> None:
        self.write_patch(added=("  std::vector<Match> suggestion_cache_;",))
        self.assertRejected("a Sunshine autocomplete or suggestion store")

    def test_a_navigation_call_taking_a_string_is_rejected(self) -> None:
        """OS-9: no first-party surface accepts a string and navigates."""

        self.write_patch(added=("  contents->OpenURLFromTab(params, std::move(callback));",))
        self.assertRejected("OS-9")

    def test_a_parser_in_a_patch_context_line_is_not_a_violation(self) -> None:
        """The rule the whole check depends on. Upstream is not Sunshine."""

        self.write_patch(
            context=(
                "  AutocompleteInput input(text, ClassifyPage(), scheme_classifier);",
                "  const VOICE_IDLE_TIMEOUT_MS = 8000;",
            ),
            added=("  // Sunshine adds a design token here and nothing else.",),
        )
        self.assertAccepted()

    def test_the_upstream_path_a_patch_names_is_not_a_violation(self) -> None:
        """`+++ b/path` starts with `+` and always names a Chromium file."""

        (self.root / "downstream/patches/0003-probe.patch").write_text(
            "--- a/components/omnibox/browser/autocomplete_input.cc\n"
            "+++ b/components/omnibox/browser/autocomplete_input.cc\n",
            encoding="utf-8",
        )
        self.assertAccepted()

    def test_a_command_id_naming_a_feature_is_not_a_field(self) -> None:
        """`tab.duplicate` is a native command, not a stored duplicate set."""

        path = self.root / "first_party/commands.json"
        registry = json.loads(path.read_text(encoding="utf-8"))
        entry = dict(registry["commands"][0])
        entry.update(
            {
                "id": "tab.pinned.toggle",
                "summary": "Pin or unpin the active tab; the duplicate set is not stored.",
                "telemetry": "Sunshine.Command.TabPinnedToggle",
            }
        )
        registry["commands"].append(entry)
        path.write_text(json.dumps(registry, indent=2), encoding="utf-8")
        self.assertAccepted()

    # --- OS-9: navigation, and the one form of it that is not a violation ----
    #
    # These exist because the OS-9 rule was narrowed. A security check that is
    # loosened needs the hole it did not open to be written down as a test, or
    # the next person has only the comment's word for it.

    def test_navigating_to_a_sunshine_host_constant_is_accepted(self) -> None:
        """The exemption. Nothing is accepted, so there is nothing to classify:
        the value is fixed when the browser is compiled."""

        self.write_patch(added=(
            "  content::OpenURLParams params("
            "GURL(chrome::kChromeUISunshineModulesURL), content::Referrer(),",
            "      ui::DispositionFromEventFlags(event.flags()),"
            " ui::PAGE_TRANSITION_AUTO_BOOKMARK, false);",
        ))
        self.assertAccepted()

    def test_navigating_to_a_variable_is_still_rejected(self) -> None:
        self.write_patch(added=(
            "  content::OpenURLParams params(GURL(target), content::Referrer());",
        ))
        self.assertRejected("navigates from an unclassified string")

    def test_navigating_to_a_concatenation_is_still_rejected(self) -> None:
        """The constant is present, but the statement builds a string from it.
        That is exactly the shape OS-9 forbids, so the closing parenthesis has
        to follow the constant immediately."""

        self.write_patch(added=(
            "  content::OpenURLParams params(GURL(base::StrCat("
            "{chrome::kChromeUISunshineModulesURL, suffix})), content::Referrer());",
        ))
        self.assertRejected("navigates from an unclassified string")

    def test_a_non_sunshine_constant_is_still_rejected(self) -> None:
        """The exemption covers Sunshine's own hosts. A Chromium page is
        Chromium's to navigate to, through Chromium's own code."""

        self.write_patch(added=(
            "  content::OpenURLParams params(GURL(chrome::kChromeUISettingsURL),"
            " content::Referrer());",
        ))
        self.assertRejected("navigates from an unclassified string")

    def test_a_second_unclassified_navigation_is_still_rejected(self) -> None:
        """One exempt navigation must not vouch for another in the same file."""

        self.write_patch(added=(
            "  content::OpenURLParams first("
            "GURL(chrome::kChromeUISunshineModulesURL), content::Referrer());",
            "  content::OpenURLParams second(GURL(whatever), content::Referrer());",
        ))
        self.assertRejected("navigates from an unclassified string")

    def test_a_javascript_navigation_is_still_rejected(self) -> None:
        """The exemption is a C++ shape. No JavaScript form is admitted."""

        self.write_patch(added=(
            "  location.href = chrome::kChromeUISunshineModulesURL;",
        ))
        self.assertRejected("navigates from an unclassified string")

    def test_the_shipped_button_patch_is_the_only_navigation_in_the_stack(self) -> None:
        """The exemption has exactly one user today. If a second appears, this
        fails and someone has to look at it rather than inherit the allowance."""

        navigating = [
            path.name
            for path in sorted((REPOSITORY_ROOT / "downstream/patches").glob("*.patch"))
            if any(
                symbol in checker.added_lines(path.read_text(encoding="utf-8"))
                for symbol in checker.NAVIGATION_SYMBOLS
            )
        ]
        self.assertEqual(["0008-sunshine-module-home-button.patch"], navigating)

    # --- TAB_LIFECYCLE_CONTRACT 13.2: no stored lifecycle flag ---------------

    def test_a_stored_loading_flag_is_rejected(self) -> None:
        self.write_patch(added=("  bool is_loading_ = false;",))
        self.assertRejected("a stored per-tab lifecycle flag")

    def test_a_serialised_tab_state_key_is_rejected(self) -> None:
        """Invariant 1: no session record stores a tab's lifecycle state."""

        (self.root / "scripts/tab_projection.py").write_text(
            "def persistable(tab):\n"
            '    return {"uuid": tab.uuid, "tab_state": tab.state}\n',
            encoding="utf-8",
        )
        self.assertRejected("a stored per-tab lifecycle flag")

    def test_a_throbber_field_is_rejected(self) -> None:
        self.write_patch(added=('  "throbber": true,',))
        self.assertRejected("a stored per-tab lifecycle flag")

    def test_the_module_lifecycle_scope_is_not_a_lifecycle_flag(self) -> None:
        """`"lifecycle": "profile"` is a manifest scope and must stay legal."""

        self.write_module(lifecycle="window")
        self.assertAccepted()

    # --- ADVANCED_TABS_CONTRACT 11.10 ----------------------------------------

    def test_a_pinned_flag_is_rejected(self) -> None:
        self.write_patch(added=('  "pinned": false,',))
        self.assertRejected("AT-1")

    def test_a_pinned_flag_spelled_as_a_chromium_constant_is_rejected(self) -> None:
        """`kPinnedTabs`, `pinnedTabs` and `pinned_tabs` are one field."""

        self.write_patch(added=("  const char kPinnedTabs[] = \"sunshine.pinned_tabs\";",))
        self.assertRejected("AT-1")

    def test_a_recently_closed_store_is_rejected(self) -> None:
        self.write_patch(added=("  std::vector<Entry> recently_closed_tabs_;",))
        self.assertRejected("AT-9")

    def test_a_duplicate_set_is_rejected(self) -> None:
        self.write_patch(added=('  "duplicate_group_id": 3,',))
        self.assertRejected("AT-12")

    def test_a_canonical_url_table_is_rejected(self) -> None:
        self.write_patch(added=("  base::flat_map<GURL, int> canonical_url_table_;",))
        self.assertRejected("a canonical-URL table")

    def test_reading_pinned_state_in_a_function_is_not_a_violation(self) -> None:
        """AT-1 requires the read. Only a stored field is the defect."""

        (self.root / "scripts/strip_projection.py").write_text(
            "def project(model, index):\n"
            "    pinned = model.IsTabPinned(index)\n"
            "    return index if pinned else index + 1\n",
            encoding="utf-8",
        )
        self.assertAccepted()

    def test_a_sunshine_owned_per_tab_persistent_store_is_rejected(self) -> None:
        """The declaration is the violation, whatever the field is called."""

        self.write_module(
            data=[{"owner": "sunshine", "scope": "tab", "access": "write", "retention": "persistent"}]
        )
        self.assertRejected("tab-scoped, persistent store")

    def test_writing_chromium_owned_tab_data_stays_legal(self) -> None:
        """Invariant 3: Sunshine writes tab session extra-data. That is the
        permitted channel and the workspace module already declares it."""

        self.write_module(
            data=[{"owner": "chromium", "scope": "tab", "access": "write", "retention": "persistent"}]
        )
        self.assertAccepted()

    def test_transient_per_tab_sunshine_state_stays_legal(self) -> None:
        """Both contracts permit state that does not survive the surface."""

        self.write_module(
            data=[{"owner": "sunshine", "scope": "tab", "access": "write", "retention": "none"}]
        )
        self.assertAccepted()

    # --- PERFORMANCE_BUDGET PB-5 -----------------------------------------------

    def test_a_repeating_interval_is_rejected(self) -> None:
        self.write_patch(added=("  setInterval(() => this.refresh_(), 30000);",))
        self.assertRejected("PB-5")

    def test_a_chromium_repeating_timer_is_rejected(self) -> None:
        self.write_patch(added=("  base::RepeatingTimer refresh_timer_;",))
        self.assertRejected("PB-5")

    def test_an_idle_callback_is_rejected(self) -> None:
        self.write_patch(added=("  requestIdleCallback(() => this.prewarm_());",))
        self.assertRejected("PB-5")

    def test_an_infinite_css_animation_is_rejected(self) -> None:
        """Idle cost does not stop being idle cost for being declarative."""

        self.write_patch(added=("  animation-iteration-count: infinite;",))
        self.assertRejected("PB-5")

    def test_a_stored_poll_interval_is_rejected(self) -> None:
        self.write_patch(added=('  "poll_interval_ms": 5000,',))
        self.assertRejected("PB-5")

    def test_a_timer_in_a_patch_context_line_is_not_a_violation(self) -> None:
        """`0002-sunshine-new-tab.patch` carries exactly this in its context."""

        self.write_patch(
            context=("const VOICE_IDLE_TIMEOUT_MS = 8000;", "  setInterval(poll, 1000);"),
            added=("  '#sunshineWordmark',",),
        )
        self.assertAccepted()

    # --- the boundary of the check -------------------------------------------

    def test_the_guards_are_deliberately_not_scanned(self) -> None:
        """A guard has to name what it forbids, so guards are out of scope.

        Pinned here so the exclusion stays a decision rather than an accident:
        a violation moved into a `verify_*.py` or `validate_*.py` file is not
        caught, and the naming convention is the whole boundary.
        """

        (self.root / "scripts/verify_probe.py").write_text(
            'PINNED_TABS = {"pinned": True}\nsetInterval = None\n', encoding="utf-8"
        )
        self.assertAccepted()

        (self.root / "scripts/probe_model.py").write_text(
            'PINNED_TABS = {"pinned": True}\n', encoding="utf-8"
        )
        self.assertRejected("AT-1")


if __name__ == "__main__":
    unittest.main()
