# ADR 0001: Electron for the Wave 0 Chromium shell

## Status

Accepted for the first implementation spike.

## Decision

Use Electron as the initial Windows-first Chromium shell, with every runtime call kept behind main-process services and a narrow typed preload API.

## Reasons

- It provides a reproducible Chromium runtime suitable for validating the security and extension-compatibility gates.
- React browser chrome and TypeScript contracts can remain independent of the embedding layer.
- Electron is a starting runtime decision, not a promise of Chrome Web Store parity.

## Required safeguards

Remote content must use sandboxing, context isolation, disabled Node integration, sender/payload validation, default-deny permissions, and an explicit window-open/navigation policy.
