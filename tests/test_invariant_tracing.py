"""Tests for invariant coverage tracing.

The gap this measures is real and mostly unfixable offline: the contracts
declare invariants about what a running browser does, and no unit test can
establish those. What it does prevent is enforcement disappearing quietly, and
a test claiming an invariant identifier that no contract declares -- which
happens when a contract is renumbered and its tests are not.
"""

from pathlib import Path
import re
import shutil
import sys
import tempfile
import unittest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]

# A third party's error code that collides with a Sunshine invariant family.
# Netflix's `E100` is shaped exactly like one of this repository's `E1`..`E8`
# identifiers and cannot be parsed whole, because the parser's range stops short
# of three digits -- so the survey reads it as a Sunshine identifier that went
# missing. Widening the parser would be the wrong fix twice over: it would not
# make `E100` ours, and it would start pulling foreign codes into tracing.
#
# The exemption is a (document, token) pair so it cannot spread. A Sunshine
# identifier that fails to parse is still a failure, in this document and every
# other, which `test_the_foreign_exemption_does_not_blunt_the_guard` asserts.
FOREIGN_IDENTIFIERS = frozenset({("0024-drm-widevine.md", "E100")})

sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))

import trace_invariants as tracer  # noqa: E402


class InvariantTracingTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, directory, True)
        self.root = Path(directory)
        (self.root / "docs").mkdir()
        (self.root / "tests").mkdir()
        (self.root / "scripts").mkdir()
        (self.root / "config").mkdir()

    def write(self, relative: str, text: str) -> None:
        (self.root / relative).write_text(text, encoding="utf-8")

    def test_the_repository_is_consistent_today(self) -> None:
        report, failures = tracer.check(REPOSITORY_ROOT)
        self.assertEqual([], failures, "\n".join(report))

    def test_declared_invariants_are_found(self) -> None:
        self.write("docs/C.md", "| OS-3 | The installer registers nothing. |\n")
        self.assertIn("OS-3", tracer.declared(self.root))

    def test_ordinary_prose_is_not_read_as_an_invariant(self) -> None:
        """`P1`, a version, and a Chromium symbol are not invariants."""

        self.write("docs/C.md", "P1 blocks this. Pinned at 152.0.7977.42. See H264 support.\n")
        self.assertEqual({}, tracer.declared(self.root))

    def test_a_claim_is_recognised(self) -> None:
        self.write("docs/C.md", "| AT-7 | Do not repurpose the visibility bit. |\n")
        self.write("tests/test_x.py", '"""Enforces: AT-7."""\n')
        report, failures = tracer.check(self.root)
        self.assertEqual([], failures)
        self.assertIn("Claimed by a test or tool: 1", report)

    def test_claiming_an_invariant_no_contract_declares_fails(self) -> None:
        """The renumbering guard.

        A contract's identifiers change and its tests keep the old ones. The
        test still passes -- it never checked the identifier -- so nothing
        notices that it now claims a rule that does not exist.
        """

        self.write("docs/C.md", "| AT-7 | Do not repurpose the visibility bit. |\n")
        self.write("tests/test_x.py", '"""Enforces: AT-9."""\n')
        _, failures = tracer.check(self.root)
        self.assertTrue(any("AT-9" in failure and "no contract declares it" in failure for failure in failures))

    def test_losing_an_enforced_invariant_fails(self) -> None:
        """Ratcheting down has to be a decision, not an accident."""

        self.write("docs/C.md", "| SC-1 | A verdict may not relax a Chromium decision. |\n")
        self.write("config/invariant_coverage.txt", "SC-1\n")
        _, failures = tracer.check(self.root)
        self.assertTrue(any("SC-1" in failure and "no longer is" in failure for failure in failures))

    def test_gaining_coverage_is_free(self) -> None:
        self.write("docs/C.md", "| SC-1 | A verdict may not relax a Chromium decision. |\n")
        self.write("tests/test_x.py", '"""Enforces: SC-1."""\n')
        self.write("config/invariant_coverage.txt", "")
        report, failures = tracer.check(self.root)
        self.assertEqual([], failures)
        self.assertTrue(any("Newly enforced" in line for line in report))

    def test_the_baseline_records_why_it_is_empty(self) -> None:
        """An empty file reads as an oversight unless it says otherwise, and
        this one is a measurement: almost nothing here is checkable offline."""

        text = (REPOSITORY_ROOT / "config/invariant_coverage.txt").read_text(encoding="utf-8")
        self.assertIn("running browser", text)
        self.assertIn("Enforces:", text)


