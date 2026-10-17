---
doc_id: ai-changelog
version: 1.2.0
canonical_path: .ai/CHANGELOG.md
updated: 2026-10-09
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

## 4.1.1 — 2026-10-17

Both test suites pass in a subscriber again. Found after 4.1.0 reached all 41
subscribers: each suite had one test that failed there, though the set's check
and every subscriber's CI passed, because neither runs the suites.

- `test_an_unfinished_template_copy_is_named` built a template copy from the
  tree it runs in. In a subscriber that tree has the project's own README, not
  the set's, so the copy's check failed on a pointer into the set's README. A
  template copy is a copy of the set's home, so the test is listed as needing
  it, like the other template tests. `PropagateTests` now reads that list, and
  the guard against stale entries covers both suites;
- `test_native_agent_model_is_optional` edits a delivered agent definition and
  expects the check to pass. In a subscriber the lock rightly reports the edit,
  so the test removes the lock from its copy first. The edit is what it tests,
  not drift.

## 4.1.0 — 2026-10-10

Roadmap item R8, option B, chosen by the user on 2026-10-10. The lock 4.0.0
introduced is the record of delivered capabilities that option needed.

- the cross-reference check no longer excuses every reference into a
  capability folder in a subscriber. It excuses one only when it names a
  capability the repository removed, or one the set ships but the
  repository holds its own version of. A pointer the set's documents or an
  entry file make to a capability that is simply not there now fails, as it
  does at the set's home. A repository adopted before 4.0.0 has no lock, and
  keeps the old tolerance until its next upgrade writes one;
- the lock records the second case as `kept: <path>`. Without it, a
  repository with its own `auto-dev` skill would fail on the set's pointer to
  the skill metadata the set withheld from it;
- the test that exposed the blind spot now runs in every subscriber, and is
  skipped only where no lock exists. Five new tests cover the check and one
  the lock.

## 4.0.0 — 2026-10-10

An adopting repository now subscribes to the set instead of owning a copy of
it. Asked for by the user on 2026-10-10. A Claude plugin was considered first
and set aside on the plugin documentation: a cloud session does not install the
plugins a repository's settings turn on, Codex has no equivalent, and the set's
repository stays private.

- **MAJOR:** editing one of the set's files in an adopting repository used to
  be allowed, and an upgrade overwrote the edit. It now fails that
  repository's check. Adoption and every upgrade write `.ai/set.lock`: the
  source, version and commit delivered, and a digest of each file delivered.
  The new *subscribed copy* check, check 9, fails on any of those files edited
  there, or removed if it is a policy document. A removed capability is still
  the repository's choice;
- a rule only one repository needs has a place: the project context's new
  *Local rules* section, `.ai/PROJECT_CONTEXT.template.md` § *Local rules*.
  It wins in that repository and names the set rule it replaces, so the
  conflict can be brought back here;
- `--upgrade` names a local edit exactly where a lock exists, and replaces
  the edited file, a subscribed capability included. It records a capability
  the repository removed as `removed: <path>` and does not deliver it again.
  Without a lock it behaves as before and writes one;
- the manager playbook is delivered once and then kept, like the denylist.
  Repositories write their candidate lessons into it, and the trial upgrade of
  every adopter found two whose lessons an upgrade would have erased;
- the set's home lists its subscribers in `.ai/SUBSCRIBERS.md`, and the new
  `propagate.py` upgrades each subscriber's clone on its own branch, commits,
  and writes the pull request body. Nothing is pushed without `--push`;
- `CLAUDE.md` and `AGENTS.md` say the set's files are edited only where the set
  lives;
- an upgrade now refreshes a capability that holds a version the set itself
  once shipped, read from the set's git history. Trying this release on every
  subscriber first found the Codex entry point kept at its first delivered
  version in all forty, because nothing before this release recorded a
  delivery. A capability the repository changed is still kept and named
  `[stale]`. Ten new tests cover the propagation, twelve the lock in adoption
  and upgrade, and sixteen the check.

## 3.7.1 — 2026-10-09

Found while preparing to upgrade the forty-one adopters, by upgrading each of
them in a scratch copy first. Two of them would have failed their own check
straight after the upgrade, on a defect that was the set's and not theirs.

