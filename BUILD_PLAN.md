# WAPFLIX: local progressive streaming build plan

Status: proposed implementation plan; no streaming backend or performance claims implied.
Date: 18 October 2026.

## 1. Goal and deployment boundary

Keep the existing public, standalone GitHub Pages proof of concept working. Add a private Docker Compose deployment that converts local video into ASCII on demand, plays before conversion completes, reads SRT subtitles and eventually browses the Plex library. Both modes retain the handset experience.

Two supported deployments, one repository:

| Mode | Catalogue and playback | Hosting | Backend required |
| --- | --- | --- | --- |
| Public demo | Original/generated sample content and existing static clips | GitHub Pages | No |
| Private library | Local files, then Plex catalogue, progressively generated chunks | Local Docker Compose | Yes |

The public site must never depend on the home server, probe a local API, request a Plex token or reveal library information. The private deployment serves its frontend and API from the same origin. Do not connect the Pages frontend to a private server through CORS as the default design.

## 2. Confirmed baseline

Host: Intel Celeron N5105 @ 2.00 GHz. User-provided device listing exposes /dev/dri/card0 and /dev/dri/renderD128, owned by root:video with group read/write access. Source media is on a locally attached USB HDD. Internal SSD availability, RAM, source codecs and sustained conversion speed remain unconfirmed.

Inspected existing code:

- tools/build.py: FFmpeg grayscale extraction, brightness-to-ASCII mapping, three sequential quality conversions, whole-clip JSON and gzip output.
- index.html: static catalogue loading, whole-clip fetch/decompression, playback state and an unbounded Map cache.
- player.js: handset rendering overrides; still expects complete clip.frames arrays.
- tools/phone_video.py: procedural handset sample scenes, not a real-video converter.
- .github/workflows/pages.yml: builds _site using build.py, catalogue.py, presentation.py and phone_video.py, then publishes _site. It currently copies an existing assets directory into the artifact if present.
- No application backend or Compose deployment exists in the inspected baseline.

GPU device presence does not establish working hardware decoding. No real-file, host-specific end-to-end benchmark has been performed in this work.

## 3. Non-negotiable constraints

1. Preserve the public static demo and its generated content.
2. Never commit or publish real episode frames, source media, subtitles, personal catalogue exports, Plex tokens or local paths.
3. Keep source media read-only; write cache and application state elsewhere.
4. Bound RAM, disk cache, subprocess concurrency and generation look-ahead.
5. Support one active conversion worker initially. No Redis, Celery, Kubernetes or separate database service for the MVP.
6. Benchmark software decoding first; retain it as a fallback. Enable hardware decoding only after a successful capability and performance test.
7. No audio in the MVP. No claims that ASCII is inherently more bandwidth-efficient than video.

## 4. Proposed repository layout

Preserve existing root files and tools during the first milestones. Add:

```text
BUILD_PLAN.md
backend/                 Python API, worker, source adapters and cache
frontend/                Shared source adapters and incremental player modules
tests/                   Backend, protocol and static compatibility tests
Dockerfile
compose.yaml
.env.example             Placeholder configuration only
.dockerignore
docs/LOCAL_SETUP.md
docs/STREAM_FORMAT.md
docs/BENCHMARKING.md
```

Use Python with FastAPI/Uvicorn, FFmpeg/ffprobe and SQLite for local job/cache metadata. Start with one application process and one explicitly managed worker; do not start multiple Uvicorn workers that each create an independent queue. Pin application dependencies and document the tested FFmpeg/driver environment.

Runtime media/cache/state must be outside the repository checkout. Add defense-in-depth ignore rules for local data, logs, benchmark outputs and secrets. A later frontend extraction must update every build-time transformation that currently edits index.html; do not assume the root HTML is the complete deployed site.

## 5. Frontend compatibility architecture

Introduce a playback-source interface rather than teaching every UI function about Plex:

- StaticSource: existing catalogue and complete gzip/JSON clips; works with relative URLs under a repository subpath and without an API.
- LocalSource: same-origin catalogue, playback sessions, manifests and chunk requests.

Select mode through deployment-provided configuration. Pages defaults explicitly to static; local configuration is served only by the private application. Share handset rendering and navigation where practical, but keep legacy clip loading supported during migration.

Replace assumptions that duration equals clip.frames.length / fps with source-provided duration and frame access. Preserve play/pause, captions, quality selection, seek, information view and accessibility announcements. Replace indefinite clip caching with a byte-budgeted LRU cache.

## 6. Conversion and rendering pipeline

```text
Validated source -> ffprobe -> FFmpeg decode/sample/scale/grayscale
                 -> byte-to-glyph mapping -> independent chunks
                 -> atomic disk cache publication -> browser buffer
```

