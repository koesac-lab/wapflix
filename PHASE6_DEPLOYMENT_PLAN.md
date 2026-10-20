# Phase 6: supported local deployment and bounded persistent cache

Status: resolved planning specification, 2026-10-20. Documentation only. No runtime, Compose, cache implementation, benchmark or deployment result is claimed. Phase 6 implementation starts only after the reviewed Stage 5 prerequisites and handset acceptance gates pass.

This document defines M6 from LOCAL_STREAMING_STEPS.md. It supersedes conflicting early deployment/cache proposals in BUILD_PLAN.md for this phase; it does not replace the Stage 5 interface/lifecycle plans or change them by implication. Plex/library integration remains later work.

## 1. Outcome and boundaries

Deliver one supported Docker Compose service on the N5105 that reads approved local media from the USB disk, serves handset/API from one origin, supports full configured finite sources, preserves Stage 5 controls/captions/seeking, and maintains a bounded persistent chunk cache. The public Pages demo remains independent.

Not included: Plex browsing, multiple viewers/converters, distributed scheduling, Redis, Kubernetes, audio, new qualities, live ASCII mode, persistent playback history/resume, cross-window cache reuse, image-subtitle OCR or unauthenticated public access. GPU decoding and Cloudflare access are optional later profiles, not prerequisites for private deployment.

Stage 5 source-time semantics, generation fencing, cancellation and caption rules remain authoritative. Freeze actual accepted request/response contracts at 6.0; do not rename endpoints to the older draft API while changing deployment.

## 2. Configuration contract

All configuration is validated before playback admission. Host-specific required values are resolved as operator inputs, not implementation choices to be silently guessed. A missing value produces a named configuration error. Local values/secrets are never committed.

| Setting | Decision |
| --- | --- |
| Application/manager count | Exactly one ASGI application process and one session manager |
| Active converter limit | Exactly one Wapflix converter; unrelated Plex processes are outside this limit |
| Profile | Accepted Stage 5 fixed LCD profile; default maximum width 240, 8 fps, two-second chunks |
| Buffer/look-ahead | Preserve accepted Stage 5 values; initial baseline four-second startup and eight published chunks ahead, plus bounded previous/pending data |
| Internal listen | 0.0.0.0:8080 inside the container |
| Published port | Default 8103; published addresses explicitly configured |
| Public origins | Required exact scheme/host/port list for enabled LAN/Tailscale access; no wildcard origins |
| Runtime UID/GID | Required host-compatible non-root numeric IDs |
| Media root/source | Required host bind and registered relative source identity; container root /media, read-only |
| Media identity | Required expected sentinel/identity within the mounted root |
| Cache/state mounts | Required separate writable locations, /cache and /state; local filesystems supporting required locks/atomic rename |
| Cache quota/free reserve | CACHE_MAX_BYTES and MIN_FREE_BYTES required positive operator values, checked on actual filesystems |
| Container memory limit | Required deployment value; release acceptance requires measured workload headroom, not an invented universal RAM default |
| PID limit | Initial ceiling 128, verified under the frozen decoder/runtime workload |
| Temporary filesystem | /tmp capped at 64 MiB and included in measured memory headroom |
| State allocation ceiling | Initial 64 MiB for index/WAL/temporary metadata, separately monitored; explicit override allowed after validation |
| Logs | Docker rotation initially 10 MiB x 3; FFmpeg stderr retained in a bounded 64 KiB ring per active process |
| Decoder | Software baseline with frozen/tested arguments; no automatic GPU assumption |
| Source safety ceiling | Finite local media only; default maximum configured window 24 hours, explicitly adjustable and validated |

The initial data-chunk JSON ceiling is 256 KiB and compressed-file ceiling 260 KiB for the fixed profile. Reject oversized data rather than unbounded decompression. Cache quota must accommodate at least ten maximum-sized chunk files, plus the independently enforced disk reserve. New profiles require a reviewed bound change. These ceilings do not imply measured host capacity.

Preflight records RAM, available space, actual mount points/filesystems, UID/GID permissions, Compose/FFmpeg/application versions, enabled origins and measured representative-source memory. Do not ship a configuration with placeholders treated as real paths.

