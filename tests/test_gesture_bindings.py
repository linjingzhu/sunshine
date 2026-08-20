"""Tests for the mouse-gesture guard.

Every rule here is checked by breaking the patch and asserting the guard
notices. A guard for a feature nobody can run yet is worth exactly as much as
its failures are real, and this project has twice shipped a check that passed
because it could no longer read its subject.

The fixture copies the parts of the tree the guard reads -- the patch stack, the
command registry, and the contract -- rather than the whole repository, and each
test mutates one of them.
"""

from pathlib import Path
import shutil
import sys
import tempfile
import unittest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))

import verify_gesture_bindings as guard  # noqa: E402

PATCH = "downstream/patches/0017-sunshine-mouse-gestures.patch"


class GuardTestCase(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, directory, True)
        self.root = Path(directory)
        for relative in ("downstream/patches", "first_party", "docs"):
            source = REPOSITORY_ROOT / relative
            shutil.copytree(source, self.root / relative)

    def patch_text(self) -> str:
        return (self.root / PATCH).read_text(encoding="utf-8")

    def rewrite(self, old: str, new: str) -> None:
        path = self.root / PATCH
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text, "the fixture no longer contains the anchor")
        path.write_text(text.replace(old, new, 1), encoding="utf-8")

    def failures(self) -> list[str]:
        return guard.check(self.root)

    def assertFailsWith(self, fragment: str) -> None:
        failures = self.failures()
        self.assertTrue(
            any(fragment in failure for failure in failures),
            f"expected a failure mentioning {fragment!r}, got {failures}",
        )


class CleanTreeTests(GuardTestCase):
    def test_the_repository_passes(self) -> None:
        self.assertEqual([], self.failures())


class BindingTests(GuardTestCase):
    def test_a_command_the_registry_does_not_know_is_rejected(self) -> None:
        """GESTURE invariant 6, which calls this a build failure rather than a
        special case."""

        self.rewrite('kBackCommand[] = "browser.back"',
                     'kBackCommand[] = "browser.reload_bypassing_cache"')
        self.assertFailsWith("first_party/commands.json does")

    def test_a_binding_the_contract_does_not_document_is_rejected(self) -> None:
        registry = self.root / "first_party/commands.json"
        registry.write_text(
            registry.read_text(encoding="utf-8").replace(
                '"id": "browser.back"', '"id": "browser.stop"', 1
            ),
            encoding="utf-8",
        )
        self.rewrite('kBackCommand[] = "browser.back"',
                     'kBackCommand[] = "browser.stop"')
        self.assertFailsWith("section 4 binds")


class NumberTests(GuardTestCase):
    def test_a_changed_activation_default_is_rejected(self) -> None:
        """Section 3.2 argues for 200 px at length, from a failure the owner
        actually hit. A patch that quietly used 32 again would undo that."""

        self.rewrite("kDefaultActivationDistance = 200;",
                     "kDefaultActivationDistance = 32;")
        self.assertFailsWith("kDefaultActivationDistance is 32")

    def test_a_changed_direction_ratio_is_rejected(self) -> None:
        self.rewrite("kDirectionRatio = 2;", "kDirectionRatio = 3;")
        self.assertFailsWith("kDirectionRatio is 3")

    def test_changed_bounds_are_rejected(self) -> None:
        self.rewrite("kMaximumActivationDistance = 600;",
                     "kMaximumActivationDistance = 900;")
        self.assertFailsWith("kMaximumActivationDistance is 900")


class SuppressionTests(GuardTestCase):
    def test_dropping_a_target_category_is_rejected(self) -> None:
        """Each row of section 3.1 is a way the feature can steal a menu the
        user wanted, so each is checked by name."""

        self.rewrite("params.is_editable || ", "")
        self.assertFailsWith("an editable field")

    def test_dropping_the_selection_check_is_rejected(self) -> None:
        self.rewrite("!params.selection_text.empty() ||", "false ||")
        self.assertFailsWith("a selection")


class ReachTests(GuardTestCase):
    def test_the_recogniser_may_not_navigate(self) -> None:
        """Invariant 5. The recogniser resolves a name; it never steers a tab."""

        # Appended to an existing line rather than added as a new one: the
        # fixture is a diff, and a line inserted without touching the hunk
        # header makes the replay unreadable rather than wrong.
        self.rewrite("void MouseGesture::Reset() {",
                     "void MouseGesture::Reset() {  // GoForward")
        self.assertFailsWith("GESTURE invariant 5")

    def test_the_recogniser_may_not_know_a_command_identifier(self) -> None:
        self.rewrite("void MouseGesture::Reset() {",
                     "void MouseGesture::Reset() {  // IDC_BACK")
        self.assertFailsWith("GESTURE invariant 5")

    def test_a_dependency_on_browser_ui_is_rejected(self) -> None:
        self.rewrite('    "//components/prefs",',
                     '    "//chrome/browser/ui",\n    "//components/prefs",')
        self.assertFailsWith("A target that can see")


class ObservationTests(GuardTestCase):
    def test_the_consuming_hook_is_refused_by_name(self) -> None:
        """Chromium offers a mouse hook whose callback returns bool. It is the
        obvious way to suppress a context menu and the contract forbids it, so
        reaching for it later has to fail rather than pass quietly."""

        self.rewrite("void MouseGesture::Reset() {",
                     "void MouseGesture::Reset() {  // AddMouseEventCallback")
        self.assertFailsWith("can swallow an event")

    def test_an_event_entry_point_that_returns_a_verdict_is_rejected(self) -> None:
        self.rewrite("void MouseGesture::OnMouseEvent(",
                     "bool MouseGesture::OnMouseEvent(")
        self.assertFailsWith("must return void")


class AvailabilityTests(GuardTestCase):
    def test_dispatching_without_asking_the_command_layer_is_rejected(self) -> None:
        """Invariant 7, and the DCHECK inside the command controller that GA-13
        would otherwise walk into at the first entry of session history."""

        self.rewrite("chrome::IsCommandEnabled(this, command)", "true")
        self.assertFailsWith("GESTURE invariant 7")


if __name__ == "__main__":
    unittest.main()
