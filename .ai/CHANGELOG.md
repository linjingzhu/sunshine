---
doc_id: ai-changelog
version: 1.1.0
canonical_path: .ai/CHANGELOG.md
updated: 2026-09-03
---

# Changelog

The version of the **policy set as a whole**. Individual documents carry their
own `version` in front matter, which says how that document changed; the number
here says what an adopter is holding. § *Document versioning* below is the rule
for both — it lives here rather than in `CORE.md` because a run never needs it.

The newest entry at the top is the current version. There is no second place
that records it — `.ai/tools/check_policy_set.py` reads this file to answer
"which version is this set", so a release that is not written here did not
happen.

**Every entry needs three things, and the check enforces all three:** a semantic
version, an ISO date, and at least one improvement. An entry that records a
version and a date but not what changed is the shape of failure this whole set
exists to prevent — a result reported without the question it answers.

## Format

```text
## MAJOR.MINOR.PATCH — YYYY-MM-DD

Optional one-line summary of what the release is for.

- what changed, and why it was worth changing
- ...
```

Judge the level by policy impact, per § *Document versioning* below:
**MAJOR** when a rule is removed or reversed, so previously compliant work stops
being compliant; **MINOR** when a rule is added or its scope widens; **PATCH**
for wording, examples and ordering that change nothing about what is required.

---

## 3.2.0 — 2026-09-25

Add a low-cost Dispatcher before the Primary Manager.

- Route every request through a read-only `gpt-5.6-luna` Dispatcher first.
- Classify intent, repository, risk, tools, verification and cost exposure
  before selecting Manager, Worker, explorer or reviewer execution.
- Keep GPT-5.6 models available for cost-sensitive implementation and fallback.

---

## 3.1.0 — 2026-09-25

Make cost-bearing hosted automation opt-in and bounded.

- Prohibit paid or uncertain-cost GitHub Actions by default.
- Require explicit owner approval, provider and workflow scope, a maximum cost,
  and an expiry or review date in the owner ledger before enabling it.
- Require cost-bearing automation to fail closed when its budget or expiry is
  not verifiable; local checks remain the default.

---

## 3.0.0 — 2026-09-25

Remove the bundled GitHub Actions automation while retaining local verification.
This is a breaking adoption CLI change: existing callers must remove
`--with-ci` from their commands.

- Remove the policy-set Actions workflow and the adoption option that copied it.
- Keep the policy checker and regression suites available as local commands;
  adoption still runs the policy checker before returning its result.
- Verify that adoption creates no workflows and preserves any workflows the
  target repository already owns.
- Update installation examples and verification instructions for local use.

---

## 2.6.0 — 2026-09-25

Codex can now use the Claude-defined workflow and roles with the same shared
policy gates.

- Add `AGENTS.md`, the Codex `auto-dev` skill and its explicit-invocation
  policy, and native Codex definitions for the two read-only agents.
- Map model roles to Codex models in `HARNESS.md`; keep the reviewer model
  selectable per run so it can differ from the implementer.
- Let the Codex reviewer accept roadmap evidence before a diff exists, and
  distinguish incomplete verification from a complete review PASS.
- Carry the Codex entry, skills and agents through adoption while preserving
  an adopter's existing entry and capabilities.
- Extend capability, reference and portability checks to Codex files and add
  regression coverage for adoption and malformed native agent definitions.
  The tools now require Python 3.11+ for standard-library TOML parsing.

---

## 2.5.0 — 2026-09-20

The set could say how to build well and had nothing to say about **what to
build next**, so every run began with a person deciding. `auto-dev` is that
decision made repeatable: propose a roadmap from evidence, challenge it, then
execute, verify and merge one item at a time.

