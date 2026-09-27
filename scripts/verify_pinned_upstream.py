#!/usr/bin/env python3
"""Check that the pinned Chromium revision still supports the patch stack.

Everything here needs the upstream sources, so it cannot run from the patch
files alone. Four questions are asked of the pinned revision:

1. the ordered patch stack applies to it,
2. the native integration seams the workspace design depends on still exist,
3. the New Tab tokens the wordmark consumes without a fallback still exist,
4. every upstream source path the contracts cite is really there.

Each token is checked against the source that defines it. `--ntp-theme-text-shadow`
is a plain custom property declared in `app.css`. `--color-new-tab-page-*` tokens
are not declared in any stylesheet: Chromium emits them from the colour IDs in
`chrome_color_id.h` and serves them through `chrome://theme`, so absence from
`app.css` is not absence. Grepping the stylesheet for both -- which this check
first did, in bash, inside the workflow -- fails the build on a token that
exists. That is why this lives in one tested place instead of two untested ones.

`--source github` reads the same revision from the GitHub mirror. It is a
convenience for environments whose egress policy blocks the authoritative host,
not a second source of truth: CI runs the default.

Both hosts meter anonymous clients by request count, and this checker asks a lot
of questions -- so how many it asks is part of what it is. Existence is settled
per directory rather than per path wherever the source can list one; see
`directory_entries`.
"""

from __future__ import annotations

import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import subprocess
import sys
import time
import tempfile
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import patch_manifest  # noqa: E402
import verify_asset_overlay  # noqa: E402

SOURCES = {
    "googlesource": (
        "https://chromium.googlesource.com/chromium/src/+/refs/tags/{version}/{path}?format=TEXT",
        True,
    ),
    "github": (
        "https://raw.githubusercontent.com/chromium/chromium/{version}/{path}",
        False,
    ),
}

# path -> ((description, needle), ...). A needle is matched against the file as
# a whole; SECTION_SEAMS below covers the cases where position matters.
SEAMS: dict[str, tuple[tuple[str, str], ...]] = {
    "chrome/browser/ui/tabs/tab_strip_model.h": (("TabStripModel", "class TabStripModel"),),
    "chrome/browser/ui/tabs/tab_group_model.h": (("TabGroupModel", "class TabGroupModel"),),
    "chrome/browser/ui/tabs/tab_strip_model_observer.h": (
        ("tab strip change notification", "OnTabStripModelChanged"),
    ),
    "components/sessions/core/session_service_commands.cc": (
        ("tab extra-data command", "CreateAddTabExtraDataCommand"),
        ("window extra-data command", "CreateAddWindowExtraDataCommand"),
    ),
}

# Workspace state rides on these fields specifically, so finding `extra_data`
# anywhere in the file would not be evidence.
SECTION_SEAMS: tuple[tuple[str, str, str, str], ...] = (
    (
        "components/sessions/core/session_types.h",
        "SessionTab.extra_data",
        "struct SESSIONS_EXPORT SessionTab {",
        "extra_data",
    ),
    (
        "components/sessions/core/session_types.h",
        "SessionWindow.extra_data",
        "struct SESSIONS_EXPORT SessionWindow {",
        "extra_data",
    ),
)

TOKENS: tuple[tuple[str, str, str, str], ...] = (
    (
        "chrome/browser/resources/new_tab_page/app.css",
        "--ntp-theme-text-shadow",
        "--ntp-theme-text-shadow:",
        "app.css no longer declares the shadow token",
    ),
    (
        "chrome/browser/ui/color/chrome_color_id.h",
        "--color-new-tab-page-primary-foreground",
        "kColorNewTabPagePrimaryForeground",
        "the colour ID that emits the wordmark's colour is gone",
    ),
)


