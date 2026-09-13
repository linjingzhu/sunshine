"""Tests for the runtime-verification evidence guard.

The guard passes vacuously against the repository as it stands -- every
manifest reads `pending`, so its central rule has nothing to judge. That makes
these tests the only place the rule is ever exercised until someone writes the
first `passed`, and it makes the injected violations load-bearing rather than
decorative: a guard whose main rule has never once fired is indistinguishable
from one whose parser silently finds nothing.

The fixture copies a real manifest out of the repository rather than inventing
one, because rule 6 hands it to `validate_first_party_modules.validate_manifest`
and a synthetic manifest would fail that validator for reasons having nothing to
do with what is being tested.
"""

import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))

import trace_invariants as tracer  # noqa: E402
import validate_first_party_modules as modules  # noqa: E402
import verify_verification_evidence as guard  # noqa: E402
import verify_pinned_upstream as upstream_module  # noqa: E402

CONTRACT = """# Security architecture

| SEC-1 | The sandbox stays on. |
| SEC-2 | Site isolation stays on. |
"""

DOCUMENT = """# Runtime verification

## 1. Automated — `scripts/verify_installed_build.py`

| Check | Invariant |
| --- | --- |
| the binary exists and is plausible | native build |

`native_build: passed` requires this script to have exited 0 on the build
machine, and the run to be identifiable.

## 2. Manual — the runtime gate

| # | Step | Expected | Invariant |
| --- | --- | --- | --- |
{runtime_rows}

## 3. Visual

| # | Step | Expected |
| --- | --- | --- |
{visual_rows}

## 4. Recording the result

```text
gate       {namespace}
result     PASS | FAIL | NOT RUN
build      workflow run number and commit sha
observed   what was actually seen
```

{records}

## 5. What has been run

Nothing yet.
"""

DEFAULTS = {
    "runtime_rows": (
        "| R1 | Open a page | The sandbox is on | SEC-1 |\n"
        "| R2 | Open two frames | Two processes | SEC-2 |"
    ),
    "visual_rows": "| V1 | Resize the page | Nothing clips |",
    "namespace": "R1..R2, V1",
    "records": "",
}


def record(gate: str, result: str = "PASS", build: str = "run 1, commit abc1234") -> str:
    """One evidence record in the shape section 4 specifies."""

    body = f"gate       {gate}\nresult     {result}"
    if build:
        body += f"\nbuild      {build}"
    return f"```text\n{body}\n```"


class GuardTestCase(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, directory, True)
        self.root = Path(directory)
        for name in ("docs", "docs/decisions", "downstream/patches", "first_party/modules"):
            (self.root / name).mkdir(parents=True)
        self.write("docs/SECURITY_ARCHITECTURE_CONTRACT.md", CONTRACT)
        # The fixture document names this script in its section 1 heading, as
        # the real one does. Rule 3 is not under test in most cases here, so
        # the file has to exist or every unrelated case fails for one reason.
        self.write("scripts/verify_installed_build.py", "# a stand-in\n")
        self.manifest = json.loads(
            (REPOSITORY_ROOT / "first_party/modules/sunshine-new-tab/module.json").read_text("utf-8")
        )
        self.set_verification()

    def write(self, relative: str, text: str) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def set_verification(self, **fields: str) -> None:
        """Write the fixture manifest with these verification states."""

        states = {field: "pending" for field in guard.FIELDS}
        states.update(fields)
        self.manifest["verification"] = states
        self.write(
            "first_party/modules/sample/module.json", json.dumps(self.manifest, indent=2)
        )

    def failures(self, **overrides: str) -> list[str]:
        fields = dict(DEFAULTS, **overrides)
        self.write("docs/RUNTIME_VERIFICATION.md", DOCUMENT.format(**fields))
        _, failures = guard.check(self.root)
        return failures


