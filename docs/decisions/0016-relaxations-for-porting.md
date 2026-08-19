---
doc_id: adr-0016-relaxations-for-porting
version: 1.0.0
canonical_path: docs/decisions/0016-relaxations-for-porting.md
updated: 2026-08-19
---

# ADR 0016: Which rules bend so existing applications can be ported

## Status

**Accepted for the amendments in §3, which are implemented by this change.**
§4 records what was proposed and not accepted, and §5 what stays fixed.

## Context

Two finished applications are to become modules —
`docs/MARKETPICK_PORT_PLAN.md` and `docs/DEV_OS_PORT_PLAN.md` — and both plans
end in the same place: a list of capabilities Sunshine has withheld. The owner
read both and gave a boundary:

> Revise the rules that can realistically be compromised. Exclude vulnerability
> to the outside, and Chromium's inherent limits.

That is a usable boundary because it is a *test*, not a preference. Applied to
each blocking rule it gives one of three answers, and this ADR is the result of
applying it.

**What the boundary does not license.** "The port is hard" is not evidence that
a rule is wrong. Several rules below are hard *and* correct, and §5 says so. The
question this ADR asks of each rule is narrower: does it protect against the
outside, or against a limit of the platform — or is it only this project being
strict with itself?

## Decision

### 1. The test, stated once

For each rule that blocked a port:

| Question | If yes |
| --- | --- |
| Does relaxing it widen what an attacker outside the browser can reach? | **Keep.** Excluded by the owner's boundary. |
| Is it a limit of Chromium rather than a choice of ours? | **Keep.** There is nothing to revise; the limit is not ours to lift. |
| Is it neither — a caution this project chose, pending work nobody did? | **Revise**, and say what replaces it. |

### 2. What was actually blocking

Both ports hit the same short list. Classified:

| Rule | Blocked | Verdict |
| --- | --- | --- |
| `network.access: allowlist` refused by the validator | Marketpick's marketplace APIs; Dev OS's GitHub calls | **Revise** — §3.1 |
| `filesystem.access: user_selected` refused by the validator | Dev OS's session directory | **Revise** — §3.2 |
| SEC-7, a module never holds a credential | Both | **Keep** — §5 |
| No module-initiated process execution | Dev OS's terminal | **Decide, not revise** — §4.1 |
| Colour and type from Chromium's pipeline only | Both | **Revise in principle, not yet in code** — §4.2 |
| No markup assignment from module data | Dev OS's whole view layer | **Keep** — §5 |
| A module is compiled in, not loaded | Both | **Keep** — §5 |
| The shell owns A, B, C's frame and D's header | Both | **Keep** — §5 |

### 3. The amendments, accepted and implemented

Both were refused by `scripts/validate_first_party_modules.py` **pending a
contract**. Its own comment said so:

> `allowlist` and `user_selected` are expressible and currently refused. The
> schema has to carry the shape before a broker exists … refusing them keeps
> the guarantee that no module reaches the network or the disk in the meantime.

That is not a security position. It is a placeholder for work nobody had done,
and the owner's boundary says a placeholder is exactly what bends. **So the
contracts are written and the refusals lift.**

#### 3.1 Network — `docs/HOST_ALLOWLIST_CONTRACT.md`

A module may declare concrete hosts and have the **browser process** call them.
The page never fetches: SEC-14's prohibition on a web asset loading a remote
resource is untouched, because the asset still loads nothing. What changes is
that the browser, on the module's behalf, may.

The contract's load-bearing terms are HA-1 to HA-8; the ones that decide whether
this is safe are that hosts are concrete and wildcardless, that the page cannot
name a host at run time, that a response is data and never instruction, and
that **an allowlisted host is not an authenticated one** — SEC-7 is unchanged,
so until a credential broker exists these calls carry no secret.

#### 3.2 Filesystem — `docs/FILE_BROKER_CONTRACT.md`

A module may hold a scoped, expiring grant to what a **user picked**, and
reaches it through a handle rather than a path. FB-1 to FB-9; the decisive ones
are that the module never names a location, never receives a path string, and
cannot widen or outlive the grant. `DOC-3` and `DOC-8` survive intact — they
forbid Sunshine holding ambient authority over the disk, and a grant the user
made to one place, which expires, is not ambient.