- the reference check no longer reads run reports under `.ai/reports/`. A
  report records a moment, and a file it named may since be gone. In
  `md-mcp` and `ai-prompt-generator`, a report preserving an old entry file
  named documents those repositories later removed, and the only fix would
  rewrite the record;
- they had passed until 3.4.2 by accident. The guess beside the referring file
  landed inside the instance folder and was excused as an instance file. 3.4.2
  stopped that guess for paths that name a directory, which was right, and
  this case came to light with it. Bisected: 3.4.1 passes both repositories,
  3.4.2 fails them;
- every other document is still read, instance files included. The project's
  lessons are read at every run, so their pointers must resolve. Two tests,
  one each way.

PATCH: what the check reads is narrowed back to what it was meant to read.

---

## 3.7.0 — 2026-10-09

A document's version is meant to say that it changed. The rule said to judge a
bump by policy impact and also not to bump "mechanically on every edit", which
reads two ways, and the history holds both.

- § *Document versioning* now says it once: a document whose text changes in a
  release is bumped exactly once in that release, at the level of the largest
  change it took. Once per edit or per commit is what "mechanically" meant;
- **document versions**, a new check, enforces that count where the set lives.
  It compares every policy document with the previous release: the oldest
  commit, walking first parents back from HEAD, in which that release stood on
  top of the changelog. Every commit of the release being made is held to one
  bump, committed or not, before its entry was written or after;
- a merge that brought the previous release in is read with care, because
  review found both ways of reading it wrong. A branch at work that merged the
  release in holds its own work in the merge, so taking the merge passed an
  unbumped change. A release landing on the base branch after an entry-less
  change holds that change, so taking the other side failed a correct bump.
  Where the merge's `.ai/` equals that side's, the readings agree. Where it
  does not, the base branch decides, read from `origin/HEAD`, and without it
  the check says it cannot tell. A release on top on both sides of a merge is
  reported the same way. At the real merge `f3e0bf1` the check now fails on
  the branch, where the first version had nothing to compare with;
- the changelog's own version describes its rules, not its record, so it is
  compared without its release entries. It goes to 1.2.0 for this rule, its
  first bump since 2026-09-03;
- a check that cannot ask its question now prints `[SKIP]` and why, instead of
  having only PASS to say. This one does so without a full git history, and in
  an adopter, which cannot fix the set's history;
- replayed over this set's history, the check fails four releases — 2.3.0,
  2.3.1, 3.1.0 and 3.2.0, six document–release pairs — and passes every release
  since. One of the six, `CORE.md` in 2.3.0, was changed while resolving a merge
  conflict, so a commit-by-commit look never sees it. Three later commits that
  changed an already-bumped document are review fixes inside their release, and
  the rule as decided allows them;
- the 3.3.0 entry said § *Paid automation* arrived in 3.2.0. It arrived in
  3.1.0, in `1b40d20`, and the entry now says so;
- twenty tests, with each branch of the check broken on purpose and seen to
  fail. They run in an adopter too: the copy is made to look like the set's
  home rather than skipped.

MINOR: a rule's meaning is settled, as one of the two readings its old text
allowed, and a check added. The check looks back one release, so no earlier
release is reopened.

---

## 3.6.0 — 2026-10-09

`--upgrade` overwrites the set's policy documents, which is its job. One that
an adopter had edited went with them, visible only in a diff nobody was told to
read. Forty upgrades are queued, of repositories this set has never read.

- **`[local]`** now names each policy document the upgrade replaced that was
  edited in the target, before the check results. A document whose text
  differs from the set's is stale if its version is lower, and edited if it is
  the same or higher. The second case includes an adopter who followed the
  versioning rule and bumped it, who would otherwise have been the one losing
  an edit silently;
- the report prints what it cannot tell. A set change that never moved its
  version looks like a local edit, and several did before the versioning rule
  was settled. A local edit to a document the set has since bumped looks stale.
  Read every flagged diff; an unflagged one is not proof;
- `.ai/CHANGELOG.md` is not judged. It grows every release while its own
  version has stayed at 1.1.0 since 2026-09-03, so every older copy would be
  flagged. A test removes the exemption and watches its test fail;
- measured on a real adopter: an untouched upgrade from 3.4.1 flagged nothing;
  the same repository with a local edit to `REVIEW.md` flagged exactly that
  file;
