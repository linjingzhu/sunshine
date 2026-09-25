---
doc_id: ai-ux
version: 1.1.0
canonical_path: .ai/UX.md
updated: 2026-09-03
---

# UX and Runtime Verification

User-facing functionality is complete only when it is understandable, discoverable, and behaves as intended—not merely when it compiles.

## UX Contract

Before meaningful UI implementation, the Manager should define a compact UX Contract:

- Entry point
- Primary action
- Expected visible result
- Important states
- Disabled/blocked behavior
- Error feedback
- Recovery/undo
- Tooltip/help expectations
- First-use briefing when the feature is not self-explanatory

## Default product expectations

Consider:
- discoverability,
- terminology consistency,
- tooltip for non-obvious controls,
- contextual explanation,
- first-use/empty-state briefing,
- visible progress/success/failure state,
- actionable error messages,
- retry/undo/recovery,
- keyboard/accessibility behavior where relevant.

A tool should explain itself inside the product when reasonable. Do not rely on external documentation for basic discoverability.

## Runtime/visual gate

For UI changes that materially affect layout, workflow, state, or appearance:

```text
Implement
→ compile
→ run `runtime_gate` from `.ai/PROJECT_CONTEXT.md` § *Facts the checks read*
  (a headless-browser script, an emulator, a device — whatever observes *this* product)
→ navigate to feature
→ exercise key states
→ inspect actual appearance
→ compare with UX Contract/reference
→ fix unexpected result
```

Use screenshots/visual comparison when the environment supports it.

Do not mark a material UI change as fully verified if it was never observed at runtime.

Tiny text/tooltip-only changes may use a lighter gate if layout risk is negligible.

## Visual surprise is a defect signal

Track cases where:
- build passes,
- tests pass,
- but actual UI differs materially from intended behavior/appearance.

Reduce future visual-surprise latency by verifying similar UI work earlier.
