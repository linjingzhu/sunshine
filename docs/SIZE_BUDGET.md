# Sunshine OS size budget

## Principle

Sunshine OS remains a complete browser. Size work must not remove sandboxing, site compatibility, security updates, accessibility, international text rendering, history, downloads, or the omnibox.

## Separate metrics

| Metric | Meaning | Initial gate |
|---|---|---:|
| Compressed download | Network transfer for the installer/archive | Measure; investigate above 150 MB |
| Installed app bundle | Application files after install | Measure; investigate above 250 MB |
| First-run profile | New user data before browsing | Measure and regress-test |
| Cache after use | Browsing data, media, and service caches | User-visible limit and cleanup policy required |

These are investigation thresholds, not promised release sizes. The first native
**Windows** release build establishes the baseline. This said macOS, which
contradicted `.ai/CORE.md` — Windows is the default build platform and a macOS
build is not performed unless the user asks — and `docs/PERFORMANCE_BUDGET.md`
depends on the two budgets sharing a reference platform, since a size and a
speed measured on different machines cannot be traded against each other.

## What is measured today, and what was not

**Two of the four metrics had no measurement at all until now, and one of them
had a threshold.** That is worth stating plainly, because a row reading
"investigate above 250 MB" beside no number reads as a budget being kept.

| Metric | Measured by | Latest |
| --- | --- | ---: |
| Compressed download | `scripts/build_chromium_windows.ps1`, since build #12 | **117.5 MB** (build #33, commit `ca1f5c0`) |
| Installed app bundle | `scripts/measure_shipped_size.py`, from build #34 | **not yet measured** |
| First-run profile | nothing | — |
| Cache after use | nothing | — |

**`chrome.exe` is not this number and never was.** The size report has recorded
it since build #12 — 4.1 MB at build #33 — and it is a launcher stub. The
browser is `chrome.dll`, and neither it nor the paks, the ICU data, the V8
snapshot, the ANGLE and SwiftShader libraries nor the locale files were counted
by anything.

**How the payload is now measured.** `chrome/installer/mini_installer/chrome.release`
is upstream's own manifest of what the installer packs, sectioned by build
configuration. `scripts/measure_shipped_size.py` reads it from the workspace,
resolves each entry against the build output, and sums what it finds. **No file
list is written into this repository**, because a copy of that manifest would be
a second list that drifts from what actually ships — and the reason to measure
at all is to stop believing a number that has drifted.

It measures the **payload the installer packs**, not the directory after setup
has run. Those differ: setup also writes the version directory layout and the
uninstall registration. The payload is the larger part and the part this budget
is about, and the difference is named here rather than left for whoever first
compares the two.

Item 5 of the release report — the five largest application files — falls out of
the same measurement, which reports the twelve largest and their share.

## Required release configuration

- `is_official_build=true`
- `is_debug=false`
- `is_component_build=false`
- `symbol_level=0` for distributable artifacts
- Debug symbols stored outside the user-facing application when crash diagnostics require them
- Installer/archive compression measured independently from installed size

## Product rules

- AI companion videos, additional character packs, offline models, and large templates are optional downloads.
- Downloaded packs are versioned and removable without uninstalling the browser.
- User cache is not counted as application binary size and must have a separate storage screen.
- Locales or codecs may be removed only after compatibility, licensing, accessibility, and target-market review.
- Security features must never be traded for size.

## Release report

Every macOS and Windows release candidate records:

1. compressed installer size;
2. installed application size;
3. clean-profile size;
4. 30-minute representative browsing cache growth;
5. the five largest application files;
6. change from the previous release.