## 3. Supported runtime and exclusive ownership

Use a thin FastAPI/Uvicorn runtime around the accepted manager/conversion operations. Keep old diagnostic tools available; do not port their standard-library HTTP server unchanged and label it the supported deployment.

Explicitly set one Uvicorn worker, no development reload and no replica scaling. Initialise the manager in application lifespan, not import-time module side effects. Run blocking management/filesystem work outside the event loop with bounded admission; no independent manager per HTTP thread/process.

Acquire nonblocking OS advisory locks on /cache/.instance.lock and /state/.instance.lock before opening writable state or accepting playback. Take cache then state; failure releases any acquired lock and fails startup clearly. A second instance sharing either root is refused, even with a different port. Lock-file existence/PID text is informational; do not decide ownership by deleting a supposedly stale PID file. Exclude lock files from eviction. Network-filesystem deployments are not supported in v1.

One converter means one managed Wapflix job per deployment, not a host-wide ban on FFmpeg. No new worker may start until replacement cleanup is confirmed. Preserve Stage 5 pre-acknowledgement Start fencing and navigation cancellation.

## 4. Container and storage layout

/app contains application/frontend and is read-only at runtime. /media is a read-only bind. /cache and /state are writable and outside Git. /tmp is bounded. Never mount the Docker socket or use privileged mode/chmod 777 as a permission fix. Drop unnecessary capabilities, enable no-new-privileges and use an init process.

Build from explicit source/frontend allowlists, not unrestricted COPY of the checkout. Exclude private frames/catalogues, media, SRTs, configuration/secrets, archives, backups, output and debug logs. Any baked static demo assets require an explicit public-content allowlist. Pin dependencies/image references and record the actual FFmpeg build.

Validate media sentinel, source identity, permissions and confined real paths. Missing bind paths must not be auto-created as fake media roots. An existing empty mount directory is not proof the USB disk is mounted. Cache/state locations must not overlap the media root or each other.

Unavailable USB storage makes playback unready without deleting cache or repeatedly restarting the service. Do not infer source deletion/version change from temporary inaccessibility. Source loss during generation produces a typed error after any playable buffered data; no infinite retry/probe loop. New playback is refused until source validation succeeds again. Source media is never a cleanup target.

## 5. Network and access contract

The handset and API use the same external origin. Validate configured public origins rather than comparing the browser Host/port with the container's internal socket address/port. Preserve host/origin validation and capability protections through Docker port mapping.

Published addresses are explicit. Direct LAN access remains supported without SSH tunnelling. Binding all host interfaces is a deliberate trusted-network choice with a warning, not public authentication. Anyone permitted to open the trusted-network page can control the single session.

Start with LAN and/or private Tailscale. Serve is a private-tailnet option; Funnel/public tunnels are not enabled implicitly. Reverse-proxy headers are accepted only from explicitly configured trusted proxy addresses. Direct clients cannot spoof a proxy identity.

Optional Cloudflare deployment protects the whole application, including API/chunks, validates the Access boundary and prevents direct-origin bypass. It is a separate profile and acceptance gate after private deployment; do not confuse a tunnel with authentication. Capabilities/nonces are dynamic and not persisted or exposed in logs.

## 6. Timeout and admission hierarchy

| Operation | Initial hard budget / behaviour |
| --- | --- |
| Client API request | 10 seconds |
| Server control operation | 6 seconds total; cached metadata only, no synchronous ffprobe in Start/seek acknowledgement |
| Chunk request | Return cached data or existing pending response promptly; disk-read deadline 2 seconds, never wait for conversion inside GET |
| Probe | 20 seconds in background validation, outside playback control requests |
| Worker termination | SIGTERM wait 2 seconds, then SIGKILL/reap wait 2 seconds |
| Session lease | 15 seconds initially, foreground heartbeat around 250 ms; preserve Stage 5 expiry semantics |
| Application cleanup | 10 seconds total for admission stop, cancellation, worker cleanup and metadata closure |
| ASGI graceful shutdown | 20 seconds |
| Compose stop grace | 30 seconds |