class FourLetterFamilyTests(unittest.TestCase):
    """SECA-n could not be parsed at all, and nothing reported the gap.

    The pattern was `[A-Z]{1,3}`, so a four-letter family matched nothing. Two
    acceptance criteria read as enforced in their contract and as unclaimed by
    the tracer, and because an unparsed token is simply absent rather than
    rejected, the disagreement was invisible from both ends.
    """

    def test_a_four_letter_family_identifier_is_parsed(self) -> None:
        self.assertEqual(["SECA-11"], [m.group(1) for m in tracer.INVARIANT.finditer("see SECA-11 here")])

    def test_the_shorter_forms_still_parse(self) -> None:
        text = "SEC-13, PO-A1, AT-9, SPA-9, S12 and BH-2"
        found = [m.group(1) for m in tracer.INVARIANT.finditer(text)]
        for token in ("SEC-13", "PO-A1", "AT-9", "SPA-9", "S12", "BH-2"):
            with self.subTest(token=token):
                self.assertIn(token, found)

    def test_every_declared_family_is_parseable_by_the_pattern(self) -> None:
        """A family nobody can parse is a family nobody enforces."""

        for family in tracer.FAMILIES:
            with self.subTest(family=family):
                sample = f"{family}-1"
                self.assertEqual(
                    [sample],
                    [m.group(1) for m in tracer.INVARIANT.finditer(sample)],
                    f"{family} is in FAMILIES but the pattern cannot parse {sample}",
                )


class SubLetteredIdentifierTests(unittest.TestCase):
    """PB-2a was the second instance of the SECA-n bug.

    `PERFORMANCE_BUDGET.md` splits PB-2 into PB-2a, PB-2b and PB-2c, each its
    own rule. The pattern ended at `\\d{1,2}`, and the trailing `\\b` then failed
    against the letter, so the token did not truncate to PB-2 -- it vanished.
    Three declared invariants were invisible, and a check claiming one would
    have registered nothing while reporting success.

    The class above proves every family parses. That was true throughout, and
    it is why the family test did not catch this: the defect was in the tail of
    an identifier, not its head.
    """

    def test_a_sub_lettered_identifier_is_parsed(self) -> None:
        self.assertEqual(
            ["PB-2a"], [m.group(1) for m in tracer.INVARIANT.finditer("see PB-2a here")]
        )

    def test_the_sub_letter_is_not_dropped_or_truncated(self) -> None:
        """The specific defect: a parse that keeps some of the characters.

        PB-2a read as PB-2 would be worse than PB-2a read as nothing, because
        PB-2 exists -- the claim would resolve, against the wrong rule.
        """

        for token in ("PB-2a", "PB-2b", "PB-2c"):
            with self.subTest(token=token):
                self.assertEqual({token}, tracer._identifiers(token))

    def test_the_contracts_declare_them(self) -> None:
        """The end-to-end statement, read from the real document."""

        declared = tracer.declared(REPOSITORY_ROOT)
        for token in ("PB-2a", "PB-2b", "PB-2c"):
            with self.subTest(token=token):
                self.assertIn(token, declared, f"{token} is declared but not traced")
                self.assertIn("PERFORMANCE_BUDGET.md", declared[token])

    def test_an_uppercase_suffix_is_prose_not_an_identifier(self) -> None:
        """`E2E` is end-to-end, and E is a declared family. The suffix being
        lowercase is the whole of what separates the two, so it is asserted
        rather than assumed."""

        self.assertEqual(set(), tracer._identifiers("an E2E test"))

    def test_ordinary_acronyms_are_still_not_identifiers(self) -> None:
        """The widening must not have opened the door to codec names."""

        self.assertEqual(set(), tracer._identifiers("AV1, MP4, MV3 and VP9 at 152.0.7977.42"))


