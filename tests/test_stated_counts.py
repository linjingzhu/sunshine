"""Tests for the stated-count guard.

Two kinds of test live here and both are load-bearing.

The first kind injects a disagreement and asserts the guard reports it. A guard
that has only ever seen a tree it agrees with is indistinguishable from one whose
patterns match nothing.

The second kind writes a sentence the guard is *designed not to match* and
asserts it stays unmatched. Those tests are the ones that keep the guard alive.
The matcher is deliberately narrow, and the obvious way to "improve" it -- drop
the requirement that a claim name its source file, or add `names` and `entries`
to the noun set -- turns correct prose in `docs/TELEMETRY_CONTRACT.md`,
`docs/OPEN_DECISIONS.md`, `docs/ADVANCED_TABS_CONTRACT.md` and
`docs/BROWSER_UTILITIES_CONTRACT.md` into a build failure. Each such test names
the real sentence it is modelled on, so anyone widening the matcher finds out
immediately which document they just broke.
"""

from pathlib import Path
import re
import sys
import tempfile
import unittest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))

import verify_stated_counts as counts  # noqa: E402


# The real repository's surviving stale counts. Failures on the real tree must be
# a subset of this: fixing a document keeps the test green, adding a new stale
# count turns it red. Delete an entry once its document is corrected.
# Empty, and kept rather than deleted. It held one entry -- a dated measurement
# in ACCEPTANCE_SUITES section 8 -- which was first replaced with a checked
# count and then with no count at all: the checked version went stale within the
# hour, on the commit that added a single test. The `tests` subject stays
# because it will catch the next document that states a total; the document that
# prompted it now names the command instead. The assertion below is a subset
# check, so an empty tuple means every stale count the guard reports is real.
KNOWN_STALE: tuple[str, ...] = ()


class TreeTestCase(unittest.TestCase):
    """A temp tree whose five countable facts are chosen by the test."""

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.addCleanup(self.directory.cleanup)
        self.build()

    def build(
        self,
        commands: int = 3,
        surfaces: int = 2,
        modules: int = 2,
        patches: int = 3,
        revision: str = "152.0.7977.42",
        tests: int = 4,
    ) -> None:
        entries = ",".join(f'{{"id": "browser.c{n}"}}' for n in range(commands))
        surface_names = ",".join(f'"s{n}"' for n in range(surfaces))
        self.write(
            "first_party/commands.json",
            f'{{"schema_version": 2, "surfaces": [{surface_names}], "commands": [{entries}]}}',
        )
        module_paths = ",".join(
            f'"first_party/modules/m{n}/module.json"' for n in range(modules)
        )
        self.write("first_party/registry.json", f'{{"modules": [{module_paths}]}}')
        self.write(
            "downstream/patches/series",
            "# ordered\n" + "".join(f"000{n}-x.patch\n" for n in range(1, patches + 1)),
        )
        self.write("config/chromium.version", f"CHROMIUM_REVISION=refs/tags/{revision}\n")
        methods = "".join(f"    def test_n{n}(self): pass\n" for n in range(tests))
        self.write("tests/test_fixture.py", f"import unittest\nclass T(unittest.TestCase):\n{methods}")

    def write(self, relative: str, text: str) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def doc(self, text: str, name: str = "docs/CONTRACT.md") -> None:
        self.write(name, text)

    def failures(self) -> list[str]:
        return counts.check(self.root)[1]

    def claims(self) -> list[counts.Claim]:
        return counts.stated_counts(self.root)

    def assertUnmatched(self, text: str) -> None:
        """No claim at all -- not merely no failure."""

        self.doc(text)
        found = self.claims()
        self.assertEqual([], [claim.sentence for claim in found])
        self.assertEqual([], self.failures())


# --- Numbers ------------------------------------------------------------------


class NumberWordTests(unittest.TestCase):
    def test_digits_words_and_compounds_all_parse(self) -> None:
        for text, expected in (
            ("24", 24),
            ("0", 0),
            ("zero", 0),
            ("nine", 9),
            ("nineteen", 19),  # must not be read as `nine` with a `teen` suffix
            ("twenty", 20),
            ("twenty-four", 24),
            ("Twenty-Seven", 27),
            ("twenty four", 24),
        ):
            with self.subTest(text=text):
                self.assertEqual(expected, counts.parse_number(text))

    def test_a_non_number_is_not_a_count(self) -> None:
        self.assertIsNone(counts.parse_number("several"))
        self.assertIsNone(counts.parse_number("twenty-twenty"))