# Sunshine's own top-level directories, plus the two tree roots that belong to
# neither repository. Everything else that has the shape of a file path is
# treated as an upstream citation and probed.
#
# This list is the inversion that matters. The previous rule named the Chromium
# top-level directories it would accept, and that list was already wrong:
# `media/` twice and `sandbox/` once had never been checked by anything, because
# an unmatched citation is absent, not rejected -- no probe, no failure, no
# mention. Naming *our own* directories instead fails the other way. A new
# Chromium top-level directory is covered the moment it is cited, and the only
# way this list can go stale is a new directory in this repository, which
# tests/test_verify_pinned_upstream.py compares against what is on disk.
#
# `src/` and `out/` are the exceptions that are neither. `src/third_party/...`
# is an upstream path written from one level above the checkout root, and
# `out/Sunshine` is build output that exists only after a build; probing either
# upstream asks for a path that was never meant to be there.
OWN_PREFIXES = frozenset({
    ".ai", ".git", ".github", "config", "docs", "downstream", "first_party",
    "installer", "scripts", "tests",
    # The agent capability directories the portable policy set ships: skills and
    # subagent definitions for Claude and Codex. Ours, and named after tools
    # rather than after this project, which is exactly why they have to be
    # listed -- a citation of `.claude/skills/auto-dev/SKILL.md` probed upstream
    # would 404 and be reported as a contract citing a file Chromium deleted.
    ".agents", ".claude", ".codex",
    # Ours, but present only after a build, so absent from a fresh clone and
    # from this list until the first CI run on the build machine failed for
    # exactly that reason. `artifacts/` holds the installer and size report the
    # build script writes; `chromium/` and `depot_tools/` are the checkout a
    # developer may keep in-tree. All are gitignored, which is why the test
    # that keeps this list honest reads what git tracks rather than what
    # happens to be on the disk of the machine running it.
    "artifacts", "chromium", "depot_tools",
    "out", "src",
    # The owner's source artwork, from which `downstream/assets/` is rendered.
    # Ours despite the generic name, and a citation of `resource/icon.png` is a
    # citation of this repository -- probing it upstream would 404 and be
    # reported as a contract citing a file Chromium deleted.
    "resource",
})

# A backticked path naming one concrete file: at least two segments, ordinary
# path characters throughout, and a suffix that starts with a letter.
#
# Every clause is doing work that the survey of docs/ asked for. The backticks
# anchor both ends, so a token is matched whole or not at all -- `chrome://…`
# cannot contribute a `chrome` prefix. Segments must begin with a letter, digit
# or underscore, which rejects the directory-with-trailing-slash citations
# (`components/sessions/`, `google_apis/`) and the ellipsis ones (`tools/...`).
# The character class excludes the space, brace, star and angle bracket that
# mark the citations that stand for more than one file (`tab_strip_model.{h,cc}`,
# `session_restore.*`, `metadata/<area>/histograms.xml`) as well as the prose
# that merely contains a slash (`max / min = 1.75`, `text/plain`). Requiring the
# suffix to start with a letter is what separates a file from a version or a
# ratio: `refs/tags/152.0.7977.42` and `13.5/7.25` are neither files nor
# upstream.
#
# What this cannot express is an upstream file with no extension -- `chrome/
# VERSION` would go unchecked. None is cited today, and admitting extensionless
# tokens would sweep in every directory reference in the contract set.
CITATION = re.compile(
    r"`([A-Za-z0-9_][A-Za-z0-9_.+-]*(?:/[A-Za-z0-9_][A-Za-z0-9_.+-]*)+\.[A-Za-z][A-Za-z0-9]{0,7})`"
)


class UpstreamCheckError(RuntimeError):
    pass


def pinned_version(root: Path = ROOT) -> str:
    for line in (root / "config/chromium.version").read_text(encoding="utf-8").splitlines():
        if line.startswith("CHROMIUM_REVISION="):
            return line.split("=", 1)[1].strip().removeprefix("refs/tags/")
    raise UpstreamCheckError("config/chromium.version has no CHROMIUM_REVISION")


# Codes that mean "the file is not there". Everything else -- 429, 5xx, a
# timeout -- means the answer is unknown, which is a different thing and must
# never be reported as an absent path. See `exists`.
ABSENT_STATUS = frozenset({404, 410})
RETRIES = 4
BACKOFF_SECONDS = 3