Probe/metadata validation occurs during background readiness preparation or explicit refresh. Start before readiness returns a quick source_not_ready response; it does not launch a long unacknowledged probe. Creating replacement conversion jobs must consume the validated snapshot instead of re-running the diagnostic constructor's probe in the control request. Implement this narrowly with compatibility tests.

Each control path uses its remaining deadline across substeps; it does not receive six fresh seconds per nested call. Keep at most four admitted control operations, coalesce superseded work under the Stage 5 identity contract and reject excess load promptly. Status/Stop must not starve behind unbounded queued Starts.

Readiness retries are capped to at most once per 30 seconds or an explicit operator retry, not each health request. Decoder progress has a 20-second no-output watchdog that counts genuine output even when cached frames are being discarded. Any future change for valid unusually slow sources is explicit and measured.

Timeouts are failures, not evidence server work vanished. Preserve ownership/fencing and refuse silent replacement when cleanup is uncertain. Under abnormal kernel/device hangs, mark degraded/unready and require operator recovery rather than promise impossible immediate process death. Test normal and forced-failure cleanup within the declared budgets.

## 7. Full-length protocol audit

Remove the diagnostic 120-second/60-chunk assumptions as a separate checkpoint before cache integration. Audit engine validation, HTTP chunk bounds, adapter validators, look-ahead, final-frame handling, subtitles and seek bounds.

Finite source windows are validated against reliable probe metadata and the configurable source safety ceiling; full-source mode uses the validated source window rather than a diagnostic 60-second default. Sources with unavailable/unreliable duration fail clearly or require explicit supported-window configuration; do not silently claim complete-source support.

Derive frame/chunk bounds from the effective requested window and frozen frame rate, using safe integer frame indices and explicit rounding. Reject negative, non-integer, non-finite and out-of-window indexes; do not replace 60 with another arbitrary magic constant. Final decoded frame count is authoritative for completion/partial tails, within the validated window. Metadata inconsistencies must be surfaced, not silently truncated or accepted as corrupt indexes.

Preserve API paths and established fields. Optional error code/retryable fields may be added, but keep the existing error string rather than changing it into an incompatible nested object. Runtime/cache schema versions are distinct from playback protocol version.

Acceptance includes footage beyond two minutes, fractional durations/offsets, caption timing, far seeks and partial final chunks with bounded RAM. CI uses generated or explicitly redistributable fixtures; host acceptance uses private local media without uploading it.

## 8. Cache v1 identity and reuse decisions

Cache v1 reuses exact effective conversion windows only. There is no promise of cross-window/canonical-grid reuse. A different seek origin can be a different key even if it overlaps cached footage.

The server-normalised, deterministically serialised job identity includes source ID/version, selected stream, effective start AND end, output dimensions/fps, aspect/rotation interpretation, tone/dither phase, pixel/encoding format, converter/filter version, FFmpeg build identity and decoder path when equivalence is unproven. Chunk identity includes relative index, start frame and actual coverage. Do not key by index alone or let a terminal partial chunk replace a full chunk from another window.

Initial source-version policy is size plus nanosecond mtime with explicit invalidation/refresh. It is not a cryptographic content guarantee; documented metadata-preserving changes require refresh. Stronger full hashing is opt-in/operator-triggered, not a full-HDD startup scan.

Normalised caption data has a separate source/SRT/parser identity. SRT edits do not invalidate unchanged image chunks. Never cache browser session IDs, capability tokens or navigation ownership as reusable frame content.

| Situation | Required v1 behaviour |
| --- | --- |
| Entire exact window remains valid in cache | Serve on demand with zero FFmpeg launch |
| Cold window | One sequential converter, incremental publication |
| Partial cached window | Serve validated available contiguous data; one converter fills missing output under look-ahead/resource limits |
| Corrupt/incomplete/incompatible chunk | Isolate entry, treat as miss, regenerate safely |
| Other source window/origin | Independent key; ordinary cold/partial behaviour |

For partial hits, the conservative decoder rule is restart at the effective conversion-window origin and discard already-cached output, publishing only required missing chunks. Reuse existing files rather than overwrite pinned readers. Do not start the decoder for a wholly satisfied request or as background pre-conversion. Catch-up can cause buffering; v1 makes no zero-delay partial-hit promise. A decoded-frame progress signal keeps legitimate discard work distinct from a hung process.

