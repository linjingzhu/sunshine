# Host Allowlist — Contract

## Status and scope

Applies to Sunshine OS on the pinned Chromium revision `152.0.7977.42`. It
defines what `network.access: allowlist` means in a first-party module
manifest, and it exists because `scripts/validate_first_party_modules.py`
refused that value "pending a future host-allowlist contract".

`docs/decisions/0016-relaxations-for-porting.md` is why it was written now: the
refusal was a placeholder for work nobody had done, not a security position, and
the owner's boundary is that a placeholder bends.

**Nothing here is implemented.** The validator accepts the declaration; no code
in the browser fetches anything on a module's behalf. §5 says what that leaves
open.

## 1. The one structural decision

**The page never fetches. The browser fetches, and hands back data.**

`SEC-14` says a Sunshine-authored web asset constructs no code at run time and
loads no remote resource, and that is untouched by this contract — the asset
still loads nothing. What this contract adds is that the *browser process* may
make a named request because a module asked it to.

The distinction is the whole of the safety argument:

- A page that fetches has the network inside the renderer, with the page's own
  parsing, its own error handling and its own opportunity to be talked into a
  request it did not intend.
- A browser that fetches has one call site, in privileged code, with the host
  fixed before the page loaded.

```text
module page  ──asks──▶  browser process  ──fetches──▶  an allowlisted host
     ▲                                                        │
     └──────────────── data, never instruction ◀──────────────┘
```

## 2. Invariants

Class **O** is decidable offline. **B** needs the built browser.

| ID | Invariant | Class |
| --- | --- | --- |
| HA-1 | A module's page issues no cross-origin request. Every remote call is made by the browser process on the module's behalf. | O |
| HA-2 | Every host is concrete. No wildcard, no scheme, no path, no port range — a host is a name the manifest states in full. | O |
| HA-3 | The page cannot name a host at run time. It selects from what the manifest declared; a host assembled from input is not a host this contract admits. | O |
| HA-4 | `access: deny` and a non-empty list is a contradiction and is refused. So is `allowlist` with an empty one — a module that needs no host declares `deny`. | O |
| HA-5 | An allowlisted host is not an authenticated one. SEC-7 is unchanged: no credential attaches to these calls until a broker exists, and a module that needs one is blocked, not exempt. | O |
| HA-6 | A response is data. It is never executed, never inserted as markup, and never treated as an instruction to the browser. | O |
| HA-7 | The allowlist is visible to the user. `chrome://sunshine-modules` shows what each module may reach, in the manifest's own words. | B |
| HA-8 | A request that fails is reported as failing. A module may not present stale or invented data as though the host answered. | B |

HA-1 through HA-6 are decidable from the manifest and the module's source.
HA-2, HA-4 and HA-5 are enforced today by
`scripts/validate_first_party_modules.py`; the rest wait on an implementation to
check.

### Why concreteness is the load-bearing term

A wildcard is not a smaller allowlist, it is a different kind of thing. `*.
example.com` admits a host nobody reviewed, chosen later, by whoever controls
the zone — which converts a decision the owner made into one an external party
makes. HA-2 exists so that the set of hosts a build can reach is fixed when the
build is made, and so that reading a manifest tells you the answer rather than
the shape of the answer.

The same reasoning is why HA-3 forbids assembling a host at run time. A module
that can compute a hostname has an allowlist of one entry: everything.

### Why HA-5 is stated separately

It is the term most likely to be read as pedantry, and it is the one that keeps
this contract from quietly undoing SEC-7. Allowing a module to *reach* a host is
not allowing it to *authenticate* to one. Marketpick's marketplace APIs and Dev
OS's GitHub calls both need a credential, so both remain blocked by SEC-7 after
this contract exists — this unblocks the manifest, not the feature.

## 3. What a module declares

```json
"network": { "access": "allowlist", "allow": ["api.example.com"] }
```

Each host needs an argument, and the argument belongs in the module's own
documentation rather than in the manifest — the manifest is read by tooling and
by the module home, and a paragraph in it would be read by neither.

## 4. Acceptance criteria

1. **HAA-1.** No module's web assets contain a cross-origin `fetch`, `XHR`,
   `WebSocket`, or remote subresource. (HA-1) — O
2. **HAA-2.** Every declared host matches the concrete-host rule, and no
   manifest declares `allowlist` with an empty list. (HA-2, HA-4) — O
3. **HAA-3.** No module declaring `allowlist` also declares
   `credentials.direct_access: true`. (HA-5) — O
4. **HAA-4.** The module home shows the declared hosts. (HA-7) — B

HAA-2 and HAA-3 are enforced. HAA-1 is decidable from source and is not checked
yet; `scripts/verify_web_asset_security.py` is where it belongs.

## 5. NOT VERIFIED

- **No browser-side fetch exists.** This contract describes a capability the
  browser does not have. A module may now declare it; nothing acts on the
  declaration.
- The shape in §1 — page asks, browser fetches — has not been built, so the
  interface it would need is undesigned. It should be one method on the
  module's own Mojo interface rather than a general-purpose one, for the reason
  in HA-3.
- HA-6 and HA-8 are properties of an implementation that does not exist.
- No claim is made about proxies, redirects, or what happens when an
  allowlisted host redirects to one that is not. **That is a real gap** and the
  first implementation must close it — a redirect is how an allowlist becomes
  advisory.
