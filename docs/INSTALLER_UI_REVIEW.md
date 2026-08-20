# An installer with a UI — review of what can and cannot be built

## 0. Status

A review, not a decision and not work. The owner asked for four things; this
says which of them Chromium's Windows installer can be made to do, what each
costs, and what has to be decided before anything is written. §6 is the
recommendation, §7 is the decision list, §8 is what is not verified.

The request, as given:

1. Running the installer shows an installation UI.
2. The user sets the **install path**.
3. The user sets the **software name**.
4. The dialog shows an **image the owner supplies**.

Everything below was read at the pinned revision `152.0.7977.42`.

## 1. The verdict, up front

| | Verdict |
| --- | --- |
| **1. An install UI** | **Yes — but not inside `mini_installer.exe`.** A separate front-end that writes an initial-preferences file and launches the existing installer. Zero upstream files. |
| **2. A user-chosen install path** | **No, as asked — settled in §7.** Chromium does not merely lack this — it reads a path from preferences and then *rejects* any value that is not one of the two Program Files roots. Making it work means patching the path logic and inheriting three other things that assume the standard roots. |
| **3. A user-chosen software name** | **No, as asked — settled in §7.** And the reason is not the installer. 518 of the browser's own strings carry the literal product name, compiled into the resource pak at build time. An install-time name renames the folder and the Start menu entry while the browser keeps calling itself Sunshine in every sentence it speaks. |
| **4. A supplied image** | **Yes.** The only real question is *when* the image arrives — at build time or at install time — and the second one has a security cost the first does not. |

Two of the four are straightforward. The other two are the interesting part of
this document, because in both cases the honest answer is not "no" but "here is
the thing you actually want, which is cheaper and does not break updates."

## 2. What the installer is today

**`mini_installer.exe` has no user interface and is built so that it cannot
easily grow one.** `chrome/installer/mini_installer/mini_installer_exe_main.cc`
declares `MainEntryPoint` and is linked with `/ENTRY`, deliberately **without
the C runtime** — the file goes on to implement `memset` by hand because the
compiler emits calls to it and there is no CRT to provide it. A dialog needs
user32, comctl32, a message loop and the CRT. That is not a patch, it is a
different program.

**It does, however, forward its own command line.** `RunSetup` in
`chrome/installer/mini_installer/mini_installer.cc` builds setup.exe's command
line and calls `AppendCommandLineFlags(configuration.command_line(), ...)`.
Anything given to `mini_installer.exe` reaches `setup.exe`. **This is the seam,
and it is the whole reason a UI is cheap:** a front-end does not need to know
how installation works, only how to phrase a request.

**What `setup.exe` accepts** is listed in `chrome/installer/util/util_constants.h`
under `namespace switches`. The relevant one is `--installerdata`, whose
argument is a JSON file — `chrome/installer/util/initial_preferences_constants.h`
names every key it may hold. **There is no install-path switch in that list.**

## 3. The install path, and why it is not a choice

`GetChromeInstallPathWithPrefs` in `chrome/installer/util/helper.cc` decides
where Sunshine goes, in this order:

1. the path recorded in the registry, if some version is already installed;
2. `GetInstallationDirFromPrefs`, from the preferences file;
3. `GetDefaultChromeInstallPathChecked` — `%LOCALAPPDATA%` for a per-user
   install, `%ProgramFiles%` for a system one, plus the product subdirectory
   and `Application`.

Step 2 looks like the opening, and it is not. `GetInstallationDirFromPrefs`
reads `program_files_dir`, and then:

- it ignores the value entirely unless this is a **system-level** install; and
- it compares the value against `%ProgramFiles%` and `%ProgramFiles(x86)%` and
  **returns an empty path unless it equals one of them**, which sends the
  caller to the default.

So the one preference that names a directory is a **bitness switch for MSI
deployments**, not a path chooser. Chromium is not missing this feature; it
declined it.

**What it would cost to add.** One upstream file (`helper.cc`) — but the file
count is the smallest part. Three other things assume the standard roots:

| | |
| --- | --- |
| `FindInstallPath` | scans only Program Files and Local AppData for a version directory. An install elsewhere is invisible to it. |
| The update path | `setup.exe --rename-chrome-exe` and `new_chrome.exe` operate on the recorded install directory; a hand-placed one has to be recorded correctly everywhere it is read. |
| Uninstall | is registered by path. A wrong path means an entry in Programs and Features that removes nothing. |

None of these fail at build time. They fail on the second install, on a
machine that already has the first — which is the case nobody tests.

**What the user probably wants instead.** Two things, and both already exist:

- **Per-user or per-machine.** `%LOCALAPPDATA%\Sunshine\Application` versus
  `%ProgramFiles%\Sunshine\Application`. This is a real choice with real
  consequences — admin rights, all users or one — and it is *supported*.
- **Where their documents live.** Already decided:
  `docs/DOCUMENT_STORE_CONTRACT.md` DS-1 says the store is a directory the user
  picks. That is the folder a person actually cares about the location of. The
  binary's folder is not.

## 4. The software name, and why the installer is not the obstacle

`docs/decisions/0015-where-the-product-name-lives.md` already established that
the name lives in three places, and that the largest is
`chrome/app/chromium_strings.grd` — **518 of its 762 messages spell the product
name out in the body of the sentence**, which is why patch 0010 rewrites 527
lines rather than two constants.

Those strings are compiled into the resource pak. **An installer cannot rewrite
them.** So an install-time name produces this:

- the folder, the Start menu entry and the shortcut say what the user typed;
- "Set Sunshine as your default browser", "About Sunshine", and five hundred
  other sentences inside the browser do not.