It owns an order and its gates, and nothing else. Each of its six steps names
the document that owns the rule it applies — `EXECUTION.md` for sizing and
Mission Packets, `REVIEW.md` for the adversarial passes, `LOOP.md` for the
attempt budget, `REPOSITORY.md` for the merge, `REPORTING.md` for the report.
A procedure that restated any of them would be a second owner for a rule, which
is the defect § *Single source* exists to prevent.

- **the mode never starts itself.** The user starts it and nothing else does —
  not an open-ended task, not a ready backlog, not a schedule, not a previous
  run that left work. A mode that chooses what to build is choosing product
  scope, which `CORE.md` § *Autonomy* puts among the few things to ask about,
  so a mode that could enter itself has already decided. No standing approval,
  project-context line or roadmap item can waive it; those widen only what
  happens after the user has started a run;
- **one gate waits for a person**, and it is the roadmap. Everything after it
  runs on the set's ordinary gates, and a run that is late does not lower one:
  speed is seventh of eight in `CORE.md` § *Priority*;
- `.ai/ROADMAP.md` is a new instance file, exempt from front matter and from
  the portability denylist for the same reason the project context is — a
  roadmap names one product's features on purpose. It is also the state card
  `CORE.md` § *Token discipline* asks for before a context reset, which is what
  makes an interrupted loop resumable rather than restartable;
- check 7 widened from agent definitions to **capability definitions**: an
  agent is named by its file, a skill by its folder, and either one declaring
  a different name is unreachable by whatever names it;
- **capability definitions now have their references checked.** A skill is
  mostly pointers into `.ai/`; a section renamed in `REVIEW.md` broke one
  silently, because nothing read those files for references. They are also
  scanned by the portability denylist now, which is the same argument: a
  capability that travels must survive the copy;
- `adopt.py` carries `.claude/skills/` alongside `.claude/agents/`, still never
  over a file the target already has;
- nine tests: four for the skill's shape, one that a dangling pointer inside a
  capability fails, one that a roadmap may name the product, and three for the
  copying, including an adopted tree passing with the capabilities it received.

---

## 2.4.0 — 2026-09-19

Read a working Claude Code setup someone had assembled by hand, and kept only
what the set could not already answer. Most of it was already here, worded
differently; three things were not, and one thing the set had been *requiring*
without shipping: `HARNESS.md` told a Mission Packet it could name a search
agent and a review agent, and there was nothing in the repository to name.

- **the set now ships two agent definitions**:
  `.claude/agents/fast-explorer.md` (read-only search, returns a conclusion and
  the paths behind it, under 150 tokens) and
  `.claude/agents/adversarial-reviewer.md` (independent review, returns `PASS`
  or a severity, a file and line, and a fix). Neither
  pins a model — a search wants the cheapest one that can read code, and a
  reviewer's model is decided against whoever implemented, per `REVIEW.md` §
  *Cross-agent independence*. They are committed because a contributor who
  clones the repository can spawn them and one who does not have them cannot;
- `REVIEW.md` gained § *What a reviewer must not raise*. The list of what to
  look for is what makes a review worth commissioning; this one is what makes
  it worth reading. Unrequested refactoring was already out of scope — this
  names it as the reviewer breaking the scope rule rather than the author;
- `EXECUTION.md` gained § *Sizing the work* — a small change is the Manager's
  to do directly, without a plan, a Packet or a subagent, and when the size is
  not obvious it is medium — and § *Resuming interrupted work*, because the
  expensive shape is a second branch for work that already has one;
- `CORE.md` gained § *Comments*: what a comment must earn, and the rule that
  the conversation never goes into the code. Not the instruction, not the
  Packet, not that a line changed;
- `HARNESS.md` now states the test for what belongs in a committed harness
  file: if a new contributor cloning the repository would **behave**
  differently without it, it is a capability and is committed; if only their
  prose would read differently, it is preference and is not;
- `adopt.py` copies `.claude/agents/`, and never over a file the target already
  has — with or without `--force`. An adopter's own copy of a definition is
  their harness;
