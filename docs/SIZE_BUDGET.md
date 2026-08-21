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
| Compressed download | `scripts/build_chromium_windows.ps1`, since build #12 | **117.6 MB** (build #37, commit `8c5f64b`) |
| Installed app bundle | `scripts/measure_shipped_size.py`, since build #37 | **419.5 MB** (build #37, commit `8c5f64b`) |
| First-run profile | nothing | — |
| Cache after use | nothing | — |

### The first measurement, and it is over the threshold

**419.5 MB across 255 files, against a row that says "investigate above
250 MB".** The threshold is met by a wide margin the first time anyone looks,
which is the outcome this section was written to make visible rather than the
one it hoped for. It is an investigation trigger, not a broken promise — no
release has been made and no size was ever promised — but the investigation is
now owed and is not started.

| Section of `chrome.release` | Size | Files |
| --- | ---: | ---: |
| GENERAL | 384.1 MB | 249 |
| DXC | 26.0 MB | 2 |
| GOOGLE_CHROME | 7.8 MB | 2 |
| HIDPI | 1.2 MB | 1 |
| SNAPSHOTBLOB | 0.4 MB | 1 |
| FFMPEG | — | no file of this section is in the build output |
| TOUCH | — | no file of this section is in the build output |

**One file is two thirds of it.** `chrome.dll` is 283.6 MB, 67.6% of the
payload. The next eleven together are less than half of that:

| File | Size | Share |
| --- | ---: | ---: |
| `chrome.dll` | 283.6 MB | 67.6% |
| `dxcompiler.dll` | 24.6 MB | 5.9% |
| `resources.pak` | 20.7 MB | 4.9% |
| `icudtl.dat` | 10.4 MB | 2.5% |
| `vk_swiftshader.dll` | 5.2 MB | 1.2% |
| `d3dcompiler_47.dll` | 4.5 MB | 1.1% |
| `elevated_tracing_service.exe` | 4.2 MB | 1.0% |
| `chrome.exe` | 4.1 MB | 1.0% |
| `elevation_service.exe` | 3.6 MB | 0.9% |
| `chrome_pwa_launcher.exe` | 3.0 MB | 0.7% |
| `notification_helper.exe` | 2.6 MB | 0.6% |
| `chrome_elf.dll` | 2.6 MB | 0.6% |

That distribution decides where a size investigation can and cannot go. Removing
every Sunshine-created surface, every locale, and every executable in the list
below `chrome.exe` would not move the number meaningfully, because the browser
*is* `chrome.dll`. Any real reduction is a build-configuration or a
feature-removal question about that one file, and `docs/BROWSER_OR_APP_REVIEW.md`
already recorded why the obvious removals are not free.

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