- the upgrade and adoption reports printed after the check results whenever
  output was piped, because a parent's buffer flushes at exit, after the
  child's. A warning meant to be read before the result came after it. Both now
  flush first;
- six tests: three that the edit is named (unbumped, bumped, and the caveat)
  and three that nothing else is (an older document, an untouched upgrade, an
  older changelog).

MINOR: `--upgrade` reports something it did not.

---

## 3.5.1 — 2026-10-09

`CLAUDE.md` told every Claude run to "enter through the **Dispatcher** first",
and there is no Dispatcher for Claude. The only one, added in 3.2.0, is a Codex
agent pinned to a GPT model. A Claude run read that line at start and could not
follow it. That is `.ai/EVOLUTION.md` § *When a run must record a lesson*,
trigger 3: a rule ambiguous at the moment of use, which the next run would
resolve differently.

- `CLAUDE.md` now says what a Claude run does instead: the Manager reads intent
  first (`.ai/MANAGER.md` duty 1), then risk (duty 2). The line names the
  Dispatcher's absence outright, so a later edit that copies the Codex entry
  file back cannot do it unnoticed. The file is 11 characters shorter, which
  matters because it is read on every turn;
- `HARNESS.md` § *Dispatcher and Codex model routing* said "every request
  enters through the low-cost Dispatcher". It now says that of Codex, and that
  a Claude run reads the request through the Manager's own duties. Its model
  table also no longer lists the Dispatcher as a Claude role to translate;
- the independent review caught the first draft overclaiming. It said
  classifying "intent, risk, size" was the Manager's first step, but
  `MANAGER.md`'s first duty is intent alone. Each sentence now names only what
  the duty it cites says;
- `AGENTS.md` is unchanged. For Codex the line is true.

PATCH: Codex runs are unaffected, and for Claude the requirement could never be
met, so nothing a run could actually do is now required or forbidden that was
not before.

---

## 3.5.0 — 2026-10-09

The set's two test suites now pass inside a repository that adopted the set, so
an adopter can learn whether its own copy of the checks works. That had never
been possible. At 3.4.1 the suites reported 25 failures in a real adopter
while every check passed, and the tools README told adopters not to run them.

The 25 were not one thing:

| Failures in the adopter | What they were | Release |
| --- | --- | --- |
| 4 | a real defect: dangling references inside capabilities passed | fixed in 3.4.2 |
| 11 | a real defect: the copy carried the source's own records | fixed in 3.4.3 |
| 1 | a fixture that removed a file an adopter never had | fixed here |
| 8 | tests whose subject exists only at the set's home | listed here, each with its reason |
| 1 | a **known blind spot** of the reference check in an adopter | listed here as one, tracked as R8 |

- **`NEEDS_THE_SETS_HOME`**, at the top of each suite, names every test skipped
  in an adopter and why. Each one prints its reason there. At the set's home
  none is skipped, so nothing is tested less here than before;
- an entry is allowed for one of two reasons, and says which:
  1. its subject exists only at the set's home — that the set still ships its
     capabilities, or GitHub's "Use this template", which copies only the set's
     own repository;
  2. it exposes a known blind spot, and names the roadmap item that owns it.

  A skip is never a fix nobody does;
- **the independent review of this change caught it misclassifying a test.** It
  had listed `test_codex_entry_references_are_checked` as home-only, reasoning
  that an adopter may lack the capability. In fact the check excuses a
  reference into a capability folder in an adopter even when the folder is
  present. A dangling pointer from `AGENTS.md` into a present `.codex/agents/`
  passes there. The entry now says so, and points at R8 — an item in the
  set's own `.ai/ROADMAP.md`, which stays at the set's home;
- R8 is proposed, not fixed here, because closing the gap has a cost. Excusing
  only an absent folder would make an adopter that removed one capability but
  kept its folder fail on the set's own documents, which name seven capability
  files individually and are rewritten on every upgrade. Choosing between the
  two failure modes changes what a check enforces, which is the user's call;
- the same review found a vacuous pass. `test_from_template_removes_only_the_marker`
  passed in an adopter without the mode ever running, because the marker was
  never there to remove. It now asserts that the mode ran, and is listed as
  home-only;