- a seventh check reads those definitions: front matter, a `name`, a
  `description`, and a `name` matching the file, because a packet naming an
  agent that does not resolve fails at spawn. It is a failure at the set's home
  if the directory is missing, and nothing to check anywhere else — the third
  time this set has had to tell its own home from a repository that adopted it,
  after 2.2.1 and 2.3.1. Cross-references into `.claude/agents/` are resolved
  the same way, or `HARNESS.md`'s pointers would dangle in every adopted tree;
- six tests for the new check and two for the copying, including the one that
  asserts the distinction above in both directions.

Deliberately not absorbed: a feature-development skill, a UX specification
format, and a repository-root entry file, each of which conflicts with a rule
this set already states and paid for. Where the two disagreed — Mission Packet
fields, how many workers, naming vendor models, the report format — the set
kept its own.

---

## 2.3.1 — 2026-09-03

Found by asking how the set is used as a GitHub template, and then trying it:
a repository made with **"Use this template"** fails its own checks on the
first run, before its owner has changed anything. The button copies every
tracked file, and `LESSONS_FROM_PRACTICE.md` is how the checks tell the set's
home from a repository that adopted it — so the new tree claims to be the set,
and the checks read its `README.md` as the set's own. 2.2.1 fixed this defect
for the documented path; the template path reintroduced it.

- added `adopt.py --from-template`, which finishes such a tree in place:
  removes `LESSONS_FROM_PRACTICE.md` (the entire correctness fix — verified by
  removing only that and watching the checks pass), reseeds the portability
  denylist from `--name` because the shipped seeds are another project's names
  and prove nothing about yours, and **reports** rather than deletes a
  `README.md` that is still this set's front page. It refuses a tree with no
  marker to remove instead of guessing;
- eight tests, one of which asserts the failure first: a copied tree with the
  adopter's own README fails, and the mode makes it pass. A fix whose defect
  was never reproduced is a fix nobody can check;
- documented the button and its extra step in `README.md` and
  `.ai/tools/README.md` § *GitHub's "Use this template"*.

PATCH: no rule was added, removed or widened. A path that was broken now works,
and nothing previously compliant changed.

## 2.3.0 — 2026-09-03

The harness, the loop, and adoption as a command. 2.2.0 checked the repository
that adopted the set; this release is about how a run is operated and how a new
repository gets one.

- added `.ai/HARNESS.md`: what the environment owes a run before its first edit,
  the rule that a run finding one of those missing names it and stops rather
  than substituting a weaker check, why the entry file is a contract and not a
  manual, where harness configuration belongs (committed, never on one
  machine), and what a Mission Packet may assume about tools;
- added `.ai/LOOP.md`: the four-step unit loop, an attempt budget — the same
  failure twice means the diagnosis is wrong, three ends the attempt — five
  signs a loop is not converging, and three stop conditions of which going
  quiet is not one;
- added `.ai/EVOLUTION.md`: five triggers that oblige a run to record a lesson,
  a table of where each kind goes, the rule that a lesson expressible over
  structure becomes a check with its blind spot written down, and pruning.
  `MANAGER.md` is untouched: it keeps § 12 and its run metrics, and is being
  improved in a separate run — moving § 12's content here is left to whoever
  owns that file;
- added four token rules to `CORE.md` § *Token discipline*, written in the
  compressed voice 2.2.2 gave that file: a stable prefix with volatile content
  last, load a document when its trigger fires rather than in case, send
  breadth-first search to a subagent and keep the conclusion, and bound the
  report as well as the reading. `CLAUDE.md` gains the three new triggers and
  points its adoption line at `adopt.py`, which travels, instead of at a
  `README.md` that does not;
- added `.ai/tools/adopt.py` and `.ai/tools/test_adopt.py` (13 tests): one
  command copies what travels, writes both instance files with the templates'
  instruction lines removed, fills the facts from `--set key=value`, and runs
  the checks in the new tree. It ends green or exits non-zero naming every fact
  still unanswered; an existing instance is kept unless `--force` says
  otherwise. CI runs the adoption tests, so a set that cannot be adopted green
  fails here instead of in someone's new repository;
