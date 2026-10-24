# R2B.3 real M4 factory checkpoint

Adds tools/lcd_m4_factory.py and tests/test_m4_factory.py only, plus this checkpoint.
No existing runtime files, routes, adapter, handset, media or source paths are changed.

Reviewed main inputs:
- tools/start_coordinator.py 9917983ca7dbc80fcf75225eba990bcb03cadd4c
- tools/lcd_stream_server.py 0e111b62f413d2f46b1bdba70a7a2437dfc8fc23
- tools/lcd_chunker.py 173aed02e4f2c12c527dd288ff7aeb2ee739b398
- tools/lcd_stream_captions.py 7e4d8ec73b1938517e6463990004cf8bc15e9bdd
- tools/srt.py c96bd50921f78d61906c50361b5ac7df86fb8f5c

M4Factory accepts only its immutable FixedSource configuration. Session construction
uses the existing real Session/LCDStream, probing exactly once during prepare with
the inherited 30-second ffprobe deadline. It creates no converter/started thread.
No legacy App/SeekApp monitor is instantiated, avoiding a second lifecycle owner.
The existing immutable SRT parse result is loaded once per factory. Source-time
caption windowing delegates to CaptionApp.caption_data; no replacement parser.

Admission publishes navigation/owner identity and schedules the real Session thread.
No Popen, probe or cleanup occurs synchronously inside the admission callback.
The existing Session.work launches the converter in its worker. Snapshot preserves
M4 fields and adds control identity. Ownership survives conversion completion.
Stop calls the real Session.stop with inherited cleanup budgets and separately
checks both process exit and thread termination before confirming release.
No fake factory is shipped, no mutable app.start is read, and no request-supplied
source/window override is accepted.

Validation performed in delivery environment:
- AST syntax validation of both new Python files.
- FixedSource invalid-configuration unit test passed (five subcases), executed
  in isolation from its exact AST. This is NOT the full repository suite.
- Eight real-media integration tests are supplied but NOT executed here.

Run these on the mini-PC; test_m4_factory generates a small temporary 60-second
64x48 FFV1 video via FFmpeg and deterministic SRT, then deletes both. It does not
use private/downloaded media. FFmpeg and ffprobe are REQUIRED: skipped real-media
tests do not count as an R2B.3 pass.

    python3 -m unittest discover -s tests -p 'test_start_fence.py' -v
    python3 -m unittest discover -s tests -p 'test_control_api.py' -v
    python3 -m unittest discover -s tests -p 'test_start_coordinator.py' -v
    python3 -m unittest discover -s tests -p 'test_m4_factory.py' -v

The nine tests in the new file cover config validation, exactly-one-probe preparation,
real gzip chunk data/geometry, caption offsets and M4 metadata, active duplicate
identity, cancellation after real preparation without launching a converter,
replacement reaping a running converter before publication, real cancellation
cleanup, fixed-source rejection, missing-source failure, and completed short-tail
ownership until explicit cancellation.

Install archive at repo root with --keep-old-files and stop on collisions. Stage
only the three new files. No service restart is needed and no new HTTP server is
provided. LAN/Tailscale control-only access remains unchanged; no localhost browser
access is needed to run these server-side tests.

Acceptance remains pending until the real-media tests run without skips. No HTTP,
browser, handset or N5105 throughput acceptance is claimed. Playback lease sweep,
validated activity renewal, navigation stop/seek ownership, Host/Origin conformance
and full route/error mapping are R2B.4; do not expose this factory through legacy
begin/stop/seek paths prematurely. R2B.3 does not complete R2B or R2C.
Rollback: remove the three added files (no existing entry point imports them).