Both amendments are enforced rather than asserted:
`scripts/validate_first_party_modules.py` now checks the contracts' checkable
terms instead of refusing the values outright, and
`tests/test_first_party_modules.py` injects each violation.

### 4. Proposed, not accepted here

#### 4.1 Module-initiated process execution

Dev OS discovers and runs sessions, which means opening a terminal. **No rule
forbids this, so no rule can be relaxed to allow it** — it is unspecified, and
unspecified is worse than forbidden because it has neither a price nor an owner.

It is out of scope here for a reason beyond scope: the shape matters more than
the permission. `run("<string>")` given to a module is not a relaxation, it is
the end of the sandbox — and Dev OS is the worst possible first holder of it,
because its views interpolate GitHub data and session output into markup, so an
injection there would become execution here.

The shape that could work is the one this project already chose for secrets:
**a module never receives a shell; it requests an operation from a fixed
vocabulary, and the broker constructs the invocation.** `resumeSession(id)`, not
a command. That deserves its own ADR, argued on its own terms, and this one does
not pre-empt it.

#### 4.2 Colour and type

`docs/DESIGN_SYSTEM_CONTRACT.md` §2.1 and §2.3 admit no colour that does not
resolve through Chromium's pipeline, and §6.2 admits no font size off a rem
scale. Both ported apps have their own palettes; the module shell already
records the conflict in `docs/MODULE_SHELL_CONTRACT.md` §7.

**This is inside the boundary** — it protects nothing from the outside and is
not Chromium's limit. It is house style, and house style is exactly what bends
for a port.

It is not amended here because the right relaxation is not "allow hex". The
value the rule protects is real and is not aesthetic: a palette that resolves
through the theme follows dark mode, high contrast and the user's own settings,
and a hardcoded one stops. The amendment worth making is therefore *a module may
declare its own tokens, provided they derive from the theme rather than replace
it* — which needs a design, a guard change, and a decision about what a module
may declare. Naming it here so it is not lost; it is the next amendment, not
this one.

### 5. What stays, and why the boundary keeps it

- **SEC-7, no module holds a credential.** Relaxing it means a token in a module
  whose content is authored elsewhere. That is precisely vulnerability to the
  outside. The answer is to build the broker ADR 0011 shapes, and building is
  not relaxing.
- **No markup assignment from module data.** Dev OS's strings interpolate
  GitHub data and session output. An injection from a remote service is the
  outside, and the unprivileged frame bounds the damage without removing it.
- **A module is compiled in, not loaded.** Loadable modules are a supply chain,
  and a supply chain is an outside. It would also not have helped either port:
  neither Python nor Node arrives because modules load.
- **The shell owns A, B, C's frame and D's header.** Not security at all — but
  relaxing it destroys the only thing it produces, which is that every module is
  operated the same way. A rule with one purpose that is defeated by any
  exception is not a rule that bends; it is one that breaks.
- **Chromium's own limits** — no Python in the build, no `chrome.send` under
  `ui::MojoWebUIController`, upstream's eslint, the `chrome://` scheme. Nothing
  here is ours to revise.

## Consequences

- Marketpick's Stage 2 and Dev OS's Stage 2 are unblocked as far as the
  manifest is concerned. Neither is unblocked in code: the browser-side fetch
  and the broker are unwritten, and §3 changes what may be *declared*, not what
  exists.
- Two contracts join the set that guards read, so a module claiming either
  capability now has terms to fail against rather than a blanket refusal.
- The refusals that lift were the last thing standing between a manifest and a
  claim it cannot back. That is a real loss of safety-by-impossibility, and it
  is replaced by safety-by-check — weaker in kind, which is why §3's terms are
  checkable and tested rather than described.

## NOT VERIFIED

- **Nothing in §3 is implemented in the browser.** The validator accepts the
  declarations; no code fetches a host or opens a file on a module's behalf,
  and no build has run.
- The contracts in §3 were written against Sunshine's own rules and the two
  port plans, not against a working implementation of either broker. Their
  terms are therefore reasoned, and the first implementation should expect to
  find at least one of them wrong.
- No module declares either capability yet, so the new validator paths are
  exercised only by tests.
