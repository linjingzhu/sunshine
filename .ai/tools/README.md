---
doc_id: ai-tools
version: 2.7.0
canonical_path: .ai/tools/README.md
updated: 2026-10-10
---

# Tools

Structural guards over the policy set.

```bash
python3 .ai/tools/check_policy_set.py        # the checks
python3 .ai/tools/test_check_policy_set.py   # prove each one fails on purpose
python3 .ai/tools/adopt.py --into <repo>     # start a repository from this set
python3 .ai/tools/adopt.py --from-template   # finish a "Use this template" repo
python3 .ai/tools/adopt.py --upgrade --into <repo>   # move an adopter to this version
python3 .ai/tools/propagate.py --clones <dir>       # at the set's home: send a release to every subscriber
python3 .ai/tools/test_adopt.py              # prove an adopted repo starts green
```

**All of them run in a repository that adopted the set, and pass there.** Run
the two test suites in an adopter too: they are how that repository learns
whether its own copy of the checks works. They are the only thing that ever
did. The one defect they found there — a guard passing while broken in every
adopter — could not appear at the set's home, where they had always been run.

A few tests exercise something that exists only at the set's home: that the
set still ships its capabilities, and GitHub's "Use this template". Each is
listed once, with its reason, in `NEEDS_THE_SETS_HOME` at the top of its suite.
In an adopter each is skipped and prints that reason; at the set's home none
is skipped. A test belongs in that list only for a reason it cannot run
elsewhere, never to make a suite pass.

One entry is a different kind and says so: a **known blind spot**. It names the
roadmap item that tracks it, so the skip is a debt somebody owns, not a fix
nobody does. That is the reference check's tolerance below.

Python 3.11 or newer, standard library only, no dependencies, no configuration
beyond the denylist. Native Codex agent definitions are parsed with `tomllib`.

## What each check asks

The script prints the question beside every result, because a result is
evidence only for the question its check actually asked — `.ai/CORE.md` §
*The question each result answers*. A check that could not ask its question
prints `[SKIP]` and why, and does not count as passed.

| Check | Question it answers |
| --- | --- |
| front matter | Does every policy document carry the four fields, with a unique `doc_id` and a `canonical_path` matching where it lives? |
| cross-references | Does every referenced file, and every pointer written as a backticked path followed by `§ *Section*`, resolve to something that exists? |
| one owner per heading | Is any section heading claimed by two policy documents? |
| portability | Does any declared project-specific term appear outside the files allowed to know what the project is? |
| changelog | Does every release entry carry a version, a date and at least one improvement, newest first and each version once? |
| project context | Does the filled-in `.ai/PROJECT_CONTEXT.md` carry every fact the set reads by name, with no placeholder or template line left — and, where no instance exists, does the template still declare every key? |
| document versions | Where the set lives: has every policy document whose text changed since the previous release been bumped, exactly once? |
| subscribed copy | In an adopter with `.ai/set.lock`: does every file the lock names still hold what the set delivered? |
| capability definitions | Does every committed capability carry a `name` matching its file (agent) or folder (skill), and a non-empty `description`? Does each native Codex agent parse as TOML and include non-empty `developer_instructions`, with valid optional model and sandbox fields? |

## What they do not answer

- **Whether a rule is right.** These read structure, not argument.
- **Whether a version bump was the right size.** Policy impact is a judgement.
  The check sees that a document whose text changed since the previous release
  was bumped, and bumped once — `.ai/CHANGELOG.md` § *Document versioning*. It
  reads the previous release from git: the oldest commit, walking first parents
  back from HEAD, in which that release stood on top of the changelog. A merge
  that brought the release in and changed `.ai/` beyond it is either the
  release landing on the base branch or a branch at work taking it in, and
  only the base branch tells which: it is read from `origin/HEAD`, which
  `git remote set-head origin --auto` records. It prints `[SKIP]` with the
  reason, never a pass, without a full history, without `origin/HEAD` where
  that merge needs it or before it has seen that merge, with the release on top on both sides of a merge, and in
  an adopter, where the set's history is not there to fix. It sees nothing
  before the previous release.