class CleanFixtureTests(GuardTestCase):
    def test_a_consistent_document_passes(self) -> None:
        self.assertEqual([], self.failures())

    def test_the_report_names_gates_references_and_manifests(self) -> None:
        self.write("docs/RUNTIME_VERIFICATION.md", DOCUMENT.format(**DEFAULTS))
        report, _ = guard.check(self.root)
        self.assertIn("3 gates", report[0])
        self.assertIn("1 manifests", report[0])

    def test_the_specification_block_is_not_read_as_a_record(self) -> None:
        """Section 4's block is the shape, not an observation.

        It is separated out by what it says -- a gate range and every result at
        once -- rather than by which section it sits in, so a real record
        placed in section 4 would still count and this one would not.
        """

        self.write("docs/RUNTIME_VERIFICATION.md", DOCUMENT.format(**DEFAULTS))
        records, templates = guard.evidence_records(
            (self.root / "docs/RUNTIME_VERIFICATION.md").read_text("utf-8")
        )
        self.assertEqual([], records)
        self.assertEqual(1, len(templates))


class EvidenceForPassedTests(GuardTestCase):
    """The rule the document exists for, and the only one with no live subject.

    `passed` with no recorded evidence is worse than `pending`, because
    `pending` is true. Every case here is the situation that sentence is about.
    """

    def test_passed_with_no_evidence_at_all_is_rejected(self) -> None:
        """The injection that matters most."""

        self.set_verification(runtime="passed")
        found = self.failures()
        self.assertTrue(any("records no PASS for gate R1" in f for f in found), found)
        self.assertTrue(any("records no PASS for gate R2" in f for f in found), found)

    def test_passed_with_a_pass_for_every_gate_is_accepted(self) -> None:
        self.set_verification(runtime="passed")
        self.assertEqual([], self.failures(records=record("R1") + "\n\n" + record("R2")))

    def test_passed_with_evidence_for_only_some_gates_is_rejected(self) -> None:
        """The partial claim, which is the one a person actually makes: the
        first gates were run, the last was skipped, and the field was advanced
        anyway."""

        self.set_verification(runtime="passed")
        found = self.failures(records=record("R1"))
        self.assertEqual(1, len(found), found)
        self.assertIn("records no PASS for gate R2", found[0])

    def test_a_failed_gate_does_not_support_a_passed_field(self) -> None:
        self.set_verification(runtime="passed")
        found = self.failures(records=record("R1") + "\n\n" + record("R2", result="FAIL"))
        self.assertTrue(any("records no PASS for gate R2" in f for f in found), found)

    def test_evidence_for_the_wrong_section_does_not_support_a_field(self) -> None:
        """A visual gate is not evidence that the runtime gates were run."""

        self.set_verification(runtime="passed")
        found = self.failures(records=record("V1"))
        self.assertTrue(any("gate R1" in f for f in found), found)

    def test_the_visual_field_is_held_to_its_own_gates(self) -> None:
        self.set_verification(visual="passed")
        self.assertEqual([], self.failures(records=record("V1")))

    def test_a_field_whose_section_defines_no_numbered_gate_cannot_be_claimed(self) -> None:
        """Section 1 has a table and no `#` column, so nothing a record could
        name. That is a gap in the document rather than in this parser, and the
        failure says which of the two it is."""

        self.set_verification(native_build="passed")
        found = self.failures()
        self.assertTrue(any("defines a numbered gate for it" in f for f in found), found)

    def test_pending_needs_no_evidence(self) -> None:
        self.set_verification()
        self.assertEqual([], self.failures())

    def test_a_state_that_is_not_passed_needs_no_evidence(self) -> None:
        """`failed` and `not_applicable` are honest states and carry no claim."""

        for state in sorted(modules.VERIFICATION_STATES - {"passed"}):
            with self.subTest(state=state):
                self.set_verification(runtime=state)
                self.assertEqual([], self.failures())


class RecordShapeTests(GuardTestCase):
    def test_a_record_naming_an_undefined_gate_is_rejected(self) -> None:
        """Not silently ignored. An unreadable claim that simply disappears is
        the mistake this repository has now made three times."""

        found = self.failures(records=record("R9"))
        self.assertTrue(any("does not define" in f and "R9" in f for f in found), found)

    def test_a_pass_with_no_build_recorded_is_rejected(self) -> None:
        found = self.failures(records=record("R1", build=""))
        self.assertTrue(any("PASS with no build recorded" in f for f in found), found)

    def test_a_result_outside_the_three_is_rejected(self) -> None:
        found = self.failures(records=record("R1", result="PROBABLY"))
        self.assertTrue(any("PROBABLY" in f for f in found), found)

    def test_contradictory_evidence_for_one_gate_is_rejected(self) -> None:
        found = self.failures(records=record("R1") + "\n\n" + record("R1", result="FAIL"))
        self.assertTrue(any("contradictory" in f for f in found), found)

    def test_a_not_run_record_needs_no_build(self) -> None:
        """`NOT RUN` is the honest entry for a gate nobody reached, and
        demanding a build reference for it would push people to omit it."""

        self.assertEqual([], self.failures(records=record("R1", result="NOT RUN", build="")))