# A quota answer is not a burst answer, and the two need different patience.
#
# Both hosts meter anonymous clients over a window rather than instantaneously:
# googlesource says so in as many words -- `RESOURCE_EXHAUSTED subject:
# "shared/shared_anonymous"`, "short term server-time rate limit exceeded". The
# ordinary backoff spends 45 seconds and gives up, which is shorter than the
# window, so a run that meets the limit fails even though waiting would have
# answered. Six attempts capped at 60 seconds spends about four minutes, inside
# the job's twenty-minute budget.
#
# This buys patience, not permission: a 429 that outlasts the budget is still a
# failure and still never an absent path. The durable fix is authenticating to
# googlesource, which leaves the shared anonymous pool entirely -- the same
# conclusion `scripts/bootstrap_chromium.py` reached for gclient, and it needs a
# credential on the build machine rather than a change here.
THROTTLED_STATUS = frozenset({429, 503})
THROTTLED_RETRIES = 6
THROTTLED_BACKOFF_SECONDS = 10


def _open(request: urllib.request.Request | str, path: str, version: str):
    """Open a URL, retrying the answers that mean "not now" rather than "no".

    GitHub rate-limits this account: an ordinary run of this checker probes two
    hundred paths, and raw.githubusercontent.com starts returning 429 partway
    through. Without the retry the checker reported eleven contract citations as
    missing upstream paths in a run whose previous run had passed, and every one
    of them existed.
    """

    last: Exception | None = None
    attempt = 0
    budget = RETRIES
    while attempt < budget:
        try:
            return urllib.request.urlopen(request, timeout=60)
        except urllib.error.HTTPError as error:
            if error.code in ABSENT_STATUS:
                raise
            last = error
            if error.code in THROTTLED_STATUS:
                budget = max(budget, THROTTLED_RETRIES)
                base = THROTTLED_BACKOFF_SECONDS
            else:
                base = BACKOFF_SECONDS
            delay = error.headers.get("Retry-After") if error.headers else None
            wait = int(delay) if delay and delay.isdigit() else base * (2**attempt)
        except urllib.error.URLError as error:
            last = error
            wait = BACKOFF_SECONDS * (2**attempt)
        except TimeoutError as error:
            last = error
            wait = BACKOFF_SECONDS * (2**attempt)
        attempt += 1
        if attempt < budget:
            time.sleep(min(wait, 60))
    raise UpstreamCheckError(f"could not reach {path} at {version} after {attempt} attempts: {last}")


def fetch(source: str, version: str, path: str) -> str:
    template, encoded = SOURCES[source]
    url = template.format(version=version, path=path)
    try:
        with _open(url, path, version) as response:
            payload = response.read()
    except urllib.error.HTTPError as error:
        raise UpstreamCheckError(f"could not read {path} at {version}: {error}") from error
    if encoded:
        payload = base64.b64decode(payload)
    return payload.decode("utf-8", errors="replace")


def section(text: str, opening: str) -> str:
    """The struct body starting at `opening`, up to the closing brace."""

    start = text.find(opening)
    if start == -1:
        return ""
    end = text.find("\n};", start)
    return text[start : end if end != -1 else len(text)]


def stack_created_paths(root: Path) -> set[str]:
    """Paths inside Chromium's tree that the patch stack creates.

    These live under `chrome/`, `components/` and the like, so nothing about
    their spelling distinguishes them from upstream ones -- but Chromium does
    not have them and must not. `scripts/patch_manifest.py` already refuses to
    let a created path also be an upstream target, so this set and the set of
    paths that must exist upstream cannot overlap.
    """

    # A root with no patch directory has no stack, so nothing is created. This
    # is not defensive padding: `check_citations` is called on fixture roots
    # that hold only `docs/`, and a citation check that needs a patch series to
    # run would be coupled to something it does not check.
    if not (root / "downstream/patches/series").is_file():
        return set()

    created: set[str] = set()
    for entry in patch_manifest.read_manifest(root):
        text = (root / "downstream/patches" / entry).read_text(encoding="utf-8")
        created.update(
            target for target, creates in patch_manifest.patch_sections(text) if creates
        )
    return created


def cited_paths(root: Path) -> dict[str, set[str]]:
    """Upstream source paths the contracts cite, mapped to the docs citing them."""

    citations: dict[str, set[str]] = {}
    for document in sorted((root / "docs").rglob("*.md")):
        for path in CITATION.findall(document.read_text(encoding="utf-8")):
            if path.split("/", 1)[0] in OWN_PREFIXES:
                continue
            citations.setdefault(path, set()).add(document.name)
    return citations