# --- Injected disagreements ---------------------------------------------------


class CommandCountTests(TreeTestCase):
    def test_a_wrong_word_count_naming_the_registry_is_reported(self) -> None:
        self.doc("`first_party/commands.json` holds twenty-four commands.")
        failures = self.failures()
        self.assertEqual(1, len(failures))
        self.assertIn("states 24 commands", failures[0])
        self.assertIn("first_party/commands.json has 3", failures[0])
        self.assertIn("holds twenty-four commands", failures[0])

    def test_a_wrong_digit_count_naming_the_registry_is_reported(self) -> None:
        self.doc("Telemetry is declared for all 11 registered commands in\n"
                 "`first_party/commands.json`. No sink exists.")
        self.assertEqual(1, len(self.failures()))

    def test_the_claim_is_found_when_the_sentence_wraps_across_lines(self) -> None:
        """Prose here is hard-wrapped, so a sentence is not a line."""

        self.doc(
            "It must come from the telemetry events declared for all\n"
            "twenty-four registered commands in `first_party/commands.json`. No\n"
            "telemetry sink exists.\n"
        )
        failures = self.failures()
        self.assertEqual(1, len(failures))
        self.assertIn("docs/CONTRACT.md:2:", failures[0])

    def test_a_table_cell_states_the_count_in_a_later_sentence(self) -> None:
        """Modelled on `docs/EXTENSION_MIME_CONTRACT.md` XM-C3.

        The cell names the file in one sentence and counts in the next, which is
        why the anchor is looked for in the whole block.
        """

        self.doc(
            "| id | O | `first_party/commands.json` registers no download command."
            " True at the state of this wave: nine commands over the surfaces. |\n"
        )
        failures = self.failures()
        self.assertEqual(1, len(failures))
        self.assertIn("states 9 commands", failures[0])

    def test_command_names_and_command_entries_are_the_same_claim(self) -> None:
        for noun in ("command names", "command entries"):
            with self.subTest(noun=noun):
                self.doc(f"`first_party/commands.json` ships twenty-four {noun}.")
                self.assertEqual(1, len(self.failures()))

    def test_a_correct_count_is_checked_and_passes(self) -> None:
        self.doc("`first_party/commands.json` holds three commands.")
        summary, failures = counts.check(self.root)
        self.assertEqual([], failures)
        self.assertIn("1 stated count(s)", summary)


class UpperBoundTests(TreeTestCase):
    """A count of commands above the registry total is wrong whatever it counts.

    No subset of the registry exceeds the registry, so this rule needs no anchor.
    It is what catches `docs/COMMAND_PALETTE_CONTRACT.md` section 4.3.
    """

    def test_a_count_above_the_total_is_reported_without_an_anchor(self) -> None:
        self.doc("Twenty-seven commands currently declare no reason tokens.")
        failures = self.failures()
        self.assertEqual(1, len(failures))
        self.assertIn("above the registry total", failures[0])

    def test_a_count_at_or_below_the_total_without_an_anchor_is_not_a_claim(self) -> None:
        """`docs/ADVANCED_TABS_CONTRACT.md`: "its two registered commands"."""

        self.assertUnmatched(
            "Sunshine's interest is settled by invariant 2 and its two registered\n"
            "commands.\n"
        )

    def test_a_conditional_sentence_above_the_total_is_not_an_assertion(self) -> None:
        """`docs/COMMAND_PALETTE_CONTRACT.md` argues about a palette that *would*."""

        self.assertUnmatched(
            "A palette that consulted the guards would execute up to ninety commands\n"
            "to draw a list.\n"
        )

    def test_the_bound_is_not_applied_to_surfaces_or_modules(self) -> None:
        """`surfaces` and `module` are ordinary words in these documents.

        "two profile-scoped surfaces", "a second module claiming the same
        implementation" -- bounding those would fire on prose that never meant
        the registry.
        """

        self.assertUnmatched(
            "Nine surfaces enumerate tabs the workspace projection hides, and nine\n"
            "modules would be needed to present them.\n"
        )