- `CLAUDE.md` no longer points at `README.md` for the adoption procedure, a
  file the adoption procedure does not copy. It points at `adopt.py`, which
  does travel. This run found the same defect 2.2.1 fixed, from the other
  side — by adopting rather than by reading — and reached the opposite fix:
  make `LESSONS_FROM_PRACTICE.md` travel so the citations resolve. 2.2.1 was
  merged first and is kept, because copying that file would make an adopting
  repository look like the set's own home and the checks would then read the
  adopter's `README.md` as this one's. `adopt.py` copies `CLAUDE.md` and
  `.ai/` only, and `.ai/tools/README.md` records why.

- fixed a brittle test the new release entry broke: the guard suite asserted
  the changelog held "5 release entries", a count kept in two places that drifts
  on every release. It now reads the count from the changelog it is checking.

Start-up read: 8,205 characters against 2.2.2's 7,672. Seven trigger and rule
lines cost 533 characters at every turn of every run, and that is the price of
this release — recorded here rather than left for someone to measure later.

MINOR: three documents and four rules were added, and two defects fixed.
Nothing previously compliant became non-compliant.

## 2.2.2 — 2026-09-03

The start-up read, measured and cut. `CLAUDE.md`, `CORE.md` and `MANAGER.md`
were 14,665 characters — about 3,700 tokens at four characters each — paid
before a run read a line of the repository.

- `MANAGER.md` rewritten as a twelve-item checklist, the same duties in the
  same order, each pointing at the file that owns its mechanics:
  5,634 → 2,755 characters;
- `CORE.md` reworded to the same rules in fewer words: 6,482 → 3,832; every
  requirement of 1.2.0 is still stated, the three evidence rules as `###`
  headings so pointers still resolve;
- `CLAUDE.md` cut to the adoption check, the read list, the trigger table and
  the one habit: 2,549 → 1,085;
- the context template's intro and "who reads each fact" list shortened:
  3,032 → 2,853.

PATCH: wording, ordering and length; nothing newly required, nothing removed.
The three policy files are now 7,672 characters, about 1,900 tokens; the
filled-in project context is the adopter's own cost, and `MANAGER.md` item 12
records the total per run.

## 2.2.1 — 2026-09-03

Found by adopting 2.2.0 into a real repository: the checks read the adopter's
own `README.md` as if it were the set's, and every pointer at
`LESSONS_FROM_PRACTICE.md` and `README.md` § *Adopting it* dangled, because
the adoption procedure copies neither file.

- the checks now read `.ai/**` and `CLAUDE.md` everywhere, and the root
  `README.md` and `LESSONS_FROM_PRACTICE.md` only at the set's home (where
  `LESSONS_FROM_PRACTICE.md` exists); pointers at those two files resolve in
  an adopting repository the way pointers at instance files do;
- one self-test: a copy without the set-home files, carrying a product name
  in its own README, passes; and the self-tests read the repository's own
  denylist instead of assuming the seed names, so they run unchanged in an
  adopting repository whose CI copies the workflow.

PATCH: nothing newly required; the checks stop failing on a repository that
followed the adoption procedure exactly.

## 2.2.0 — 2026-09-03

Guards for the adopter. 2.1.0 made the set check itself; this release makes it
check the repository that adopted it, with rules paid for by a second project
(`LESSONS_FROM_PRACTICE.md` entries 24–29).

- added `PROJECT_CONTEXT.template.md` § *Facts the checks read*: ten
  `key: value` facts a run reads by name — base branch, whether merge deploys,
  the runtime gate command, the verified commands, generated artefacts,
  external scripts, public identifiers, the owner ledger — and a sixth check, *project context*,
  that refuses an instance missing a key, leaving a placeholder, or keeping a
  template instruction line; where no instance exists it checks the template
  still declares every key;
