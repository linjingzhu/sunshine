# Installer front-end — Contract

## Status and scope

Applies to Sunshine OS on the pinned Chromium revision `152.0.7977.42`. It
defines the program a person runs to install Sunshine: what it asks them, what
it does with the answers, and what it is not allowed to do.

`docs/INSTALLER_UI_REVIEW.md` is the analysis this rests on — in particular §2,
which establishes that `mini_installer.exe` has no UI and cannot reasonably grow
one, and that it forwards its command line to `setup.exe`. **That forwarding is
the entire mechanism.**

**Six decisions the owner made, which everything below follows from:**

| | Decision |
| --- | --- |
| Shape | **One file.** `sunshine-setup.exe` carries the engine inside it. |
| Path | **Per-user or per-machine, and nothing else.** Shown, never typed. |
| Name | **Fixed at `Sunshine`.** No control changes it, not even cosmetically. |
| Image | **Built in**, from `downstream/assets/`. Nothing is read from disk at run time. |
| Build | **Its own compiler invocation** in the workflow. Zero upstream files. |
| Look | **Sunshine's**, by mapping the design tokens to native values. |

**No implementation exists.** §9 says what that leaves open, and §10 says what
is not verified.

## 1. The one structural decision

**The front-end asks questions and phrases a request. It does not install
anything.**

Every rule below is a consequence of that sentence. `mini_installer.exe` stays
exactly as upstream built it and keeps handling every failure it already
handles: a partial download, a running browser, an in-progress update, a
downgrade, a corrupt archive. The front-end has no opinion about any of them,
which is why it can be rewritten in an afternoon without risking an install.

It also fixes what the front-end may *not* become. Anything it did itself would
be a second installer — one with no update path, no uninstall registration, and
no upstream to inherit fixes from.

## 2. What the user chooses

| Control | How it is expressed |
| --- | --- |
| Install for me / for all users | `--system-level`, and the elevation that requires |
| Desktop shortcut | `do_not_create_desktop_shortcut` |
| Taskbar shortcut | `do_not_create_taskbar_shortcut` |
| Quick Launch shortcut | `do_not_create_quick_launch_shortcut` |
| Make Sunshine the default browser | `make_chrome_default_for_user` |
| Launch when finished | `do_not_launch_chrome` |

Every one of these is a key `chrome/installer/util/initial_preferences_constants.h`
already defines, or a switch `chrome/installer/util/util_constants.h` already
declares. **The front-end invents no installation behaviour**, and that is
checkable: a control whose effect is not one of those names is a control that is
doing something upstream did not agree to.

**The install location is displayed and never typed.** It is
`%LOCALAPPDATA%\Sunshine\Application` or `%ProgramFiles%\Sunshine\Application`,
whichever the choice above implies, and §3 of the review says why there is no
third answer.

**The product name has no control at all.** Not a text field, not a display-name
override. `docs/decisions/0015-where-the-product-name-lives.md` is why: the name
is 518 compiled strings, a set of registry keys, and the taskbar's notion of
which window belongs to which application.

## 3. Elevation, and the three ways it goes wrong

A per-user install needs no privilege. A per-machine install needs
administrator. Doing this carelessly is how an installer becomes a local
privilege escalation, so the rules are stated rather than left to the
implementation.

| Rule | Why |
| --- | --- |
| The manifest requests `asInvoker` | An installer that always elevates makes the per-user install — the default, and the safe one — demand admin for no reason. |
| Elevation happens **only** after the user picks per-machine, by relaunching | The dialog is drawn unprivileged. Only the act of installing is elevated. |
| Choices cross the relaunch as a **closed set of switches** | Not as a file. A file in a user-writable directory that an elevated process then reads is the classic shape of this bug. |
| The engine is extracted **only after** elevation, into a directory unprivileged users cannot write | Otherwise an unprivileged user replaces the extracted engine between write and execute, and the elevated process runs it. |
| The engine's hash is checked against the value baked in at build time, before it is executed | The cheap defence that makes the previous rule's failure non-fatal rather than fatal. |

