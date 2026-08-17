# Open decisions

Every decision the contracts hand to the product owner, in one place.

This index exists because the count crossed the point where nobody could answer
"what is waiting on me?" — thirty-odd questions across fifteen documents, some of
them the same question asked three times, and several already answered without
the asking documents being updated. That last failure is the expensive one: a
question recorded as open, and answered elsewhere, reads as blocking work that
is not blocked.

**It records status and location, not content.** The owning contract states each
question in full; duplicating that here would create a second version to drift.
Where a decision is settled, the settling document is named and the question is
struck through in its original home as well, so a reader arriving from either
direction sees the same thing.

## P0 — blocking

| Question | Owner document | Blocks |
| --- | --- | --- |
| Is `proprietary_codecs=false` intended? A build from this pipeline cannot play H.264 or AAC, so most web video will not play. The alternative needs a licensing position Sunshine does not inherit from Chrome. | `docs/WINDOWS_CHROMIUM_BUILD.md`, `docs/ACCEPTANCE_SUITES.md` §9 | Stage 1 dogfood |
| Are the Stage 1 and Stage 2 acceptance suites gates or reports? Handoff §10 forbids starting a wave while a gate knowingly fails, and no item in any suite can be decided offline today. | `docs/ACCEPTANCE_SUITES.md` §9 | Stage 1 exit |
| What may a provider `block` verdict actually do? Held at an attributed advisory; anything stronger is a second blocking path beside Chromium's. | `docs/SECURITY_CENTER_CONTRACT.md` §14 | Security Center |
| Is origin-only egress accepted, given it reduces detection for path-specific threats and constrains which providers are compatible? | `docs/SECURITY_CENTER_CONTRACT.md` §14 | Security Center |
| Is a permanently account-free browser the product, or is local-only the Stage 1 state of a browser that later gains sign-in? | `docs/PROFILE_ONBOARDING_CONTRACT.md` §9 | onboarding scope |
| Is **no first run at all** acceptable? A keyless build suppresses the first-run experience entirely. | `docs/PROFILE_ONBOARDING_CONTRACT.md` §9 | Stage 1 UX |
| Is Fork C accepted — record, do not report? It is also a decision not to build a data pipeline. | `docs/TELEMETRY_CONTRACT.md` §12 | Stage 2 exit |
| What behaviour is allowed for a warned dangerous download: warn/allow, warn/block, or policy-dependent? | handoff §11, `docs/DOWNLOAD_SAFETY.md` | download release |
| What is the default profile and data deletion and backup policy? | handoff §11 | persistence release |
| Is partial extension compatibility acceptable for v1? | handoff §11 | Stage 1 architecture gate |

## P1 — shapes the work, does not stop it

Recorded in their owning documents; named here so they are not rediscovered.

- Split view: enable `kSplitViewHorizontal` (stacked)? enable `kSplitViewTabRestore`? what happens when one member of a split moves workspace? may a workspace contain a split in the MVP? — `docs/TAB_WORKSPACE_SPLIT_CONTRACT.md`, `docs/ADVANCED_TABS_CONTRACT.md`
- Can a workspace span multiple windows? — handoff §11, and it gates three other answers
- On returning to a workspace whose tabs were discarded: restore one tab or all? — `docs/TAB_LIFECYCLE_CONTRACT.md`
- Reopened tabs lose their workspace at the pinned revision. Accept, or patch the two seam points? — `docs/ADVANCED_TABS_CONTRACT.md` Q3
- Does the Sunshine build disable `kVerticalTabsLaunch`, which is enabled by default? — `docs/ADVANCED_TABS_CONTRACT.md` Q5
- Is duplicate detection wanted at all? A "no" makes handoff §7.4 entirely inherited. — `docs/ADVANCED_TABS_CONTRACT.md` Q1
- Which platform is the performance baseline, and is a statistical budget a hard gate or an investigation threshold? — `docs/PERFORMANCE_BUDGET.md` §9
- Korean initial-consonant search in the palette — a Korean-first product plausibly needs it and it is currently scoped out. — `docs/COMMAND_PALETTE_CONTRACT.md` §15
- Command registry: twenty-four histogram names, or one enumeration with twenty-four buckets? — `docs/TELEMETRY_CONTRACT.md` §12
- Tabs panel scope, and whether the downloads panel coexists with the native bubble or replaces it. — `docs/SIDE_PANEL_CONTRACT.md` §14
- Should acceptance criteria that are still bare ordinals get stable prefixes, so enforcement can be counted? — `docs/ACCEPTANCE_SUITES.md` §9
- Security Center event retention, currently proposed at 30 days. — `docs/SECURITY_CENTER_CONTRACT.md` §14

## Settled, and where

Kept because each was open long enough to be planned around, and because a
reader may arrive holding the old question.

| Was | Settled by |
| --- | --- |
| Is an internal `sunshine` scheme registered? | `docs/decisions/0003-internal-scheme.md` — no scheme; surfaces are `chrome://sunshine-*` |
| Who owns profile onboarding and OAuth separation? | `docs/PROFILE_ONBOARDING_CONTRACT.md` |
| What is the telemetry and crash sink? | `docs/TELEMETRY_CONTRACT.md` — record, do not report |
| Does §5.6.1's popup policy handler survive? And §5.6.3's default-deny? | Both withdrawn in place; `docs/PERMISSION_POLICY.md` governs |
| Should Sunshine keep its own split-view model? | `docs/TAB_WORKSPACE_SPLIT_CONTRACT.md` — retired to Chromium's native split tabs |
| Does the command registry separate the operation from the availability predicate? | Registry schema 2 — `implementation`, `predicate`, `unavailable_reasons` |
| Is `font-weight: 650` resolvable? | Changed to 600, inside the allowed set; `docs/DESIGN_SYSTEM_CONTRACT.md` S8 now passes |
| Do the New Tab colour tokens exist upstream? | Yes — `kColorNewTabPagePrimaryForeground` at the pinned tag; checked in CI |

## Keeping this honest

A settled question is struck through in its owning document *and* moved here in
the same change. An index that only grows becomes a second backlog, and one that
disagrees with its sources is worse than none — which is the failure it was
built to end.