- added `CORE.md` § *Tests check the shape of configuration*, § *Generated
  artefacts* and § *Public identifiers and secrets*; four token-discipline
  rules on watched events, list queries, waiting and the pre-reset state card;
  two autonomy rules on attachments that never arrive and on standing
  directives;
- added `REPOSITORY.md` § *Branch lifecycle* (one branch per pull request,
  recreated from the base after a squash merge, draft first, commit size cap,
  no tooling residue) and § *Merge and deploy* (`merge_deploys: yes` means a
  user-visible change is shown before it merges); `personal` mode now allows a
  feature branch and a draft pull request instead of asking every time;
- `REVIEW.md` no longer names vendors: the independent reviewer is a different
  *model* from the implementer, both named in the report, and a same-model
  fresh context is labelled `FALLBACK REVIEW`;
- `REPORTING.md` § *Owner ledger*: work only the user can do lives in one
  ledger file with row ids that reports cite; the persistent-report threshold
  is now a rule (a merged pull request, a ledger row changed, or a `FAILED`
  run) instead of "substantial"; the report names the implementing and
  reviewing models;
- `MANAGER.md` § 1 states the reading in one line before building an ambiguous
  product or visual ask; § 12 names four metrics that session logs already
  carry — start-up tokens, watched-event turn share, merged-then-reverted pull
  requests, unattributed commits;
- `UX.md` runs the project's own `runtime_gate` instead of a generic
  build-and-launch; `EXECUTION.md` gives a generated artefact one owner, the
  integration branch;
- moved § *Document versioning* and § *Set version* out of `CORE.md` into this
  file: a run never needs them, and `CORE.md` is read at every start;
- removed the `Default behavior` list from `CLAUDE.md`, a summary of `CORE.md`
  and `MANAGER.md` that the heading check could not see and that had grown to
  seven lines;
- `LESSONS_FROM_PRACTICE.md` entries 24–29, from a web product built by four
  agents in turn.

MINOR: rules were added and one permission widened; nothing previously
compliant became non-compliant. Adopters gain ten facts to fill in and a check
that will fail until they do — which is the point.

## 2.1.0 — 2026-09-03

Guards. Until now every rule in the set was enforced by whoever happened to read
it carefully.

- added `.ai/tools/check_policy_set.py`: five structural checks — front matter,
  cross-references, one owner per heading, a denylist of project-specific
  names, and this changelog — each printing the exact question it answers;
- added `.ai/tools/test_check_policy_set.py`: 18 tests that break one thing at a
  time and assert the matching check reports it, plus a control that the
  untouched tree stays clean. A guard that has never failed on purpose has not
  been tested;
- added `.github/workflows/policy-set.yml`, which runs the self-tests first and
  the checks second. The tools travel with `.ai/`; the workflow does not;
- added this changelog as the single home of the set's version, plus
  § *Set version* (then in `CORE.md`, now below) and a check that refuses an entry missing a
  version, a date or its improvements, out of order, or with a version already
  used;
- fixed a drift the new heading check caught on its first run:
  `PROJECT_CONTEXT.template.md` still defined `repository_mode: auto` in the
  wording `REPOSITORY.md` had moved away from in 2.0.0. The template now carries
  the value and points at `REPOSITORY.md` for the meaning.

MINOR rather than PATCH: adopting repositories now have something to maintain —
a denylist of their own names, and a place to run the checks.

## 2.0.1 — 2026-09-03

Each rule is now stated in exactly one file.

- single-sourced six rules that had been stated in two to four files each: the
  evidence habit (`CORE.md`), the compile and build ladder, conflict prevention
  and session strategy (`EXECUTION.md`), the cross-agent reviewer rule
  (`REVIEW.md`), and the adoption procedure (`README.md`);