- **3.4.2 overstated its fix.** It said capabilities "are no longer tolerated as
  unchecked". That holds for a pointer written *inside* a capability. A
  reference *into* a capability folder from elsewhere is still unchecked in an
  adopter, as above. The comments that repeated the overstatement in the
  checker and its test are corrected;
- measured in a real adopter: guard suite OK with 4 skipped, adoption suite OK
  with 6 skipped, checks green. At the set's home both pass with none skipped;
- the tools README now tells adopters to run the suites, and records the blind
  spot under § *What they do not answer*.

MINOR: the suites' scope widens to every adopting repository.

---

## 3.4.3 — 2026-10-09

A run at the set's home has to write a roadmap there; that is step one of the
`auto-dev` skill. Doing so would have handed that roadmap to every repository
adopted or upgraded afterwards. Adoption copies `.ai/` wholesale, and nothing in
the copy knew which files a repository owns.

- **two definitions, and the copy used neither.** The checker lists instance
  files in `INSTANCE_PATHS` and `INSTANCE_DIRS`, to exempt them. `adopt.py`
  listed them again in `PRESERVED` and `PRESERVED_DIRS`, to restore them after
  an upgrade, and `PRESERVED_DIRS` was used nowhere. The copy consulted neither
  list, so a roadmap, a report, or a filled-in context at the source reached
  the target. `adopt.py` now reads the checker's definition, skips every
  instance file when it copies, and builds `PRESERVED` from the same list. The
  inert second definition is gone;
- **the upgrade report no longer claims a file it created.** It printed
  `[keep] … is this repository's` for every preserved path that existed
  *after* the copy, including a roadmap the copy had just put there. It now
  reports only the files the target had before;
- the reports directory's `.gitkeep` still travels: it is the placeholder that
  makes the directory exist, not a report;
- **reading the checker's definition is an import, and Python caches imports.**
  The first push of this change carried a compiled cache of the checker, written
  beside it by the first run and swept into the commit. In an adopter the same
  run would leave that cache in their tree, and the copy would carry it from
  this repository into the next adopted one. `adopt.py` no longer writes
  bytecode, the copy skips any cache it finds, and this repository now ignores
  one. A test runs the tool and asserts that no cache is left or carried;
- four tests, written first and failing first: adoption and upgrade from a
  source that carries its own context, lessons, roadmap and report, the
  `[keep]` claim with and without a roadmap of the target's own, and the
  bytecode cache;
- inside a real adopting repository, the adoption suite went from 16 failures
  to 5. That is the share this copy caused. The 5 left all exercise
  `--from-template`, which needs the set's home, and are the next roadmap item;
- `README.md` stops saying this repository ships no filled-in instance, because
  its own roadmap is one. It says instead that instance files never travel;
- **`LESSONS_FROM_PRACTICE.md` entry 30**, recorded for 3.4.2. A reference
  check passed in every downstream repository while broken, and its test
  suites had only ever run at home, the one place the defect could not appear.

Policy impact is none — instance files always belonged to the repository that
holds them — so this is a PATCH.

---

## 3.4.2 — 2026-10-09

The reference check had been passing while broken in every repository that
adopted the set. A pointer to a missing file, written inside an agent definition
or a skill, failed the check at the set's home and passed in every adopter.
Found by running the set's own test suites inside a real adopter, and confirmed
by an independent review that reproduced it.

- the resolver guesses a short reference relative to the document that wrote
  it — `CORE.md` from inside `.ai/`. It made that guess for *every* reference,
  including ones that name a directory, like .ai/MISSING.md. From inside
  `.claude/agents/` the guess is .claude/agents/.ai/MISSING.md, and anything
  under a capability folder is tolerated in an adopter, because an adopter may
  lack that capability. So the resolver gave up before it tried `.ai/`, and
  reported nothing;
- the guess is now made only for a reference written relative to its document:
  a bare name, or one starting `./` or `../`. A reference that names its own
  directory means that directory. Capabilities stay tolerated as *absent* in
  an adopter, and are no longer tolerated as *unchecked*;
- the independent review of this fix found the same hole one shape over: a
  sibling written bare or with ./ from inside a capability folder was still
  excused as an absent capability. A guess beside a document that itself
  lives in a capability folder is no longer excused that way, because the
  folder is evidently there and a missing neighbour is a broken pointer;
