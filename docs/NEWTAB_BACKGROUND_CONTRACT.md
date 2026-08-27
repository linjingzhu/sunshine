# New Tab background — contract

## Status and scope

The content area's background on `chrome://new-tab-page`, for the Chromium
revision pinned by Sunshine OS: `152.0.7977.42` (see `config/chromium.version`).

**Implemented, and never run.** Four patches:
`0020-sunshine-newtab-background-format.patch` decides what a background may
be (§2) and reads it; `0021-sunshine-newtab-background-source.patch` serves it
(§3); `0002-sunshine-new-tab.patch` shows it (§4);
`0022-sunshine-searchbox-state.patch` decides what the searchbox does over it
(§3c).
`scripts/verify_newtab_background.py` holds the patch stack to this document.
Nothing has been built or displayed — §5 is the whole of what that means.

Every decision below was made by the owner. This document records them and the
evidence each rests on; it does not re-derive them.

## 1. What was decided

| | Decision |
| --- | --- |
| **Formats** | PNG, JPEG and WebP — including the animated forms of the first and last, APNG and animated WebP. Nothing else. |
| **Loop** | An animated asset loops for as long as it says it does, including forever — an APNG in its `acTL` chunk, a WebP in its `ANIM` chunk. |
| **Where it lives** | A file in the install directory. **Not embedded in the binary.** |
| **Animation rules** | `docs/PERFORMANCE_BUDGET.md` PB-5a's three properties, all required together: visible-only, opt-in, self-contained. |
| **Video** | Excluded. |

**Video is excluded because it is not needed**, and "we did not get to it" is a
different thing from "we decided against it". The animated image formats do
what this feature is for, and a short clip looks the same from two metres away.

The exclusion was lifted for one day and withdrawn without any code being
written. `docs/PERFORMANCE_BUDGET.md` PB-5a records what that round corrected:
two of the three grounds first written here — a codec-licensing question and an
audio track needing proof of silence — did not survive re-reading, and only the
per-New-Tab decode pipeline stands. The cancellation does not rest on any of
them.

## 2. What a background may be — NTB-1, NTB-2, NTB-4

**PNG, JPEG or WebP, decided from the file's first bytes.**

**Neither animated form is a separate format, and saying so is the point.** An
APNG *is* a PNG — the same eight-byte signature, the same `.png` name, the
animation carried in ancillary chunks (`acTL`, `fcTL`, `fdAT`) a decoder
either understands or skips. An animated WebP *is* a WebP, its frames in the
same RIFF container a still one uses. A build that accepts the still format
accepts the animated one without being told about it, and code that tried to
detect either separately would be claiming to distinguish two things that are
one thing. `verify_newtab_background.py` refuses that shape.

The graceful-degradation property falls out of the same design: an APNG's
**first frame is a valid standalone PNG**, so any decoder that does not know
the animation chunks shows a still image rather than an error.

| | |
| --- | --- |
| **NTB-1** | The background source declares the PNG, JPEG and RIFF signatures as byte arrays, and all are present. |
| **NTB-2** | No excluded format's signature is declared, and no code path decides a background's format from its file name. |
| **NTB-4** | WebP is recognised by **both** of its tags: `RIFF` at offset 0 and `WEBP` at offset 8. Declaring the first without the second is refused, and so is declaring the second without ever reading it at offset 8. |
| **NTB-5** | The path the handler answers is a path the source will actually service. One named constant, used three times — declared, matched in the handler, listed in the allowlist. |

**NTB-5 exists because the feature shipped broken and everything went green.**
`untrusted_source.cc` gates every request through `ShouldServiceRequest`, an
allowlist of exact paths. The handler branch was written; the allowlist entry
was not. Every request was refused with `ERR_INVALID_URL` before reaching the
branch, which was unreachable code — and a correctly installed, correctly
signed asset produced exactly what a missing one produces, because §5 records
that those two states are indistinguishable. The compiler had no objection, the
build was green, and this guard passed, because none of the three knew the two
places had to agree. Counting uses of one constant is what makes them one fact.

The rule counts the **constant**, not the function name. An edit to the
allowlist changes a `return` chain, not a signature, so `ShouldServiceRequest`
arrives as a context line and a check that searched for it would fail on a
correct patch. Three uses in the added lines is the shape a correct patch has.

**NTB-4 exists because WebP's identity is not a prefix.** `RIFF` is a
container tag that WAV and AVI open with too. What says WebP is the four bytes
at offset 8, after the container's length field. A check that accepted
anything beginning `RIFF` would accept a renamed WAV as a New Tab background
**while reading, in the diff, exactly like a signature check** — the same
failure shape as deciding by extension, one layer further down. That is why
the guard names the missing tag specifically rather than trusting that a
constant's presence means it is used.

**NTB-2's second half is the one that matters.** A file called `.png` that
begins with `GIF89a` is a GIF, and Blink would decode it happily — Blink picks
its decoder by signature, exactly as this rule does. So an implementation that
accepted files by extension would admit precisely the formats the rule exists
to refuse, while *looking*, in the source, like it was enforcing something.
The extension selects which file is **looked for**; it never decides what the
file **is**.

