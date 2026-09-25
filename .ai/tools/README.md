---
doc_id: ai-tools
version: 2.0.0
canonical_path: .ai/tools/README.md
updated: 2026-09-25
---

# Tools

Structural guards over the policy set.

```bash
python3 .ai/tools/check_policy_set.py        # the checks
python3 .ai/tools/test_check_policy_set.py   # prove each one fails on purpose
python3 .ai/tools/adopt.py --into <repo>     # start a repository from this set
python3 .ai/tools/adopt.py --from-template   # finish a "Use this template" repo
python3 .ai/tools/test_adopt.py              # prove an adopted repo starts green
```

Python 3.11 or newer, standard library only, no dependencies, no configuration
beyond the denylist. Native Codex agent definitions are parsed with `tomllib`.

## What each check asks

The script prints the question beside every result, because a result is
evidence only for the question its check actually asked — `.ai/CORE.md` §
*The question each result answers*.

| Check | Question it answers |
| --- | --- |
| front matter | Does every policy document carry the four fields, with a unique `doc_id` and a `canonical_path` matching where it lives? |
| cross-references | Does every referenced file, and every pointer written as a backticked path followed by `§ *Section*`, resolve to something that exists? |
| one owner per heading | Is any section heading claimed by two policy documents? |
| portability | Does any declared project-specific term appear outside the files allowed to know what the project is? |
| changelog | Does every release entry carry a version, a date and at least one improvement, newest first and each version once? |
| project context | Does the filled-in `.ai/PROJECT_CONTEXT.md` carry every fact the set reads by name, with no placeholder or template line left — and, where no instance exists, does the template still declare every key? |
| capability definitions | Does every committed capability carry a `name` matching its file (agent) or folder (skill), and a non-empty `description`? Does each native Codex agent parse as TOML and include non-empty `developer_instructions`, with valid optional model and sandbox fields? |

## What they do not answer

- **Whether a rule is right.** These read structure, not argument.
- **Whether a version bump was correct.** Policy impact is a judgement; the
  check only sees that the field is well-formed.
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