The last two are the ones most likely to be skipped as paranoia. They are not:
"extract a payload to temp and run it" is a documented elevation-of-privilege
pattern, and this program does exactly that by construction.

## 4. The image, and everything else on screen

**The image is a build-time asset.** It is committed under `installer/`,
beside the program that compiles it in, and the running program reads no image
file from disk.

It is deliberately **not** under `downstream/assets/`. That directory is an
overlay onto Chromium's own tree — ADR 0008's mechanism for replacing an
upstream file — and a banner belonging to a program that is not part of
Chromium has no upstream file to replace. Putting it there made
`verify_asset_overlay.py` report it as an untracked overlay of a Chromium path
that does not exist, which was the guard being right.

That closes the whole class of problem §5 of the review describes: an installer
that decodes a file it did not author, potentially while elevated.

**The look is Sunshine's, by translation rather than by reference.**
`docs/DESIGN_SYSTEM_CONTRACT.md` is written for web surfaces and its tokens are
CSS custom properties; a Win32 dialog cannot resolve them. So the tokens are
*mapped* — one table, in one place, from token name to native value — and the
mapping is the thing that is reviewed when the design system changes.

| | |
| --- | --- |
| Light and dark | Follows the system setting, and follows a change to it while the dialog is open. |
| Scaling | Legible from 100% to 300%. Per-monitor DPI aware. |
| Keyboard | Every control reachable and operable from the keyboard alone; a visible focus indicator at every stop. |
| Screen readers | Every control has an accessible name. The image is decorative and is marked as such. |

The accessibility rows are not decoration either. This is the **only** Sunshine
surface a person meets before the browser exists, so it is the one surface that
cannot fall back to "use the browser's own accessibility".

## 5. What happens when it fails

| Situation | What the front-end does |
| --- | --- |
| The engine exits non-zero | Reports the exit code as the engine's, not as its own, and says which stage it was at. |
| The engine cannot be extracted or fails its hash check | Refuses to install. Does not fall back to any other copy. |
| The user declines the elevation prompt | Returns to the dialog with the choice intact. Not an error, and not a silent switch to per-user. |
| Anything | Leaves nothing extracted behind. |

The third row is worth stating because the tempting behaviour — quietly
installing per-user when the user declined admin — installs something other than
what they asked for.

## 6. What this is not

- **Not an uninstaller.** `setup.exe` registers uninstallation, as it does
  today. Programs and Features points at upstream's own code and nothing here
  changes that.
- **Not an updater.** Updates are the browser's business.
- **Not a place to configure the browser.** The one preference file it writes is
  about installation. Anything about how Sunshine behaves belongs in the
  browser, where the user can change their mind.
- **Not a second installer.** §1.

## 7. Invariants

Class **O** is decidable offline. **B** needs the built front-end. **U** needs a
person.

| ID | Invariant | Class |
| --- | --- | --- |
| IU-1 | The front-end owns zero upstream Chromium files. | O |
| IU-2 | The engine is `mini_installer.exe` as upstream built it. The front-end copies no file into place, writes no registry key, and creates no shortcut. | O |
| IU-3 | Every user choice is expressed as an initial-preferences key or a setup switch that upstream already defines. | O |
| IU-4 | The install location is displayed and never accepted as input, and is what the per-user/per-machine choice implies. | O |
| IU-5 | No control changes the product name, its directory, its registry keys or its ProgID. | O |
| IU-6 | The dialog's image is compiled in. The front-end opens no image file at run time. | O |
| IU-7 | The manifest requests `asInvoker`. Elevation occurs only on a per-machine choice, and only by relaunching. | O |
| IU-8 | Choices cross the elevation boundary as a closed set of switches. No file in a user-writable location is read after elevating. | O |
| IU-9 | The engine is extracted only into a directory unprivileged users cannot write, and only after elevation when elevating. | B |
| IU-10 | The engine's hash is verified against the build-time value before it is executed. | B |
| IU-11 | A failed install leaves nothing extracted. | B |
| IU-12 | A declined elevation prompt returns to the dialog and never installs per-user instead. | B |
| IU-13 | The dialog resolves its colours through the token mapping, follows the system light/dark setting, and is legible from 100% to 300% scaling. | U |
| IU-14 | Every control is reachable and operable from the keyboard alone, with a visible focus indicator, and every control has an accessible name. | U |
| IU-15 | There is no switch, argument, environment variable or registry value that makes `sunshine-setup.exe` install without showing the dialog. Every installation it performs was watched by a person. | O |
| IU-16 | The only state the front-end reads about *the installation* before the user has agreed to anything is whether Sunshine is installed and at what version. Exactly one further read is permitted — the system's light/dark preference, which is needed to draw — and nothing is written. | O |