Direct restart at the first missing chunk boundary is disabled until byte/time parity tests prove it preserves the frozen sampling/dither phase, including variable-frame-rate and fractional-origin cases. It is an explicit later optimisation, not an undecided v1 path. Seeking still follows the accepted M4A protocol; a cache hit is an internal source optimisation.

## 9. Atomic publication and recoverable metadata

Store gzip chunk blobs as files; SQLite stores only recoverable index/usage metadata. Keep one writer. Use reservations and bounded streaming validation; never load or decompress an entire movie.

Publication order: reserve maximum bounded write budget; write temporary data inside the cache filesystem; validate encoding/coverage/size/checksum; flush it as required by the durability contract; atomic rename; then commit its index row. Readers see published complete files only. All stages use the same cache filesystem for rename, even when /state is another mount.

At startup with exclusive locks: reconcile missing blobs, orphaned blobs and abandoned temporary files. Count them toward actual disk usage until handled. Quarantine is bounded, not an unbounded second cache. Missing/invalid entries become misses; no partial file is returned as complete.

A crash between rename and index commit leaves a recoverable orphan; a missing index target is never assumed valid. Cache cleanup is confined under approved cache paths, rejects path/symlink escapes and cannot touch media. Corrupt decompression is capped by the profile's uncompressed size limit.

## 10. Capacity failure contract

CACHE_MAX_BYTES bounds managed published/staging/orphan chunk data. Actual free-space reserve is checked on cache AND state filesystems. Small lock/version overhead is separately bounded; SQLite/WAL/temporary metadata and rotated logs have their own ceilings. Do not count only indexed finished blobs.

Evict least-recently-used unpinned chunks. Pin current readers and the active rolling window, not an entire episode. Reserve space before writes; release reservations on cancellation/failure. Never remove a file being read or overwrite it in place.

On pressure: stop speculative generation, evict eligible chunks, then either reserve successfully or fail that generation/session with a typed capacity error. Keep Stop/health/diagnostics usable. Do not spill into unlimited /tmp, silently exceed quota, retry forever or leave an endless buffering screen. Existing readable buffers may drain, but inability to produce the required next chunk becomes an explicit terminal error.

Use HTTP 507 with error string plus code such as cache_full, state_full or disk_reserve_exhausted for capacity failures. Use 503/code media_unavailable, cache_unavailable or source_not_ready for availability failures. Preserve existing 409 navigation semantics; never relabel every failure as session expiry. Code fields are additive and backend/client contract tests must verify compatibility.

State-limit handling may attempt one bounded checkpoint before failing; no busy-loop checkpoint/retry. Retain committed valid cache and let restart reconciliation repair metadata. No write failure requires source deletion.

## 11. Migration, backup and rollback

Maintain separate application release, playback protocol, cache-format and index-schema versions. Cache filenames/namespaces encode their format/converter identity. Unsupported cache namespaces are ignored, not interpreted optimistically or deleted as user media.

Before a schema-changing upgrade: stop playback/admission, take a consistent SQLite backup using its supported backup mechanism or a clean stopped/checkpointed database, and record the prior image/config/schema versions. Do not copy only an actively written main SQLite file while ignoring its WAL. Configuration backup is separate; secrets remain local.

Migrations are forward-versioned and transactional where supported; no automatic downgrade claim. An older binary refuses newer unsupported state. Rollback means pinning the prior image/config and restoring its compatible metadata snapshot, or explicitly rebuilding a disposable cache index against supported namespaces. Never restore a backup over a running writer.

Frame blobs are disposable and need not be backed up. If metadata is rebuilt, validate files before reindexing and enforce quota during the scan. Restore/rollback must not change source media or restart old browser navigations; runtime capabilities/session ownership rotate on service restart and clients must establish a fresh session.

## 12. Health and recovery decisions