**Verified at the pin**, and the reason the format rule is cheap to keep.
`PngImageDecoder` is declared as decoding "the PNG image format using
`SkPngRustCodec`" and derives from `SkiaImageDecoderBase`, the multi-frame
path. `WEBPImageDecoder` declares `RepetitionCount()`, `DecodeFrameCount()`,
`FrameDurationAtIndex()` and `InitializeNewFrame()` — the whole multi-frame
interface. **Both animated formats decode in this build without anything
being added to it.**

## 3. Where it lives, and how it is served — not written

**The install directory, beside `chrome.exe`.** Not the versioned directory
next to it: an update replaces that wholesale, so a background left there
would vanish the first time Sunshine updated itself, silently, with nothing
for the owner to point at. The install root survives, which is what makes
"replace the file" a durable instruction rather than one that works until the
next update.

Three file names are looked for — `newtab-background.png`,
`newtab-background.jpg` and `newtab-background.webp` — one per permitted
format, because asking for a JPEG named `.png` would be asking someone to
write down something untrue.

**A folder of frames becomes one file before it reaches the install directory,
and never after.** `scripts/build_newtab_background.py` assembles numbered
frames into a single self-animating asset. It is a hand-run tool for the same
reason the background is a file rather than a feature: composing 150 frames in
the browser would read 150 files to draw a New Tab, which `PERFORMANCE_BUDGET.md`
PB-4 refuses in its first zero-tolerance condition, and something would then
have to advance the frames, which is exactly what NTB-3 forbids. The tool reads
the permitted names and `kMaxAssetBytes` out of patch 0020 rather than holding
its own copy, so it cannot write a file the browser will not read without
saying so.

**Ping-pong is a property of the frames, not of playback.** No image format can
reverse itself: `acTL` and `ANIM` both carry a repeat count and no direction.
A background that plays forward and back is one whose frames run `1..N` then
`N-1..2`, and dropping both endpoints is what keeps the turn from holding a
still frame for two durations. `--pingpong` writes that sequence.

**Serving costs two upstream files, and they are now owned.** A WebUI page
cannot read an arbitrary disk path. Chromium's own local-background bytes
reach the New Tab page through
`chrome/browser/ui/webui/new_tab_page/untrusted_source.cc`, which serves one
fixed name out of the **profile** directory and validates it strictly against
directory traversal. Patch 0021 adds one branch there for
`sunshine-background.png`, plus the dependency edge in
`chrome/browser/ui/webui/new_tab_page/BUILD.gn`. The stack owns twenty-two
upstream files after this, up from twenty.

**The Sunshine branch needs no traversal defence, and the reason is worth
stating rather than assumed.** Upstream's branch validates because its path
comes from a preference — a name that reached it from outside. Sunshine's
takes no name from anywhere: the request path is a fixed string, and
`ReadInstalledBackground` looks only beside `chrome.exe`, only for names it
holds itself. There is no path to traverse because there is no path in the
request.

The rejected alternative is worth recording. Copying the asset into each
profile at first run would need no new upstream file, and would break the
decision in §1: replacing the file in the install directory would then change
nothing for any profile that already existed.

### The browser will also register one — decided, not built

**The owner's decision: a Sunshine surface, not Chromium's Customize panel.**
The picker lives on a Sunshine settings surface, which costs zero upstream
files by the seam in `docs/decisions/0007-module-contribution-seam.md`.
Chromium's own Customize Chrome panel keeps working and keeps writing its own
profile background; the two are separate features that happen to draw in the
same place.

**Two locations, in order.** The install directory alone cannot work, because
the browser cannot write to it:

| | Asset | Written by | Writable without elevation |
| --- | --- | --- | --- |
| 1st | `<profile>/Sunshine/newtab-background.*` | the picker | **always** |
| 2nd | install directory, as §3 above | copying a file in | per-user only |

A per-machine install puts the install directory under `%ProgramFiles%`, and a
browser that asked for administrator rights to set a wallpaper would be
answering a decoration request with an elevation prompt. So the picker writes
to the profile, and the install directory keeps being what it already is: the
default, and the way a machine-wide image is deployed.

**This does not reopen the rejected alternative above.** That one copied into
each profile *at first run*, which is why replacing the install file stopped
reaching existing profiles. Here a profile holds an asset only when a person
put one there deliberately, and replacing the install file still reaches every
profile that has not.

**The bytes are copied, never re-encoded.** Re-encoding would decode and
re-emit the image, and the first frame of an APNG or an animated WebP is a
valid still — so a converting picker silently turns an animation into a
photograph. Copy verbatim, or the format rules in §2 are enforced on bytes the
user never chose.

**Validate before writing, and say why on refusal.** §5 records that a rejected
file and a missing file are indistinguishable on screen. A picker is the first
place that can be fixed: it holds the file, the rule and the person at the same
moment. "This is a GIF" and "this is 112 MB, the limit is 100" are sentences
nothing in this feature can say today.