- **Whether a run report's pointers still resolve.** A report under
  `.ai/reports/` records what was true when it was written, and the reference
  check does not read it: a file it named may have gone since, and the only
  fix would rewrite the record. Every other document, instance files
  included, is read.
- **Whether a pointer stayed a pointer.** "One owner per heading" catches a rule
  re-added under its own heading, which is how re-duplication usually happens.
  Prose that restates another file's rule *without* reusing its heading is not
  detected, and stays a convention enforced by review.
- **Whether a project-specific fact leaked using no denylisted word.** The
  denylist is a list of proper nouns someone wrote down on purpose.
- **Whether a changelog entry is true, or its version level right.** The check
  sees that a version, a date and improvements are present and ordered. Whether
  the improvements listed are the ones that shipped is a judgement.
- **Whether the facts in the project context are true.** The check sees that
  `test_command` has a value; whether that command runs the tests is answered
  by running it.
- **Whether a capability definition is any good.** The check sees that a packet
  naming the agent, or a run naming the skill, would find it. Whether the
  instructions inside produce a useful search, a review worth reading, or a
  roadmap worth building is answered by using it.
- **Whether a skill is invoked when it should be.** Nothing structural can see
  that. A skill that must not start on its own says so in its own text, and
  whether a run honoured it is visible only in what the run did.
- **In a repository adopted before 4.0.0, whether a reference into a
  capability folder resolves.** Without a lock nothing tells a capability the
  adopter removed from one that never existed, so every such reference is
  excused there. In a subscriber the lock decides: only a capability it
  records as removed, or as kept because the repository holds its own in that
  place, is excused, and every other dangling reference fails as it does at
  the set's home. A pointer written *inside* a capability is checked either
  way.
- **In a subscriber, files the lock does not name.** A document added to `.ai/`
  there is not reported, and a capability the repository already had before
  adoption is its own. A repository adopted before 4.0.0 has no lock until its
  next upgrade, and the check prints `[SKIP]` there.
- **Whether a test listed in `NEEDS_THE_SETS_HOME` really needs it.** The suite
  checks that every listed name is a real test, not that its reason is true.
  Whether a skip is justified is a reviewer's question, which is why the list
  is short and each entry says why.
- **Whether a run stayed inside what it was allowed to change.** No file
  records who approved an edit, so `.ai/EVOLUTION.md` §
  *What a run may change on its own* is enforced by the report and the diff a
  person reads, not here. The same holds for the rest of that class: whether a
  size was re-judged when the work outgrew it, whether a Worker returned
  instead of widening its ownership, and which git command a run reached for.
  These are the largest unchecked area in the set, and they are unchecked
  because structure cannot see intent.

Guards here read structure — front matter, headings, references, paths — rather
than prose, per `LESSONS_FROM_PRACTICE.md` entry 14: a check that greps
documentation teaches contributors to avoid words, not defects. The portability
denylist is the deliberate exception, and it matches names rather than rules.

## Where the checks look

`.ai/**`, `CLAUDE.md`, `AGENTS.md`, the Markdown capabilities under `.claude/**`
and `.agents/skills/**`, native `.codex/agents/*.toml`, and skill metadata in
`.agents/skills/auto-dev/agents/openai.yaml`, everywhere. The root `README.md` and
`LESSONS_FROM_PRACTICE.md` are read only where the set itself lives (detected
by `LESSONS_FROM_PRACTICE.md` being present): in a repository that adopted the
set, the root `README.md` is the adopter's own and names its product, and the
set's pointers at those two files resolve to files that were deliberately not
copied.

`.claude/agents/`, `.claude/skills/`, `.codex/agents/` and `.agents/skills/`
are checked where they exist and
reported as nothing to check where they do not — except at the set's home,
where their absence is a failure: the set ships those definitions, and
`HARNESS.md` points at them by path. An adopter who deleted or replaced them
has made a choice, not a mistake. The Codex entry point must also remain
present at the set's home. Codex agents use TOML rather than Markdown front
matter; their model is optional so a run can select the appropriate reviewer.
These checks do not prove a configured model is available to the current user.

Their **references** are read everywhere, along with the policy documents'. A
capability definition is mostly pointers into `.ai/`, so a section renamed in
`REVIEW.md` breaks a skill exactly as it breaks a policy document, and nothing
else would notice. Backticked `.toml` and `.yaml` paths are resolved alongside
Markdown paths. Portability checks also read the Codex entry point, native
agents, skills and skill metadata.

