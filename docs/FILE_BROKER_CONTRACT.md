# File Broker — Scoped Filesystem and Tool Execution Requirements

## Status and scope

This document applies to Sunshine OS on the pinned Chromium revision
`152.0.7977.42` recorded in `config/chromium.version`.

It exists because the module validator already refuses the only filesystem
value that is not `none`:

```
scripts/validate_first_party_modules.py:120
    raise ModuleValidationError(
        f"{source}: scoped file access requires a future file-broker contract")
```

`FILESYSTEM_ACCESS` is `{"none", "user_selected"}`, and `user_selected` is
rejected pending that contract. Until it exists, **no first-party module can
touch a file.** This document is the requirements input for the contract, not
the contract itself.

This wave is **documentation-only**. It adds no downstream patch, no first-party
module, no registry entry, and no localised string.

**Verification.** Two behavioural claims in §3 were executed and are reported as
measured: git 2.43.0 on Linux, in a throwaway repository, deleted afterwards.
Every claim about the pinned Chromium revision is `NOT RUN` — nothing here has
been compiled, launched, or observed in the browser.

---

## 1. Why this document exists now, and not after the broker is designed

The first real consumer of scoped file access is the development control
surface (`dev-os`) once its Git capability is merged into it. A Git client is
not a marginal consumer; it is the consumer that decides whether the contract
holds, because it needs every axis at once:

| What a Git surface needs | What "a few user-picked files" would give it |
|---|---|
| A whole working tree, tens of thousands of files | One file at a time |
| To run `git`, because correctness lives in `git` | Bytes only |
| Minutes-long operations with progress and cancellation | One request, one response |
| Network credentials it must never itself hold | Nothing |
| Operations that destroy work irreversibly | No such concept |

A broker designed without this consumer will be designed against the easy case
and reopened when the hard one arrives. The purpose of this document is to put
the hard case on the table before the shape is fixed.

**Non-negotiable premise.** Git's behaviour is owned by `git`. A module that
reimplements it to avoid asking for execution is not a smaller risk; it is a
Git client that disagrees with the user's own `git`, silently, on the user's own
repository.

---

## 2. Requirements

Each requirement states what the broker must decide. None of them prescribe an
implementation.

### R1 — The unit of a grant is a directory tree, not a file

A repository is a tree. Reading its history touches the object database; showing
a commit's files touches thousands of paths that were never individually chosen.
A per-file grant cannot express "this project", and a prompt per file is not a
consent mechanism, it is a way of training people to click through.

The grant names one root. Everything beneath it is in scope; everything outside
it is not, including symbolic links that resolve outside the root.

### R2 — Access must include execution, and execution must be part of the grant

Reading bytes is insufficient. The broker must be able to run a named program
with an argument vector inside a granted root, and return its exit status,
standard output, and standard error.

This is the requirement most likely to be refused on instinct. Refusing it does
not remove the capability from the product; it moves the capability into the
module, where it is implemented worse and reviewed less.

### R3 — Arguments are a vector, never a shell string

The broker accepts `["clone", "--", url, folder]`, never `clone -- $url $folder`.
A repository path containing a space or a quote must not be able to become a
second command. No shell is involved at any layer.

### R4 — Long operations need progress and cancellation

Cloning a large repository takes minutes. A contract that models file access as
a synchronous call cannot carry it: the surface will either block or lie about
what is happening. The broker must express a running operation, its progress,
and a cancellation that is honoured.

### R5 — Credentials are used by the broker, never handed to the module

The validator already states the rule:

```
scripts/validate_first_party_modules.py:126
    raise ModuleValidationError(
        f"{source}: a module never receives a credential directly")
```

A Git surface must still fetch and push. Therefore the broker performs the
authenticated operation on the module's behalf, holding the credential itself.
The module names *what* it wants done and *for which grant*; it never learns the
secret. A design that satisfies the rule by making authenticated operations
impossible has not satisfied the requirement.

### R6 — Irreversible operations are the broker's concern, not the surface's

Four operations destroy work that no undo recovers:

| Operation | What is lost |
|---|---|
| `reset --hard` | Uncommitted changes. Commits remain reachable by hash; changes do not |
| `clean -fd` | Untracked files. Nothing records they existed |
| `branch -D` | An unmerged branch tip |
| `push --force` / `--force-with-lease` | Commits on the remote, including other people's |

The lesson from the surface that already implements these: **the confirmation
must live where the command executes, not where the button is drawn.** A surface
that renders a confirmation dialog protects only the users who go through that
surface. Once a broker will run an argument vector, the vector is the boundary.

Two further findings from that implementation, both measured there:

- `--force-with-lease` is **not** a sufficient safety mechanism. It refuses only
  when the local remote-tracking ref is stale; immediately after a fetch it will
  overwrite commits the user has never seen. Safety came from showing which
  commits would be destroyed and pinning the lease to the hash that was shown.
