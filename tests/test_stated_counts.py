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
import sys
import tempfile
import unittest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))

import verify_stated_counts as counts  # noqa: E402


# The real repository's surviving stale counts. Failures on the real tree must be
# a subset of this: fixing a document keeps the test green, adding a new stale
# count turns it red. Delete an entry once its document is corrected.
KNOWN_STALE = (
    # Section 4.3 still reads 27 after the three `view.split.*` commands were
    # retired. Section 15 of the same contract already records the correction,
    # and `docs/ACCEPTANCE_SUITES.md` C5 records it again.
    "docs/COMMAND_PALETTE_CONTRACT.md:349",
)


class TreeTestCase(unittest.TestCase):
    """A temp tree whose four countable facts are chosen by the test."""

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