**The cost, named rather than absorbed.** Looking in two directories doubles
the names probed at startup — six instead of three, still once per process.
`docs/PERFORMANCE_BUDGET.md` PB-4's first zero-tolerance condition admits one
file on the startup path, and this feature already carries a residue against
it. This widens that residue. It is recorded here rather than fixed by amending
PB-4, because amending the budget a feature violates is the pattern that
produced this contract's worst defect.

**Nothing is built.** No picker, no second lookup path, no profile asset.

## 3a. Resting — the background alone, three seconds after focus leaves

**Decided by the owner.** When the browser window loses focus and three seconds
pass, the New Tab's own content fades out and the background is the only thing
on screen. Focus returning restores it at once.

| | |
| --- | --- |
| **NTB-6** | Resting requires an installed background. With none, nothing hides — an empty New Tab is not a feature. |
| **NTB-7** | The delay is a **one-shot** timer, armed on the transition and cancelled on any transition out. Sunshine owns no repeating task for it. |
| **NTB-8** | While resting, the hidden content takes no pointer events. The click that restores focus wakes the page and does nothing else. |

**Focus is not visibility, and this feature is the first thing here to need the
difference.** §4's `visibilitychange` handling stops the animation when the tab
is hidden or the window minimised. A window that is merely *unfocused* is still
visible, still animating, and — until now — indistinguishable to this page from
a focused one. Resting is driven by `document.hasFocus()` and window
`focus`/`blur`; hiding remains driven by `visibilityState`. **Two signals, two
jobs, and they compose rather than override**: a hidden window rests nothing,
because there is nothing to see.

The state is derived rather than accumulated. On any of the three events —
`blur`, `focus`, `visibilitychange` — the page recomputes one predicate:

```text
rest  ⇔  background available
      ∧  document.visibilityState === 'visible'
      ∧  !document.hasFocus()
```

and arms or cancels from that. A state machine that instead remembered which
event happened last is the version that gets stuck resting after a tab switch,
which is the bug this shape does not have.

**Everything except the background fades, by exclusion rather than by list.**
The rule names the background frame and hides its siblings; it does not
enumerate `#content`, the customize buttons and the attribution link. Upstream
adds a fixed-position element to this page from time to time, and a list would
be correct until it did.

**Cancel the pending timer when the window is hidden.** A timeout left armed
across a minimise is work scheduled for a moment nobody is looking at, which is
`docs/PERFORMANCE_BUDGET.md` PB-5's whole subject even when the work is one
assignment.

### What this does to PB-5a's reasoning, said rather than glossed

PB-5a permits an animated background because *"it costs while it is watched, it
stops when it is not, and it is absent unless someone asked for it."*

**This feature makes the animation the only thing on screen at the moment the
user turned away.** It satisfies property 1 exactly — the tab is visible, the
window is not occluded, and property 1 is written about visibility rather than
attention — and it pushes against the sentence that property was derived from.
Recorded here because a later reader should find that the tension was noticed
and accepted, not that it was missed.

The narrow reading holds: an unfocused window on a second monitor is being
watched, and a minimised one is not, which is the line `visibilityState` already
draws. Nothing about resting changes what happens when the window is actually
hidden.

**Nothing is built.**

## 3b. The status row — the time, and the way in

**Decided by the owner.** The bottom-right corner of the New Tab carries the
current time, and beside it a button that opens the OS file picker to choose a
background.

| | |
| --- | --- |
| **NTB-9** | The clock shows minutes and wakes once per minute, aligned to the boundary, only while the surface is visible. `docs/PERFORMANCE_BUDGET.md` PB-5b is the row that permits it, and it is the only repeating task Sunshine owns. |
| **NTB-10** | The clock survives resting; the button does not. |
| **NTB-11** | The picker copies the chosen file **byte for byte** and validates it before it lands. A file the format rules refuse is refused with the reason shown, and nothing is written. |
| **NTB-14** | A background's file name is decided in one place. The names the reader searches, the extensions the dialog offers, and the name the picker writes each format under are one list three times, and they agree. |

**NTB-10 is the one worth arguing for.** §3a hides the page's content three
seconds after focus leaves, and the obvious rule hides everything that is not
the background. But a clock is exactly what a person wants on a screen they are
not typing into — it is the reason to look over at all — while a settings
button on a resting screen is a control nobody is reaching for. So the fade
excludes the background **and the clock**, and hides the button separately.

**The button needs a browser-side write, and there is no way around it.** The
page can open a picker with `<input type="file">` and never touch Mojo, but a
`File` in a renderer is bytes with nowhere to go: persisting them is a browser
process operation. What that costs is set out below, because it is the first
time this feature takes ownership of an upstream file that is not already ours.

### What upstream already does, read rather than assumed

Chromium's own *Upload from device* is the same shape, and answers a question
§3a left open:

```cpp
void CopyFileToProfilePath(const base::FilePath& from_path,
                           const base::FilePath& profile_path) {
  base::CopyFile(from_path, profile_path.AppendASCII(
      chrome::kChromeUIUntrustedNewTabPageBackgroundFilename));
}
```

**`base::CopyFile`, verbatim.** Upstream does not decode and re-emit, so its
picker preserves an animation. §3a warned that a converting picker would
silently turn an APNG into a photograph; upstream does not convert, and neither
may this one. That warning stands as a rule and is no longer a suspicion about
upstream.

The dialog itself is `ChooseLocalCustomBackground()` in
`chrome/browser/ui/webui/side_panel/customize_chrome/customize_chrome.mojom`,
landing in `NtpCustomBackgroundService::SelectLocalBackgroundImage`. It writes
**Chromium's** profile background, which is a different asset from Sunshine's
and stays that way — two systems, one of which Sunshine does not own.

### The ownership this takes — struck, see §3d

This section said the button needed three upstream files:

| File | Why |
| --- | --- |
| ~~`chrome/browser/ui/webui/new_tab_page/new_tab_page.mojom`~~ | one method for the page to call |
| ~~`chrome/browser/ui/webui/new_tab_page/new_tab_page_handler.h`~~ | the declaration, and a `ui::SelectFileDialog::Listener` |
| ~~`chrome/browser/ui/webui/new_tab_page/new_tab_page_handler.cc`~~ | open the dialog, validate the signature, copy the bytes |

**None of them is taken.** §3d found that this contradicted §3, put the choice
to the owner, and the answer was to keep the button here and have it *navigate*
to a Sunshine surface. A navigation is not a Mojo call, so upstream's handler is
untouched and the feature stops being free somewhere cheaper.

The reasoning that made this section right on its own terms still holds and is
worth keeping: `docs/decisions/0007-module-contribution-seam.md` gives a WebUI
surface its files for free, and a Mojo method on **upstream's** WebUI is not
that. What changed is that the method moved to a surface that is Sunshine's.

**Validation moves into the handler, and that is the substantive win.** §5
records that a rejected file and a missing file are indistinguishable on
screen. The handler holds the bytes, the rule and the person at the same
moment, so it can say *this is a GIF* or *this is 112 MB and the limit is 100*
— sentences nothing in this feature can produce today.

**Built, and never run.** `0024-sunshine-settings-surface.patch` is the button,
the surface it opens, and the picker on it. NTB-11 was written ahead of the code
it constrains — this repository's pattern, and the reason the allowlist defect
was not repeated — and what it constrains is a picker on a Sunshine surface
(§3d) rather than one on this page. The invariant did not change when the place
did: copy byte for byte, validate before it lands, say why on refusal.

The button is an `<a href="chrome://sunshine-settings/">`. **A renderer-initiated
navigation between two WebUI hosts is upstream's own arrangement, not something
this discovered**: `chrome/browser/resources/history/side_bar.html.ts` at the pin
carries `href="chrome://settings/clearBrowserData"`, which is `chrome://history`
linking to a different privileged host exactly this way. Read, not assumed —
and still not run, because nothing in this stack has been.

### One clause of NTB-11 turned out to be unbuildable as written

§3b said the handler could say *this is a GIF* or *this is 112 MB and the limit
is 100*. **The second is built. The first is not, and it cannot be** — saying
"this is a GIF" means comparing the file's bytes against a GIF signature, and
NTB-2 forbids this build from declaring any excluded format's signature. That
rule is not incidental: a table of refused signatures is one edit from being a
table of accepted ones, and the guard that refuses it is the reason a renamed
WAV cannot become a background.

So the sentence a person gets names the three formats that are allowed and says
these bytes are none of them, and adds that the file's *name* was not what
decided it. That is the whole of what can be said without the table the rules
refuse, and it is enough to act on. The size refusal is unaffected and reports
both measured numbers.

**NTB-11 is now enforced rather than only stated.**
`scripts/verify_newtab_background.py` reads the chain end to end — every
`InstallResult` the browser can produce is translated by the handler, every
`BackgroundOutcome` the interface declares is one the browser can send, and
every refusal has a sentence in `app.ts`. Nothing in any compiler holds those
three declarations together: a refusal added to the browser and not to the page
is not a build error, it is a person who is told nothing, which is the state §5
says this feature already produces too often. The guard also refuses a picker
that re-encodes rather than copies, and one that decides a refusal *after*
`base::CopyFile` rather than before.

**NTB-14 exists because the picker gave the file name a second author.** Until
now one list decided what a background could be called, and only the reader read
it. The picker writes under a name derived from the detected format, and the
dialog filters by extension, so the same fact is now consulted in three places
in one file. A `Format::kWebp` that returned the `.png` entry would write a WebP
under a name the reader then refuses for its bytes — a defect that surfaces as
"the picker did nothing", with no error anywhere. The guard checks the three
against each other.

## 3c. The searchbox — glass at rest, solid in use

**Decided by the owner.** The New Tab's search field has two states. *Normal* —
nothing is being asked of it — is translucent. *Highlight* — it is focused, or
it is holding text — is solid.

