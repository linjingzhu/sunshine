# ADR 0006: What a Sunshine module is allowed to be

## Status

**Accepted — Position A.** A Sunshine module stays a compiled capability. The
module architecture brief's security rules were adopted and are enforced; its
runtime, SDK, bundle format and lifecycle manager are not built.

Position B is not rejected on its merits. It is deferred to a point where it can
be judged on them — see *Revisiting* below.

## Context

A module architecture brief proposed redefining a Sunshine module as:

```text
Sunshine Module = Web App Package + Manifest + Capability Contract
                + Lifecycle Contract + Security Policy + Adapter
                + Shared Design System
```

with React/TypeScript/Vite as the recommended stack, local bundles served from
`sunshine-module://<module-id>/`, a Module Runtime that loads them, a Capability
Broker behind an SDK, and a lifecycle manager moving modules between ACTIVE,
BACKGROUND, SUSPENDED, HIBERNATED and TERMINATED.

The brief is internally coherent and its instincts are good — minimal Chromium
patching, domain logic outside the browser core, no unrestricted shell or
filesystem, first-party is not trusted-by-default. Several of its rules were
adopted directly, below.

## What was adopted

| Brief section | Adopted as | Enforced by |
| --- | --- | --- |
| §17 Web Security — no `eval`, no remote script, origin discipline | SEC-14, SECA-9 | `scripts/verify_web_asset_security.py` |
| §5, §13 — no privileged surface behind a Sunshine-owned scheme | SEC-13, SECA-10 | `scripts/verify_first_party_surfaces.py` |
| §6 manifest fields — network, filesystem, credentials | manifest schema 2, already landed | `scripts/validate_first_party_modules.py` |
| §16 Network default DENY, no wildcards | SEC-6 | same |
| §8 no credential reaches a module | SEC-7 | same |
| §26 classify existing code KEEP/EXTEND/REFACTOR/REMOVE before rewriting | how schema 2 was done — the existing schema was revised, not replaced | — |

Note that §5 was adopted **against** the brief's own recommendation. The brief
proposed `sunshine-module://` as the default module origin; SEC-13 forbids it.
The reason is in the next section.

## The conflict

Four decisions already taken are incompatible with the brief's central premise.

**1. `sunshine-module://` contradicts ADR 0003.**
`docs/decisions/0003-internal-scheme.md` settled that Sunshine registers no URL
scheme — not internally, and not with any operating system. First-party surfaces
are `chrome://sunshine-*`. The brief proposes a new scheme as the default
execution origin for every module. This one is not a judgement call: it is a
settled decision the brief did not know about, because nothing enforced it.
It does now.

**2. A React/Vite bundle cannot exist in this repository.**
`scripts/verify_architecture.py` rejects any `package.json` outright. That guard
exists to keep wrapper runtimes out, and it does not distinguish "npm because
Electron" from "npm because Vite". A web-app module stack requires the file the
guard bans.

**3. `.ai/PROJECT_CONTEXT.md` defines modules as the opposite of this.**

> First-party platform: declarative module registry under `first_party/`;
> modules are compiled Sunshine capabilities, **not extensions or remotely
> loaded plug-ins**.

The brief's module is a loaded plug-in. It is loaded from local disk rather than
the network, which is better, but it is a bundle the browser executes rather
than a capability compiled into it.

**4. The scope table excludes the reference module.**
`docs/SUNSHINE_OS_STAGE_1_TO_3_IMPLEMENTATION_HANDOFF.md` places the J-OS
product line outside this project, and line 697 forbids adding a Stage 4 app
runtime while Stage 1–3 gates remain open. The brief's Phase 2 *is* a Stage 4
app runtime, and its Phase 4 connects a product module as the reference.

### The uncomfortable observation

The brief is aware of the risk and states it: *"SDK가 Electron과 같은 범용 OS
wrapper가 되지 않도록 한다."* The distinction it draws is real — a capability
abstraction is not an OS abstraction, and the permission model it proposes is
genuinely stricter than Electron's.

But the shape is the same shape. A renderer running a bundled web application,
reaching privileged operations through an SDK, brokered by a trusted process,
with a lifecycle manager and inter-module messaging, is Electron's architecture
with a better trust model. `docs/decisions/0002-native-chromium-downstream.md`
excluded that architecture by name. Whether it stays excluded when the trust
model is inverted is precisely the question the owner has to answer, and it is
not one a guard can answer, because `verify_architecture.py` does not
distinguish the two either — it bans the file, not the idea.

