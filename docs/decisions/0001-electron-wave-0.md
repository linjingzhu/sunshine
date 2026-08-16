# ADR 0001: Electron for the Wave 0 Chromium shell

## Status

Superseded by ADR 0002. This decision contradicted the explicit instruction to remove Electron and must not be used as an implementation precedent.

## Decision

The first implementation spike used Electron as a Windows-first Chromium wrapper. All code produced by that spike has been removed from the active architecture.

## Reasons

- It provides a reproducible Chromium runtime suitable for validating the security and extension-compatibility gates.
- React browser chrome and TypeScript contracts can remain independent of the embedding layer.
- Electron is a starting runtime decision, not a promise of Chrome Web Store parity.

## Historical safeguards

Remote content must use sandboxing, context isolation, disabled Node integration, sender/payload validation, default-deny permissions, and an explicit window-open/navigation policy.

These safeguards remain useful history, but native Chromium now supplies the browser process model and renderer sandbox.