| | |
| --- | --- |
| **NTB-12** | **The normal state is the one written.** Highlight is upstream's surface with nothing done to it, reached by a rule failing to match rather than by a second rule. |
| **NTB-13** | Highlight is one predicate with two halves — focus, and text — and neither is a copy of anything. Focus is read in CSS; text is upstream's own `hasUserInput_`, reflected. |

**NTB-12 is the invariant, and the reason is a defect this feature already
shipped.** §3a hid the page's content and faded the background with it, because
the rule described what should disappear and nothing asked where the thing that
must stay was. The same shape is available here: a rule keyed on
`[has-user-input_]` instead of on its negation reads correctly, applies
cleanly, and makes the box glass exactly when someone is typing into it.
Writing only the normal state removes the possibility — if the rule is wrong,
or a roll moves it, the failure is upstream's opaque box, which is what
Chromium ships.

**Why the searchbox at all.** The background is the point of §3, and upstream's
searchbox sits on top of it as an opaque slab. Recessing it while it is idle is
what makes the background a background. Nothing else on the page needed this:
the wordmark and the clock are text with a shadow, and shortcuts are already
translucent.

### The halves, and why there are two

Focus alone is nearly enough and is wrong in one case: **type a query, then
click the page.** The text is still there, the box no longer has focus, and a
focus-only rule turns it to glass with the user's own words behind it. So
highlight is `focused ∨ has text`.

CSS can see focus by itself. `:focus-within` on `#inputWrapper`, not `:focus` —
the element that actually takes focus is the `<input>` inside
`<cr-searchbox-input>`, two shadow trees down, and focus is composed.

CSS cannot see text, and this is where the decision was made:

| Option | Cost |
| --- | --- |
| Track the text in `app.ts` from the composed `searchbox-input-text-updated` event | No new upstream file, and **a second notion of "there is text in the box"** beside the one upstream already keeps |
| Reflect upstream's `hasUserInput_` | One line in `ntp_searchbox.ts`, and one notion of the fact |

**The second.** `hasUserInput_` is already maintained by the element from the
same input event, already the flag its compose button reads, and already
`!!value.trim()` — which is the predicate this wants. Sunshine adds
`reflect: true` and nothing else. Two copies of a boolean that must agree is
how the searchbox ends up solid with an empty box, and the failure would be
invisible until someone looked.

**Upstream's flag is upstream's flag, and it has a known edge.**
`setInputText()` — the programmatic path, used by voice search and by the
composebox — does not fire the input event, so neither `hasUserInput_` nor
anything derived from it moves. Sunshine inherits that exactly; it does not
inherit it *worse*. In every such flow the box is also focused, which is the
other half of the predicate, so the visible behaviour is correct even where the
flag is stale. Recorded because it is the kind of thing a later reader should
find written down rather than discover.

### What this costs, measured

Two upstream files this stack did not own: `ntp_searchbox.css` and
`ntp_searchbox.ts`. `docs/decisions/0007-module-contribution-seam.md` gives a
Sunshine WebUI surface its files for free; upstream's New Tab search field is
not that.

Fetched at the pin, at the next milestone and at trunk, comparing only after
checking the HTTP status — the first roll-cost measurement in this repository
did not, saved a 404 body as content, and reported a whole file as changed.

| | at pin | 153.0.8000.0 | main |
| --- | --- | --- | --- |
| `ntp_searchbox.css`, whole file | 378 lines | 12 lines differ | 42 lines differ |
| `hasUserInput_: {type: Boolean}` | line 202 | line 202, **identical** | line 202, **identical** |
| **`git apply` of this patch** | **applies** | **applies** | **applies** |

**The last row is the measurement; the others are why it is not luck.** The
patch was checked out against each of the three revisions and applied to all
three — so the next roll costs nothing here, and neither does the one after it
as far as trunk can predict.

That row was red when it was first taken. The first version added its
`transition` to upstream's `#inputWrapper` rule, which needs ten lines of
context to reach; at trunk a `border` declaration has moved out of that rule
into an `#inputWrapper::after`, and the hunk conflicted. Re-anchoring below the
`[in-voice-search-mode]` rule fixed it — and the way it was fixed, by declaring
`#inputWrapper` a second time, is what native build #46 then rejected.

**Both measurements were right and the patch was still wrong**, because the two
answer different questions. `git apply` answers *will this patch land*.
Stylelint answers *will Chromium accept what it lands*. Nothing here had ever
asked the second one. Dropping the fade satisfies both at once, which is why it
is the fix rather than a compromise.

### The value, and what has not been checked

The normal state is `color-mix(in srgb, var(--color-searchbox-background) 65%,
transparent)` — Chromium's own token at 65% opacity, composed through the one
mechanism `docs/DESIGN_SYSTEM_CONTRACT.md` §2.2(3) admits. The box follows the
theme exactly as it did; only its opacity is Sunshine's.