class GateNamespaceTests(GuardTestCase):
    def test_a_duplicated_gate_is_rejected(self) -> None:
        found = self.failures(
            runtime_rows="| R1 | a | b | SEC-1 |\n| R1 | c | d | SEC-2 |", namespace="R1..R1, V1"
        )
        self.assertTrue(any("defined 2 times" in f for f in found), found)

    def test_a_gap_in_the_numbering_is_rejected(self) -> None:
        found = self.failures(
            runtime_rows="| R1 | a | b | SEC-1 |\n| R3 | c | d | SEC-2 |", namespace="R1..R3, V1"
        )
        self.assertTrue(any("without a gap" in f for f in found), found)

    def test_the_template_namespace_must_match_the_tables(self) -> None:
        """The template declares what a record may name. If it and the tables
        are edited apart, a record written against the template cites a gate
        nothing defines."""

        found = self.failures(namespace="R1..R4, V1")
        self.assertTrue(any("a different set" in f for f in found), found)
        self.assertTrue(any("R3, R4" in f for f in found), found)

    def test_a_gate_defined_but_left_out_of_the_template_is_reported(self) -> None:
        found = self.failures(namespace="R1..R2")
        self.assertTrue(any("defined and undeclared: V1" in f for f in found), found)

    def test_a_document_with_no_record_template_is_rejected(self) -> None:
        """Deleting section 4's block would leave this rule with nothing to
        compare and no reason to complain -- passing by having no work to do,
        which is the failure mode this whole guard is written against."""

        self.write(
            "docs/RUNTIME_VERIFICATION.md",
            DOCUMENT.format(**DEFAULTS).replace("```text", "```json", 1).replace(
                "gate       R1..R2, V1", "nothing here"
            ),
        )
        _, found = guard.check(self.root)
        self.assertTrue(any("no evidence record template" in f for f in found), found)


class ReferenceTests(GuardTestCase):
    def test_an_invariant_no_other_document_declares_is_rejected(self) -> None:
        """Self-satisfaction is the trap here: the citation is itself an
        occurrence, so a rule asking only "is this declared anywhere" would
        resolve a typo against the typo."""

        found = self.failures(runtime_rows="| R1 | a | b | SEC-9 |\n| R2 | c | d | SEC-2 |")
        self.assertTrue(any("SEC-9" in f and "no other document" in f for f in found), found)

    def test_an_adr_that_does_not_exist_is_rejected(self) -> None:
        found = self.failures(runtime_rows="| R1 | a | b | ADR 0099 |\n| R2 | c | d | SEC-2 |")
        self.assertTrue(any("ADR 0099" in f for f in found), found)

    def test_an_adr_that_exists_is_accepted(self) -> None:
        self.write("docs/decisions/0099-a-decision.md", "# A decision\n")
        self.assertEqual(
            [], self.failures(runtime_rows="| R1 | a | b | ADR 0099 |\n| R2 | c | d | SEC-2 |")
        )

    def test_a_patch_that_does_not_exist_is_rejected(self) -> None:
        found = self.failures(runtime_rows="| R1 | a | b | patch 0007 |\n| R2 | c | d | SEC-2 |")
        self.assertTrue(any("patch 0007" in f for f in found), found)

    def test_a_patch_that_exists_is_accepted(self) -> None:
        self.write("downstream/patches/0007-a-change.patch", "--- a/x\n")
        self.assertEqual(
            [], self.failures(runtime_rows="| R1 | a | b | patch 0007 |\n| R2 | c | d | SEC-2 |")
        )

    def test_a_repository_path_that_does_not_exist_is_rejected(self) -> None:
        found = self.failures(visual_rows="| V1 | see `scripts/absent.py` | nothing |")
        self.assertTrue(any("scripts/absent.py" in f for f in found), found)

    def test_a_url_a_gate_tells_a_person_to_type_is_not_a_path(self) -> None:
        """`chrome://version` and `sunshine://anything` are instructions, not
        files, and a rule that demanded they exist would be deleted at once."""

        self.assertEqual(
            [],
            self.failures(
                visual_rows="| V1 | Open `chrome://version`, type `sunshine://x` | fine |"
            ),
        )

    def test_gate_labels_are_not_resolved_as_contract_identifiers(self) -> None:
        """R1..R9 here and R1..R14 in `DESIGN_SYSTEM_CONTRACT.md` are different
        namespaces sharing a prefix. Reading a whole row would resolve this
        document's gate numbers against that document's runtime checks, so only
        the invariant column is scanned."""

        found = self.failures(runtime_rows="| R1 | a | b | SEC-1 |\n| R2 | c | R7 is fine | SEC-2 |")
        self.assertEqual([], found)