- a test places a dangling reference at each place a capability can live
  (Claude agents and skills, Codex agents, and the Codex skill and its
  metadata), in three shapes (a path naming a directory, a bare sibling, a ./
  sibling), in the shape of an adopted repository. Before the fixes, all
  fifteen passed unseen. In a real adopter, the fixed check stays green on its
  unmodified tree, catches every injected reference, and still tolerates
  capability folders the adopter removed;
- the defect came in with 2.4.0, which made capability folders tolerated in
  adopters, and became reachable in 2.5.0, when capability files began to be
  scanned for references.

Policy impact is none — references were always required to resolve,
everywhere — so this is a PATCH. An adopter that upgrades may see
cross-reference failures it has never seen. Each one is a real dangling pointer
that the check had been hiding.

---

## 3.4.1 — 2026-09-27

Ran the first upgrade against a repository that had adopted the set, and its
two test suites reported two dozen failures while every check passed. Nothing
was broken: the suites adopt *from* the tree they run in, so inside an adopter
they copy that repository's filled-in context into a scratch directory and then
report on it. The same failures were there before the upgrade, at 3.2.0.

- `.ai/tools/README.md` now says which of the three commands runs where:
  `check_policy_set.py` is the guard an adopter runs and it passes there; the
  two suites are the set's own development tools and belong where
  `LESSONS_FROM_PRACTICE.md` is. The file had listed all three as if they were
  interchangeable, which is how an adopter reads two dozen failures as
  breakage;
- recorded the matching blind spot: the checks answer whether the set works in
  an adopting repository, the suites answer whether the *checks* work, and
  nothing yet verifies an adopted tree's tooling from inside that tree.

Wording only — no rule changed, and no behaviour. It is here because the next
thing this release does is copy those instructions into forty repositories.

---

## 3.4.0 — 2026-09-27

Asked to propagate a release to the 41 repositories that have adopted this set,
and found the set had no way to do it. `adopt.py` starts a repository; nothing
moved an existing one forward. The obvious substitute — run adoption again —
destroys something every time.

- **`adopt.py --upgrade --into <repo>`** refreshes the policy documents and the
  tools in a repository that already has them, and hands back everything that
  repository owns: `.ai/PROJECT_CONTEXT.md`, `.ai/memory/PROJECT_LESSONS.md`,
  `.ai/ROADMAP.md`, `.ai/reports/**`, and `.ai/tools/portability-denylist.txt`;
- **the denylist is why the mode exists.** Adoption copies `.ai/` wholesale and
  the set ships its own denylist, so a second run over a lived-in repository
  replaces that project's names with this set's seeds. Its portability check
  then keeps passing while proving nothing about the repository it runs in —
  the failure the seeds' own comment warns about, arriving by the one path
  nobody had tried. Reproduced first: the test that asserts the loss runs
  before the one that asserts the fix, so the mode cannot quietly stop
  preventing it;
- it refuses a tree that never adopted the set, because adoption needs the
  project's facts and inventing eleven of them per repository is the failure
  this set exists to prevent; it refuses the set's own home; and it refuses to
  be combined with `--from-template`, which is a different job;
- it prints the version it moved from and to, and ends by running the checks in
  the upgraded tree. Over dozens of repositories that line is the only way to
  see which ones actually moved;
- **capabilities are not replaced.** One the repository already has stays,
  because it may be theirs — the promise adoption already made. But one whose
  content differs from the set's is now reported `[stale]`, because silence
  there meant an improved agent definition never reached an adopter and nobody
  could see it. `--refresh-capabilities` replaces them and loses local changes,
  which is why it is not the default;
- eight tests, including the reproduction above and both refusals.

The gap this fills was invisible from inside the set's own repository: every
check here passes whether or not adopters can be moved forward, because nothing
here is an adopter. It took being asked to update 41 of them.

---

## 3.3.0 — 2026-09-26

Read a multi-agent operating system someone else had written for their own
repository, and took the six rules this set did not already have. Most of that
document was already here in different words; where the two disagreed, the set
kept its own, and the disagreements are listed at the end.

The largest gap was the one a self-improving set is least able to see in
itself.

