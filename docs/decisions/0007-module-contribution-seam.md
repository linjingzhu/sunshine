# ADR 0007: One seam, many surfaces

## Status

**Accepted.** Design recorded now; implementation waits for the first build of
patch 0004, for the reason in *Sequencing* below.

## Context

ADR 0006 settled that a Sunshine module is a compiled capability contributed
through a WebUI, command, or profile-service contribution point. Patch 0004 built
the first one — `chrome://sunshine-security` — and in doing so measured what a
contribution point actually costs.

It modifies seven upstream files:

```text
chrome/common/webui_url_constants.h        host constant
chrome/common/webui_url_constants.cc       ChromeURLHosts()
chrome/browser/ui/webui/chrome_web_ui_configs.cc   AddWebUIConfig call
chrome/browser/ui/webui/BUILD.gn           C++ source_set dep
chrome/browser/resources/BUILD.gn          resource target dep
chrome/chrome_paks.gni                     pak into the bundle
tools/gritsettings/resource_ids.spec       resource id range
```

**The second surface collides with the first on all seven.** This was not
reasoned about, it was run: a copy of 0004 renamed to a second surface and
appended to the series makes `scripts/patch_manifest.py` exit 1 and name every
one of them.

The exclusivity rule it violates is correct and should not be relaxed for
upstream paths. Three of those seven — `resource_ids.spec`, `chrome_paks.gni`
and `webui_url_constants.h` — are among the more actively edited files in
Chromium, so N surfaces built this way means rebasing N patches against the same
churn at every roll. The cost is not linear in surfaces; it is linear in
surfaces multiplied by roll frequency.

## Decision

**Split a contribution point into a seam and a surface.**

| Patch | Touches | Changes when a surface is added |
| --- | --- | --- |
| `0004-sunshine-webui-seam` | the seven upstream files, once | no |
| `0005-sunshine-security-surface` | only files under Sunshine-owned directories | — |
| `0006-…-surface` | the same | — |

The seam contributes one of each thing upstream needs to know about, and each of
them is a list Sunshine owns rather than an entry Sunshine adds:

- **One registration call.** `chrome_web_ui_configs.cc` gains a single line
  calling a Sunshine-owned `RegisterSunshineWebUIConfigs(map)`. Which surfaces
  exist is decided inside that function, in a file the seam creates.
- **One resource bundle.** A single grd for every Sunshine surface, so
  `resource_ids.spec` and `chrome_paks.gni` each carry one Sunshine entry
  forever. The current shape needs a new id range per surface, and that file is
  the likeliest conflict of the seven.
- **One host list.** Sunshine host constants live in a Sunshine-owned header,
  and `ChromeURLHosts()` gains one loop rather than one line per host.

After the seam, adding a surface is: files under
`chrome/browser/ui/webui/sunshine/<name>/` and
`chrome/browser/resources/sunshine/<name>/`, plus a line in the seam's own
registry file. **No upstream file is touched.**

### The guard changes with it, narrowly

`scripts/patch_manifest.py` currently forbids any two patches from claiming the
same target. That rule exists to keep upstream edits rebasable, and it will be
narrowed to upstream paths only: a file the stack *creates* cannot conflict with
upstream churn, because upstream does not have it. Two surface patches extending
the seam's registry is ordinary ordered application, not a rebase hazard.

This is a guard being loosened, which deserves suspicion. What keeps it honest
is that the rule's purpose is unchanged and its coverage of that purpose is
unchanged: every upstream path stays exclusively owned. Only paths that exist
solely because Sunshine created them leave the rule, and for those the rule was
never protecting anything.

## Sequencing

**The seam is not built until patch 0004 compiles.**

Nothing in 0004 has been through a build. The resource-id choice, the generated
`kSunshineSecurityResources` and `IDR_SUNSHINE_SECURITY_APP_HTML` names, the GN
dependency labels and Chromium's WebUI lints are all unexercised. The seam is an
abstraction over exactly that machinery, so building it first would mean
discovering a mistake in the abstraction and the foundation at the same time,
with no way to tell which was wrong.

One build settles it. The design is recorded now so that the moment it is green,
the restructure is mechanical rather than a fresh decision.

## Consequences

- Surfaces stop being expensive. The marginal cost of the second surface falls
  from seven upstream edits to none.
- The roll cost stops growing with the product. One patch rebases against the
  seven churning files no matter how many surfaces exist.
- `first_party/registry.json` gains a real counterpart in the browser: the
  seam's registry function is the code that the declarations have never had.
- A surface can be reverted by removing one patch, without touching upstream
  edits that other surfaces depend on.

## What was actually built

The seam landed as `0004-sunshine-webui-seam.patch`, and it is weaker than the
fallback this ADR named. Recorded here rather than in a commit message,
because the gap changes what the next surface costs.

**Three of the seven files are now generic.** `chrome_web_ui_configs.cc` calls
one `sunshine::RegisterWebUIConfigs(map)`; `webui_url_constants.h` includes one
Sunshine-owned header; `webui_url_constants.cc` appends a Sunshine-owned list
to `ChromeURLHosts()` once. A surface extends the two Sunshine-owned registries
those create and touches none of the three again. `0005-sunshine-security-webui.patch`
demonstrates it: zero upstream sections, two registry-extension sections.

**Four are not.** `chrome/browser/resources/BUILD.gn`,
`chrome/browser/ui/webui/BUILD.gn`, `chrome/chrome_paks.gni` and
`tools/gritsettings/resource_ids.spec` carry `sunshine_security`-specific lines
inside the seam patch, because each is tied 1:1 to the surface's `grd_prefix`,
and changing that prefix would change `IDR_SUNSHINE_SECURITY_APP_HTML`. The
shared-grd assumption below was not resolved; it was worked around by baking
the one surface that exists into the seam.

**So a second surface costs four upstream-file edits, not zero, and not the
one this ADR's fallback predicted.** The seam's genericity stops at the
registration and host halves. Any claim that a second surface is now free is
wrong, and one was made in the commit that landed the seam before this section
was written.

The resource half is therefore still open work, not a solved problem: either a
shared grd that several surfaces can populate, or an accepted per-surface cost
in four files, recorded as a decision rather than as a workaround discovered
during implementation.

## NOT VERIFIED

- Neither the seam nor the surface patch has been compiled. `verify_pinned_upstream.py`
  confirms all five patches apply cleanly to 152.0.7977.42; that is not the
  same as GN accepting the registry targets or `rc.exe` linking the resources.
- That a single grd can serve several independent WebUI surfaces remains
  untested, and is now the specific question the resource half is blocked on.
- Whether `ChromeURLHosts()` accepts a loop over a Sunshine-owned list was
  checked against the pinned source during implementation and reworked into a
  `base::NoDestructor<std::vector<...>>` append; that it compiles is still
  unobserved.