class IdentifierSurveyTests(unittest.TestCase):
    """The property that would have caught PB-2a without anybody noticing it.

    Both bugs here were the same shape: a token the contracts contain, the
    pattern cannot read, and nothing rejects -- because an unparsed token is
    absent, not refused. No count moves and no check fails, so the only way
    either was ever going to surface was a person happening to look.

    This looks. Every identifier-shaped token in `docs/` is surveyed with a
    pattern deliberately wider than the parsing one, and each is required to be
    either parsed whole or excluded by the one documented rule: its family is
    not a family any contract declares. A token that is neither -- PB-2a, or
    whatever the next widening turns out to be -- fails here first.
    """

    def survey(self) -> list[tuple[str, str]]:
        """(document, token) for every identifier-shaped token in the docs."""

        found = []
        for path in sorted((REPOSITORY_ROOT / "docs").rglob("*.md")):
            for token in tracer.CANDIDATE.findall(path.read_text(encoding="utf-8")):
                found.append((path.name, token))
        return found

    def test_the_survey_pattern_is_wider_than_the_parser(self) -> None:
        """Without this the property below is circular: a survey that can only
        see what the parser sees can only ever agree with it.

        Neither shape exists in the contracts today. That is the point -- these
        are the directions an identifier has already grown twice, and the
        survey has to be able to see the next one arrive.
        """

        for beyond in ("PB-100", "PB-2abc", "SECA-123"):
            with self.subTest(token=beyond):
                self.assertTrue(tracer.CANDIDATE.fullmatch(beyond), beyond)
                self.assertIsNone(tracer.INVARIANT.fullmatch(beyond), beyond)

    def test_the_survey_finds_the_identifiers_that_exist(self) -> None:
        """A survey matching nothing would pass the property vacuously."""

        tokens = {token for _, token in self.survey()}
        for known in ("AT-1", "SECA-11", "PO-A15", "S12", "PB-2a"):
            with self.subTest(token=known):
                self.assertIn(known, tokens)

    def test_the_foreign_exemption_does_not_blunt_the_guard(self) -> None:
        """A Sunshine identifier that cannot parse is still caught.

        The exemption is a pair, document and token, so it cannot spread to
        another document or to another token in the same one. Checked here
        rather than trusted, because an exemption that quietly widened would
        hide exactly the defect this class exists for.
        """

        for token in ("E100", "E999", "SEC100"):
            with self.subTest(token=token):
                self.assertEqual(set(), tracer._identifiers(token),
                                 "the premise: three digits is outside the parser")
        self.assertEqual(
            {("0024-drm-widevine.md", "E100")}, FOREIGN_IDENTIFIERS)
        self.assertNotIn(("0024-drm-widevine.md", "E999"), FOREIGN_IDENTIFIERS)

    def test_every_token_of_a_declared_family_parses_whole(self) -> None:
        """The guard against a third instance.

        Run against the pattern as it was before PB-2a, this fails and names
        PB-2a, PB-2b and PB-2c in PERFORMANCE_BUDGET.md and ACCEPTANCE_SUITES.md.
        """

        lost: list[str] = []
        for document, token in self.survey():
            if tracer._family(token) not in tracer.FAMILIES:
                continue  # the documented exclusion: not a family any contract uses
            if (document, token) in FOREIGN_IDENTIFIERS:
                continue
            if tracer._identifiers(token) != {token}:
                parsed = tracer._identifiers(token) or "nothing"
                lost.append(f"{document}: {token} parses as {parsed}")
        self.assertEqual(
            [],
            sorted(set(lost)),
            "a contract declares an identifier the pattern cannot read whole; "
            "an unparsed token is absent rather than rejected, so widen INVARIANT",
        )

    def test_the_excluded_tokens_are_excluded_by_family_alone(self) -> None:
        """The exclusion rule has to be one a reader can check, or the property
        above degrades into "whatever the pattern happens to skip"."""

        excluded = {
            token for _, token in self.survey() if tracer._family(token) not in tracer.FAMILIES
        }
        self.assertTrue(excluded)
        for token in excluded:
            with self.subTest(token=token):
                self.assertNotIn(tracer._family(token), tracer.FAMILIES)

    def test_widening_the_pattern_added_only_sub_lettered_identifiers(self) -> None:
        """Mission control for the widening itself: a big jump in the declared
        total would mean prose is now being read as invariants.

        The pattern as it stood before is restated here, as history rather than
        as a rule, and everything the new one gains over it must be a token that
        ends in a sub-letter. A future edit that makes `S8s` in some sentence
        parse as an invariant fails this and gets looked at.
        """

        previous = re.compile(r"\b([A-Z]{1,4}-?[A-Z]?\d{1,2})\b")
        gained = set()
        for path in sorted((REPOSITORY_ROOT / "docs").rglob("*.md")):
            text = path.read_text(encoding="utf-8")
            before = {
                token
                for token in previous.findall(text)
                if tracer._family(token) in tracer.FAMILIES
            }
            gained |= tracer._identifiers(text) - before
        self.assertTrue(gained, "the widening gained nothing; PB-2a should be in here")
        for token in sorted(gained):
            with self.subTest(token=token):
                self.assertRegex(token, r"^[A-Z]{1,4}-?[A-Z]?\d{1,2}[a-z]$")