class SurfaceModuleAndPatchTests(TreeTestCase):
    def test_a_wrong_surface_count_is_reported(self) -> None:
        self.doc("`first_party/commands.json` declares nine surfaces.")
        failures = self.failures()
        self.assertEqual(1, len(failures))
        self.assertIn("states 9 command surfaces", failures[0])

    def test_a_wrong_module_count_is_reported(self) -> None:
        self.doc("`first_party/registry.json` lists five first-party modules.")
        failures = self.failures()
        self.assertEqual(1, len(failures))
        self.assertIn("first_party/registry.json has 2", failures[0])

    def test_a_wrong_patch_count_is_reported(self) -> None:
        self.doc("The stack in `downstream/patches/series` is seven patches.")
        failures = self.failures()
        self.assertEqual(1, len(failures))
        self.assertIn("states 7 patches", failures[0])

    def test_the_series_comment_line_is_not_a_patch(self) -> None:
        self.doc("`downstream/patches/series` holds three patches.")
        self.assertEqual([], self.failures())

    def test_a_missing_source_file_is_left_to_the_guard_that_owns_it(self) -> None:
        (self.root / "downstream/patches/series").unlink()
        self.doc("`downstream/patches/series` holds seven patches.")
        self.assertEqual([], self.failures())


class RevisionCitationTests(TreeTestCase):
    def test_a_stale_revision_literal_is_reported(self) -> None:
        self.doc("Target: Chromium 151.0.7000.10 recorded in `config/chromium.version`.")
        failures = self.failures()
        self.assertEqual(1, len(failures))
        self.assertIn("cites Chromium 151.0.7000.10", failures[0])
        self.assertIn("pins 152.0.7977.42", failures[0])

    def test_the_pinned_revision_is_accepted_wherever_it_appears(self) -> None:
        self.doc(
            "See [tab_strip_model.h]"
            "(https://github.com/chromium/chromium/blob/152.0.7977.42/chrome/x.h).\n"
        )
        self.assertEqual([], self.failures())

    def test_a_section_number_is_not_a_revision(self) -> None:
        self.assertUnmatched("Section 4.2.1 and rule 13.20 are unchanged.")

    def test_the_roll_cost_measurement_may_name_a_revision_that_is_not_the_pin(self) -> None:
        """`docs/BROWSER_OR_APP_REVIEW.md` section 10 measures what the stack
        costs at another revision. Its literal is the experiment's subject, not
        a link into upstream source, so a roll must leave it alone."""

        exempt, = counts.NOT_THE_PIN["docs/BROWSER_OR_APP_REVIEW.md"]
        self.doc(f"| `{exempt}` — the next milestone | 3 of 16 |",
                 name="docs/BROWSER_OR_APP_REVIEW.md")
        self.assertEqual([], self.failures())

    def test_the_exemption_does_not_spread_to_another_document(self) -> None:
        """The reason it is keyed by document. A second file naming the same
        revision is naming it as a link, which is exactly what the rule is for."""

        exempt, = counts.NOT_THE_PIN["docs/BROWSER_OR_APP_REVIEW.md"]
        self.doc(f"Read against Chromium {exempt}.", name="docs/OTHER_CONTRACT.md")
        failures = self.failures()
        self.assertEqual(1, len(failures))
        self.assertIn(f"cites Chromium {exempt}", failures[0])

    def test_the_exempt_document_is_still_held_to_every_other_revision(self) -> None:
        self.doc("Read against Chromium 151.0.7000.10.",
                 name="docs/BROWSER_OR_APP_REVIEW.md")
        failures = self.failures()
        self.assertEqual(1, len(failures))
        self.assertIn("cites Chromium 151.0.7000.10", failures[0])


# --- Forms the matcher deliberately does not match ----------------------------