# Whether a path exists is a question about a directory, not about a file, and
# a directory answers it once for everything in it. The citation check asks it
# of ~215 paths that sit in ~99 directories, so asking the directory is less
# than half the requests, and the ratio improves every time a contract cites
# another file beside one already cited.
#
# This is not a speed optimisation. The guard failed CI at 900d747 with
# `HTTP Error 429` from googlesource -- not the mirror, which was the throttled
# one before. The quota is on request count from one anonymous client, so
# backoff cannot help: `scripts/bootstrap_chromium.py` documents the same host
# answering RESOURCE_EXHAUSTED for `shared/shared_anonymous` and bounds
# gclient's job count for the same reason. Fewer questions is the only fix.
#
# googlesource only. raw.githubusercontent.com serves file bytes and has no
# listing route; the GitHub API that does is a different host with a 60-request
# anonymous hourly quota, which is worse than what it would replace. The mirror
# keeps the per-path probe, so the saving lands on the source CI actually uses
# rather than on the fallback one.
LISTING = {
    "googlesource":
        "https://chromium.googlesource.com/chromium/src/+/refs/tags/{version}/{path}?format=JSON",
}

# Gitiles prefixes its JSON with an XSSI guard that is deliberately not valid
# JSON, so it has to come off before parsing.
XSSI_PREFIX = ")]}'"


def directory_entries(source: str, version: str, directory: str) -> set[str] | None:
    """The names in one upstream directory, or None if it could not be listed.

    None means "ask another way". It never means "not there". A listing that
    404s, that comes back as HTML because the route moved, or that parses to
    something with no entries in it sends the caller back to probing each path
    on its own -- which costs requests only when something is already wrong,
    and is the only reading that is safe: treating an unreadable listing as an
    empty directory would accuse every contract citing it of naming a dead path,
    which is the false accusation this checker has already made once.

    A throttled listing is deliberately not caught. `_open` retries and then
    raises, and that must stop the run: falling back to individual probes while
    the host is refusing requests would turn one refusal into as many requests
    as the directory has citations.
    """

    template = LISTING.get(source)
    if template is None:
        return None
    url = template.format(version=version, path=directory)
    try:
        with _open(url, directory, version) as response:
            payload = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as error:
        if error.code in ABSENT_STATUS:
            return None
        raise UpstreamCheckError(f"could not list {directory} at {version}: {error}") from error

    if payload.startswith(XSSI_PREFIX):
        payload = payload[len(XSSI_PREFIX):]
    try:
        entries = json.loads(payload)["entries"]
        names = {entry["name"] for entry in entries}
    except (ValueError, KeyError, TypeError):
        return None
    # An empty directory does not exist in git, so an empty listing is a
    # malformed answer rather than a directory with nothing in it.
    return names or None


def exists(source: str, version: str, path: str) -> bool:
    template, encoded = SOURCES[source]
    url = template.format(version=version, path=path)
    if encoded:
        # googlesource has no HEAD for this route; the smallest existence probe
        # is the ordinary page rather than the base64 payload.
        url = url.removesuffix("?format=TEXT")
    request = urllib.request.Request(url, method="GET" if encoded else "HEAD")
    try:
        with _open(request, path, version) as response:
            return response.status == 200
    except urllib.error.HTTPError as error:
        # Only 404 and 410 reach here; `_open` retries everything else and then
        # raises UpstreamCheckError, so a throttled probe stops the run with an
        # honest reason instead of accusing a contract of citing a dead path.
        if error.code in ABSENT_STATUS:
            return False
        raise UpstreamCheckError(f"could not probe {path}: {error}") from error