class AgreementTests(GuardTestCase):
    """Section 4's claim about the other validator, checked by calling it."""

    def test_the_claim_holds_against_the_real_validator(self) -> None:
        self.assertEqual([], self.failures())

    def test_a_validator_that_stopped_refusing_is_reported(self) -> None:
        original = modules.validate_manifest
        self.addCleanup(setattr, modules, "validate_manifest", original)
        modules.validate_manifest = lambda manifest, source: ("sunshine.x", set())
        found = self.failures()
        self.assertTrue(any("it does not" in failure for failure in found), found)

    def test_a_validator_that_cannot_run_is_reported_rather_than_assumed(self) -> None:
        original = modules.validate_manifest

        def broken(manifest, source):
            raise RuntimeError("schema moved")

        self.addCleanup(setattr, modules, "validate_manifest", original)
        modules.validate_manifest = broken
        found = self.failures()
        self.assertTrue(any("could not confirm" in failure for failure in found), found)


class DerivedShapeTests(unittest.TestCase):
    """The identifier grammar is the tracer's, not a fourth copy of it."""

    def test_no_identifier_shape_is_restated_in_this_guard(self) -> None:
        source = (REPOSITORY_ROOT / "scripts/verify_verification_evidence.py").read_text("utf-8")
        for fragment in ("[A-Z]{1,4}", r"\d{1,2}"):
            with self.subTest(fragment=fragment):
                for line in source.splitlines():
                    if fragment in line and not line.lstrip().startswith("#"):
                        self.fail(f"identifier shape restated: {line.strip()}")

    def test_identifier_extraction_is_delegated_to_the_tracer(self) -> None:
        """Not a pattern of its own: the module calls `_identifiers`, so a
        family or a widening added there arrives here on the same commit."""

        self.assertEqual({"SEC-1", "SEC-2"}, tracer._identifiers("SEC-1, SEC-2"))
        self.assertEqual({"PB-2a"}, tracer._identifiers("PB-2a"))


class UpstreamPathReferenceTests(unittest.TestCase):
    """A gate may name the Chromium file it is about.

    Every backticked path in the document must exist, which is right for the
    repository's own files and impossible for Chromium's: this guard is offline
    and `chrome/` is not in the working tree. Requiring it anyway would have
    meant RV-10's cause -- found in `chrome/app/chrome_exe.rc`, where an
    undefined `IDR_MAINFRAME` makes the icon resource names strings -- could not
    be written down beside the gate it explains.

    Upstream paths are not unchecked. `verify_pinned_upstream.py` reads every
    path cited anywhere in `docs/` and asks whether it exists at the pinned
    revision, which is the question worth asking about an upstream file.
    """

    def setUp(self) -> None:
        directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, directory, True)
        self.root = Path(directory)
        (self.root / "docs").mkdir()
        self.document = self.root / guard.DOCUMENT
        self.document.parent.mkdir(parents=True, exist_ok=True)

    def write(self, body: str) -> list[str]:
        self.document.write_text(body, encoding="utf-8")
        _, failures = guard.check(self.root)
        return failures

    def test_a_chromium_path_is_left_to_the_guard_that_can_check_it(self) -> None:
        failures = self.write("Cause: `chrome/app/chrome_exe.rc`.\n")
        self.assertEqual(
            [], [f for f in failures if "chrome_exe.rc" in f], failures
        )

    def test_a_repository_path_that_does_not_exist_still_fails(self) -> None:
        """The exemption is by prefix, and `scripts/` is ours."""

        failures = self.write("See `scripts/verify_nothing_at_all.py`.\n")
        self.assertTrue(
            any("verify_nothing_at_all.py" in f for f in failures), failures
        )

    def test_the_prefixes_are_the_shared_ones(self) -> None:
        """Two lists would drift. This is the same set
        `verify_pinned_upstream.py` uses to decide the same question."""

        self.assertIs(guard.upstream.OWN_PREFIXES, upstream_module.OWN_PREFIXES)
        for ours in ("scripts", "docs", "downstream", "first_party", "tests", "config"):
            self.assertIn(ours, guard.upstream.OWN_PREFIXES)
        self.assertNotIn("chrome", guard.upstream.OWN_PREFIXES)
        self.assertNotIn("components", guard.upstream.OWN_PREFIXES)