The second problem is identity. `chrome/install_static/chromium_install_modes.h`
is one table, and patch 0009 rewrites it: `kProductPathName`, `base_app_name`,
`base_app_id`, `browser_prog_id_prefix`, the ProgID descriptions, and an Active
Setup GUID. Those are not labels — they are **registry keys and the taskbar's
notion of which application a window belongs to**. Make them runtime values and:

- two installs under different names become two products that cannot see each
  other, so the second does not upgrade the first, it joins it;
- the default-browser registration key moves with the name, and
  `verify_installed_build.py`'s SEC-13 checks and gates RV-26, RV-29 and RV-30
  assert a fixed identity — they would have nothing left to assert.

**What is actually affordable** is a **display name**: the text on the shortcut
and the Start menu entry, with the directory, the registry keys and the ProgID
staying `Sunshine`. That is a rename of two shortcuts after installation, it
costs zero upstream files, and it is honest about being cosmetic — but it will
still disagree with the browser's own 518 sentences, and the person choosing it
should be told that in the dialog rather than discovering it later.

## 5. The image

Two places it can come from, and they are not equally safe.

| | |
| --- | --- |
| **Build time** | Committed beside the front-end and baked into its resources. Zero new risk, and nothing is opened at run time. |
| **Install time** | Read from a file beside the installer. The installer then **decodes an image file it did not author** — and for a system-level install it does so **elevated**. Image decoders are a classic elevation-of-privilege surface. |

If the requirement is "the owner supplies the image", build time satisfies it.
If the requirement is "each deployment supplies its own image without a
rebuild", install time is the only answer, and it needs: a fixed format, a size
cap, decoding **before** elevation, and a failure that falls back to the built-in
image rather than aborting.

## 6. Recommendation

**Build a Sunshine installer front-end. Do not patch `mini_installer.exe`.**

```
sunshine-setup.exe            (new, ours, no Chromium code)
  ├─ shows the dialog: image, per-user vs per-machine, shortcuts, make default
  ├─ writes initial_preferences JSON to a temp file
  └─ runs mini_installer.exe --installerdata=<that file> [--system-level]
```

Why this shape:

- **Zero upstream files.** The same argument ADR 0007 made for the WebUI seam:
  a surface that costs nothing upstream survives a Chromium rebase.
- **The engine stays silent and stays upstream's.** Every failure mode
  `mini_installer` already handles it keeps handling.
- **The dialog can change without a Chromium build.** A 20-minute rebuild of a
  small executable, not a 20-hour one of a browser.
- **It is the only place the four requests can be met at once**, because three
  of them are UI and the fourth is a preference file.

What the dialog can honestly offer, all of it supported today:

| Control | Mechanism |
| --- | --- |
| Install for me / for all users | `--system-level`, and the elevation that needs |
| Desktop shortcut | `do_not_create_desktop_shortcut` |
| Taskbar and Quick Launch shortcuts | `do_not_create_taskbar_shortcut`, `do_not_create_quick_launch_shortcut` |
| Make Sunshine the default browser | `make_chrome_default_for_user` |
| Launch after installing | `do_not_launch_chrome` |
| The install location | **shown, not typed** — the path the choice above implies |
| The image | built in, from `downstream/assets/` |

**Deliberately not offered:** a typed install path, and a typed product name.
§3 and §4 say why. If either is wanted anyway, it is a decision to take with
the costs in view, not a checkbox.

## 7. What has to be decided

Nothing below is implied by anything above; each is a real fork.

**All six are settled, and all six went to the recommendation.** They are
recorded here as the record of the choice; `docs/INSTALLER_UI_CONTRACT.md` is
what follows from them.

| | Decision | Answer |
| --- | --- | --- |
| **D1** | Front-end and engine, one file or two | **One file.** `sunshine-setup.exe` carries `mini_installer.exe` inside it, so there is no wrong file to double-click. The cost taken on: both are repackaged for every release, and a silent deployment now needs a switch rather than a second executable — §9 of the contract keeps that open. |
| **D2** | The install path | **Per-user or per-machine, and nothing else.** The path is shown, never typed. `helper.cc` is not patched, so §3's three consequences are not incurred — and the folder a person actually cares about is the document store, which DS-1 already lets them pick. |
| **D3** | The software name | **Fixed at `Sunshine`.** No display-name override either. The folder, the registry keys, the ProgID, the taskbar identity and the browser's own 518 sentences all say one thing, and RV-26, RV-29, RV-30 and the SEC-13 checks keep having something to assert. |
| **D4** | Where the image comes from | **Build time**, committed beside the front-end. The front-end opens no image file at run time, which closes §5's decoder-at-elevation problem outright rather than mitigating it. |
| **D5** | How the front-end is built | **Its own compiler invocation in the workflow.** Zero upstream files, and a dialog change costs a small link rather than a browser build. |
| **D6** | What it looks like | **Sunshine's**, by mapping the design tokens to native values. The cost taken on is real and named in the contract: dark mode, per-monitor DPI and keyboard accessibility all become this program's work instead of the system's. |

## 8. NOT VERIFIED

- **Nothing here is built and nothing has been run.** Every claim about the
  installer is read from the pinned source, not observed. The installer from
  build #33 has itself never been run — `docs/RETURN_RUN_SHEET.md` block A is
  where that first happens.
- The claim that a front-end can drive `mini_installer.exe` rests on
  `AppendCommandLineFlags` forwarding the command line, which is read from
  source. It has not been tested with a real `--installerdata` file.
- The elevation behaviour in §5 is reasoned from how a system-level install
  must work, not measured. Which process decodes the image, and at what
  integrity level, has to be checked before install-time images are accepted.
- No estimate is offered for how long the front-end takes to build, because
  there is no comparable piece of work in this repository to estimate from.