def check_citations(source: str, version: str, root: Path, report: list[str]) -> bool:
    """Every upstream path a contract cites must exist at the pinned revision.

    Contracts are only as good as the sources they name, and this surface moves:
    the omnibox edit model and view left components/omnibox/browser/ for
    chrome/browser/ui/omnibox/, and the child-process security policy is a
    public header rather than the impl one that is usually quoted. A path cited
    from memory reads as evidence while pointing at nothing.
    """

    citations = cited_paths(root)

    # A path the stack creates is a Sunshine file that happens to live in
    # Chromium's tree, and asking whether Chromium has it is asking the wrong
    # question -- the correct answer upstream is "absent", which this check
    # would report as a failure. It is not skipped silently: the count is in
    # the report, so a citation that quietly stopped being checked is visible.
    #
    # This appeared the first time a contract cited such a file --
    # `chrome/common/sunshine/sunshine_webui_hosts.h`, cited by
    # OMNIBOX_CONTRACT.md for the host constants the module home added. Until
    # then every cited path really was upstream and the distinction had never
    # come up.
    created = stack_created_paths(root) & set(citations)
    for path in sorted(created):
        del citations[path]
    if created:
        report.append(
            f"  OK   {len(created)} cited path(s) are created by the patch stack, "
            "so upstream is not asked for them"
        )

    if not citations:
        report.append("  OK   no upstream paths cited by the contracts")
        return True

    directories: dict[str, list[str]] = {}
    for path in citations:
        directories.setdefault(path.rsplit("/", 1)[0], []).append(path)
    ordered = sorted(directories)

    # Four, not twelve. Two hundred probes at twelve concurrent requests was
    # enough to make the host rate-limit this account partway through the run,
    # so the parallelism that made the check fast was also what made it fail.
    # The bound stays where it is: it is now applied to far fewer requests.
    with ThreadPoolExecutor(max_workers=4) as pool:
        listings = dict(zip(ordered, pool.map(
            lambda directory: directory_entries(source, version, directory), ordered)))

    found: dict[str, bool] = {}
    unlisted: list[str] = []
    listed = 0
    for directory in ordered:
        names = listings[directory]
        if names is None:
            unlisted.extend(directories[directory])
            continue
        listed += 1
        for path in directories[directory]:
            found[path] = path.rsplit("/", 1)[1] in names

    if unlisted:
        with ThreadPoolExecutor(max_workers=4) as pool:
            found.update(zip(unlisted, pool.map(
                lambda path: exists(source, version, path), unlisted)))

    dead = sorted(path for path, present in found.items() if not present)
    for path in dead:
        report.append(f"  FAIL cited path absent at {version}: {path}")
        report.append(f"       cited by {', '.join(sorted(citations[path]))}")
    if not dead:
        # The request count is reported because it is the thing that broke CI.
        # A run that says "0 directory listings, 215 individual probes" has
        # fallen back for every directory and is one quota away from failing
        # again, and that has to be visible in the log rather than inferred
        # from how long the step took.
        report.append(
            f"  OK   {len(citations)} cited upstream paths all exist "
            f"({listed} directory listing(s), {len(unlisted)} individual probe(s))"
        )
    return not dead


def check_asset_overlay(source: str, version: str, root: Path, report: list[str]) -> bool:
    """Overlay destinations, asked of upstream in whichever direction applies.

    The overlay carries whole binary files by path -- see
    `docs/decisions/0008-binary-asset-overlay.md` -- and a whole-file copy
    cannot fail the way a patch does. `git apply` rejects a hunk whose context
    moved; `shutil.copyfile` is happy to write anywhere. So the probe is the
    only thing standing between a moved upstream file and a build that reports
    success while shipping the wrong bytes, and there are two ways to get it
    wrong:

    * a **replacement** must still exist. If upstream renames `chromium.ico`,
      the copy lands beside the real icon, the `.rc` still names Chromium's,
      and the build ships Chromium's icon under Sunshine's name.
    * an **addition** must not exist. An added image is new by construction --
      a patch introduces the `.grd` entry that reads it -- so upstream having
      a file of that name means the copy is quietly replacing a real Chromium
      resource, and the patch's entry may now be reading upstream's drawing.

    Which is which is declared in `scripts/verify_asset_overlay.py`, not
    inferred from the answer; inferring it would make a mistyped destination
    into an addition and skip the very check that catches it.

    It is an existence probe, not a comparison. Upstream's own artwork is
    expected to differ -- replacing it is the point.
    """

    base = root / "downstream/assets"
    destinations = sorted(
        path.relative_to(base).as_posix() for path in base.rglob("*") if path.is_file()
    ) if base.is_dir() else []
    if not destinations:
        return True

    additions = verify_asset_overlay.ADDITIONS
    healthy = True
    for destination in destinations:
        present = exists(source, version, destination)
        if destination in additions:
            if present:
                report.append(
                    f"  FAIL overlay addition already exists upstream: {destination}")
                healthy = False
            else:
                report.append(f"  OK   overlay addition is new upstream: {destination}")
        elif present:
            report.append(f"  OK   overlay destination: {destination}")
        else:
            report.append(f"  FAIL overlay destination absent upstream: {destination}")
            healthy = False
    return healthy