## Starting a repository from this set

`adopt.py` copies what travels — `CLAUDE.md`, `AGENTS.md`, `.ai/`, and the
capabilities under `.claude/agents/`, `.claude/skills/`, `.codex/agents/` and
`.agents/skills/` — writes the two instance files from
their templates with the instruction lines removed, fills the facts given as
`--set key=value`, and then runs the checks against the new tree.

A capability or Codex entry point the target already has is **kept, never
written over**, with or without `--force`: an existing `AGENTS.md`, agent file
or skill directory belongs to the adopter. An existing skill directory is
kept as a unit, including its metadata, so the packaged skill metadata
cannot change how the adopter's skill is invoked. The run prints `[keep]` for
each packaged file it left alone. It does not copy or modify machine settings
or the adopter's Codex configuration.

`.ai/ROADMAP.md` is not written by adoption. It is an instance file like the
project context — the checks exempt it from front matter and from the
portability denylist, because a roadmap names one product's features on
purpose — and the `auto-dev` skill creates it when a run is told to.

**No instance file is ever copied**, by adoption or by upgrade. The set's home
can carry its own roadmap and run reports, and they stay there: the copy skips
every file the checker counts as an instance, and both tools read that from
one list, `INSTANCE_PATHS` and `INSTANCE_DIRS` in `check_policy_set.py`. When
they kept two lists, the copy consulted neither, and a roadmap written here
reached every repository adopted afterwards.

It ends in one of two states, never in between:

- **green**, when every fact was supplied — the new repository starts passing;
- **exit 1 with every unanswered fact named**, when they were not. A context
  that looks finished and is not is the failure this whole set exists to
  prevent, so a half-filled one is loud.

What it copies is exactly what § *Where the checks look* assumes: copying
`LESSONS_FROM_PRACTICE.md` as well would make an adopting repository look like
the set's own home, and the checks would start reading the adopter's `README.md`
as if it were this one's. Adoption does not install GitHub Actions workflows
or alter workflows already in the target repository. An existing instance file
is kept, not overwritten, unless `--force` says otherwise.

## Upgrading a repository that already adopted the set

`--upgrade --into <repo>` refreshes the policy documents and the tools in a
repository that already has them, and hands back everything that repository
owns:

```text
.ai/tools/portability-denylist.txt
.ai/memory/MANAGER_PLAYBOOK.md
.ai/PROJECT_CONTEXT.md
.ai/memory/PROJECT_LESSONS.md
.ai/ROADMAP.md
.ai/reports/**
```

The manager playbook is delivered once, like the denylist, and then belongs to
the repository: it ships with nothing but its promotion rule, and a repository
writes its candidate lessons into it.

The dangerous one is the **denylist**, and it is why this mode exists. Plain
adoption copies `.ai/` wholesale and the set ships its own denylist, so running
it a second time over a lived-in repository replaces that project's names with
this set's seeds. The portability check then goes on passing while proving
nothing about the repository it is running in — which is exactly what the
seeds' own comment warns about. A test asserts that defect before the fix, so
the mode cannot quietly stop preventing it.

It prints the version it moved from and to, refuses a tree that never adopted
the set (adoption needs the project's facts, and inventing them is the failure
this set exists to prevent), refuses the set's own home, and ends by running
the checks in the upgraded tree.

**Capabilities are not replaced.** An agent definition or skill the repository
already has stays, because it may be theirs — but one whose content differs
from the set's is reported as `[stale]`, since the repository will go on
running the older definition. `--refresh-capabilities` replaces them and says
so; it loses local changes to those files, which is why it is not the default.

**Policy documents are replaced, and a local edit to one is named first.** An
upgrade's job is to move the set's documents forward, so it overwrites them. A
document whose text differs from the set's is either *stale* or *edited*:

- its version is lower than the set's → stale, replaced without comment;
- its version is the same or higher → edited in this repository, reported as
  `[local]`. That includes an adopter who followed the versioning rule and
  bumped it. That adopter must not be the one whose edit disappears silently.

