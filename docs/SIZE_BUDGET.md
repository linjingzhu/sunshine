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

These are investigation thresholds, not promised release sizes. The first native macOS release build establishes the baseline.

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
