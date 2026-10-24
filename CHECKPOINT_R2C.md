# R2C browser adapter Start-fencing integration

Implementation ready; combined backend/adapter host acceptance PENDING.

Reviewed exact Git blob baselines:
- stream-source.js 40653a3ac686ec0b99dde746dc436e94ed2049bf
- tests/test_stream_source.cjs 65d1241a2cf66690fea5599e35706ebc4244591a
- tools/lcd_stream_fenced_api.py 1e3341ca0841d65bad4f72bb11ed46d85a594a00
- docs/plans/R2B_BACKEND_CONTRACT.md c633324e89530c407abb065e19b84c58ea60dbf2
Both existing JS baselines were reproduced byte-for-byte and their Git blob SHA1s
verified before generating the patch. No backend/handset/static catalogue edits.

Changed:
- stream-source.js
- tests/test_stream_source.cjs
New:
- tests/stream_source_http_client.cjs
- tests/test_stream_source_http.py
- CHECKPOINT_R2C.md

Contract:
- Constructor stays inert and keeps the existing public start/stop/poll/frame API.
- Explicit Start registers via /api/control/open and requires exact
  start-fence-v1, 48-character lowercase-hex handle, and 60-second lease.
- A control handle is reused across explicit Starts with monotonically increasing
  safe-integer start_revision. Seek revisions remain a different server concern;
  this pass does NOT add an adapter seek() method.
- Pending Start owns a cleanup obligation before its navigation is acknowledged.
- Stop/new Start launches /api/control/cancel out of band, BEFORE aborting the
  client Start operation. Cleanup does not wait behind the Start being cancelled.
- The lifecycle queue still owns release/adoption. New work waits for confirmed
  scoped cleanup, never merely fetch abort, timeout or playback lease expiry.
- Normal acknowledged release ALSO uses scoped control cancellation. It replaces
  the old navigation-stop transport call and cancels exactly this Start revision;
  it cannot stop a newer revision or foreign navigation.
- Cancellation is accepted only with fence_recorded=true and cleanup confirmed
  or not_required. Generic 404/410, malformed success, timeout and unconfirmed
  cleanup retain the obligation and block replacement. The sole gone-handle
  exception is structured 404/control_client_gone: backend contract says expired
  active owners remain cancellable, so this code identifies a gone nonowner.
- Start response protocol, handle and revision must match before adoption.
  Invalid/foreign metadata is cleaned using our own scoped identity, NEVER by
  navigation IDs supplied by an untrusted mismatched reply.
- Current gone/superseded control errors retire the handle for the NEXT explicit
  Start only. No auto-renewal, silent retry or protocol downgrade. Stale replies
  cannot replace/retire a newer control handle or restore old metadata.
- Stop during registration aborts adoption: no Start can be sent without a known
  handle. A lost/late registration may consume an idle registry slot until the
  inherited lease reclaims it; no converter exists for it. There is no unbounded
  retry loop or client-side registry history.
- R1 readiness latch, paused prefill, reset-on-generation, bounded rolling cache,
  chunk/status validation, same-origin capability boundary and request deadlines
  remain. No background polling/timers, rendering, UI controls or autoplay added.

Validation actually run here:
- node --check for the adapter and both JS test clients.
- 44 standalone adapter tests passed (all 24 prior cases retained, fixtures now
  model the fenced contract; 20 additional R2C lifecycle/protocol tests).
- Python AST syntax validation for the combined test runner.
- git apply --check + actual application in a temporary baseline checkout,
  followed by byte-for-byte comparison of all five resulting files.
- The FIVE combined real backend/Node/HTTP/FFmpeg tests are supplied but NOT RUN
  here: the full repository dependency set was not available in this environment.
  Do not turn the 44 mocked-transport tests into a combined/backend/browser claim.

Install from repository root. This changes existing files, so do NOT overlay with
an unchecked tar extraction. The archive contains only R2C.patch:

    git pull --ff-only origin main
    git diff -- stream-source.js tests/test_stream_source.cjs
    tar --keep-old-files -xzf wapflix-r2c.patch.tar.gz
    git apply --check R2C.patch
    git apply R2C.patch

Stop on conflicts or local edits needing review. The patch includes complete
source/test/docs changes, no media, token, backup or generated test output.

Focused host gate:

    node tests/test_stream_source.cjs
    node tests/test_handset_live_bridge.cjs
    python3 -m unittest discover -s tests -p 'test_stream_source_http.py' -v
    python3 -m unittest discover -s tests -p 'test_fenced_api.py' -v

Full retained backend regression commands:

    python3 -m unittest discover -s tests -p 'test_start_fence.py' -v
    python3 -m unittest discover -s tests -p 'test_control_api.py' -v
    python3 -m unittest discover -s tests -p 'test_start_coordinator.py' -v
    python3 -m unittest discover -s tests -p 'test_m4_factory.py' -v

Requires Node 18+ with native fetch plus ffmpeg/ffprobe. Skipped combined/media tests
are NOT an accepted gate. Combined tests generate temporary video, start a real
in-process HTTP server, and run the actual adapter through Node native fetch:
1. Real frame/chunk/pulse/scoped cleanup.
2. Stop before delayed old HTTP handler dispatch; newer Start survives late work.
3. Start timeout then newer intent; old HTTP dispatch is actually sent ignoring
   AbortSignal, and the server must reject its cancelled revision.
4. Stop after real admission but before the adapter sees the acknowledgement;
   old session is ended and late response cannot displace a fresh one.
5. Control-only server is refused rather than silently downgraded.
They run on the mini-PC; no browser access to localhost is needed, and they do not
use your private source video or expose capability tokens in successful output.

Runtime remains the separately launched fenced API on LAN/TS port 8103, with the
same-origin capability restriction. The legacy diagnostic M4 remains separate.
An old/simulated handset host without control routes now fails closed by design.
Do NOT weaken it or point the adapter at another origin to make it appear working.
The existing fenced landing page still has no connected handset player. Real
5A.3 hosting/rendering/browser acceptance is the next integration gate after this
combined suite passes. No real browser, all-five-model controls, LAN throughput
or N5105 manual acceptance is claimed by this patch.

Stage only the five listed implementation/test/docs paths, not R2C.patch or archives.
Rollback before commit: restore the two existing files from the reviewed baseline
and remove the three new files, after checking for unrelated local work. After a
commit, revert that checkpoint commit rather than resetting other history.
R2 is not declared complete until combined backend/adapter acceptance passes;
later handset, pause/caption/seek UI milestones remain distinct.