- **`EVOLUTION.md` § *What a run may change on its own*** — three levels,
  decided by what a change lets *later* runs do. **Record** (project memory,
  the playbook, the roadmap, reports) a run may edit on its own; **Rule** (the
  policy documents and the checks) needs the user to ask or approve; and
  **Direction** — what the product is and is not, and the list `CORE.md` §
  *Autonomy* says to ask about, including the table itself — is never a run's
  to change. The size of the edit does not decide the level: one sentence
  turning a MEDIUM review into a LOW is a Rule change. A set that improves
  itself can lower its own gates, and a run under pressure has every reason
  to;
- **`EVOLUTION.md` § *Activity is not a result*** — agent count, tool calls,
  investigation, tokens spent and report length measure effort. The measure
  that is an outcome is **cost per accepted change**. A strategy that halves
  the agent count and doubles the rework made the number that matters worse,
  and so did one that bought efficiency with a regression;
- **`EXECUTION.md` § *The size was a hypothesis*** — the size was judged when
  the least was known, so work outgrowing it is normal and continuing at the
  old size is the defect. A Worker whose Pack turns out larger returns
  `FOUND / WRONG / RISK / NEEDS` and stops, rather than widening its own
  ownership; the Mission Packet template now carries that as a
  `RETURN INSTEAD IF` contract beside `DONE WHEN`. S → M → L is an outcome,
  not a failed estimate;
- **`REPOSITORY.md` § *The local base branch is a mirror*** — it tracks the
  remote and holds nothing of its own, so syncing it is only ever
  `--ff-only`, and a sync that cannot fast-forward stops and reports instead
  of resolving itself. A plain `git pull` there writes a merge commit
  recording a divergence nobody intended, on the branch every other branch is
  cut from, and it looks deliberate afterwards. This run reached exactly that
  situation on `stable` and was stopped before the pull ran;
- **`REPOSITORY.md` § *Deleting a branch*** — the four conditions, and `-d`
  as the check rather than the convenience: it refuses a branch whose commits
  are not in the history it is being deleted from. **Automation never uses
  `-D`**, which deletes precisely the branch the check would have saved and
  says nothing;
- **`EXECUTION.md`**, two smaller ones: each worktree builds into its own
  directory, because two sharing one overwrite each other's artefacts and the
  failure reads as a source defect in whichever built second — a compiler
  cache may still be shared, being keyed by content; and a Manager session is
  replaced at a **task boundary**, never on a clock, into the same branch and
  worktree.

`REPOSITORY.md` goes to 1.2.0, and that one bump covers two rule additions:
3.1.0 added § *Paid automation* to it without moving the version, which the
checks do not catch — `.ai/tools/README.md` § *What they do not answer* already
records that a bump's correctness is a judgement. Recorded rather than
back-dated.

**No new check.** None of the six can be read from structure: nothing in a
file says who approved an edit, whether a size was re-judged, or which command
a run reached for. They are stated in their owning documents and that is all
the enforcement there is — `.ai/tools/README.md` § *What they do not answer*
is where that kind of limit belongs, and this is a large addition to it.

These rules were not paid for by a defect in this repository, so none of them
becomes a `LESSONS_FROM_PRACTICE.md` entry. They are adopted because the gap
was real, not because this project proved it.

Its role-to-model table needed nothing: 3.2.0 had already added
`HARNESS.md` § *Codex capabilities and model routing*, which maps the same
three tiers the document names. The Claude agent definitions still pin no
model, and a reviewer's is still decided against the implementer's
(`REVIEW.md` § *Cross-agent independence*).

Deliberately not taken: a second document layout for `.ai/`;
`Easy / Normal / Difficult` beside the existing `S / M / L`; a per-Worker
child-branch hierarchy, where one write owner per path already prevents the
conflict more cheaply; and a separate git-only agent role, whose forbidden list
is `REPOSITORY.md` and `CORE.md` § *Autonomy* already.
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

Judge the bump by policy impact, **once per release**: a document whose text
changes in a release is bumped exactly once in that release, at the level of
the largest change it took. Not once per edit or per commit — that is what bumping
mechanically means. Do not bundle a `MAJOR` reversal into an edit described as
wording.

This file's own version describes its rules — the sections above and below the
release entries — not its record. Adding a release entry does not bump it.

Where the set lives, `.ai/tools/check_policy_set.py` compares every document
with the previous release and fails one whose text changed without a bump, or
that was bumped more than once. Whether the level is right stays a judgement.

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
