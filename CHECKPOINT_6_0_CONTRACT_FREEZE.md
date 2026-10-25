# Checkpoint 6.0A — accepted Stage 5 contract and read-only deployment inventory

Status: tooling prepared; host inventory/operator review still pending. No supported runtime or Compose deployment is implemented by this patch. This is the first small delivery within checkpoint 6.0, not a claim that all of 6.0 is closed.

## Evidence and baseline

- Reference main: 055169fe37d5b07ce36249485d2344b9ceeb822b, "Add handset restart-seeking with fenced position-based transport".
- The user reported the expanded local regression command passed, and subsequently reported browser seeking acceptance as good on 2026-10-25. This records operator-reported evidence; no independent browser, FFmpeg-worker, resource or security measurements were made in preparation.
- The accepted transport/server source blobs and Phase 6 plan are pinned in the inventory and package manifest. No playback source, test or deployment-plan file is changed.

## Accepted transport contract to preserve at 6.1

Frontend and API share an external origin. The adapter refuses cross-origin configuration. Existing clients use X-Wapflix-Test, same-origin credentials, no-store and redirect:error. Tokens and browser ownership are dynamic and must not be cached as reusable media.

| Operation | Request fields | Semantics |
| --- | --- | --- |
| POST /api/control/open | empty object | start-fence-v1; 48-lowercase-hex control_client_id; control_lease_seconds=60 |
| POST /api/start | control_client_id, start_revision | Monotonic safe-integer Start revision; response identity must match; new navigation. |
| POST /api/control/cancel | control_client_id, cancel_through | Scoped tombstone, including an unacknowledged Start and pending seeks owned by that Start. Client accepts only fence_recorded=true with confirmed/not_required cleanup, or structured 404/control_client_gone. Generic 404 is not cleanup proof. |
| POST /api/seek | navigation_id, revision, position | Absolute source seconds; increasing seek revision, distinct from Start revision. Keep original navigation; replacement has a new stream/session and snapped source_start. Do not cancel the owner before ordinary seeking. |
| POST /api/pulse | id, frame, paused | Relative frame index in current stream; foreground heartbeat. Prefill before honouring a paused startup; readiness latch survives cache eviction. |
| GET /api/chunk | query id, n | Validated relative chunk index; pending=204; evicted=410. No browser-side parallel transport implementation. |
| POST /api/navigation/stop | navigation_id | Existing server route; scoped cancellation. Browser adapter currently stops via /api/control/cancel. |
| POST /api/stop | id | Existing session-scoped compatibility route. |

Start metadata includes id, navigation_id, source_start, original range_start/range_end, geometry/fps/chunk_frames and source-time captions, plus fenced Start identity. Seek metadata retains navigation/range and includes seek revision. Keep these existing fields/API paths; do not rename them to older draft proposals.

The accepted converter profile is 8 fps with two-second chunks; geometry is carried in each validated response. LCD chunks use version=1, layout=lcd-1bit, encoding=hex-msb, start_frame and relative frames. Final total_frames is authoritative within the configured window. Do not mix caches across stream IDs. The adapter retains at most one previous plus four current/ahead chunks; this is not the same thing as the server's publication look-ahead.

The browser owns time and presentation: current-stream relative position differs from actually presented absolute source time and original-extract progress. Captions select from the presented frame. Numeric 2 toggles captions; 4/6 seek -/+5 seconds; 5 pauses/resumes (or explicitly cancels startup/restarts a terminal session). Physical navigation/roller movement must not alias those numeric actions. Stop/navigation invalidate stale UI work before asynchronous cleanup.

Errors keep the existing string error plus structured code where supplied. Latest-operation failures surface; only locally known superseded responses are discarded. Cleanup uncertainty blocks silent replacement. Hidden-page return remains paused and validates before Resume.

## Current limitations — not deployment promises

The accepted server is a diagnostic standard-library HTTP host, not FastAPI/Uvicorn. Its current Origin comparison is direct HTTP Host based, not a supported HTTPS-proxy contract. Its chunk route still enforces n<60. Start/seek preparation can probe synchronously. Current adapter default request timeout is ten seconds; playback lease is fifteen seconds and control-client lease sixty seconds.