class DeliberateNonMatchTests(TreeTestCase):
    """Each sentence here is real, or modelled directly on a real one.

    If a change to the matcher makes one of these fail, the change has made the
    guard fire on a correct document.
    """

    def test_a_design_question_about_histogram_shape_is_not_a_registry_claim(self) -> None:
        """`docs/OPEN_DECISIONS.md` P1 and `docs/TELEMETRY_CONTRACT.md` section 5.5.

        The registry's number appears because the question is *about* the
        registry's size, but the things counted -- histogram names, XML entries,
        buckets -- are not held by this repository at all.
        """

        self.assertUnmatched(
            "Command registry: twenty-four histogram names, or one enumeration with\n"
            "twenty-four buckets? Twenty-four separate histogram names means\n"
            "twenty-four XML entries, twenty-four expiry dates and twenty-four\n"
            "owners for one question, against `first_party/commands.json`.\n"
        )

    def test_a_quoted_wrong_count_beside_its_correction_is_not_a_claim(self) -> None:
        """`docs/ACCEPTANCE_SUITES.md` C5, exactly.

        The paragraph quotes two wrong numbers in order to correct them and then
        gives the true count from the registry. The paragraph names the registry,
        so only the quotation rule keeps the correction from being reported as
        the defect it is fixing.
        """

        self.doc(
            '**C5 — the palette contract misstates the registry.** It refers to\n'
            '"the 27 registered commands" and to "the 21 Chromium-owned commands".\n'
            "`first_party/commands.json` holds three commands.\n"
        )
        self.assertEqual([], self.failures())
        self.assertEqual([3], [claim.stated for claim in self.claims()])

    def test_a_count_of_a_named_owner_is_a_count_of_a_part(self) -> None:
        """`docs/COMMAND_PALETTE_CONTRACT.md`: "the twenty-one Chromium-owned commands"."""

        self.assertUnmatched(
            "For the twenty-one Chromium-owned commands in `first_party/commands.json`\n"
            "that enumeration is a claim about the pinned revision.\n"
        )

    def test_a_retired_subset_is_a_count_of_a_part(self) -> None:
        """`docs/TAB_WORKSPACE_SPLIT_CONTRACT.md`: "three split commands"."""

        self.assertUnmatched(
            "Sunshine registered three split commands in `first_party/commands.json`.\n"
            "They are gone.\n"
        )

    def test_a_count_of_some_other_noun_is_not_a_count_of_commands(self) -> None:
        """`docs/BROWSER_UTILITIES_CONTRACT.md`: "Eleven of these utilities ...".

        The registry path is in the same sentence and the number is a subset of
        the registry. Adding `utilities`, `entries`, `rows` or `names` to the
        noun set breaks this document.
        """

        self.assertUnmatched(
            "Eleven of these utilities are now registered in `first_party/commands.json`,\n"
            "all `chromium`-owned. A palette rendering eleven rows and eleven names\n"
            "would consult eleven entries.\n"
        )

    def test_a_noun_followed_by_the_identifiers_it_counts_is_a_part(self) -> None:
        """`docs/ADVANCED_TABS_CONTRACT.md` names the two it means."""

        self.assertUnmatched(
            "`first_party/commands.json` records the two registered commands\n"
            "`tab.group.create` / `tab.group.ungroup` and nothing more here.\n"
        )

    def test_a_section_reference_is_an_address_not_a_quantity(self) -> None:
        self.assertUnmatched(
            "`first_party/commands.json` is the authoritative list. Section 9\n"
            "commands and invariant 12 modules are described elsewhere, as is\n"
            "schema version 9 modules handling.\n"
        )

    def test_a_heading_number_is_not_a_quantity(self) -> None:
        self.assertUnmatched(
            "### 9 Commands\n\n"
            "`first_party/commands.json` is the authoritative list.\n"
        )

    def test_an_anchor_in_one_list_item_does_not_reach_the_next(self) -> None:
        self.build(commands=12)
        self.assertUnmatched(
            "- `first_party/commands.json` was read, not modified.\n"
            "- Nine commands were retired in an earlier wave.\n"
        )

    def test_an_anchor_in_one_paragraph_does_not_reach_the_next(self) -> None:
        self.build(commands=12)
        self.assertUnmatched(
            "`first_party/commands.json` is validated by\n"
            "`scripts/validate_commands.py`.\n"
            "\n"
            "Nine commands were retired in an earlier wave.\n"
        )

    def test_none_and_no_are_not_counts(self) -> None:
        """`docs/EXTENSION_MIME_CONTRACT.md`: "registers no download command"."""

        self.assertUnmatched(
            "`first_party/commands.json` registers no download command and none of\n"
            "the modules declares one.\n"
        )

    def test_a_fenced_code_block_is_not_prose(self) -> None:
        self.assertUnmatched(
            "`first_party/commands.json` is the list.\n"
            "\n"
            "```\n"
            "# ninety commands, ninety modules, ninety patches\n"
            "```\n"
        )

    def test_a_backticked_span_is_code_not_a_claim(self) -> None:
        self.assertUnmatched(
            "Every entry in `first_party/commands.json` declares\n"
            "`unavailable_reasons: [] for 99 commands`.\n"
        )