**65% is chosen, not derived.** No contrast measurement stands behind it, and
one cannot easily: the composite depends on the photograph underneath, which is
the user's. What is known is the direction of the risk — the placeholder text
stays at full opacity while the surface behind it moves toward the image, so
the failure mode is a washed-out placeholder over a bright picture, not
unreadable typed text. §5 carries this as unverified, and it is the first thing
to look at when a background is finally on screen.

**The change between states is instant, and that was decided by a build.** A
150 ms `background-color` fade was written first. It needs `transition` on
`#inputWrapper` in both states, and the only place to put it without inventing a
selector is upstream's own `#inputWrapper` rule — so the patch declared the
selector a second time. Chromium's WebUI build lints this folder with its own
stylelint config, `no-duplicate-selectors` is in it, and native build #46 failed
in twenty seconds:

```text
gen/chrome/browser/resources/new_tab_page/preprocessed/ntp_searchbox.css
  140:1  ✖  Unexpected duplicate selector "#inputWrapper", first used at line 84
```

The three ways out were: add the declaration to upstream's rule and take a
conflict at trunk; write a synthetic selector such as `:host #inputWrapper` to
slip past the linter; or drop the fade. **The fade was decoration nobody asked
for**, and the other two both spend something real to keep it, so it is gone.
One rule, no upstream line edited, no `@media` block, and the patch applies at
the pin, at 153.0.8000.0 and at trunk.

A focus change being instant is not obviously worse, either. Focus rings snap;
a box that turns solid the instant it is clicked reads as responsive rather than
abrupt. That is a claim about a screen nobody has seen — §5.

`docs/DESIGN_SYSTEM_CONTRACT.md` S13 now checks the rule that caught this, so
the next patch to duplicate an upstream selector fails in CI rather than on the
owner's workstation ten hours into a queue.

## 3d. Where the picker lives — this document contradicts itself

**Two sections of this contract answer the same question differently, and the
answers differ by three upstream files.** Found while starting to build it, so
it is written down before any of it is.

| Section | Says | Costs |
| --- | --- | --- |
| §3, *The browser will also register one* | "The picker lives on a **Sunshine settings surface**, which costs **zero upstream files** by the seam" | 0 |
| §3b, *The ownership this takes* | the button is beside the clock **on the New Tab**, and needs `new_tab_page.mojom` plus `new_tab_page_handler.h/.cc` | **3** |

Neither is wrong on its own terms. §3 was written when the picker was a
surface; §3b was written after the owner asked for a button beside the clock,
and it is exact about what that costs — *"a Mojo method on upstream's WebUI is
not that, and this is the point where the background feature stops being free."*
What nobody did was go back and reconcile them, so the document now says both.

### A third shape, which neither section costed

**The button is on the New Tab and opens a Sunshine surface, which holds the
picker.** A navigation is not a Mojo call, so the New Tab page needs no method
on upstream's handler and the three files stay unowned. The surface is free by
ADR 0007, exactly as §3 said.

| | New Tab button, Mojo picker (§3b) | New Tab button, surface picker | Surface only (§3) |
| --- | --- | --- | --- |
| Upstream files newly owned | **3** | **0** | **0** |
| Clicks to a chosen file | 1 | 2 | 2, plus finding the surface |
| Where the refusal sentence appears | in place, on the New Tab | on the surface | on the surface |
| Survives an upstream roll | three files to re-apply | nothing to re-apply | nothing to re-apply |
| Needs a Sunshine settings surface to exist | no | **yes** — none exists today | **yes** |

**The second column is not obviously worse than the first.** It costs one extra
click and it costs building a settings surface that does not exist — which this
project will want for other reasons long before it wants a second Mojo method.
What it buys is three upstream files never owned, on a page (`new_tab_page`)
that this stack already patches heavily and re-applies at every roll.

**Settled by the owner, 2026-08-27: the second column.** The button stays on the
New Tab where §3b put it, and it navigates to a Sunshine surface that holds the
picker. **`new_tab_page.mojom` and `new_tab_page_handler.h/.cc` are not owned**,
and §3b's ownership table is struck.

Persisting bytes is still a browser-process operation, so the picker still needs
a Mojo method — on **Sunshine's own** handler, where ADR 0007 makes it free.
`downstream/patches/0006-sunshine-document-webui.patch` is the worked example:
a surface with its own `mojom` interface, its own handler, and no upstream file.

What this costs instead is a settings surface that does not exist yet. That is a
real cost and it is not hidden here — but it is one this project wants for other
reasons before it wants a second method on upstream's New Tab handler.

**All of it is built now, and none of it has been run.** The reader looks in
both directories, `chrome://sunshine-settings` exists with its own `mojom` and
handler, the picker is on it, and the New Tab's status row carries the link that
opens it. §5 is the whole of what "never run" means here.

Making the reader profile-aware turned up one thing worth stating, because it
was not in §3's table and it is not obvious from it:

**The availability cache had to be keyed by profile, and that was forced.**
`WarmAvailability`/`AvailableFromCache` were one `std::atomic<int>` for the
process, which was right while the only place a background could live was
beside `chrome.exe` — a property of the machine, the same for every profile in
it. The profile location makes it a property of a *profile*. A process-wide
answer would tell the second profile that a background exists because the first
one has one, and it would then create a frame for a file that is not there —
the exact defect the cache was introduced to avoid, arriving from the other
direction. It is a small map under a lock now, one entry per profile that has
opened a window.

## 4. The animation rules — NTB-3, and PB-5a

`docs/PERFORMANCE_BUDGET.md` PB-5a permits this animation and is the reason
the feature is allowed at all. Its three properties are required **together**,
and the third is the one a check can hold:

| | |
| --- | --- |
| **NTB-3** | Nothing Sunshine owns drives the animation: no repeating timer, no frame callback, no interval. The asset carries it. |

**Why that is the load-bearing one.** PB-5a's amendment turns on the animation
being the user's asset animating itself rather than Sunshine deciding to
animate forever. The moment Sunshine owns a timer driving frames, the third
property is false, the amendment no longer covers the feature, and PB-5's
original zero-tolerance rule applies again. So this is not a style preference
about how to write an animation — it is the condition under which the feature
is permitted to exist.

**Covering the viewport takes three declarations, and two of them are easy to
miss.** The page asks for `size=cover`, which is what "fit the shorter side,
keep the aspect ratio, leave no gap" means in CSS — upstream's helper template
sets `background-size: $i18n{size}` and nothing else scales the image. But
`cover` covers *its own box*, and the box is the iframe.

`iframe.css` sizes ntp-iframe's inner frame with `height: inherit` and
`width: inherit`. `inherit` takes the host's **computed** width and height, not
"all of the host". A host positioned with `inset: 0` alone computes both to
`auto`, and an iframe is a replaced element, so `auto` resolves to the
**300×150 default**. The host filled the viewport and the frame inside it did
not — a small rectangle in a corner with the page's own dark background around
it, which reads as a broken image rather than a mis-sized one. `#sunshineBackground`
states `height: 100%` and `width: 100%` for the same reason upstream's
`#oneGoogleBar` does.

**How the page shows it, and why it is an iframe.** The New Tab page overrides
`child-src` to admit `chrome-untrusted://new-tab-page` and does **not**
override `img-src`, so an `<img>` or a CSS `background-image` pointing there
would be refused by the page's own policy. That is why upstream's custom
background is an iframe too, and patch 0002 reuses upstream's
`custom_background_image` helper rather than inventing a second way in.

The iframe carries `hidden` whenever `document.visibilityState` is not
`visible`. A hidden subtree renders nothing, so an animated asset inside it
decodes nothing — which is PB-5a's first property made structural rather than
assumed. **Hidden rather than removed, deliberately**: `UntrustedSource` does
not cache, so removing the iframe would re-read the whole file from disk on
every return to the tab.

**Visible-only and opt-in are runtime criteria** and are PB-5a's own two
measured runs: idle with no asset configured must equal PB-5's original zero,
and idle with an asset configured but the New Tab hidden must equal the
no-asset run. Neither needs a baseline and the second is decidable the first
time anyone opens a second tab. They are not restated here as NTB numbers
because they already have a home.

## 5. NOT VERIFIED

- **Nothing has been run.** No background has been placed, served, or
  displayed, and no animated asset has played in a Sunshine build. The whole
  of §2 to §4 is source a guard holds, not evidence about a browser. It has
  been compiled — build #40, run `32445665066` — and compiling is not running:
  the feature was in fact **broken at that point** and the green build said
  nothing about it. See the note under NTB-5.
- **That the instant state change reads as responsive rather than abrupt is a
  guess.** It replaced a fade for a build reason, not a design one, and nobody
  has seen either version.
- **The searchbox's 65% has never been looked at.** §3c's normal state is a
  chosen opacity with no contrast measurement behind it, and the composite it
  has to remain legible against is a photograph nobody has picked yet. The
  placeholder is the exposed element — it sits at full opacity over a surface
  that moves toward the image behind it. Two states have been proved to exist
  in source and neither has been seen.
- **`hasUserInput_` is stale after a programmatic `setInputText()`**, which is
  upstream's behaviour and now Sunshine's too. §3c argues the visible result is
  still correct because those paths also focus the box, and that argument has
  been read out of the source rather than watched happen.
- **A rejected file is indistinguishable from no file, everywhere except the
  picker.** `ReadInstalledBackground` returns empty for a missing file, an
  oversized one, and one whose bytes are not a permitted format alike, and
  nothing that *serves* a background says which happened. The settings surface
  is the one place that does: it holds the bytes, the rule and the person at the
  same moment, so it can say *112 MB, and the limit is 100*. A file placed in a
  directory by hand still produces silence, and always will — nobody is there to
  be told.
- **Nothing about the picker has been run.** No dialog has opened, no file has
  been copied, and no refusal sentence has been read by anyone. What is known is
  that the chain of declarations is complete, because a guard reads it end to
  end — not that a person who picks a 4 GB video sees the sentence this contract
  says they will.
