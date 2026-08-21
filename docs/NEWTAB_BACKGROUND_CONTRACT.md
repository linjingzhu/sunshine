# New Tab background — contract

## Status and scope

The content area's background on `chrome://new-tab-page`, for the Chromium
revision pinned by Sunshine OS: `152.0.7977.42` (see `config/chromium.version`).

**Partly implemented.** `downstream/patches/0020-sunshine-newtab-background-format.patch`
implements §2 — what a background may be, and how that is decided — and
`scripts/verify_newtab_background.py` holds the patch to this document. The
serving path (§3) and the page itself (§4) are not written.

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

**Video was excluded on grounds worth keeping**, because "we did not get to it"
is a different thing from "we decided against it". A short clip decoded on the
GPU is affordable; what it is not is *free of everything else*. It brings a
decode pipeline, an audio track that would have to be proven silent, and a
codec-licensing question that `docs/decisions/0004-media-codecs.md` scoped
deliberately to page content. An animated image needs none of that and looks
the same from two metres away.

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

**Serving is not implemented and has a measured cost.** A WebUI page cannot
read an arbitrary disk path. Chromium's own local-background bytes reach the
New Tab page through `chrome/browser/ui/webui/new_tab_page/untrusted_source.cc`,
which today serves one fixed name out of the **profile** directory and
validates the path strictly against directory traversal. Serving from the
install directory means owning that file: **+1 upstream file**, currently
owned by no patch. It is the honest place for it — serving these bytes to
this page is that file's whole job — and it is a real cost against a stack
that owns twenty upstream files today.

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

**Visible-only and opt-in are runtime criteria** and are PB-5a's own two
measured runs: idle with no asset configured must equal PB-5's original zero,
and idle with an asset configured but the New Tab hidden must equal the
no-asset run. Neither needs a baseline and the second is decidable the first
time anyone opens a second tab. They are not restated here as NTB numbers
because they already have a home.

## 5. NOT VERIFIED

- **Nothing has been run.** No background has been placed, served, or
  displayed, and no APNG has been animated in a Sunshine build. §2 is a rule a
  guard holds over source, not evidence about a browser.
- The serving path of §3 does not exist, so the format rule currently
  constrains code that nothing calls.
- Whether Blink suspends an animated background's decoding in a hidden tab
  **to the degree PB-5a's second run requires** is an assumption about
  upstream behaviour, not a measurement. It is the likeliest place for this
  feature to fail its own budget, and it fails there quietly.
- **No size limit is set for the asset and none is enforced.** It matters more
  for APNG than for the alternatives: APNG is lossless, so photographic or
  gradient-heavy material can be very large, while an animated WebP of the
  same material is lossy and typically far smaller. The installed payload
  measured at build #37 was already 419.5 MB against `docs/SIZE_BUDGET.md`'s
  250 MB investigation threshold, and whatever is placed adds to it directly.
- Which format suits which material is a judgement no check makes. APNG keeps
  sharp edges, text and alpha exactly; WebP is smaller for photographs and
  gradients at the cost of being lossy. Both are permitted and the file
  decides.