class UnreadableClaimTests(unittest.TestCase):
    """The same gap closed from the claiming side.

    A check writing `Enforces: PB-2a` registered no claim and reported success.
    Nothing was wrong with the check; the tool could not read what it said. An
    unreadable claim is now a failure, so the next unparseable shape announces
    itself from whichever end it appears at first.
    """

    def setUp(self) -> None:
        directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, directory, True)
        self.root = Path(directory)
        for name in ("docs", "tests", "scripts", "config"):
            (self.root / name).mkdir()

    def write(self, relative: str, text: str) -> None:
        (self.root / relative).write_text(text, encoding="utf-8")

    def test_a_claim_the_pattern_cannot_parse_is_reported(self) -> None:
        """`PB-100` is a shape no contract uses yet, which is exactly why it is
        the right fixture: this is the third instance of the bug arriving, and
        it has to fail rather than count as nothing."""

        self.write("docs/C.md", "| PB-1 | The panel mounts once. |\n")
        self.write("tests/test_x.py", '"""Enforces: PB-100."""\n')
        _, failures = tracer.check(self.root)
        self.assertTrue(
            any("PB-100" in failure and "cannot parse" in failure for failure in failures),
            failures,
        )

    def test_a_sub_lettered_claim_now_registers(self) -> None:
        """Before the widening this produced no claim, no failure and no note
        of any kind -- the check simply did not appear in the coverage."""

        self.write("docs/C.md", "| PB-2a | Hidden-workspace tabs are background tabs. |\n")
        self.write("tests/test_x.py", '"""Enforces: PB-2a."""\n')
        report, failures = tracer.check(self.root)
        self.assertEqual([], failures)
        self.assertIn("PB-2a", tracer.claimed(self.root))
        self.assertIn("Claimed by a test or tool: 1", report)

    def test_a_claim_after_a_lowercase_word_is_still_read(self) -> None:
        """The capture used to stop at the first lowercase character, so an
        identifier written after any prose on the line was lost the same way."""

        self.write("docs/C.md", "| SEC-4 | x |\n| SECA-9 | y |\n")
        self.write("tests/test_x.py", '"""Enforces: SEC-4 and also SECA-9."""\n')
        self.assertEqual({"SEC-4", "SECA-9"}, set(tracer.claimed(self.root)))

    def test_an_acronym_in_a_claim_is_not_reported(self) -> None:
        """Enforces lines are prose as well as lists. Reporting every
        capitalised token in one would make the new rule unusable, so it is
        restricted to families a contract actually declares."""

        self.write("docs/C.md", "| SEC-4 | Modules are MV3-shaped. |\n")
        self.write("tests/test_x.py", '"""Enforces: SEC-4 for MV3 and AV1 modules."""\n')
        _, failures = tracer.check(self.root)
        self.assertEqual([], failures)

    def test_the_real_repository_has_no_unreadable_claims(self) -> None:
        self.assertEqual([], tracer.unparsed_claims(REPOSITORY_ROOT))


if __name__ == "__main__":
    unittest.main()
