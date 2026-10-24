# Wapflix master roadmap

Status: planning index, updated 2026-10-24. For actual checkpoint status and the next task, start at [docs/START_HERE.md](docs/START_HERE.md). File existence, a commit message or a design document is not proof of host acceptance.

## Destination

A private single-user service: browse supported Plex content in a retro handset on a modern browser, watch progressively converted LCD video, pause/seek/use captions and eventually resume later. Run through Compose with bounded resources. Keep public Pages independent of private APIs, media, credentials and catalogue data. Not a replacement for Plex or an actual legacy-WAP hardware client.

## Phase map

| Phase | Outcome | Position |
| --- | --- | --- |
| 1 | Predictable local conversion | Existing foundation; evidence remains checkpoint-specific |
| 2 | Progressive delivery with bounded buffers | Existing diagnostic foundation |
| 3 | Source-time captions | Existing diagnostic foundation |
| 4 | Safe seeking and cleanup | Existing diagnostic foundation |
| 5 | One on-demand source in the actual handset | Incomplete integration; prerequisites/real-backend recovery remain |
| 6 | Supported deployment and persistent bounded cache | Plan, not implementation completion |
| 7 | Safe Plex-backed browsing/playback | Gated plan |
| 8 | Everyday viewing and personal-use v1 | High-level proposal |
| 9 | Evidence-led compatibility expansion | Candidate backlog |
| 10 | Measured performance/creative refinement | Candidate backlog |

## Active sequence

1. R1 readiness correction: committed at 32d042177b0e2eb71fb778deff5de0854cc29e1f; current status evidence is in START_HERE.
2. R2A ownership core: committed at fe442e669c64f3af3c358a71ceda6328e548643b; unit core only.
3. R2B backend integration: use [the small contract/passes](docs/plans/R2B_BACKEND_CONTRACT.md), starting with R2B.1.
4. R2C adapter integration after the real backend gate passes.
5. Repair/finish the 5A.3 host/bridge and real-browser acceptance, then 5A.4-5A.6.

Do not redo R1 merely because an older plan records its original defect. Do not mark full R2 or 5A.3 complete from the isolated core or fake-response tests.

## Detailed phase requirements

- Phase 5: [HANDSET_5A3_PLAN.md](HANDSET_5A3_PLAN.md), [HANDSET_STAGE5_REMAINING_PLAN.md](HANDSET_STAGE5_REMAINING_PLAN.md). These remain design/review records; START_HERE owns up-to-date completion status and the R2B contract owns the newly split R2B protocol.
- Phase 6: [PHASE6_DEPLOYMENT_PLAN.md](PHASE6_DEPLOYMENT_PLAN.md). One supported runtime, read-only media, explicit origins, full configured windows, quota/cache/recovery/rollback. Implement only after Stage 5 acceptance.
- Phase 7: [PHASE7_PLEX_PLAN.md](PHASE7_PLEX_PLAN.md). One server/credential, allowed libraries, safe local resolution and existing conversion pipeline. No original-video proxy or Plex transcoding dependency in v1.

## Phase 8: everyday viewing/v1

Detail after Phase 7 identity is stable: presented-position Continue Watching, changed-source handling, next-episode progression with explicit autoplay preference, persistent My List/local completion state, coherent device/navigation/error behaviour and release/setup/upgrade validation. Temporary sessions, capabilities and cache jobs are not viewing identity. Keep state local; Plex watch-state writes need a separate approved contract.

## Phase 9: compatibility candidates

Additional media-version cases, embedded text subtitles, language selection, multi-part sources and tested containers/codecs. Alternative source retrieval only for an evidenced requirement. Listed in Plex does not automatically mean supported.

## Phase 10: measured refinement candidates

Hardware-decoder comparison, partial-cache recovery, cross-window reuse after parity work, cold-start/CPU/disk improvements, compared LCD profiles, legibility, accessibility and handset polish. Do not silently replace the baseline or reuse incompatible cache.

## Optional experiments and boundaries

Audio, offline downloads, background conversion, multiple viewers/converters, other server adapters and elaborate public demos are separate decisions. Private access remains governed by Phase 6, not unauthenticated public exposure.

Separate catalogue references, immutable source descriptors, conversion/cache identity, temporary playback ownership and persistent viewing state. Media stay read-only; private content stays out of public artifacts. Same-origin hosting, bounded resources and explicit ownership persist.

Save one narrow checkpoint at a time with versions, files, tests, limitations and next gate. Keep mocked, real HTTP, real-browser and host results distinct. Preserve working fallbacks. Useful release points: dependable technical MVP after 6, Plex-backed alpha after 7, everyday-use v1 after 8; 9-10 need not block v1. No dates or completion claims are implied.
