# Wapflix master roadmap

Status: planning index, 2026-10-20. File/plan existence is not proof of implementation or host acceptance. This document adds no runtime features, deployment or test results. Detailed phase documents own their contracts; this index does not silently override them.

## Destination

A private single-user service: open the retro handset in a modern browser over LAN/private access, browse supported Plex content, and watch on-demand dithered LCD video with captions, pause, seek and eventual resume. Run it through Docker Compose with bounded resources. Keep the public GitHub Pages demo independent of the home server and private library.

This is not a replacement for Plex, an actual legacy-WAP hardware client or a multi-user commercial platform.

## Phase map

| Phase | Purpose | Exit outcome | Planning position |
| --- | --- | --- | --- |
| 1 | Conversion foundation | Predictable LCD frames | Existing foundation; acceptance evidence remains specific |
| 2 | Progressive delivery | Playback before complete conversion, bounded buffers | Existing checkpoint foundation |
| 3 | Source-time captions | Correct cue timing through holds | Existing checkpoint foundation |
| 4 | Safe seeking | Latest intent and cleanup | Existing checkpoint foundation |
| 5 | Handset integration | One fixed source inside the actual handset | In progress/planned gates; reviewed prerequisites apply |
| 6 | Supported local deployment | Compose, full-source handling, recovery and persistent bounded cache | Detailed plan committed; no completion claim |
| 7 | Plex integration | Browse and play supported library items safely | Detailed gated plan alongside this index |
| 8 | Everyday viewing/v1 | Leave, return and continue without developer intervention | High-level proposal |
| 9 | Compatibility expansion | Cover evidenced unsupported library cases | Post-v1 candidate backlog |
| 10 | Performance/creative refinement | Measured improvements without breaking the baseline | Post-v1 candidate backlog |

## Phase 5

Follow [HANDSET_5A3_PLAN.md](HANDSET_5A3_PLAN.md) and [HANDSET_STAGE5_REMAINING_PLAN.md](HANDSET_STAGE5_REMAINING_PLAN.md). Fix readiness-after-eviction and unacknowledged-Start ownership prerequisites before the live connection. Then finish one live entry, lifecycle, captions and handset seeking. Static playback remains intact.

## Phase 6

Follow [PHASE6_DEPLOYMENT_PLAN.md](PHASE6_DEPLOYMENT_PLAN.md). Preserve the accepted Phase 5 protocol while adding one supported runtime, restricted Compose image, read-only media, explicit origins, full configured source windows, persistent exact-window cache, quotas, recovery and rollback. Exit is a dependable self-hosted technical MVP with a configured source.

## Phase 7

Follow [PHASE7_PLEX_PLAN.md](PHASE7_PLEX_PLAN.md). One Plex server/credential and selected libraries. Use Plex metadata, safe local source resolution and the existing Wapflix playback/cache pipeline. No original-video proxy or Plex transcoding dependency in v1. Exit is a useful Plex-backed personal alpha for supported items.

## Phase 8: everyday viewing and first complete v1

Detail after Phase 7 source identity is stable:

- Persistent viewing identity tied to server/item/version/source, never temporary sessions or capabilities.
- Continue Watching stores presented source position, not conversion look-ahead. Handle changed/missing media and distinguish resume from restart.
- Next-episode progression and explicit autoplay preference, with cancellation and unsupported-next-item handling.
- Persistent My List and local watched/completed state across the user's devices.
- Clear disconnected/expired/unavailable screens and a complete keyboard/touch/handset journey.
- Reproducible setup, troubleshooting, upgrade/recovery and end-to-end release validation.

Keep viewing state local initially. Plex watch-state/timeline writes require a separate approved contract. Target a complete everyday-use v1 after this phase, rather than postponing it for every format or optimisation. No delivery date is implied.

## Phase 9: evidence-led compatibility

Candidate slices: additional media-version selection, embedded text subtitles, language/track selection, multi-part media and additional tested local containers/codecs. Alternative source retrieval only if local mapping cannot cover a real requirement. Each gets an explicit supported/unsupported contract. Listed in Plex never automatically means playable in Wapflix.

## Phase 10: measured refinement

Candidate slices: hardware-decoder comparison, faster partial-cache recovery, cross-window reuse after parity work, cold-start/CPU/disk improvements, compared LCD/dither profiles, motion/legibility work and handset/accessibility polish. Do not silently change the stable default or reuse incompatible cached output.

## Optional experiments

Audio, offline downloads, background pre-conversion, concurrent viewers/converters, other media-server adapters and elaborate public-demo experiences are not core commitments. Promote them only through separate scope and resource/security decisions. Private remote access and its optional authenticated edge profile remain governed by Phase 6, not an excuse for unauthenticated exposure.

## Architecture and delivery rules

Separate catalogue identity, immutable resolved source, conversion/cache identity, temporary playback ownership and persistent viewing state. A metadata title edit is not a source-file replacement; a session ID is not a resume identity.

Keep source files read-only; private frames, full SRTs, credentials and library exports stay outside public artifacts. Same-origin application/API, bounded resources and explicit ownership persist across phases.

Implement one narrow checkpoint at a time, save it, then advance. Do not create another server/player generation per feature. Record exact versions, changed files, tests, limitations and next gate. Separate mocked tests, real HTTP, browser validation and host performance. Keep a working fallback.

Useful stopping points: after 6, dependable technical MVP; after 7, Plex-backed alpha; after 8, complete personal-use v1. Phases 9-10 are candidates, not mandatory v1 blockers.