- rewrote `MANAGER.md` as a spine: each step states the duty that is genuinely
  the Manager's and points to the file that owns the mechanics, instead of
  re-narrating it;
- emptied `memory/MANAGER_PLAYBOOK.md` of three seed lessons that were already
  policy, which its own promotion rule had always forbidden keeping, and made
  that rule say to *move* a lesson rather than summarise it;
- marked owning sections *Single source*, and stated the convention: a pointer
  is not a summary and must not grow into one.

PATCH: rules moved between documents; nothing became newly required.

## 2.0.0 — 2026-09-03

The set stopped claiming to be portable and started being portable.

- removed the filled-in `PROJECT_CONTEXT.md`, the filled-in
  `memory/PROJECT_LESSONS.md`, and eight run reports, all describing a
  repository that was not this one. The set now ships templates and no instance;
- generalised eight reusable defects out of that material into
  `LESSONS_FROM_PRACTICE.md` entries 16–23 — a clean merge is not a compatible
  merge, preparation passes the repository's own tests, record what was built
  rather than what was configured, do not shadow the platform's state, match on
  durable identity, a run over a changing tree is not a run, milestones and
  delivery units need separate status, amend a specification beside it;
- removed a specific organisation's repository name from `REPOSITORY.md` and
  replaced it with portable signals; `auto` now resolves a missing project
  context to **protected**, so an unconfigured repository fails safe;
- removed a hardcoded build platform from `CORE.md` and four other files, which
  now defer to the primary target platform named in `PROJECT_CONTEXT.md`;
- added § *Document versioning* (then in `CORE.md`, now below) and front matter on every document
  in `.ai/`, which the README had promised and nothing had implemented;
- made `CORE.md` § *The question each result answers* a normative rule rather
  than an idea repeated in three introductions.

MAJOR: rules were removed and reversed. Work that relied on the old fixed
platform, or on the old `auto` heuristic, is no longer compliant.

## 1.0.0 — 2026-08-24

First publication, extracted from the project that paid for it.

- `CLAUDE.md`, `README.md`, and the `.ai/` policy set: `CORE`, `MANAGER`,
  `EXECUTION`, `REVIEW`, `UX`, `REPOSITORY`, `REPORTING`, plus `memory/`;
- `LESSONS_FROM_PRACTICE.md` entries 1–15, each one generalised from a defect
  that had already cost something.

The extraction was incomplete — the source project's context, memory and reports
came with it, which is what 2.0.0 finished.

---

## Document versioning

Every document in `.ai/` carries front matter:

```text
---
doc_id: <stable id, never renamed>
version: MAJOR.MINOR.PATCH
canonical_path: <path this document is addressed by>
updated: YYYY-MM-DD
---
```

- `doc_id` and `canonical_path` are how other documents address this one. Change
  them only when the document itself moves or is replaced.
- `MAJOR` — a rule is removed or reversed, so previously compliant work is now
  non-compliant.
- `MINOR` — a rule is added or its scope widens.
- `PATCH` — wording, examples, or ordering, with no change to what is required.

Judge the bump by policy impact. Do not bump mechanically on every edit, and do
not bundle a `MAJOR` reversal into an edit described as wording.

Project instance files (`PROJECT_CONTEXT.md`, `memory/PROJECT_LESSONS.md`) are
versioned the same way but belong to their repository, not to this policy set.

## Set version

A document's own `version` says how that document changed. The version of the
**set as a whole** — what an adopter is holding — is the newest release entry
above, and nowhere else. The two numbers are different things and are not
expected to match.

Every release entry records three things, and the check refuses an entry
missing any of them:

- the **version**, at the level its policy impact earns;
- the **date** it was released, as `YYYY-MM-DD`;
- the **improvements** — what changed and why it was worth changing.

A version and a date without the improvements is a release reported without the
question it answers. Log the release in the same change that makes it, not
afterwards from memory.