Starting profile: 40 columns, 6 fps, aspect-correct rows using the actual 6x8 handset cells. For display aspect ratio A, rows are approximately round(columns * 6 / (8 * A)); for 16:9 this is about 17 rows. Preserve letterboxing rather than stretch or silently crop. Validate sample aspect ratio, rotation and unusual dimensions.

Check the glyph brightness ramp against actual bitmap ink coverage. Consider a precomputed byte translation table to reduce Python per-pixel work. Start with independent full frames, not temporal delta encoding; optimise only after measurement.

Use one FFmpeg process for consecutive chunks, not one process per chunk. Read exact frame byte counts and fail clearly on incomplete frames or decoder errors. Drain stderr safely and bound retained logs. Publish validated chunks via temporary files and atomic rename.

Backpressure: stop consuming new frame output at the look-ahead limit, allowing bounded pipes/queues to stall generation. The pipe and decoder may retain a small bounded amount of extra work. Do not repeatedly terminate FFmpeg merely because the buffer is full. Close/kill and reap subprocesses on cancellation or timeout, including when blocked. Uncached seeks can restart decoding near the target.

Benchmark optional VAAPI/QSV decoding separately. Account for frame transfer and filter compatibility; GPU support is codec/driver dependent. A failed hardware attempt must not poison the cache or silently report hardware success.

## 7. Chunk protocol and timeline

Initial proposed values: two-second chunks, four seconds buffered before playback, roughly 20-30 seconds of look-ahead. All are configurable and are hypotheses, not performance guarantees.

A versioned manifest describes media duration, profile, frame rate, dimensions, renderer version, chunk duration, source identity and readiness. Each chunk includes absolute starting frame index, frame count and frames. Define the final partial chunk, end-of-stream and timestamp rounding explicitly. Use integer frame indices as the ASCII playback timeline; map source timestamps and subtitle cues onto it.

Gzip each chunk independently. Keep transport compression semantics explicit: either application-level gzip with browser decompression, or HTTP Content-Encoding, never both accidentally. Specify MIME types, compressed/uncompressed limits and a fallback for browsers without DecompressionStream.

The player must start before the episode finishes converting, prefetch bounded chunks, pause its media clock on underrun, distinguish buffering from completion and release old decoded data. Seeking within cached data is immediate; an uncached seek shows buffering and invalidates stale requests. Quality changes preserve episode time but use a new profile/session generation. AbortController plus generation IDs prevent late responses overwriting current state.

## 8. API and worker model

Proposed private API, subject to protocol tests:

- GET /api/health and /api/capabilities
- GET /api/catalogue: local test items initially, paginated Plex items later
- POST /api/playbacks: opaque item ID, profile and initial position
- GET /api/playbacks/{id}/manifest: state and available chunks
- GET /api/playbacks/{id}/chunks/{index}: completed chunk, pending response or explicit error
- PATCH /api/playbacks/{id}: playhead/seek updates and lease renewal
- DELETE /api/playbacks/{id}: release viewer lease
- GET /api/playbacks/{id}/subtitles: normalised timed cues

Define pending responses and retry hints; never return a partial chunk as complete. Begin with bounded polling and ordinary HTTP requests, not a custom WebSocket transport.

Separate playback sessions from conversion jobs. Deduplicate overlapping requests for the same source/profile, prioritise the active seek region and enforce one converter globally. Leases expire if the browser disappears; a pause stops unnecessary generation after bounded look-ahead. Cache data can outlive sessions.

SQLite stores recoverable metadata, not frame blobs. Restart recovery removes abandoned temporary files and marks incomplete work retryable. Invalid or corrupt cache entries regenerate safely.

## 9. Sources and subtitles

First source: explicitly configured local MP4 and SRT paths, outside Git, exposed to the browser only through opaque IDs. No arbitrary client-supplied filesystem paths or remote URLs.

Plex adapter follows the proven local pipeline: server URL/token remain backend-only; fetch catalogue lazily with pagination; resolve a selected media part and map Plex path prefixes onto container media roots. Validate all resolved paths remain within approved roots, including symlinks.

MVP Plex scope: a selected single-part local media version plus external SRT, where available. Explicitly report inaccessible paths, multiple versions, multi-part media and unsupported subtitle types. Add selection rules before claiming general library compatibility. Server-mediated retrieval is a later option, not required initially.

Parse SRT into absolute episode-relative start/end/text cues. Handle BOM, common encodings, CRLF, multiline cues, overlaps and malformed entries. Strip unsupported formatting, render safely and preserve caption toggling. Seeking must not shift subtitle timing. Embedded text subtitles can follow; image subtitles and OCR are out of scope.

## 10. Cache and resource policy

