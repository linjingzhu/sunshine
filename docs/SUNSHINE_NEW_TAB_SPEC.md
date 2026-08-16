# Sunshine New Tab — Stage 1 Specification

## Product contract

Sunshine OS remains a browser first. The New Tab surface is a fast path into ordinary browsing, not a Life OS dashboard.

## User-visible structure

1. `SUNSHINE` wordmark
2. Chromium New Tab search box
3. Chromium Most Visited shortcuts

The browser omnibox remains visible in browser chrome and continues to accept URLs and search terms.

## Behavior preserved from Chromium

- configured default search provider;
- search suggestions and keyboard behavior;
- Most Visited profile data and shortcut management;
- light, dark, and background-image theme compatibility;
- focus ring and accessibility semantics;
- lazy rendering and existing New Tab lifecycle.

## Explicit non-goals

- AI assistant or generated recommendations;
- notes, tasks, calendar, weather, or life metrics;
- 3D/WebGL presentation;
- remote dashboard content;
- a second history or frequent-sites database;
- hardcoded Google startup or search URL.

## UX contract

- Entry point: open a new tab.
- Primary action: enter a URL or search query.
- Visible result: Sunshine wordmark, search, and frequent sites.
- Empty state: search remains usable when no frequent sites exist.
- Keyboard: Chromium search and shortcut keyboard behavior remains intact.
- Accessibility: the wordmark is exposed as the page heading and has an explicit accessible name.

## Verification gate

This slice is not runtime-complete until the pinned Chromium revision accepts the patch, the native target compiles, and the New Tab is visually inspected at default size, narrow width, 200% zoom, light theme, and dark theme.
