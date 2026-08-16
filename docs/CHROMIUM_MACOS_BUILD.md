# Native Chromium macOS test build

## Requirements

- A supported macOS and Xcode version from Chromium's current macOS build instructions
- `depot_tools` on `PATH`
- At least 100 GB of free local disk space; substantially more is recommended
- A fast local SSD and sufficient memory

## Build

```bash
git clone https://chromium.googlesource.com/chromium/tools/depot_tools.git
export PATH="$PWD/depot_tools:$PATH"
python3 scripts/bootstrap_chromium.py
cd chromium/src
gn gen out/Sunshine --args='is_official_build=true is_debug=false is_component_build=false is_chrome_branded=false symbol_level=0'
autoninja -C out/Sunshine chrome
open out/Sunshine/Chromium.app
```

## Expected first-run behavior

- Native Chromium tab strip and omnibox are always visible.
- A native New Tab Page opens; `https://www.google.com/` is not forced.
- Omnibox text searches with the configured default provider; URLs navigate directly.
- Back, forward, reload, history, downloads, and multiple tabs use Chromium's native implementations.

## Current limitation

The first migration patch changes product metadata. Product icons and the Sunshine New Tab WebUI belong to the next reviewed slices. Until those land, some open-source Chromium visual assets can remain visible.

## Measure size

```bash
du -sh out/Sunshine/Chromium.app
ditto -c -k --sequesterRsrc --keepParent out/Sunshine/Chromium.app Sunshine-OS-mac.zip
du -h Sunshine-OS-mac.zip
```

Record both installed bundle size and compressed download size; they are different product metrics.