Cache identity includes source version, stream selection, output dimensions/fps, glyph/renderer version and converter version. Prefer path-independent internal IDs; detect source changes using size/mtime plus an explicit refresh or fingerprint policy.

Set configurable disk quota, decoded-browser byte budget, job limits and idle expiry. Evict least-recently-used unleased chunks; do not remove active chunks. If all remaining chunks are pinned, stop generation and report quota pressure. Check free space, handle disk-full and disconnected USB storage, and do not spin in retry loops.

Prefer internal SSD for cache/state if available. Otherwise use a dedicated HDD directory, acknowledging source reads and cache writes share the disk. Avoid concurrent jobs and measure cold reads, spin-up and seeks separately from warm-cache replay.

## 11. Docker and access

One Compose service initially, non-root runtime user, read-only media bind mount, writable cache/state mounts and healthcheck. Example host paths belong in local environment configuration, not tracked settings. Optional GPU device passthrough and supplemental numeric group IDs must follow host permissions, not a hardcoded assumption that every system uses a render group. Never use privileged mode or chmod 777 as the fix.

Default host binding is loopback. Direct LAN exposure requires authentication or a documented trusted-access boundary. Prefer Tailscale for private access; if using a Cloudflare hostname, protect the whole application with Access or equivalent authentication. Do not trust origin obscurity or CORS as authentication. Protect expensive session endpoints, validate inputs and redact credentials/paths from client errors and logs.

## 12. Delivery milestones and acceptance gates

### M0: protect the existing demo

Capture static build output and browser smoke checks before changes. Add ignore rules and artifact checks. Preserve the existing workflow; later tighten its broad assets copy into an explicit public-content allowlist. Gate: Pages builds and plays sample content with no backend and no /api requests, including repository-subpath hosting.

### M1: real-file diagnostic

Add containerised probe/conversion command, one handset profile, SRT parser and machine-readable benchmark output. Use generated fixtures in CI and a user-provided private source on the host. Gate: playable real extract, correct proportions, captions and measured time-to-first-chunk, throughput, output bitrate, CPU and peak memory.

### M2: progressive local playback

Add API, chunk cache, worker scheduling and LocalSource. Gate: playback starts while conversion continues; buffer/memory remain bounded; pause, resume, cached/uncached seeks, subtitle timing, EOF and decoder errors work.

### M3: reliability and hardware comparison

Add lease cleanup, restart recovery, quota eviction, software/hardware comparison and resource controls. Gate: a full episode test, cancellation without orphaned FFmpeg, disk-full/USB disconnect handling, cold/warm replay and simultaneous ordinary Plex playback. Include sustained thermal behaviour, not just a short burst.

### M4: Plex catalogue

Add server-side credentials, paginated browsing, media-version selection, path mapping and subtitle resolution. Gate: a selected supported Plex item plays without exposing tokens or filesystem paths; unsupported sources fail clearly; Pages still has no Plex dependency.

### M5: tune and document

Tune quality and buffering from actual measurements. Add optional profiles only when the baseline is reliable. Document deployment, backup scope, cache reset, driver troubleshooting and known limitations. Delta encoding, background pre-conversion, audio and multiple concurrent viewers remain separate follow-up work.

## 13. Benchmark decision criteria

Record host/container versions, source codec/resolution/bit depth/fps, profile, decoder path, storage/cache state, first-chunk latency, startup delay, sustained media-seconds/wall-second, compressed bytes/second, CPU, peak RSS and stalls.

Target comfortably above 1x throughput; approximately 2x or better is a useful initial headroom goal, not a guaranteed capacity. If throughput is marginal, compare decoder paths and reduce fps/detail before extending the startup buffer. Longer buffering only postpones underrun when sustained generation is slower than playback. If necessary, offer explicit advance conversion instead of mislabelling it real-time.

## 14. Test and publishing policy

Unit tests: frame mapping/aspect ratios, SRT edge cases, chunk boundaries, cache keys, path traversal, request validation and worker state transitions. Integration tests: FFmpeg-generated fixtures, partial final chunks, seeks, cancellation, duplicate requests, restart recovery, corruption, quota exhaustion and storage failure. Browser tests: both source adapters, caption timing, buffering clock, quality switches, stale responses, bounded caches, keyboard controls and accessibility.

Every playback-related change must pass static build and smoke tests as well as backend tests. Test the assembled _site, not only root files. CI uses generated or explicitly redistributable media; never home-server credentials or personal episodes. Keep backend/runtime files, secrets, local configuration and private assets out of the Pages artifact using an allowlist and automated assertions.

Documentation-only adoption of this plan must not alter the existing Pages workflow or application behaviour. All later implementation commits should state what was actually tested and distinguish host benchmarks from CI checks.