Phase 6.1 must split validation/probe admission and provide one managed application lifetime without weakening ownership or timing semantics. Phase 6.4 handles explicit external origins/proxies. Phase 6.5 audits the full-length/chunk limit separately. Merely packaging the diagnostic host in Docker does not satisfy these checkpoints.

## Inventory tool scope

The new tools/deployment_inventory.py emits JSON to stdout. No environment dump, directory tree scan, media decode/probe, converter/container start, Docker daemon query or settings change. It reads selected /proc metadata, stat/statvfs for configured paths, optional bounded sentinel contents, fixed frozen source files, and fixed local version commands with five-second deadlines. ffprobe -version is a binary-version query, not a media probe.

The tool never creates media/cache/state directories, sentinel files or an output file. Shell redirection is an explicit operator output action. Missing inputs appear as named pending items rather than invented paths/UID/quota/RAM choices. Source safety checks use a confined relative file; sentinel input requires an expected SHA-256 and reads at most 4097 bytes to reject a sentinel over 4096 bytes.

Reported current-process permissions are not proof the future container UID has access. Mountinfo/statvfs observations are not USB identity proof, lock/atomic-rename tests or measured workload headroom. A matched sentinel is evidence for operator review, not a guarantee that a directory is the intended live USB mount. Reports always say deployment_ready=false and phase6_0_complete=false until human review/evidence closes the gate. An inventory process exit code of zero means a report was collected, NOT that deployment is ready.

## Run locally

From the checkout root:

```sh
python3 -m unittest discover -s tests -p 'test_deployment_inventory.py' -v
(umask 077; python3 tools/deployment_inventory.py --root "$PWD" > "$HOME/wapflix-deployment-inventory.json")
```

Keep this JSON outside Git. It can contain private paths, source filenames, mount points and network origins. Do not commit or automatically upload it. Do not run with sudo merely to make permission observations pass. First collect the unconfigured report to establish versions/RAM; then provide the required explicit values.

Optional operator flags (all values are local operator choices, not defaults):

- --media-root, --cache-root, --state-root: absolute existing directories; do not create missing media roots as a workaround.
- --source: confined path relative to media root.
- --sentinel and --sentinel-sha256: confined existing identity file and independently expected digest. Do not create a sentinel automatically over a missing mount.
- --runtime-uid, --runtime-gid: explicitly selected positive non-root IDs; observed invoking UID/GID are separate fields.
- --origin (repeatable): exact HTTP(S) external origin; no credentials, wildcards, paths, query or fragment.
- --publish-address (repeatable): explicit IP; selecting 0.0.0.0 or :: produces an all-interfaces warning, not an authentication claim.
- --cache-max-bytes, --min-free-bytes, --memory-limit-bytes: positive byte values requiring capacity/headroom review. No universal memory default is supplied.

The planned container listen is 8080 and default published port 8103 in PHASE6_DEPLOYMENT_PLAN.md. No port is opened by this inventory. External origins must describe the operator's chosen actual host ports.

## To close 6.0

Review actual versions/mounts, choose non-root identity and exact origins/published addresses/port, approve registered source and sentinel, choose distinct writable roots/quota/reserve, and record representative-source memory/headroom. Record the earlier Stage 5 acceptance and any untested cases. Keep host-specific inputs/secrets local. Then begin 6.1: thin supported runtime and probe-admission split. Cache implementation, Compose, Plex, GPU and Cloudflare profiles remain out of this patch.

## Commit this tooling after local tests

```sh
git add -- tools/deployment_inventory.py tests/test_deployment_inventory.py CHECKPOINT_6_0_CONTRACT_FREEZE.md tools/apply_phase6_0.py MANIFEST_6_0.json
git diff --cached --check
git diff --cached --stat
git commit -m "Freeze accepted playback contracts and add read-only deployment inventory"
git push origin main
```

This commit records tooling, not deployment completion or benchmark results.
