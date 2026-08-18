# ADR 0004: Proprietary media codecs, under a personal-use premise

## Status

Accepted, conditionally. The condition is the whole decision: it holds only
while Sunshine is built and run by its owner, on their own machines, and is not
distributed. It must be revisited before any build reaches a second person.

## Context

`build/config/features.gni` at the pinned revision:

```text
proprietary_codecs = is_chrome_branded || is_castos || is_cast_android ||
                     is_chrome_for_testing_branded
```

Sunshine sets none of those, so `proprietary_codecs` is false by derivation, not
by a choice anyone made. `scripts/build_chromium_windows.ps1` stated it
explicitly, which made the value visible but did not make it decided.

The consequence was found by `docs/ACCEPTANCE_SUITES.md` tracing a Stage 1
acceptance item back to the build script: **a build from this pipeline cannot
decode H.264 or AAC.** Most video on the web is H.264, so much of the Stage 1
media corpus would not have played, and the failure would have looked like a
regression rather than a configuration.

The alternative is `proprietary_codecs=true` with `ffmpeg_branding="Chrome"`,
which compiles the H.264 and AAC paths. That is a licensing question, not an
engineering one. H.264/AVC is covered by a patent pool; Google holds a position
for Chrome that a downstream does not inherit by rebuilding Chromium's source.
Chromium ships the flag off precisely so that whoever turns it on takes the
question deliberately.

## Decision

**Enable `proprietary_codecs=true` and `ffmpeg_branding="Chrome"` for personal
use.**

The premise is that the owner builds Sunshine for themselves and runs it on
their own machines. Under that premise the browser is a private tool, and the
distribution question that drives the licensing analysis does not arise.

The premise is recorded here rather than assumed, because it is doing the work.
Nothing about the code changes if it stops being true; only the answer does.

## Consequences

- The Stage 1 media acceptance item becomes evaluable. It was previously
  determined by a build flag no document mentioned.
- FFmpeg is rebuilt with different sources, so the first build after this change
  recompiles a substantial part of the media stack rather than reusing cache.
- `docs/OPEN_DECISIONS.md` loses its oldest P0.
- **This decision does not travel with the artifact.** An installer produced
  under it is not licensed for redistribution by virtue of having been built.
  Publishing a release, handing a build to a colleague, or shipping to any third
  party requires revisiting this ADR first — and the honest default at that point
  is to turn the flag back off unless a licence has been obtained.
- The alternative left unexplored is delegating to the operating system's own
  decoders, which Windows users are already licensed for. Chromium has the
  Media Foundation pieces (`media/mojo/services/media_foundation_service.h`,
  `media/filters/win/media_foundation_audio_decoder.h`), but whether that path
  is reachable while `proprietary_codecs` is false is **NOT VERIFIED** — the
  flag also governs the MP4 demuxer and the H.264 parser, so an OS decoder may
  never be handed a stream to decode. If Sunshine is ever distributed, this is
  the first thing to establish, because it would remove the licensing question
  instead of answering it.

## Alternatives considered

**Leave it off.** VP9 and AV1 are royalty-free and YouTube serves them
preferentially, so the browser is not silent. But sites that offer only H.264
are common enough that dogfooding would repeatedly hit "the video does not
play", and the acceptance suite could not distinguish that from a defect.

**Delegate to OS decoders.** The right answer if it works, since it needs no
licence. Unverified, as above, and it cannot be verified without a build. Left
as the path to take if the personal-use premise ever ends.
