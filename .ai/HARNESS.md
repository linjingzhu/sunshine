---
doc_id: ai-harness
version: 1.3.0
canonical_path: .ai/HARNESS.md
updated: 2026-09-25
---

# Operating Harness

*Most of this file is convention adopted from operating agents, not a rule some
defect paid for. Where an entry in `LESSONS_FROM_PRACTICE.md` stands behind a
rule, it is named. Treat the unnamed ones as the set's current best practice and
demote any that fails in use.*

The policy set says what a run must do. This file says what the run must be
standing on before it starts, and where the configuration that provides it
lives.

## What the harness owes a run

Before the first edit, these are known or the run says so:

- the repository is checked out at a named base commit;
- the commands in `.ai/PROJECT_CONTEXT.md` § *Facts the checks read* actually
  run here — `test_command`, `lint_command`, `build_command`, `runtime_gate`;
- what network access exists, and what is blocked;
- what the run may do without asking — the permission mode, and any allowlist;
- where reports and the owner ledger are written.

A run that finds one of these missing **names it and stops on that point**. It
does not substitute a weaker check and report the weaker one's result: that is
`.ai/CORE.md` § *The question each result answers* in its most expensive form.

## The entry file is read every turn

`CLAUDE.md` and `AGENTS.md` are contracts, not manuals. Every line is paid for
at every turn of every run, so each holds only:

- the check that the set has been adopted here,
- the role,
- what to read at the start, and what to load when a trigger fires,
- the pointers that make the rest reachable.

**A section that summarises another document does not belong there.** It costs
tokens on every turn, it drifts from what it summarises, and the heading check
cannot see it because a summary rarely reuses the heading. Set 2.2.0 removed one
such list that had grown to seven lines.

Anything a run needs *sometimes* lives in `.ai/` behind a trigger. Growing
an entry file is the most expensive way to add a rule.

## Where harness configuration belongs

Two kinds of setting get confused because the harness stores them the same way.
Sort them by **whose behaviour they change**:

- **Personal preference** changes how a run talks to *one person* — the
  language it answers in, how terse the reporting is, which model that person
  pays for by default. It belongs in that person's own configuration. Committing
  it makes one contributor's taste into everyone's rule.
- **Project capability** changes what *any* run on this repository can do — an
  agent a Mission Packet names, a workflow others are expected to follow, a
  permission, a hook, an external server. It belongs in the repository.

The test: if a new contributor cloning the repository would behave differently
without it, it is a capability and must be committed. If only their prose would
read differently, it is preference and must not be.

Capabilities are **committed, never left on one machine**. A permission granted
interactively is not a permission the next run has, and an agent definition
that exists only in someone's home directory is a capability the Mission Packet
can name and no one else can run.

| Concern | Where it belongs |
| --- | --- |
| What may run without a prompt | the harness's committed settings file |
| Behaviour at a lifecycle point — before a commit, at session start | a hook in that settings file; policy prose cannot execute |
| A specialised role a Mission Pack assigns | a committed agent definition under `.claude/agents/` or `.codex/agents/`, so the packet can name it |
| A procedure repeated across runs | a committed command or skill, not a paragraph re-typed each time |
| An external capability | a committed server configuration, with its scope written down |

A run that changes any of these says so in its report: they alter what every
later run is allowed to do, which makes them policy, not preference.

The Claude harness ships three such capabilities, and they travel with the set:
`.claude/agents/fast-explorer.md` for breadth-first search whose conclusion is
worth more than its transcript, `.claude/agents/adversarial-reviewer.md` for
the independent review `.ai/REVIEW.md` requires, and
`.claude/skills/auto-dev/SKILL.md`, the repeated procedure this row of the
table describes. Neither Claude agent pins a model — one because the cheapest
capable model wins, the other because independence is defined against whoever
implemented.

A skill that decides **what to build**, rather than how, is started by the user
and by nothing else. The *This mode never starts itself* section in each
platform's `auto-dev` skill holds that rule, because the file that carries the
capability is the only place it cannot be separated from.

## Codex capabilities and model routing

Codex enters through `AGENTS.md`, discovers the skill at
`.agents/skills/auto-dev/SKILL.md`, and discovers the two project agents at
`.codex/agents/fast-explorer.toml` and
`.codex/agents/adversarial-reviewer.toml`. Use a Codex release supporting
standalone agent TOML files. `.agents/skills/auto-dev/agents/openai.yaml` sets
`allow_implicit_invocation: false`, preserving the source skill's explicit
invocation policy; start it with `$auto-dev` only when the user asks.
Project-local configuration must be trusted through Codex's normal project
trust flow before relying on its agent settings; skill discovery alone does
not establish that those settings loaded.

The Claude definitions leave model choice to the harness. For Codex, use this
role-based correspondence when translating a Claude model choice; it is a
local routing convention, not a claim that the models are interchangeable:

| Claude tier / role | Codex choice |
| --- | --- |
| Haiku / bounded exploration | `gpt-6-luna`, high reasoning |
| Sonnet / ordinary implementation | `gpt-6-sol`, medium reasoning |
| Opus / demanding analysis or review | `gpt-6-astra`, high reasoning |

Preserve a user's explicit model choice for the main run. The explorer selects
Luna in its TOML file. For `adversarial-reviewer`, choose Astra unless the
implementer used Astra, then choose Sol. Pass the chosen model and a supported
reasoning effort explicitly when spawning a fresh reviewer; provide only the
review packet, without the implementer's conversation history. The reviewer
file deliberately leaves both settings unset: a model set in a custom agent
file takes precedence over a spawn request and would prevent this choice.

Check the models actually available in the current harness. When a preferred
model is unavailable, choose another available Codex model suitable for the
role; for review, preserve `.ai/REVIEW.md` § *Cross-agent independence*,
including its labelled fallback. Record the models actually used. If the
harness cannot select a model, do not claim the table changed it.

Both agent files request a read-only sandbox and forbid edits in their
instructions. Verify the effective permissions: parent runtime overrides can
supersede the file's sandbox setting. Claude's tool allowlists and `maxTurns`
are not Codex configuration keys; the Codex instructions preserve the read-only
roles and bounded work without claiming those are enforced turn counters.

Format and availability references (checked 2026-09-25):
[Codex subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents),
[Codex models](https://learn.chatgpt.com/docs/models), and
[building skills](https://learn.chatgpt.com/docs/build-skills).

## Tools a Mission Packet may assume

A Mission Packet names the tools its Worker needs, alongside the ownership and
verification it already carries (`.ai/EXECUTION.md` § *Mission Packet
template*).

- A Worker that lacks a named tool stops and reports it. It does not reach for a
  weaker substitute — a grep stands in for a type checker only in the report of
  someone who did not say which they ran.
- A Worker given a read-only role has no write ownership, whatever it finds.
- A subagent spawned to search owns nothing. Its output is a conclusion and the
  paths behind it, not the files it read.

## Reproducing a run

A run that cannot be reproduced cannot be reviewed. Record, with any result that
will be quoted later: the base commit, the exact command, and the tool
versions the command depended on — `LESSONS_FROM_PRACTICE.md` entry 18 is the
build this rule was paid for.