def check_patch_stack(source: str, version: str, root: Path, report: list[str]) -> bool:
    entries = subprocess.run(
        [sys.executable, str(root / "scripts/patch_manifest.py"), "--paths"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    if not entries:
        raise UpstreamCheckError("patch manifest returned no upstream targets")

    series = [
        line.strip()
        for line in (root / "downstream/patches/series").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]

    with tempfile.TemporaryDirectory() as directory:
        worktree = Path(directory)
        for path in entries:
            target = worktree / path
            target.parent.mkdir(parents=True, exist_ok=True)
            # `write_bytes`, never `write_text`. Text mode translates "\n" to
            # the platform line ending, so on Windows every fetched upstream
            # file was written with CRLF while the patches carry LF context --
            # and all three patches failed to apply on the build runner while
            # applying cleanly on Linux. The patch stack was fine; the harness
            # was corrupting its own inputs.
            target.write_bytes(fetch(source, version, path).encode("utf-8"))

        # `core.autocrlf=false` for the same reason, one layer down: on Windows
        # git's default would normalise on add and convert back on checkout,
        # reintroducing the mismatch this temp tree exists to avoid.
        git = ["git", "-C", str(worktree), "-c", "core.autocrlf=false", "-c", "core.eol=lf"]
        subprocess.run([*git, "init", "--quiet"], check=True)
        subprocess.run([*git, "add", "."], check=True)
        subprocess.run(
            [*git, "-c", "user.name=check", "-c", "user.email=check@localhost",
             "commit", "--quiet", "-m", "upstream-inputs"],
            check=True,
        )

        healthy = True
        for entry in series:
            patch = root / "downstream/patches" / entry
            applied = subprocess.run([*git, "apply", str(patch)], capture_output=True, text=True)
            if applied.returncode == 0:
                report.append(f"  OK   patch applies: {entry}")
            else:
                report.append(f"  FAIL patch does not apply: {entry}: {applied.stderr.strip()}")
                healthy = False
        return healthy


def verify(source: str = "googlesource", root: Path = ROOT) -> tuple[bool, list[str]]:
    version = pinned_version(root)
    report = [f"Pinned Chromium {version} via {source}"]
    healthy = True

    for path, expectations in sorted(SEAMS.items()):
        text = fetch(source, version, path)
        for description, needle in expectations:
            if needle in text:
                report.append(f"  OK   seam: {description}")
            else:
                report.append(f"  FAIL seam absent upstream: {description} ({needle})")
                healthy = False

    # Both section seams live in the same header, and fetching it once per
    # expectation asked upstream the same question twice. Cheap, but this
    # checker is now failing CI on request count, so a free request is worth
    # not spending.
    bodies = {path: fetch(source, version, path) for path in sorted({s[0] for s in SECTION_SEAMS})}
    for path, description, opening, needle in SECTION_SEAMS:
        body = section(bodies[path], opening)
        if needle in body:
            report.append(f"  OK   seam: {description}")
        else:
            report.append(f"  FAIL seam absent upstream: {description}")
            healthy = False

    for path, token, needle, explanation in TOKENS:
        if needle in fetch(source, version, path):
            report.append(f"  OK   token: {token}")
        else:
            report.append(f"  FAIL token: {token} -- {explanation}")
            report.append(f"       checked for {needle!r} in {path}")
            healthy = False

    healthy = check_citations(source, version, root, report) and healthy
    healthy = check_asset_overlay(source, version, root, report) and healthy
    healthy = check_patch_stack(source, version, root, report) and healthy
    return healthy, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        choices=sorted(SOURCES),
        default="googlesource",
        help="where to read the pinned revision; the default is authoritative",
    )
    arguments = parser.parse_args()

    try:
        healthy, report = verify(arguments.source)
    except UpstreamCheckError as error:
        print(f"Pinned upstream check failed: {error}", file=sys.stderr)
        return 1

    print("\n".join(report))
    if not healthy:
        print("Pinned upstream no longer satisfies the patch stack.", file=sys.stderr)
        return 1
    print("Pinned upstream check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