- The safe implementation re-derives the plan at the point of execution rather
  than trusting a plan computed by the surface, because the repository can
  change between the two moments.

The contract must decide, explicitly, which of these it adopts:

1. The broker classifies argument vectors and requires a user decision for the
   destructive class, or
2. The grant is scoped to a non-destructive operation set by default, and the
   destructive set is a separate, separately-granted capability.

Silence is the one answer that is not available: a broker that runs any vector
with no classification has made `clean -fdx` a single unaudited call.

### R7 — Grants are enumerable, revocable, and outlive nothing silently

The user must be able to see which roots are granted to which module, when the
grant was made, and revoke any of them. Revocation takes effect on the next
operation, not at the next restart.

### R8 — A vanished root is an ordinary state, not an error to hide

People move and delete directories. A grant whose root no longer exists must
report exactly that, and must never resolve to a different directory that now
occupies the path.

### R9 — Profile modes are part of the grant

The module manifest already declares `profile_modes`. A grant made in a regular
profile must not be visible from an off-the-record one, and a grant made in an
off-the-record profile must not survive it.

---

## 3. The finding that most changes the design

**Granting "run `git` in this directory" is not the same as granting "run
`git`."** A repository configures the programs `git` runs, and that
configuration lives inside the granted directory.

Both of the following were executed on git 2.43.0 in a throwaway repository.

**Local configuration executes an arbitrary program during an ordinary read.**
A repository's own `.git/config` named an external diff program. A plain
`git diff` — a read, with no flags — ran it.

```
$ git config diff.external /tmp/probe/evil.sh     # local config, inside the repo
$ git diff > /dev/null
$ cat /tmp/probe/PROOF.txt
[external program executed] argc=7
```

**Hooks execute during an ordinary write.** A `pre-commit` hook in the
repository ran on `git commit`.

```
$ git commit -qm two
$ cat /tmp/probe/PROOF2.txt
[hook executed]
```

Neither is a defect in git. Repositories are meant to configure their own
tooling. The consequence for this contract is that **the broker cannot treat
"we only run a known-good binary" as a bound on what executes.** The bound is
whatever the granted directory says.

Note the practical shape of the exposure: neither hooks nor local config are
transferred by `git clone`, so a freshly cloned repository carries neither. The
risk is a directory that was already on the machine — cloned earlier from
elsewhere, unpacked from an archive, or synchronised by another tool.

The contract must therefore decide, explicitly, one of:

1. **Run hardened.** Neutralise the repository-controlled execution surfaces at
   invocation (hooks path, external diff and merge drivers, filter drivers,
   `fsmonitor`, pager, and any successor mechanism). This is a moving target: it
   is a list that git grows, and a broker that pins it once will fall behind.
2. **Price the grant honestly.** Treat "execute in this root" as what it is —
   running code the repository author chose, with the user's identity — and make
   the consent text say so.

The first option is more comfortable and less true. The second is unpleasant to
put in a prompt and does not decay.

`NOT RUN`: whether Chromium's process model on the pinned revision permits a
browser-process broker to spawn a child process at all, and under what sandbox
policy. That question gates R2 and has not been examined here.

---

## 4. Non-goals

- A general filesystem API for web content. This contract is for first-party
  modules compiled and signed with the browser, and for nothing else.
- A second permission store. `docs/PERMISSION_POLICY.md` keeps Chromium's
  per-origin permission system authoritative; a file grant to a first-party
  module is a different object and must not be modelled as an origin permission.
- Arbitrary program execution as a capability in its own right. R2 is execution
  *within a grant*, of a program the contract names, for a declared purpose.

---

## 5. Open questions for the contract author

| # | Question | Why it cannot be deferred |
|---|---|---|
| 1 | May a broker spawn a child process under the pinned revision's sandbox policy? | If not, R2 is impossible and the Git surface cannot exist as a module in any form |
| 2 | Hardened invocation or honest consent (§3)? | The two produce different prompts, different threat models, and different maintenance burdens |
| 3 | Destructive-class classification, or a separately-granted destructive capability (R6)? | Both are defensible; neither can be retrofitted quietly |
| 4 | Does a grant survive a browser restart? | R7 is unanswerable without this |
| 5 | Is the credential delegation of R5 per-operation or per-grant? | Per-grant is a confused deputy waiting to happen; per-operation costs a round trip |

---

## 6. Verification

| Item | State |
|---|---|
| Native build | `pending` — no patch in this wave |
| Runtime | `pending` — nothing launched |
| Visual | `not_applicable` — no surface in this wave |
| Git behaviour in §3 | **executed**, git 2.43.0 on Linux |