# --- The real repository ------------------------------------------------------


class TestCountTests(TreeTestCase):
    """The fifth subject: how many tests `unittest discover` would report."""

    def test_a_wrong_test_count_citing_the_discover_command_is_reported(self) -> None:
        self.doc(
            "On 2026-08-17 `python -m unittest discover -s tests` reported 9 tests.\n"
        )
        failures = self.failures()
        self.assertEqual(1, len(failures))
        self.assertIn("states 9 tests", failures[0])
        self.assertIn("tests/ has 4", failures[0])

    def test_a_correct_test_count_passes_and_is_counted(self) -> None:
        self.doc("`python3 -m unittest discover -s tests` reports four tests.")
        summary, failures = counts.check(self.root)
        self.assertEqual([], failures)
        self.assertIn("1 stated count(s)", summary)

    def test_test_methods_and_test_cases_are_the_same_claim(self) -> None:
        for noun in ("test methods", "test cases"):
            with self.subTest(noun=noun):
                self.doc(f"`unittest discover -s tests` reports 9 {noun}.")
                self.assertEqual(1, len(self.failures()))

    def test_a_date_in_the_sentence_is_not_a_count(self) -> None:
        """The dated form is the sentence being replaced; its date must not parse."""

        self.doc("On 2026-08-17 `python -m unittest discover -s tests` reported 4 tests.")
        self.assertEqual([], self.failures())
        self.assertEqual([4], [claim.stated for claim in self.claims()])


class TestCountNonMatchTests(TreeTestCase):
    """Forms the tests subject deliberately does not match."""

    def test_a_count_of_tests_without_the_discover_command_is_not_a_claim(self) -> None:
        """`docs/TAB_WORKSPACE_SPLIT_CONTRACT.md` §4.2, which names a test file.

        This is the reason the anchor is the discover command and not `tests/`.
        With `tests/` as the anchor this correct sentence is reported as
        claiming the suite holds two tests.
        """

        self.assertUnmatched(
            "These identifiers must leave `first_party/commands.json`, this section,\n"
            "and the two tests that assert their presence in the same commit, because\n"
            "`tests/test_command_registry.py` fails when the registry and this table\n"
            "disagree.\n"
        )

    def test_a_contracts_acceptance_criteria_are_not_the_suite(self) -> None:
        """`docs/ACCEPTANCE_SUITES.md` section 2 counts criteria, calling them tests."""

        self.assertUnmatched(
            "| `docs/SESSION_PROFILE_CONTRACT.md` | 14 tests SRA-1…SRA-14 in 5 groups |"
            " SRA-, numbered continuously |\n"
        )

    def test_prose_about_where_tests_live_is_not_a_count(self) -> None:
        """`docs/SECURITY_ARCHITECTURE_CONTRACT.md` §10."""

        self.assertUnmatched(
            "Security tests live in `tests/` with everything else. A separate\n"
            "`security/` tree would fork the suite, and a forked suite is one somebody\n"
            "forgets to run.\n"
        )