| Condition | Process behaviour | Playback behaviour |
| --- | --- | --- |
| Process alive | /health/live is cheap and responsive | No implied media readiness |
| Storage/config/source preparation incomplete | Keep UI and diagnostics available; /health/ready returns 503 | Refuse new playback with reason |
| USB/media disappears | No restart loop or cache deletion; capped readiness retry | Controlled media-unavailable error |
| Cache/state unavailable/full | Keep control routes responsive; mark unready/degraded | Refuse or terminate affected generation clearly |
| Conversion fails | End that session; keep application running | Typed error and explicit retry path |
| Process crashes | Compose restart policy applies | Old sessions are not restored |
| Corrupt cache entry | Isolate/regenerate under normal limits | Miss/buffering or explicit failure, not corrupt frames |

Health checks read cached validation state, never start FFmpeg or repeatedly wake the media disk. Initial health interval is 30 seconds, timeout 2 seconds, three failed checks, start period 30 seconds. Health status reports a fault; it does not itself restart an unhealthy container. Initial process restart policy is unless-stopped. Do not add an auto-heal sidecar; operator/runbook handles persistent degraded conditions.

Logs expose bounded session/job IDs, versions, profile, startup/throughput, cache hit/miss/eviction and cleanup outcomes without capability values, credentials or unnecessary host paths. Startup diagnostics and source probes are distinct from health requests.

## 13. Delivery checkpoints

| Checkpoint | Only deliver | Gate |
| --- | --- | --- |
| 6.0 | Stage 5 contract freeze and deployment inventory | Required host values and known-good versions recorded |
| 6.1 | Thin supported runtime/lifespan adapter and probe admission split | Playback compatibility and timeout budgets pass |
| 6.2 | Restricted image and single-service Compose | Same configured source plays inside container |
| 6.3 | Mount identity, non-root permissions, exclusive locks and shutdown | Missing USB/second instance fail safely; no normal-stop orphan |
| 6.4 | Explicit external origins and LAN/Tailscale access | Port mapping works without weakening checks |
| 6.5 | Full-length bounds audit | Beyond-two-minute playback/captions/seeking remain bounded |
| 6.6 | Exact-window identity, reservations and atomic cache writes | No collision/partial publication |
| 6.7 | Cache reads, partial-hit rule and restart reconciliation | Warm complete hit has zero converter; partial/corrupt cases are correct |
| 6.8 | LRU/pins/quota/state-pressure failures | Disk-full and all-pinned cases are bounded/actionable |
| 6.9 | Upgrade/rollback, observability and host acceptance | Reproducible deployment and tested recovery |

Normally one or two implementation files plus focused tests per pass; save each completed pass. Subdivide a checkpoint again if its scope grows. No implementation commit may claim later gates passed.

Optional later profiles: Cloudflare Access with full route protection/origin-bypass tests; measured GPU decoder comparison with software fallback. They do not alter the core v1 cache/access assumptions silently.

## 14. Acceptance and evidence

Use controlled unit tests, real FFmpeg/HTTP fixtures, browser tests and host tests as separate evidence. Include complete/cold/partial cache, mismatched terminal partial chunk, source/SRT change, corrupt gzip, interrupted writes, orphan recovery, quota/all-pinned/state-full, instance conflict, unavailable/unmounted USB, control admission, Start/seek cancellation, full-length tails, SIGTERM/forced stop and upgrade/rollback.

On the N5105, test cold USB reads, warm cache, sustained playback and ordinary concurrent Plex use; do not extrapolate old low-resolution ASCII benchmark figures into a guarantee for the new deployment. Measure first playable buffer, sustained conversion, peak RAM/CPU, cache use and stalls. Set required memory/cache values from that record with headroom.

Completion: Compose boots with protected media and bounded writable mounts; handset works over LAN; a supported full source plays with Stage 5 controls; repeated stop/restart has no normal-case abandoned worker; exact-window warm cache avoids FFmpeg; cache survives restart correctly; storage failures are explicit; rollback is demonstrated; public Pages has no private API/data dependency. State all remaining limitations. No such result is asserted by committing this plan.

## References

- https://docs.docker.com/reference/compose-file/services/
- https://www.uvicorn.org/deployment/
- https://www.sqlite.org/wal.html
- https://tailscale.com/docs/features/tailscale-serve
- https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/self-hosted-public-app/
