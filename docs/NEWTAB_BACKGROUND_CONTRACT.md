# New Tab background — contract

## Status and scope

The content area's background on `chrome://new-tab-page`, for the Chromium
revision pinned by Sunshine OS: `152.0.7977.42` (see `config/chromium.version`).

**Implemented, and never run.** Three patches:
`0020-sunshine-newtab-background-format.patch` decides what a background may
be (§2) and reads it; `0021-sunshine-newtab-background-source.patch` serves it
(§3); `0002-sunshine-new-tab.patch` shows it (§4).
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
| **Video** | **Permitted, by the owner's decision reversing the exclusion.** WebM only, carrying VP9 or AV1 — the codecs `docs/decisions/0004-media-codecs.md` actually ships. Muted, and looping by the element's `loop` attribute. |

**Video was excluded, and the exclusion has been voided by the owner.** The
grounds are kept here because two of the three did not survive being re-read,
and a record that quietly drops its own reasoning is worth less than one that
shows where it was wrong.

| Ground recorded for the exclusion | On re-reading |
| --- | --- |
| A codec-licensing question | **Did not survive.** ADR 0004 decided to leave proprietary codecs *off*: H.264 and AAC are absent, and VP9, AV1 and Opus are royalty-free. A WebM file the owner encodes raises no licensing question. |
| An audio track that must be proven silent | **Did not survive.** `muted` on the element is a stronger guarantee than reading the container, and the autoplay policy requires it anyway. |
| A decode pipeline | **Stands.** A media pipeline and a video decoder instance per New Tab, which no image needs, and which nothing has measured. |

**And one thing changed on the other side of the ledger.** §5 records that the
asset is re-read on every New Tab, because `UntrustedSource::AllowCaching()` is
false. A video codec makes the same material about an order of magnitude
smaller than an animated WebP does, so admitting video *reduces* the largest
cost this feature is known to carry. That was not true when the exclusion was
written, because that measurement did not exist yet.

**What is not yet built, and what it needs.** No code serves or plays a video.
The page cannot simply gain a `<video>` element: the New Tab page reaches its
background through an iframe precisely because its own content policy refuses
media loaded from `chrome-untrusted://new-tab-page`, and that applies to
`media-src` as it does to `img-src`. So a video background is a **second helper
document**, served from the untrusted source with a policy that admits its own
media — not a relaxation of the New Tab page's policy. That choice is recorded
before the code exists so that the cheaper, worse option is a visible decision
rather than a default.

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
- **A rejected file is indistinguishable from no file.** `ReadInstalledBackground`
  returns empty for a missing file, an oversized one, and one whose bytes are
  not a permitted format alike, and no surface anywhere says which happened.
  An owner whose background does not appear has nothing to read.
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