## The two coherent positions

**A. Modules stay compiled capabilities.** The current definition holds. Product
features are WebUI surfaces patched into Chromium and native services, which is
what `first_party/` already describes. The brief's security rules are adopted —
they already have been — and its runtime, SDK, lifecycle manager and bundle
format are not built. Cost: every product feature carries Chromium build time,
measured today at 6 h 31 min for a full build.

**B. Modules become local web-app bundles.** The brief is adopted as written,
which requires amending ADR 0003 (or finding a scheme-free origin — WebUI hosts
can serve bundled resources, which is worth investigating before amending
anything), amending `.ai/PROJECT_CONTEXT.md`, changing or scoping
`verify_architecture.py` so a build toolchain is distinguishable from a wrapper
runtime, and re-opening the Stage 4 gate. Benefit: product features stop costing
a Chromium build, which is the brief's actual motivation and a real one.

The middle path — adopting the vocabulary without the runtime — is the one to
avoid. It produces documents describing a module system that does not exist,
and this contract set has already been through that once with split view.

## Decision

**Position A.** A Sunshine module is a compiled capability declared in
`first_party/`, contributed through a WebUI, command, or profile-service
contribution point. It is not a bundle the browser loads and executes.

Nothing in the brief is lost by this. Its security rules are already enforced,
and those are the part that is expensive to retrofit — a runtime built later
against invariants that already exist is a better runtime than one built now
against invariants written to justify it.

### Position A is already enforced by construction

No new guard was needed, which is itself evidence the definition was real rather
than aspirational:

- `scripts/validate_first_party_modules.py` accepts four entrypoint types --
  `chromium_webui`, `chromium_webui_overlay`, `native_command`,
  `profile_service`. There is no bundle or application entrypoint, so a
  web-app module cannot be *declared*, not merely cannot be shipped.
- `scripts/verify_architecture.py` rejects `package.json`, so no build
  toolchain for such a bundle can enter the tree.
- SEC-13 rejects the origin scheme the brief proposed to serve one from.

### The cost, stated rather than assumed

Every product feature now carries Chromium build time. The measured figure is
**6 h 31 min** for a full build on the project's only build machine, which is
also its only CI. Incremental builds are much shorter, but any change touching a
widely included header is not incremental in practice.

This is the price of Position A and it is accepted knowingly. It is also the
strongest argument for B, which is why B is deferred rather than closed.

## Revisiting

Reconsider Position B when the Stage 1–3 gates close, or earlier if build time
becomes the binding constraint on product work rather than an annoyance.

One investigation should happen first, and it may make the question smaller:
**can a WebUI host serve bundled resources without a registered scheme?** If it
can, B costs an amendment to `.ai/PROJECT_CONTEXT.md` and a rescoping of
`verify_architecture.py`, but leaves ADR 0003 untouched. That is a materially
cheaper version of B than the one the brief described.

**That investigation has been done, and the answer is yes.**
`docs/MODULE_INSTALL_REVIEW.md` §3b: `WebUIConfig` takes its host as a
constructor argument, `URLDataSource::StartDataRequest` answers with bytes
decided when the request arrives, and this repository already uses both — the
document surface's untrusted half and the New Tab background respectively. No
scheme is registered and ADR 0003 is untouched, exactly as this section
predicted.

This does not reopen the decision. It removes the reason this section gave for
not reopening it, which is a different thing, and the question of whether to
open a second tier is now carried as a P0 in `docs/OPEN_DECISIONS.md` rather
than as a sentence here. One inference remains load-bearing and is stated in
§3b: that a config may be registered **after** startup was read off the API's
shape and not from any caller that does it.

## Consequences

- SEC-13 and SEC-14 are enforced regardless of which position is taken. Both are
  requirements of either.
- `.ai/PROJECT_CONTEXT.md` needs no change. Its existing definition — modules are
  compiled Sunshine capabilities, not extensions or remotely loaded plug-ins —
  is Position A, and this ADR is the record of it having been tested against a
  concrete alternative and held.
- The brief's Phases 2 through 4 — module runtime, bundle loader, SDK,
  messaging, lifecycle manager, DevOS as reference module — are not work items.
  They become work items only if this ADR is superseded.
- The brief's `permissions:` list is not adopted in either position. Manifest
  schema 2 already carries capabilities, network, filesystem and credentials,
  and a second permission vocabulary in the security layer is the failure this
  contract set is most exposed to.
