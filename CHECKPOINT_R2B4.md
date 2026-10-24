# R2B.4 fenced M4 HTTP integration (experimental, host gate pending)

Adds only:
- tools/lcd_stream_fenced_api.py
- tests/test_fenced_api.py
- CHECKPOINT_R2B4.md

Reviewed baselines from main:
- start_coordinator.py 9917983ca7dbc80fcf75225eba990bcb03cadd4c
- lcd_m4_factory.py b052d78b10319ded5f4b3558fe58f7beb5198aea
- start_fence.py 1ad91736143c8f9ed02ccf75566cebd81d9f4ef6
- lcd_stream_control_api.py 72c3accce374380d7b8cc927473cba45b857006a
- lcd_stream_seek_api.py d0b8ec4c659487155be5f4d72942761f3a612267
- docs/plans/R2B_BACKEND_CONTRACT.md c633324e89530c407abb065e19b84c58ea60dbf2

No existing implementation, media, HTML, adapter, handset or workflow is changed.
The legacy real-media M4 and control-only entry points remain isolated. This new
server does not invoke their begin/stop/seek paths and has no weaker Start fallback.
Runtime uses the required NavigationFactory -> M4Factory -> real Session/LCDStream.
Injected mocks exist only in tests; there is no synthetic runtime conversion.

Implementation:
- Capability/Host/Origin-checked bounded POST routes for control open/cancel,
  fenced Start, pulse, session-stop, navigation-stop and restart-seek.
- Authenticated GET /api/chunk?id=...&n=... preserves gzip/204/410 semantics.
- Full inherited pulse snapshot fields; no per-frame/caption endpoints.
- Missing Start identity => 409/fencing_required, never legacy begin().
- Scoped cancellation before cleanup, truthful 503 cleanup_unconfirmed body,
  retained ownership on failed reaping or partial publication.
- Existing 15-second playback lease plus separate 60-second control lease.
  Only validated matching-session pulses renew control. Registration does not
  touch workers; GET chunk does not extend the existing playback heartbeat policy.
- Automatic bounded-interval expiry monitor, plus reap_once for deterministic tests.
- Seek preparations bounded to four and done outside lifecycle/core locks. The
  original extract range, navigation owner and Start identity survive worker changes.
  Seek revisions remain separate, source positions snap down at 8fps as in M4.
- Stop/expiry/newer intent/shutdown prevent stale seek or Start publication.
- NavigationFence confines core-private coupling to one small update_owner method:
  it atomically checks the active ticket/owner and runs a short publication callback
  under the core lock. No probe/reap waits under that lock. Failed update retains
  ownership. No existing StartFence file is edited. Its private contract is covered
  by five focused tests, and must be rechecked if the core changes.
- Probe/stop/join time budgets are inherited; none is extended. The existing
  coordinator's bounded lifecycle waits/capacity still apply. Errors are sanitized
  rather than exposing probe stderr, source paths or capability tokens.

Validation actually performed here:
- Syntax parsing of both delivered Python files.
- Five NavigationFence tests passed in isolation against transcribed current core.
- 23 tests passed in a temporary local harness, including 18 real loopback HTTP /
  generated-media FFmpeg tests. Runtime dependencies were manually transcribed
  from reviewed code, omitting unrelated CLI/viewer/export sections, comments and
  some type annotations. This is NOT a cloned/full-repository regression run.
- The legacy real-media viewer fallback test was excluded from that harness because
  the actual repository HTML/overlay/legacy application files were not present.
- No browser/handset, LAN/TS host, N5105 throughput or public security certification.

The delivered test file has 24 tests (five core-extension, nineteen integration).
Run ALL tests below against the actual checkout before marking R2B.4 accepted:

    python3 -m unittest discover -s tests -p 'test_start_fence.py' -v
    python3 -m unittest discover -s tests -p 'test_control_api.py' -v
    python3 -m unittest discover -s tests -p 'test_start_coordinator.py' -v
    python3 -m unittest discover -s tests -p 'test_m4_factory.py' -v
    python3 -m unittest discover -s tests -p 'test_fenced_api.py' -v

The real-media tests require ffmpeg/ffprobe, generate temporary video/SRT, and run
on the mini-PC without a browser. Skips do NOT constitute a passed media gate.
Existing R1/browser/handset regressions remain distinct and must not be inferred
from these server tests. The new tests verify the legacy real-media fallback with
its actual repository viewer dependencies as well as fenced bypass refusal.

Install from repo root with tar --keep-old-files; stop on collisions. The archive
contains only new paths, so existing services do not need restarting.

Opt-in LAN/Tailscale server, AFTER tests pass, from repo root:

    python3 -m tools.lcd_stream_fenced_api --enable-fenced --bind 0.0.0.0 --port 8103

Use the same --video, --start, --seconds and --srt/--no-srt arguments as your real
M4 source if not using its default source/window. Hostname aliases require
--allow-host NAME (without scheme/port); direct LAN/TS IPv4 does not.
The capability is printed only to the trusted local terminal. Do not publish logs.
This is plain trusted-network HTTP, not public authentication or Cloudflare HTTPS
proxy support. No port forwarding. Existing strict Origin policy remains HTTP.
The landing page says Experimental fenced API / Browser adapter not connected.
It is intentionally not a playback UI or a handset integration claim.

Remote smoke flow (replace BASE and TOKEN with LAN/TS address and terminal token):
- POST /api/control/open {} => control_client_id
- POST /api/start {control_client_id,start_revision:1} => real session metadata
- POST /api/pulse {id,frame:0,paused:false} => normal pulse snapshot
- GET /api/chunk?id=ID&n=0 with capability header => gzip chunk or 204 while pending
- POST /api/seek {navigation_id,revision:1,position:VALID_ABSOLUTE_SOURCE_SECONDS}
  => new session id, same navigation and original range
- POST /api/control/cancel {control_client_id,cancel_through:1} => confirmed cleanup
Use X-Wapflix-Test for capability, Content-Type application/json for POST. Keep
valid pulses within the playback lease during manual testing.

Stage only the three added files; do not stage archives/media/logs.
Rollback: stop the port-8103 experimental server and remove only these three files.
Legacy M4/control-only remain unchanged. After full host acceptance, R2C wires
browser registration/identity/out-of-band cancellation and combined tests. R2 is
NOT complete merely because this archive exists or its landing page loads.