**No check claims any of these yet, because no code implements them.** IU-1 to
IU-8 become decidable the moment the front-end is written, and the guard that
decides them should be written with it rather than after —
`docs/DOCUMENT_STORE_CONTRACT.md` §6 says the same thing for the same reason,
and this project's record is that a rule with no check is a rule that drifts.

## 8. What this reverses

Nothing. It is the first contract to describe anything that runs outside the
browser, which is why §7 needed a family of its own: every existing family
speaks for a surface that only exists once Sunshine is installed.

## 9. Two answers, and what each costs

**No silent mode.** There is no switch that installs without the dialog.

The two situations are one feature. Fifty machines set up from a deployment
script is the same switch that an installer for some other program, or a script
nobody read, would use to put Sunshine on a machine whose owner never asked for
it. **Convenience and risk are not separable here**, and the honest way to hold
that is to have neither until a deployment need is real enough to be argued on
its own. IU-15 is the rule; when the need arrives, this section is what has to
be reopened rather than quietly worked around.

**The dialog says when it is updating.** "Sunshine 1.0 is installed; this will
update it to 1.1", rather than a button reading Install that silently does
something else.

The cost is named in IU-16 and is deliberately bounded: the front-end reads the
machine **before the user has agreed to anything**, which is a thing an
installer should do as little of as possible. So it reads exactly one fact about
the installation — whether Sunshine is installed, and at what version — from
`Software\Microsoft\Windows\CurrentVersion\Uninstall\Sunshine`'s
`DisplayVersion`, in the 32-bit view, which is where `setup.exe` writes it. An
installer that inspects a machine it has not been given permission to change is
a pattern worth keeping to one line.

**IU-16 admits a second read, and saying so is the point.** Drawing in the
user's chosen light or dark theme means reading `AppsUseLightTheme`. That was
not inventory of the machine and the first draft of IU-16 forbade it anyway, by
saying "no other key" — a rule the implementation would have had to break
quietly or the feature dropped. Naming the exception is what keeps the invariant
enforceable: the guard asserts the source reads **those two keys and no
others**, which is a stronger check than "as few as possible" ever was.

**What this does not become.** It does not become a repair flow, a downgrade
prompt, or a "you already have the latest version" refusal. `mini_installer`
decides what to do with an existing installation; the dialog only reports what
it found, and if the read fails the dialog says Install and proceeds, because a
missing fact is not a reason to block an installation.

## 10. NOT VERIFIED

- **Nothing here is built.** No dialog exists, no engine has been embedded, and
  no install has been driven by anything but a double-click on
  `mini_installer.exe` — which itself has not happened yet;
  `docs/RETURN_RUN_SHEET.md` block A is where that first occurs.
- **The command-line forwarding is read, not tested.** `RunSetup` in
  `chrome/installer/mini_installer/mini_installer.cc` calls
  `AppendCommandLineFlags` with its own command line, and §1's whole mechanism
  depends on that. It has never been exercised with a real `--installerdata`
  file.
- The elevation rules in §3 are reasoned from how a system-level install must
  work. Which process actually needs the privilege, and at what point, has to be
  measured before the implementation trusts this section.
- The token mapping in §4 does not exist and may not be possible for every
  token. Some design-system values are expressed in ways a native control cannot
  take, and that will be found by writing the table rather than by discussing it.