- **The settings surface's route from the New Tab is upstream's own shape,
  read rather than exercised.** `chrome://history` links to
  `chrome://settings/clearBrowserData` with a plain anchor at the pinned
  revision, so a renderer-initiated navigation between WebUI hosts is
  established practice. Whether *this* anchor, in the New Tab's shadow root,
  navigates as intended has not been seen.
- **The move of the generated Mojo bindings to a `mojom/` directory is the
  least-tested change in patch 0024, and it touches a surface that works.**
  `build_webui()` copies every surface's bindings into one directory by
  basename; that directory used to be the document surface's own, which made
  its prefix filter serve them for free. It is now nobody's, each surface names
  its own file, and the document surface's import moved with it. This is read
  from `ui/webui/resources/tools/build_webui.gni` — `outputs = [
  "${preprocess_dir}/${mojo_base_path}/{{source_file_part}}" ]` — and the first
  thing to check in build #47 is whether `chrome://sunshine-document` still
  loads.
- **One file probe per process remains, and it is a deviation from PB-4.**
  The page is told whether a background exists, so a build with no asset
  creates no frame and opens no file per tab. The browser answers from a cache
  it fills once, warmed when the first window is created. That fixed the
  original defect — three probes on **every** New Tab, which broke PB-4's
  zero-tolerance condition 1 ("not once per window, not once per tab") and its
  condition 3 ("no cost that scales with anything else"). The feature had been
  reasoned against PB-5 alone, the budget that was being amended for it.

  What remains is one file probe per browser process, and PB-4 condition 1
  permits **no** file on the startup path but the workspace catalog. That is a
  deviation and it is recorded here rather than legislated away: amending a
  second budget to fit the same feature is the pattern that produced this
  finding, and doing it again would be the wrong lesson.
- **The first New Tab of a session may show no background.** The probe runs
  off the UI thread, and a New Tab created before it returns is told `false`.
  Window creation precedes tab creation so the window is normally milliseconds
  wide, but it is a race and nothing closes it. The alternative was file I/O
  on the thread that draws.
- **`GetMimeType` names the path, not the bytes.** A `.png` request returns
  JPEG or WebP bytes when that is what was installed. Blink chooses its
  decoder by signature rather than by declared type — the same fact the format
  rule rests on, and one this page already relies on upstream — but it is an
  assumption about Blink, not a measurement.
- Whether Blink suspends an animated background's decoding in a hidden tab
  **to the degree PB-5a's second run requires** is an assumption about
  upstream behaviour, not a measurement. It is the likeliest place for this
  feature to fail its own budget, and it fails there quietly.
- **The asset is read once per New Tab, not once per process, and that is
  read rather than assumed.** `UntrustedSource::AllowCaching()` returns `false`
  at the pinned revision, so `content/browser/webui/url_data_manager_backend.cc`
  sets `Cache-Control: no-cache` on every response and attaches no ETag or
  `Last-Modified` for a cache to revalidate against. Each New Tab showing a
  background therefore re-enters `StartDataRequest` and reads the whole file
  again into the browser process before it crosses to the renderer. At the
  100 MB cap, five New Tabs read half a gigabyte. **What has not been measured
  is whether Blink's in-process memory cache short-circuits some of those
  loads** -- that needs a running browser, and the source says only what the
  HTTP layer will do.
- **The helper requests the asset twice per New Tab, and only one of those is
  the background.** `background_image.html` carries `<img src="{url}" hidden>`
  alongside the CSS `background-image`, commented upstream as existing "purely
  to capture the load event". Whether both reach `StartDataRequest` or the
  second is served from the renderer's in-process cache is **not verified** —
  it needs a running browser. If both do, every figure in the bullet above
  doubles.
- **The cap was raised from 32 MB to 100 MB by the owner's decision, and the
  earlier number had no measurement behind it either.** What changed is that
  the cost per New Tab above is now known, so the number is a choice made
  against a stated cost rather than against a shrug. It is still not a bound
  proven survivable: no build has read a file of this size.
- **A 100 MB cap is enforced, and nothing tells a reader they hit it.**
  `kMaxAssetBytes` is `100u * 1024u * 1024u` and `ReadFileToStringWithMaxSize`
  refuses a larger file outright rather than truncating it. An earlier draft of
  this bullet said no limit was set or enforced, which was false and sat in the
  NOT VERIFIED list where it would be believed. Size matters more
  for APNG than for the alternatives: APNG is lossless, so photographic or
  gradient-heavy material can be very large, while an animated WebP of the
  same material is lossy and typically far smaller. The installed payload
  measured at build #37 was already 419.5 MB against `docs/SIZE_BUDGET.md`'s
  250 MB investigation threshold, and whatever is placed adds to it directly.
- Which format suits which material is a judgement no check makes. APNG keeps
  sharp edges, text and alpha exactly; WebP is smaller for photographs and
  gradients at the cost of being lossy. Both are permitted and the file
  decides.
