---
doc_id: adr-0025-home-button-by-default
version: 1.0.0
canonical_path: docs/decisions/0025-home-button-by-default.md
updated: 2026-09-13
---

# ADR 0025: The home button is on by default

## Status

**Accepted, and implemented by `downstream/patches/0030-sunshine-home-button-by-default.patch`.**
Read against the pinned revision `152.0.7977.42`. It is not compiled here; §5
says what that leaves open.

## Context

The owner asked for a home button **on the left of the title bar**. Two things
were true and they pointed at different work, so the question was put back
rather than guessed at.

**Upstream already has a home button, and it is not in the title bar.**
`chrome/browser/ui/views/toolbar/toolbar_view.cc` constructs `HomeButton` into
the toolbar row, bound to `IDC_HOME`, and shows it from `prefs::kShowHomeButton`.
`chrome/browser/ui/browser_ui_prefs.cc` registers that pref:

```cpp
registry->RegisterBooleanPref(prefs::kShowHomeButton, false,
                              pref_registration_flags);
```

So the button exists, is wired, is keyboard-reachable and is accessible — and
nobody who has not been through Settings has ever seen it.

**The title bar has no such button and would need a new one.** The tab strip
region is not a toolbar; a button there is a new view, a new icon and new
command wiring, on the scale of patch 0027's split-swap affordance.

The owner chose the toolbar.

## Decision

**Change the registered default of `prefs::kShowHomeButton` from `false` to
`true`.** One token, in one upstream file, exactly the shape of ADR 0022.

### Why the default and not an override

The same reason as ADR 0022, arrived at the same way: a `SetDefaultPrefValue()`
from Sunshine's own registration is a call that has to happen *after* the pref
exists, and every such arrangement is a new ordering constraint that fails as a
CHECK rather than as a compile error. Moving the registered default has no
ordering at all.

### What is deliberately not decided here

**The home target.** `prefs::kHomePageIsNewTabPage` is registered `true` on the
line immediately above and this patch does not touch it, so the button opens the
New Tab page — which is Sunshine's own surface, with its own wordmark, search
field and background. Had the patch set a home *URL*, it would have been
choosing a destination for the owner. It does not, and the pref the owner would
change to pick one is untouched.

**The title bar.** Not built, and not refused — deferred. If the owner still
wants a button at the tab strip's leading edge after using this one, that is a
separate ADR and a separate patch, and this one does not make it harder.

## Consequences

- Patch **0030**, one upstream file. The stack is 30 patches, 33 upstream files
  exclusively owned.
- **A new profile shows the button; an existing profile may not.** The pref is
  `SYNCABLE_PREF`, so a profile that has ever written a value keeps it. This is
  the same trap as ADR 0022 and RV-48, and RV-59 says so rather than leaving the
  next reader to rediscover it.
- The toolbar gains a control, so everything to the right of it shifts. Nothing
  else in the stack positions itself against the toolbar's contents.
- **The user can still turn it off.** Settings → Appearance → Show home button
  writes the same pref. A default that could not be reversed would be a
  different and worse decision.

## 5. NOT VERIFIED

- That the button appears — **RV-59**, on a fresh profile.
- That it opens the New Tab page rather than a blank page or a URL from
  somewhere else — **RV-60**. `kHomePageIsNewTabPage` is read, not observed.
- That the Settings toggle still reverses it — **RV-61**. The whole argument for
  moving only the default is that upstream's switch survives, and that claim is
  worth one line of checking rather than assertion.