class RunSheetTests(GuardTestCase):
    """Rule 7 -- the run sheet schedules exactly what is still owed.

    The sheet exists because the gates are cheap individually and unmanageable
    as a list of forty-three, and it is allowed to hold no expectations at all.
    What it can do is go stale, in three ways, and each has a case here.
    """

    SHEET = "docs/RETURN_RUN_SHEET.md"

    def sheet(self, text: str) -> None:
        self.write(self.SHEET, text)

    def test_a_sheet_naming_every_unrun_gate_is_accepted(self) -> None:
        self.sheet("Run R1, then R2, then V1.\n")
        self.assertEqual([], self.failures())

    def test_a_gate_left_off_the_sheet_is_reported(self) -> None:
        self.sheet("Run R1, then V1.\n")
        failures = self.failures()
        self.assertTrue(any("R2" in failure for failure in failures), failures)

    def test_a_gate_with_a_pass_need_not_be_scheduled(self) -> None:
        """The other direction of staleness: a gate already run stays off the
        sheet, and the sheet must not be forced to keep telling someone to run
        it."""

        self.sheet("Run R2, then V1.\n")
        self.assertEqual([], self.failures(records=record("R1")))

    def test_a_gate_the_document_does_not_define_is_reported(self) -> None:
        self.sheet("Run R1, R2, V1 and R9.\n")
        failures = self.failures()
        self.assertTrue(any("R9" in failure for failure in failures), failures)

    def test_an_identifier_from_another_series_is_not_read_as_a_gate(self) -> None:
        """A stop rule naming SEC-1 is citing a contract invariant, not
        mistyping a gate. Reading it as one would make every sheet that
        explains *why* a gate matters fail."""

        self.sheet("Run R1, R2, V1. If R1 fails, SEC-1 is not what it claims.\n")
        self.assertEqual([], self.failures())

    def test_no_sheet_leaves_the_rule_with_nothing_to_say(self) -> None:
        """Deliberate, and the reason the repository-level test below exists:
        absence is not a failure here, so absence must be a failure there."""

        self.assertEqual([], self.failures())