class UncountableSuiteTests(TreeTestCase):
    """Constructs that make the count undecidable must refuse, never guess low.

    Under-counting is the dangerous direction: the documented number would drift
    back toward the truth from the wrong side and read as agreement. Each
    construct here was checked against real `unittest` discovery first, and each
    is absent from `tests/` today.
    """

    def claim_with(self, module: str) -> list[str]:
        self.write("tests/test_fixture.py", module)
        self.doc("`python -m unittest discover -s tests` reports 4 tests.")
        return self.failures()

    def test_load_tests_builds_the_suite_at_runtime(self) -> None:
        failures = self.claim_with(
            "import unittest\n"
            "class A(unittest.TestCase):\n    def test_a(self): pass\n"
            "def load_tests(loader, tests, pattern):\n    return tests\n"
        )
        self.assertEqual(1, len(failures))
        self.assertIn("load_tests", failures[0])
        self.assertIn("cannot be checked", failures[0])

    def test_a_class_defined_outside_the_module_body_is_refused(self) -> None:
        failures = self.claim_with(
            "import unittest\nimport sys\n"
            "if sys.platform:\n"
            "    class A(unittest.TestCase):\n        def test_a(self): pass\n"
        )
        self.assertEqual(1, len(failures))
        self.assertIn("outside the module body", failures[0])

    def test_setattr_can_add_test_methods_at_import_time(self) -> None:
        failures = self.claim_with(
            "import unittest\n"
            "class A(unittest.TestCase): pass\n"
            "setattr(A, 'test_x', lambda self: None)\n"
        )
        self.assertEqual(1, len(failures))
        self.assertIn("setattr()", failures[0])

    def test_a_base_class_from_another_module_is_refused(self) -> None:
        failures = self.claim_with(
            "import unittest\nfrom helpers import Base\n"
            "class A(Base):\n    def test_a(self): pass\n"
        )
        self.assertEqual(1, len(failures))
        self.assertIn("not defined in that module", failures[0])

    def test_a_class_bound_to_a_second_name_would_be_counted_twice(self) -> None:
        failures = self.claim_with(
            "import unittest\n"
            "class A(unittest.TestCase):\n    def test_a(self): pass\n"
            "Alias = A\n"
        )
        self.assertEqual(1, len(failures))
        self.assertIn("twice", failures[0])

    def test_a_subdirectory_under_tests_is_refused(self) -> None:
        self.write("tests/nested/test_deep.py", "import unittest\n")
        failures = self.claim_with("import unittest\n")
        self.assertEqual(1, len(failures))
        self.assertIn("subdirectory", failures[0])

    def test_an_uncountable_suite_is_silent_when_no_document_claims_a_count(self) -> None:
        """Not being able to count is not by itself a defect."""

        self.write("tests/test_fixture.py", "def load_tests(l, t, p):\n    return t\n")
        self.doc("`first_party/commands.json` holds three commands.")
        self.assertEqual([], self.failures())