Read every `[local]` file's diff before committing. The report says what it
cannot tell. A set change that never moved its version looks like a local edit;
several did, before the versioning rule was settled. A local edit to a document
the set has also bumped since looks stale. `.ai/CHANGELOG.md` is not judged at
all: it grows every release, while its own version moves only when its rules
do, so an older copy with the same rules would be named.

## The subscription

Since 4.0.0 an adopting repository subscribes to the set instead of owning a
copy of it. Adoption and every upgrade end by writing `.ai/set.lock`: where the
set came from (`source`), its `version`, the `commit` delivered, and a SHA-256
digest of every file delivered, with line endings normalised. Those files —
`CLAUDE.md`, `.ai/` less the repository's own files, and each capability the
repository holds exactly as the set ships it — are now the set's, not the
repository's:

- the *subscribed copy* check fails on any of them edited or, for a policy
  document, removed. Removing a capability is still the repository's choice;
- an upgrade's `[local]` is exact: the lock says what was delivered, so any
  difference is an edit, and the edited file is replaced — a subscribed
  capability included, like a policy document. Without a lock the upgrade
  falls back to comparing versions, as above, and says what that cannot tell;
- a capability the repository removed is recorded as `removed: <path>` and
  is not delivered again, by that upgrade or any later one. One the set ships
  but the repository holds its own version of, or lacks inside its own skill,
  is recorded as `kept: <path>`;
- the cross-reference check reads both: a pointer into a capability folder is
  excused only when it names a capability recorded as removed or kept, or one
  delivered and since taken out.

A rule only one repository needs goes in its project context, under the
heading `.ai/PROJECT_CONTEXT.template.md` § *Local rules* describes. A rule
every repository would want belongs here, at the set's home.

## Propagating a release

The set's home lists its subscribers in `.ai/SUBSCRIBERS.md`, an instance file
that never travels: one `owner/repo  base-branch` line each, inside a fenced
block, optionally followed by `hold: <why>`. After a release merges,
`propagate.py --clones <dir>` takes each subscriber's clone from `<dir>/<repo>`,
cuts `claude/set-<version>` from its base branch, runs `adopt.py --upgrade`, and
commits. It writes the pull request body beside the clone as `<repo>.pr.md`,
with the upgrade's report and the check result, and prints one line per
subscriber: `upgraded`, `current`, `hold`, `no clone` or `failed`.

Nothing is pushed without `--push`, so a first run shows every upgrade before
any of them leaves the machine. Opening the pull requests is left to whoever
runs it, since that needs the forge's credentials rather than git's. Whether
each one merges is that repository's decision under its own repository mode.

## GitHub's "Use this template"

That button copies **every tracked file**, including the two `adopt.py`
deliberately leaves behind. One of them breaks the result: with
`LESSONS_FROM_PRACTICE.md` present, § *Where the checks look* treats the new
repository as the set's home and reads its `README.md` as the set's own. The
checks fail on the first run, in a repository whose owner has changed nothing.

`--from-template` finishes such a tree, in place:

```bash
python3 .ai/tools/adopt.py --from-template --name "My Project" --set ...
```

- removes `LESSONS_FROM_PRACTICE.md`, which is the entire correctness fix —
  once it is gone the checks ignore `README.md` completely;
- reseeds `portability-denylist.txt` from `--name`. The shipped seeds are
  another project's names and prove nothing about yours; without `--name` it
  says so rather than leaving them silently;
- **reports** that `README.md` is still this set's front page. It does not
  delete it. A tool that removes a repository's front page because it
  recognised the text is a tool nobody should run twice;
- then writes the instance files and runs the checks, exactly as a normal
  adoption does.

It refuses a tree that has no `LESSONS_FROM_PRACTICE.md` to remove, rather than
guessing at something that looks close enough.

## Adopting this

`.ai/tools/` travels with the set. Configure the denylist and run the tools
locally:

1. **`portability-denylist.txt`** ships seeded with the names removed when this
   set was separated from the project that produced it. Replace them with your
   own product and organisation names. An empty denylist makes that check
   vacuous, and the script says so rather than passing quietly.
2. **Local verification.** Run the three check commands at the top of this
   document before submitting changes. The set no longer ships a GitHub Actions
   workflow or the `--with-ci` adoption option.