class RepositoryStateTests(unittest.TestCase):
    """The repository as it stands, and what of this guard is live in it.

    Rules 1 to 4 and 6 read real subjects on every run. Rule 5 -- the one the
    document is for -- has nothing to judge, because no manifest claims
    anything. That is recorded here rather than left implicit, so the day a
    field advances, this test is where the change is visible.
    """

    def setUp(self) -> None:
        self.report, self.failures = guard.check(REPOSITORY_ROOT)

    def test_the_repository_passes(self) -> None:
        self.assertEqual([], self.failures, "\n".join(self.report))

    def test_the_document_defines_seventy_three_gates_in_two_series(self) -> None:
        sections = guard.parse_sections(
            (REPOSITORY_ROOT / guard.DOCUMENT).read_text(encoding="utf-8")
        )
        found = [gate for section in sections for gate in guard.gates(section)]
        # The prefixes are `RV` and `RVV`, not a bare `R` and `V`. The bare
        # forms collided with DESIGN_SYSTEM_CONTRACT's own R series -- the
        # tracer reported this document's gates as declared by both -- while
        # `V` belonged to no family and so could never be claimed at all.
        self.assertEqual(
            [f"RV-{n}" for n in range(1, 69)] + [f"RVV-{n}" for n in range(1, 6)],
            [gate.label for gate in found],
        )

    def test_the_runtime_table_is_ordered_by_number(self) -> None:
        """The table is a numbered list; the run sheet decides execution order.

        RV-39 and RV-40 were first written into the middle of the table, beside
        the bookmark-bar gates they belong with, and this assertion caught it.
        Section F of `docs/RETURN_RUN_SHEET.md` says RV-39 runs first; that is
        the right place to say it, because every other section already reorders
        gates freely and section A starts at RV-11.
        """

        sections = guard.parse_sections(
            (REPOSITORY_ROOT / guard.DOCUMENT).read_text(encoding="utf-8")
        )
        for section in sections:
            numbers = [
                int(gate.label.rsplit("-", 1)[1]) for gate in guard.gates(section)
            ]
            with self.subTest(section=section.heading[:40]):
                self.assertEqual(sorted(numbers), numbers)

    def test_each_field_is_owned_by_exactly_one_section_with_a_table(self) -> None:
        """Rule 5 maps a manifest field to a gate set through the section that
        names it. Two owners would make that mapping ambiguous and the rule
        would quietly check the wrong gates."""

        sections = guard.parse_sections(
            (REPOSITORY_ROOT / guard.DOCUMENT).read_text(encoding="utf-8")
        )
        for field, expected in (("native_build", "1"), ("runtime", "2"), ("visual", "3")):
            with self.subTest(field=field):
                owners = guard.owning_sections(sections, field)
                self.assertEqual([expected], [section.number for section in owners])

    def test_every_manifest_still_reads_pending(self) -> None:
        """The premise of the vacuity note in the module docstring. When this
        fails, the guard has stopped being a ratchet and started being a check,
        and the docstring needs rewriting."""

        found = guard.manifests(REPOSITORY_ROOT)
        self.assertTrue(found)
        for label, manifest in found:
            with self.subTest(module=label):
                self.assertEqual(
                    {field: "pending" for field in guard.FIELDS}, manifest["verification"]
                )

    def test_the_recorded_evidence_is_only_what_was_actually_observed(self) -> None:
        """This asserted `[] == records` for one day, and that was right then.

        The owner has since run build #12 and reported the wordmark, so RV-7
        has evidence. The assertion is kept rather than deleted because the
        risk it guards has grown, not gone: the temptation now is to record the
        adjacent gates too. Build #12 was commit 6aa75ff, which precedes both
        the codec change and the infobar removal, so the binary that was
        launched did not contain the code RV-5, RV-6 and RV-8 are about.

        A record for any of those would be a claim about a build nobody ran.
        """

        records, templates = guard.evidence_records(
            (REPOSITORY_ROOT / guard.DOCUMENT).read_text(encoding="utf-8")
        )
        self.assertEqual(1, len(templates), "section 4's record template is missing")
        self.assertEqual(["RV-7"], [record.gate for record in records])
        self.assertEqual(["PASS"], [record.result for record in records])
        self.assertIn("6aa75ff", records[0].build)

    def test_the_run_sheet_exists_and_rule_seven_is_live(self) -> None:
        """Rule 7 is a no-op where there is no sheet, so this is the assertion
        that the repository is not that case. Forty-two of the forty-three
        gates are owed, and the sheet has to say when to run every one."""

        self.assertTrue((REPOSITORY_ROOT / guard.RUN_SHEET).is_file())
        self.assertTrue(
            any(guard.RUN_SHEET in line for line in self.report),
            "\n".join(self.report),
        )

    def test_evidence_alone_advances_no_manifest(self) -> None:
        """A gate passing is not a module being verified.

        RV-7 is one of nine runtime gates, and `runtime: passed` needs all of
        them. Recording the first is what makes that arithmetic visible rather
        than something to be argued about later.
        """

        _, failures = guard.check(REPOSITORY_ROOT)
        self.assertEqual([], failures)
        for label, manifest in guard.manifests(REPOSITORY_ROOT):
            with self.subTest(module=label):
                self.assertNotIn("passed", manifest["verification"].values())


if __name__ == "__main__":
    unittest.main()