class DiscoveryAgreementTests(unittest.TestCase):
    """The static count must equal what the command the document cites reports.

    This is the contract the whole subject rests on, so it is asserted against
    `unittest` itself rather than argued for in a comment. Discovery imports the
    test modules -- already imported, since this file is one of them -- and
    `countTestCases()` collects without executing, so this stays fast and runs
    no test body.

    If someone adds a construct the static counter cannot model, this test fails
    and names the gap. That is the intended outcome: the choice is then to teach
    the counter or to drop the claim from the document, and both are decisions a
    person should make.
    """

    @staticmethod
    def discovered(start: Path) -> int:
        saved_path = list(sys.path)
        saved_modules = set(sys.modules)
        try:
            return unittest.TestLoader().discover(str(start)).countTestCases()
        finally:
            for name in set(sys.modules) - saved_modules:
                del sys.modules[name]
            sys.path[:] = saved_path

    def test_the_static_count_equals_real_discovery_on_this_repository(self) -> None:
        self.assertEqual(
            self.discovered(REPOSITORY_ROOT / "tests"),
            counts.count_tests(REPOSITORY_ROOT),
        )

    def test_the_static_count_equals_real_discovery_on_the_awkward_shapes(self) -> None:
        """The three the brief named, plus the ones that broke a first attempt."""

        shapes = {
            "a subTest loop is one test": (
                "import unittest\n"
                "class A(unittest.TestCase):\n"
                "    def test_many(self):\n"
                "        for i in range(50):\n"
                "            with self.subTest(i=i): pass\n"
            ),
            "a skipped test is still counted": (
                "import unittest\n"
                "class A(unittest.TestCase):\n"
                "    @unittest.skip('why')\n"
                "    def test_skipped(self): pass\n"
                "    def test_ok(self): pass\n"
            ),
            "an inherited method counts once per subclass": (
                "import unittest\n"
                "class Base(unittest.TestCase):\n    def test_shared(self): pass\n"
                "class A(Base):\n    def test_a(self): pass\n"
                "class B(Base):\n    def test_b(self): pass\n"
            ),
            "an override is one test, not two": (
                "import unittest\n"
                "class Base(unittest.TestCase):\n    def test_shared(self): pass\n"
                "class A(Base):\n    def test_shared(self): pass\n"
            ),
            "a fixture base class with no test methods adds nothing": (
                "import unittest\n"
                "class Fixture(unittest.TestCase):\n    def setUp(self): pass\n"
                "class A(Fixture):\n    def test_a(self): pass\n"
            ),
            "diamond inheritance": (
                "import unittest\n"
                "class Base(unittest.TestCase):\n    def test_base(self): pass\n"
                "class L(Base):\n    def test_l(self): pass\n"
                "class R(Base):\n    def test_r(self): pass\n"
                "class D(L, R):\n    def test_d(self): pass\n"
            ),
            "a non-TestCase class named like one is not collected": (
                "import unittest\n"
                "class Helper:\n    def test_not_a_test(self): pass\n"
                "class A(unittest.TestCase):\n    def test_a(self): pass\n"
            ),
            "a class nested in a class is not a module attribute": (
                "import unittest\n"
                "class A(unittest.TestCase):\n"
                "    def test_a(self): pass\n"
                "    class Inner(unittest.TestCase):\n        def test_inner(self): pass\n"
            ),
            "the prefix is `test`, not `test_`": (
                "import unittest\n"
                "class A(unittest.TestCase):\n"
                "    def testCamel(self): pass\n"
                "    def test_snake(self): pass\n"
                "    def helper_test(self): pass\n"
                "    def _test_private(self): pass\n"
            ),
            "`from unittest import TestCase`": (
                "from unittest import TestCase\n"
                "class A(TestCase):\n    def test_a(self): pass\n"
            ),
            "an asyncio case": (
                "import unittest\n"
                "class A(unittest.IsolatedAsyncioTestCase):\n"
                "    async def test_async(self): pass\n"
                "    def test_sync(self): pass\n"
            ),
        }
        for name, module in shapes.items():
            with self.subTest(shape=name):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    (root / "tests").mkdir()
                    # A unique module name per shape: `discover` imports by name
                    # and a cached module would answer for the previous shape.
                    stem = "test_" + re.sub(r"\W+", "_", name)
                    (root / "tests" / f"{stem}.py").write_text(module, encoding="utf-8")
                    # Not matching `test*.py`, so discovery must ignore it.
                    (root / "tests" / "helper_support.py").write_text(
                        "import unittest\n"
                        "class Ignored(unittest.TestCase):\n    def test_x(self): pass\n",
                        encoding="utf-8",
                    )
                    self.assertEqual(
                        self.discovered(root / "tests"), counts.count_tests(root)
                    )


class RealRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.summary, self.repository_failures = counts.check(REPOSITORY_ROOT)
        self.claims = counts.stated_counts(REPOSITORY_ROOT)

    def test_the_documents_are_actually_scanned(self) -> None:
        """A matcher that found nothing would pass every other test silently."""

        self.assertGreaterEqual(len(self.claims), 5)
        self.assertTrue(any(claim.subject == "commands" for claim in self.claims))
        self.assertTrue(counts.revision_citations(REPOSITORY_ROOT))
        self.assertIn("stated count(s)", self.summary)

    def test_every_claim_points_at_a_real_document_line(self) -> None:
        for claim in self.claims:
            path = REPOSITORY_ROOT / claim.document
            self.assertTrue(path.is_file(), claim.document)
            lines = path.read_text(encoding="utf-8").splitlines()
            self.assertTrue(1 <= claim.line <= len(lines), claim.failure())

    def test_the_known_registry_claims_are_matched(self) -> None:
        """The six anchored claims the corpus survey found, by document."""

        documents = {claim.document for claim in self.claims if claim.rule.startswith("names")}
        self.assertEqual(
            {
                "docs/ACCEPTANCE_SUITES.md",
                "docs/EXTENSION_MIME_CONTRACT.md",
                "docs/PROFILE_ONBOARDING_CONTRACT.md",
                "docs/ROADMAP_NATIVE_COMMAND_EXPANSION.md",
                "docs/TELEMETRY_CONTRACT.md",
            },
            documents,
        )

    def test_no_disagreement_beyond_the_ones_already_recorded(self) -> None:
        unexpected = [
            failure
            for failure in self.repository_failures
            if not failure.startswith(KNOWN_STALE)
        ]
        self.assertEqual([], unexpected)


if __name__ == "__main__":
    unittest.main()
